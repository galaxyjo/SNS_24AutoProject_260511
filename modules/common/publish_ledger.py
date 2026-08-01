"""modules/common/publish_ledger.py — 260801 Step6B 완전자동 예약게시 MVP.

unique_publish_key(=content_id+account_code+channel) 단위 Atomic Reserve와
상태전이(RESERVED→PUBLISHING→PUBLISHED/FAILED/UNKNOWN/RECEIPT_SYNC_PENDING/DLQ)를
SQLite에 영속 저장한다. Instagram Post ID는 Airtable 기록 이전에 이 Ledger에
먼저 저장한다 — Airtable PATCH가 실패해도 "Instagram 게시 성공" 사실 자체는
유실되지 않는다(RECEIPT_SYNC_PENDING으로 분리 보존).

Airtable Schema 변경 없이 동작한다 — Instagram_Posts에 content_id/unique_publish_key
필드가 없어도 이 SQLite Ledger가 독립적으로 dedup 계약을 담당한다(260801 Step6B
Read-only Gate 조사 결과 확정 — 근거: docs/CURRENT_RUNTIME_CONTEXT.md·MERGE_JOURNAL.md
Step3 E4 기록 참조).

기존 선례 재사용(REUSE): modules/common/canary_execution_guard.py의
PRIMARY KEY + BEGIN IMMEDIATE + sqlite3.IntegrityError Duplicate Reject 패턴을
그대로 채택한다 — 이 코드베이스에서 이미 Live Runtime 경로로 검증된 패턴.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from modules.common.logger import get_logger

logger = get_logger(__name__)

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "publish_ledger.db"

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS publish_ledger (
        unique_publish_key    TEXT PRIMARY KEY,
        content_id            TEXT NOT NULL,
        account_code          TEXT NOT NULL,
        channel               TEXT NOT NULL,
        state                 TEXT NOT NULL,
        instagram_creation_id TEXT NOT NULL DEFAULT '',
        instagram_post_id     TEXT NOT NULL DEFAULT '',
        airtable_record_id    TEXT NOT NULL DEFAULT '',
        last_error_code       TEXT NOT NULL DEFAULT '',
        created_at            TEXT NOT NULL,
        updated_at            TEXT NOT NULL
    )
"""

_ALLOWED_TRANSITIONS = {
    ("RESERVED", "PUBLISHING"),
    ("PUBLISHING", "PUBLISHED"),
    ("PUBLISHING", "FAILED"),
    ("PUBLISHING", "UNKNOWN"),
    ("PUBLISHED", "RECEIPT_SYNC_PENDING"),
    ("RECEIPT_SYNC_PENDING", "PUBLISHED"),
    ("FAILED", "DLQ"),
}


class PublishLedgerError(Exception):
    """상태전이 계약 위반 또는 중복 Reserve."""


def make_unique_publish_key(content_id: str, account_code: str, channel: str = "instagram") -> str:
    content_id = (content_id or "").strip().lower()
    account_code = (account_code or "").strip().lower()
    channel = (channel or "").strip().lower()
    if not content_id or not account_code or not channel:
        raise PublishLedgerError("content_id/account_code/channel 전부 필수")
    return f"{content_id}|{account_code}|{channel}"


def _connect(db_path: "Path | None" = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def reserve(content_id: str, account_code: str, channel: str = "instagram", *, db_path: "Path | None" = None) -> str:
    """RESERVED로 원자적 선점. 이미 이 key가 존재하면(어떤 state든) 재시도를
    허용하지 않고 즉시 PublishLedgerError — 이 함수는 최초 1회 예약 전용이다."""
    key = make_unique_publish_key(content_id, account_code, channel)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        try:
            conn.execute(
                "INSERT INTO publish_ledger "
                "(unique_publish_key, content_id, account_code, channel, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'RESERVED', ?, ?)",
                (key, content_id, account_code, channel, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise PublishLedgerError(f"unique_publish_key 재사용 금지: {key}") from exc
    logger.info(f"[PublishLedger] RESERVED | key={key}")
    return key


def transition(
    key: str,
    new_state: str,
    *,
    instagram_creation_id: str = "",
    instagram_post_id: str = "",
    airtable_record_id: str = "",
    last_error_code: str = "",
    db_path: "Path | None" = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT state FROM publish_ledger WHERE unique_publish_key=?", (key,)
        ).fetchone()
        if row is None:
            raise PublishLedgerError(f"reserve() 없이 전이 금지: {key}")
        current = row["state"]
        if (current, new_state) not in _ALLOWED_TRANSITIONS:
            raise PublishLedgerError(f"허용되지 않은 전이: {current}->{new_state}")

        fields = ["state=?", "updated_at=?"]
        params: list = [new_state, now]
        if instagram_creation_id:
            fields.append("instagram_creation_id=?")
            params.append(instagram_creation_id)
        if instagram_post_id:
            fields.append("instagram_post_id=?")
            params.append(instagram_post_id)
        if airtable_record_id:
            fields.append("airtable_record_id=?")
            params.append(airtable_record_id)
        if last_error_code:
            fields.append("last_error_code=?")
            params.append(last_error_code)
        params.append(key)
        conn.execute(
            f"UPDATE publish_ledger SET {', '.join(fields)} WHERE unique_publish_key=?",
            params,
        )
    logger.info(f"[PublishLedger] {current}->{new_state} | key={key}")


def get_state(key: str, *, db_path: "Path | None" = None) -> "dict | None":
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM publish_ledger WHERE unique_publish_key=?", (key,)
        ).fetchone()
        return dict(row) if row else None
