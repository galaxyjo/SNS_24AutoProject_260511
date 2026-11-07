"""
modules/common/ai_usage_ledger.py — AI 호출 장부 1단계 (261107 Gate 7 설계, 회장 승인 "구현 승인")

계정별로 AI 공급자를 몇 번·어느 공급자/모델로·성공/실패로 불렀는지만 기록한다(가시성 전용).
호출 흐름·재시도·대체 순서·게시 판정은 바꾸지 않는다. 기록 실패는 호출자에게 전파하지 않는다(fail-open).

- 기본 OFF: 환경변수 `AI_USAGE_LEDGER_ENABLED=true`일 때만 기록·래핑한다. OFF이면 `wrap_gemini_client`는
  받은 객체를 그대로(동일 객체) 돌려준다.
- 저장소: 기존 `db/error_events.db` 파일의 새 테이블 `ai_calls`(기존 `events`·`alert_log`는 건드리지 않는다).
- 저장 항목: ts, account, provider, model, stage, outcome(ok/fail), status, tin, tout, ms.
  프롬프트·응답·키·오류 문구 원문은 저장하지 않는다.

조회: python -m modules.common.ai_usage_ledger --since 24h --by account,provider,outcome
"""

import argparse
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from modules.common.logger import get_logger

logger = get_logger(__name__)

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "error_events.db"

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS ai_calls (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        ts       TEXT NOT NULL,
        account  TEXT NOT NULL DEFAULT '',
        provider TEXT NOT NULL DEFAULT '',
        model    TEXT NOT NULL DEFAULT '',
        stage    TEXT NOT NULL DEFAULT '',
        outcome  TEXT NOT NULL,
        status   INTEGER,
        tin      INTEGER,
        tout     INTEGER,
        ms       INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ai_calls_ts ON ai_calls(ts)",
)

_TOKEN_RE = re.compile(r"\b(?:EAA|IGAA|IGQ|THAA|AIza|AQ\.|sk-)[A-Za-z0-9_\-\.]{10,}")
_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9_.:\-/ ]")


def is_enabled() -> bool:
    return os.getenv("AI_USAGE_LEDGER_ENABLED", "").strip().lower() == "true"


def _clean(value, limit: int = 60) -> str:
    text = _TOKEN_RE.sub("", str(value or ""))
    return _SAFE_CHARS_RE.sub("", text).strip()[:limit]


def _int_or_none(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def record_ai_call(
    *, account: str, provider: str, model: str = "", stage: str = "", outcome: str,
    status=None, tin=None, tout=None, ms=None,
    db_path: Optional[Path] = None, now: Optional[datetime] = None,
) -> None:
    """AI 호출 1건을 기록한다. 플래그 OFF(그리고 db_path 미지정)이면 아무것도 하지 않는다. 어떤 실패도 전파하지 않는다."""
    try:
        if db_path is None and not is_enabled():
            return
        now = now or datetime.now()
        out = "ok" if outcome == "ok" else "fail"
        path = db_path or _DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=3)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            for stmt in _SCHEMA:
                conn.execute(stmt)
            with conn:
                conn.execute(
                    "INSERT INTO ai_calls(ts, account, provider, model, stage, outcome, status, tin, tout, ms) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (now.strftime("%Y-%m-%d %H:%M:%S"), _clean(account, 40), _clean(provider), _clean(model),
                     _clean(stage), out, _int_or_none(status), _int_or_none(tin), _int_or_none(tout),
                     _int_or_none(ms)),
                )
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — 기록 실패가 AI 호출 흐름을 바꾸면 안 된다
        logger.warning("[AiLedger] 기록 실패(호출 흐름 무영향) | %s", type(exc).__name__)


# ── Gemini(genai.Client 호환) 기록 래퍼 ─────────────────────────────────────────

def _usage_tokens(response) -> tuple:
    usage = getattr(response, "usage_metadata", None)
    return (_int_or_none(getattr(usage, "prompt_token_count", None)),
            _int_or_none(getattr(usage, "candidates_token_count", None)))


def _error_status(exc: Exception):
    for name in ("code", "status_code"):
        value = getattr(exc, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


class _RecordingModels:
    def __init__(self, owner: "UsageRecordingClient"):
        self._owner = owner

    def generate_content(self, *args, **kwargs):
        started = time.time()
        model = kwargs.get("model", "")
        try:
            response = self._owner._inner.models.generate_content(*args, **kwargs)
        except Exception as exc:
            self._owner._record("fail", model, started, status=_error_status(exc))
            raise
        tin, tout = _usage_tokens(response)
        self._owner._record("ok", model, started, tin=tin, tout=tout)
        return response

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._owner._inner.models, name)


class UsageRecordingClient:
    """genai.Client 호환 기록 래퍼. 호출 인자·반환값·예외는 그대로 통과시키고 결과만 장부에 남긴다."""

    def __init__(self, inner, account: str, stage: str = ""):
        self._inner = inner
        self._account = account
        self._stage = stage
        self.models = _RecordingModels(self)

    def _record(self, outcome: str, model, started: float, status=None, tin=None, tout=None) -> None:
        try:
            record_ai_call(account=self._account, provider="gemini", model=model, stage=self._stage, outcome=outcome,
                           status=status, tin=tin, tout=tout, ms=int((time.time() - started) * 1000))
        except Exception as exc:  # noqa: BLE001 — 장부 문제가 호출 결과를 바꾸면 안 된다(이중 방어)
            logger.warning("[AiLedger] 기록 호출 실패(호출 흐름 무영향) | %s", type(exc).__name__)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._inner, name)


def wrap_gemini_client(client, account: str, stage: str = ""):
    """플래그 OFF이면 받은 객체를 그대로(동일 객체) 돌려준다. ON이면 기록 래퍼로 감싼다."""
    if not is_enabled() or client is None:
        return client
    return UsageRecordingClient(client, account, stage)


# ── 조회 ────────────────────────────────────────────────────────────────────────

def summarize(since_hours: int, by: tuple, db_path: Optional[Path] = None, now: Optional[datetime] = None) -> list:
    allowed = {"account": "account", "provider": "provider", "model": "model", "stage": "stage", "outcome": "outcome"}
    cols = [allowed.get(b) for b in by]
    if not by or any(c is None for c in cols):
        raise ValueError("by 는 account,provider,model,stage,outcome 중에서 고른다")
    now = now or datetime.now()
    since = (now - timedelta(hours=since_hours)).strftime("%Y-%m-%d %H:%M:%S")
    path = db_path or _DB_PATH
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=3)
    try:
        sql = (f"SELECT {', '.join(cols)}, COUNT(*), COALESCE(SUM(tin),0), COALESCE(SUM(tout),0), MAX(ts) "
               f"FROM ai_calls WHERE ts >= ? GROUP BY {', '.join(cols)} ORDER BY COUNT(*) DESC")
        return conn.execute(sql, (since,)).fetchall()
    finally:
        conn.close()


def _parse_since(text: str) -> int:
    m = re.fullmatch(r"(\d+)([hd])", text.strip().lower())
    if not m:
        raise ValueError("--since 는 24h 또는 7d 형식")
    return int(m.group(1)) * (24 if m.group(2) == "d" else 1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AI 호출 장부 집계(읽기 전용)")
    ap.add_argument("--since", default="24h")
    ap.add_argument("--by", default="account,provider,outcome")
    a = ap.parse_args(argv)
    try:
        rows = summarize(_parse_since(a.since), tuple(x.strip() for x in a.by.split(",") if x.strip()))
    except (ValueError, sqlite3.Error) as exc:
        print(f"오류: {exc}")
        return 2
    if not rows:
        print(f"최근 {a.since} 기록 없음")
        return 0
    for row in rows:
        *keys, count, tin, tout, last = row
        print(" | ".join(str(k) for k in keys), f"| {count}건 | 입력 {tin} 출력 {tout} | 마지막 {last}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
