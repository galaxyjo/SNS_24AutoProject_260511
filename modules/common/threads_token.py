"""modules/common/threads_token.py — 261015 Threads 장기 토큰 자동 갱신.

Threads 장기 사용자 토큰은 60일 뒤 만료되고, 60일 안에 갱신하지 않으면 다시
살릴 수 없다(공식 문서 developers.facebook.com/docs/threads/get-started/long-lived-tokens).
갱신 조건: 발급·갱신 후 24시간 이상 지났고 아직 만료 전일 것. 갱신하면 그 시점부터
다시 60일.

저장 위치:
  - 최초 토큰(seed)은 `.env`의 `{KEY}_THREADS_ACCESS_TOKEN`.
  - 갱신된 토큰은 `db/threads_token.db`(SQLite, `*.db`라 gitignore 대상)에 저장하고,
    이후에는 이 값을 우선 사용한다. 런타임이 `.env`를 다시 쓰지 않는다(비밀 파일 전체
    손상 위험 회피).

토큰 원문은 로그·예외 메시지에 남기지 않는다(앞 4글자만).
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import requests

from modules.common.logger import get_logger

logger = get_logger("threads_token")

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "threads_token.db"
_REFRESH_URL = "https://graph.threads.net/refresh_access_token"
_TS_FMT = "%Y-%m-%d %H:%M:%S"
REFRESH_EVERY_DAYS = 7      # 60일 만료 대비 넉넉한 주기(실패해도 50일 넘게 재시도 여유)
_MIN_AGE = timedelta(hours=24)


def _connect(db_path: "Path | None" = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS threads_token ("
        " credential_key TEXT PRIMARY KEY,"
        " access_token TEXT NOT NULL,"
        " refreshed_at TEXT NOT NULL,"
        " expires_at TEXT NOT NULL)"
    )
    return conn


def _mask(token: str) -> str:
    return f"{token[:4]}…(len={len(token)})" if token else "(empty)"


def _load_row(key: str, db_path: "Path | None" = None) -> "dict | None":
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT access_token, refreshed_at, expires_at FROM threads_token WHERE credential_key = ?",
            (key,),
        ).fetchone()
    if not row:
        return None
    return {"access_token": row[0], "refreshed_at": row[1], "expires_at": row[2]}


def get_threads_token(key: str, *, db_path: "Path | None" = None) -> str:
    """갱신된 토큰이 있으면 그것을, 없으면 `.env`의 seed 토큰을 반환한다."""
    row = _load_row(key, db_path)
    if row and row["access_token"]:
        return row["access_token"]
    return os.getenv(f"{key}_THREADS_ACCESS_TOKEN", "").strip()


def refresh_threads_token(key: str, *, now: "datetime | None" = None,
                          db_path: "Path | None" = None) -> str:
    """토큰 1개를 필요하면 갱신한다. 반환값: "refreshed" / "not_due" / "no_token" / "failed".

    - DB에 기록이 없으면(아직 한 번도 갱신 안 함) 바로 갱신을 시도한다. 발급 24시간
      전이면 Meta가 거부하므로 "failed"로 남고 다음 실행에서 다시 시도한다.
    - DB 기록이 있으면 마지막 갱신 후 REFRESH_EVERY_DAYS일이 지났을 때만 갱신한다.
    - 실패하면 기존 토큰을 그대로 둔다(덮어쓰지 않음).
    """
    now = now or datetime.now()
    token = get_threads_token(key, db_path=db_path)
    if not token:
        return "no_token"
    row = _load_row(key, db_path)
    if row:
        try:
            last = datetime.strptime(row["refreshed_at"], _TS_FMT)
        except ValueError:
            last = None
        if last and now - last < max(timedelta(days=REFRESH_EVERY_DAYS), _MIN_AGE):
            return "not_due"

    try:
        r = requests.get(
            _REFRESH_URL,
            params={"grant_type": "th_refresh_token", "access_token": token},
            timeout=30,
        )
        body = r.json() if r.content else {}
    except Exception as exc:  # 네트워크·JSON 오류 — 원문 토큰은 예외에 포함되지 않음
        logger.error(f"[ThreadsToken] 갱신 요청 실패 | key={key} | {type(exc).__name__}")
        return "failed"

    new_token = (body or {}).get("access_token", "")
    expires_in = (body or {}).get("expires_in")
    if r.status_code != 200 or not new_token or not isinstance(expires_in, (int, float)):
        msg = ((body or {}).get("error") or {}).get("message", "")[:150]
        logger.error(f"[ThreadsToken] 갱신 거부 | key={key} | status={r.status_code} | {msg}")
        return "failed"

    expires_at = now + timedelta(seconds=int(expires_in))
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO threads_token (credential_key, access_token, refreshed_at, expires_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(credential_key) DO UPDATE SET"
            " access_token=excluded.access_token, refreshed_at=excluded.refreshed_at,"
            " expires_at=excluded.expires_at",
            (key, new_token, now.strftime(_TS_FMT), expires_at.strftime(_TS_FMT)),
        )
        conn.commit()
    logger.info(
        f"[ThreadsToken] 갱신 성공 | key={key} | token={_mask(new_token)} | "
        f"expires_at={expires_at.strftime(_TS_FMT)}"
    )
    return "refreshed"


def get_token_status(key: str, *, db_path: "Path | None" = None) -> dict:
    """대시보드·점검용 — 토큰 원문 없이 상태만 돌려준다."""
    row = _load_row(key, db_path)
    if row:
        return {"source": "db", "refreshed_at": row["refreshed_at"], "expires_at": row["expires_at"]}
    has_seed = bool(os.getenv(f"{key}_THREADS_ACCESS_TOKEN", "").strip())
    return {"source": "env" if has_seed else "none", "refreshed_at": None, "expires_at": None}
