"""
modules/common/error_events.py — 오류 이벤트 원장 1단계 (261103 설계, 회장 승인)

Meta 게시 실패를 분류해 로컬 SQLite(`db/error_events.db`)에 기록하고, 인증·권한·정책 차단 계열만
계정당 하루 1회 알림한다. 설계: docs/design/ERROR_EVENT_LEDGER_DESIGN_261103.md

범위(1단계): 기록과 알림만. 게시 흐름·재시도·상태 변경·Airtable 쓰기는 하지 않는다
(Instagram_Posts 에 오류 필드를 쓰지 않는다 — ERR-075). 기록이 실패해도 호출자에게 예외를 전파하지 않는다.
Caller: launcher/main.py `_record_meta_failure` (게시 실패 지점).

분류 코드표는 Graph API 공식 오류 코드 문서를 기준으로 작성했으며 운영 데이터(META_UNCLASSIFIED 집계)로
보강한다. 로그·DB 에는 토큰·URL 쿼리·캡션을 남기지 않는다(앞 200자, 쿼리 제거, redact_sensitive).

조회: python -m modules.common.error_events --since 24h --by account,class
"""

import argparse
import re
import sqlite3
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import unquote

from modules.common.log_sanitizer import redact_sensitive
from modules.common.logger import get_logger

logger = get_logger(__name__)

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "error_events.db"

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ts          TEXT NOT NULL,
        source      TEXT NOT NULL,
        account     TEXT NOT NULL DEFAULT '',
        error_class TEXT NOT NULL,
        severity    TEXT NOT NULL,
        http        INTEGER,
        code        INTEGER,
        subcode     INTEGER,
        stage       TEXT NOT NULL DEFAULT '',
        record_id   TEXT NOT NULL DEFAULT '',
        detail_head TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)",
    """
    CREATE TABLE IF NOT EXISTS alert_log (
        day         TEXT NOT NULL,
        account     TEXT NOT NULL,
        error_class TEXT NOT NULL,
        PRIMARY KEY (day, account, error_class)
    )
    """,
)

# ── Meta 분류표 ────────────────────────────────────────────────────────────────
META_AUTH = "META_AUTH"
META_PERMISSION = "META_PERMISSION"
META_POLICY_BLOCK = "META_POLICY_BLOCK"
META_RATE_LIMIT = "META_RATE_LIMIT"
META_MEDIA_FETCH = "META_MEDIA_FETCH"
META_TRANSIENT = "META_TRANSIENT"
META_CONTAINER = "META_CONTAINER"
META_OUTCOME_UNKNOWN = "META_OUTCOME_UNKNOWN"
PUBLISH_INTERNAL = "PUBLISH_INTERNAL"
META_UNCLASSIFIED = "META_UNCLASSIFIED"

# Codex 리뷰(261103): 458·459·460·463·467 은 최상위 code 가 아니라 `code=190` 아래의 error_subcode 로 온다.
# 80004·80006 은 Ads·Messenger 맥락이라 게시 원장 분류표에서 뺀다.
_AUTH_CODES = frozenset({102, 190})
_AUTH_SUBCODES = frozenset({458, 459, 460, 463, 467})
_PERMISSION_CODES = frozenset({3, 10} | set(range(200, 300)))
_POLICY_CODES = frozenset({368})
_POLICY_SUBCODES = frozenset({2207050})          # 계정 제한(action blocked)
_RATE_CODES = frozenset({4, 17, 32, 613, 80002})
_TRANSIENT_CODES = frozenset({1, 2})
_MEDIA_FETCH_SUBCODES = frozenset({2207052})

_SEVERITY = {
    META_AUTH: "P1", META_PERMISSION: "P1", META_POLICY_BLOCK: "P1",
    META_RATE_LIMIT: "P2", META_MEDIA_FETCH: "P2", META_CONTAINER: "P2", META_UNCLASSIFIED: "P2",
    META_OUTCOME_UNKNOWN: "P0", PUBLISH_INTERNAL: "P2", META_TRANSIENT: "P3",
    # 261105 Gemini 진단 1단계 (modules/common/gemini_failure_diag.py)
    "GEMINI_QUOTA_ZERO": "P1", "GEMINI_AUTH": "P1", "GEMINI_RATE": "P3", "GEMINI_TRANSIENT": "P3",
    "GEMINI_RECOVERED": "P3",
}
_ALERT_CLASSES = frozenset({META_AUTH, META_PERMISSION, META_POLICY_BLOCK})


def severity_of(error_class: str) -> str:
    return _SEVERITY.get(error_class, "P2")


def classify_meta_error(http: Optional[int], code: Optional[int], subcode: Optional[int]) -> str:
    """Graph API 오류(http·code·subcode) → 분류. 하위 코드(subcode)를 먼저 본다."""
    if subcode in _POLICY_SUBCODES:
        return META_POLICY_BLOCK
    if subcode in _MEDIA_FETCH_SUBCODES or code == 9004:
        return META_MEDIA_FETCH
    if code in _AUTH_CODES or subcode in _AUTH_SUBCODES:
        return META_AUTH
    if code in _POLICY_CODES:
        return META_POLICY_BLOCK
    if code in _PERMISSION_CODES:
        return META_PERMISSION
    if code in _RATE_CODES or http == 429:
        return META_RATE_LIMIT
    if code in _TRANSIENT_CODES or (http is not None and http >= 500):
        return META_TRANSIENT
    return META_UNCLASSIFIED


_CODE_RE = re.compile(r"\bcode=(\d+)")
_SUBCODE_RE = re.compile(r"\bsubcode=(\d+)")
_HTTP_RE = re.compile(r"^\s*(\d{3})\s+(?:Client|Server)\s+Error")
_NON_HTTP_CLASSES = (
    ("outcome_unknown", META_OUTCOME_UNKNOWN),
    ("container_", META_CONTAINER),
    ("child", META_CONTAINER),
    ("parent_create_failed", META_CONTAINER),
)


def parse_publish_failure(raw: dict) -> dict:
    """publish_single/publish_carousel 의 실패 dict → {error_class, http, code, subcode}.
    code/subcode 는 `_extract_meta_error_detail` 이 만든 detail 문자열에서, http 는 error 문자열에서 읽는다."""
    error = str(raw.get("error", "") or "")
    detail = str(raw.get("detail", "") or "")
    code_m, sub_m, http_m = _CODE_RE.search(detail), _SUBCODE_RE.search(detail), _HTTP_RE.search(error)
    code = int(code_m.group(1)) if code_m else None
    subcode = int(sub_m.group(1)) if sub_m else None
    http = int(http_m.group(1)) if http_m else None
    if raw.get("outcome_unknown"):
        return {"error_class": META_OUTCOME_UNKNOWN, "http": http, "code": code, "subcode": subcode}
    if code is None and http is None:
        for prefix, cls in _NON_HTTP_CLASSES:
            if error.startswith(prefix):
                return {"error_class": cls, "http": None, "code": None, "subcode": None}
        lowered = error.lower()
        if "timeout" in lowered or "connection" in lowered:
            return {"error_class": META_TRANSIENT, "http": None, "code": None, "subcode": None}
        return {"error_class": PUBLISH_INTERNAL, "http": None, "code": None, "subcode": None}
    return {"error_class": classify_meta_error(http, code, subcode), "http": http, "code": code, "subcode": subcode}


_URL_QUERY_RE = re.compile(r"(https?://[^\s?]+)\s*\?\S*")
# 키 이름 없이 값만 남는 경우를 대비한 접두 패턴(Meta/Threads/Google 토큰) — 최후 방어선
_BARE_TOKEN_RE = re.compile(r"\b(?:EAA|IGAA|IGQ|THAA|AIza|AQ\.)[A-Za-z0-9_\-\.]{15,}")


def safe_text(*parts: str, limit: int = 200) -> str:
    """외부 오류 문자열을 알림·기록에 쓸 수 있게 만든다. requests 의 HTTPError 문자열은 요청 URL(쿼리 포함)을
    담고 있어 그대로 Slack 등에 보내면 access_token 이 노출될 수 있다(261103 발견, ERR-194).

    순서: 공백·줄바꿈 정리 → 퍼센트 디코딩(최대 2회: `access%5Ftoken` 같은 인코딩된 키 이름 대응) →
    URL 쿼리 제거 → redact_sensitive(key=value 마스킹) → 접두 토큰 패턴 마스킹 → 앞 limit 자."""
    text = " ".join(str(p) for p in parts if p)
    text = re.sub(r"\s+", " ", text)
    for _ in range(2):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    text = _URL_QUERY_RE.sub(r"\1?<params>", text)
    text = redact_sensitive(text)
    text = _BARE_TOKEN_RE.sub("[REDACTED]", text)
    return text[:limit]


_safe_detail = safe_text


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=3)
    conn.execute("PRAGMA journal_mode=WAL")
    for stmt in _SCHEMA:
        conn.execute(stmt)
    return conn


def record_event(
    *, source: str, account: str, error_class: str, http: Optional[int] = None, code: Optional[int] = None,
    subcode: Optional[int] = None, stage: str = "", record_id: str = "", detail: str = "",
    db_path: Optional[Path] = None, now: Optional[datetime] = None,
) -> None:
    now = now or datetime.now()
    conn = _connect(db_path or _DB_PATH)
    try:
        with conn:
            _insert_event(conn, now, source, account, error_class, http, code, subcode, stage, record_id, detail)
    finally:
        conn.close()


def _insert_event(conn, now, source, account, error_class, http, code, subcode, stage, record_id, detail) -> None:
    conn.execute(
        "INSERT INTO events(ts, source, account, error_class, severity, http, code, subcode, stage, record_id, "
        "detail_head) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (now.strftime("%Y-%m-%d %H:%M:%S"), source, account or "", error_class, severity_of(error_class),
         http, code, subcode, stage, record_id, detail),
    )


def _claim_alert_conn(conn, account: str, error_class: str, now: datetime) -> bool:
    """계정·분류별 하루 1회만 True (같은 연결·트랜잭션 안에서)."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO alert_log(day, account, error_class) VALUES (?,?,?)",
        (now.strftime("%Y-%m-%d"), account or "", error_class),
    )
    return cur.rowcount == 1


def _send_alert(notify: Callable[[str], None], message: str, run_async: bool) -> None:
    """알림은 게시 실패 처리 경로를 늦추지 않도록 기본적으로 별도 데몬 스레드에서 보낸다(Codex 리뷰 261103)."""
    def _run() -> None:
        try:
            notify(message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ErrEvt] 알림 실패(게시 흐름 무영향) | %s", type(exc).__name__)

    if run_async:
        threading.Thread(target=_run, name="errevt-notify", daemon=True).start()
    else:
        _run()


def record_publish_failure(
    raw: dict, *, account_code: str, record_id: str, stage: str,
    notify: Optional[Callable[[str], None]] = None, db_path: Optional[Path] = None, now: Optional[datetime] = None,
    notify_async: bool = True,
) -> Optional[str]:
    """게시 실패 dict 를 분류·기록하고(필요 시 알림) 분류명을 돌려준다. 어떤 실패도 예외로 전파하지 않는다.

    이벤트 기록과 알림 중복 확인은 하나의 SQLite 연결·트랜잭션으로 처리하고(연결 대기 최대 3초 1회),
    Slack 발송은 DB 를 닫은 뒤 별도 데몬 스레드에서 한다 — 게시 실패 처리 경로의 지연 상한은 DB 대기 3초."""
    try:
        now = now or datetime.now()
        parsed = parse_publish_failure(raw or {})
        alert_message = None
        conn = _connect(db_path or _DB_PATH)
        try:
            with conn:
                _insert_event(
                    conn, now, "meta_publish", account_code, parsed["error_class"], parsed["http"], parsed["code"],
                    parsed["subcode"], stage, record_id,
                    safe_text(str((raw or {}).get("error", "")), str((raw or {}).get("detail", ""))),
                )
                if notify and parsed["error_class"] in _ALERT_CLASSES and _claim_alert_conn(
                        conn, account_code, parsed["error_class"], now):
                    alert_message = (
                        f"[긴급] Meta {parsed['error_class']} — 계정 {account_code or 'legacy'} "
                        f"code={parsed['code']} subcode={parsed['subcode']}\n"
                        f"토큰·권한·계정 상태 확인 필요 (기록·알림만 적용, 게시 보류는 아직 없음)")
        finally:
            conn.close()
        logger.info("[ErrEvt] src=meta_publish acct=%s class=%s code=%s subcode=%s http=%s stage=%s",
                    account_code or "-", parsed["error_class"], parsed["code"], parsed["subcode"], parsed["http"], stage)
        if alert_message:
            _send_alert(notify, alert_message, notify_async)
        return parsed["error_class"]
    except Exception as exc:  # noqa: BLE001 — 기록 실패가 게시 흐름을 바꾸면 안 된다
        logger.warning("[ErrEvt] 기록 실패(게시 흐름 무영향) | %s", type(exc).__name__)
        return None


def summarize(since_hours: int, by: tuple, db_path: Optional[Path] = None, now: Optional[datetime] = None) -> list:
    """최근 since_hours 시간 이벤트를 by 컬럼(account/error_class/severity/source/stage)별로 집계한다."""
    allowed = {"account": "account", "class": "error_class", "error_class": "error_class", "severity": "severity",
               "source": "source", "stage": "stage"}
    cols = [allowed.get(b) for b in by]
    if not by or any(c is None for c in cols):
        raise ValueError("by 는 account,class,severity,source,stage 중에서 고른다")
    now = now or datetime.now()
    since = (now - timedelta(hours=since_hours)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect(db_path or _DB_PATH)
    try:
        sql = f"SELECT {', '.join(cols)}, COUNT(*), MAX(ts) FROM events WHERE ts >= ? GROUP BY {', '.join(cols)} " \
              f"ORDER BY COUNT(*) DESC"
        return conn.execute(sql, (since,)).fetchall()
    finally:
        conn.close()


def _parse_since(text: str) -> int:
    m = re.fullmatch(r"(\d+)([hd])", text.strip().lower())
    if not m:
        raise ValueError("--since 는 24h 또는 7d 형식")
    return int(m.group(1)) * (24 if m.group(2) == "d" else 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="오류 이벤트 원장 집계")
    ap.add_argument("--since", default="24h")
    ap.add_argument("--by", default="account,class")
    a = ap.parse_args(argv)
    try:
        rows = summarize(_parse_since(a.since), tuple(x.strip() for x in a.by.split(",") if x.strip()))
    except ValueError as exc:
        print(f"오류: {exc}")
        return 2
    if not rows:
        print(f"최근 {a.since} 기록 없음")
        return 0
    for row in rows:
        *keys, count, last = row
        print(" | ".join(str(k) for k in keys), f"| {count}건 | 마지막 {last}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
