"""
comment_event_store.py — 댓글 이벤트 Inbox (FP-047 idempotency)

웹훅(dm_receiver.py)과 폴러(comment_poller.py)가 같은 댓글을 동시에 처리하는
것을 막기 위한 원자적 claim 저장소. retry_queue.py와 책임이 다름:
  - 이 모듈: "이 이벤트를 이미 받았는가"를 원자적으로 판정(Inbox)
  - retry_queue.py: "이미 접수된 실패 작업"을 나중에 재실행(Retry)

설계 근거: docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md

사용법:
    token = try_claim("instagram_comment", comment_id, claimed_by="webhook")
    if token is None:
        return  # 이미 처리 중/완료/억제 대상
    ...
    mark_effect_started("instagram_comment", comment_id, token, "private_reply")
    ...
    mark_effect_done("instagram_comment", comment_id, token, "private_reply")

모든 mark_* 함수는 claim_token이 일치할 때만 실제로 갱신되고(fencing),
불일치(이미 다른 worker가 reclaim해서 token이 바뀐 경우) 시 False를 반환한다 —
호출부는 False를 받으면 그 즉시 나머지 처리를 중단해야 한다(소유권 상실).
"""

import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.common.logger import get_logger

logger = get_logger(__name__)

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "comment_events.db"
_LOCK = threading.Lock()

_VALID_EFFECTS = ("private_reply", "telegram")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comment_events (
            source                 TEXT    NOT NULL,
            source_event_id        TEXT    NOT NULL,
            status                 TEXT    NOT NULL DEFAULT 'RECEIVED',
            claim_token            TEXT    NOT NULL,
            claimed_by             TEXT,
            claimed_at             TEXT    NOT NULL,
            lease_expires_at       TEXT    NOT NULL,
            updated_at             TEXT    NOT NULL,
            private_reply_status   TEXT    NOT NULL DEFAULT 'NOT_APPLICABLE',
            telegram_status        TEXT    NOT NULL DEFAULT 'NOT_APPLICABLE',
            airtable_status        TEXT    NOT NULL DEFAULT 'PENDING',
            manual_review_required INTEGER NOT NULL DEFAULT 0,
            retry_task_id          INTEGER,
            last_error             TEXT,
            migration_tag          TEXT,
            first_seen_mode        TEXT,
            deployment_epoch       TEXT,
            PRIMARY KEY (source, source_event_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_lease
        ON comment_events(status, lease_expires_at)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comment_dead_alerts (
            retry_task_id   INTEGER PRIMARY KEY,
            status          TEXT NOT NULL DEFAULT 'PENDING',
            alerted_at      TEXT
        )
    """)
    conn.commit()


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


_conn: sqlite3.Connection | None = None


def _c() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _get_conn()
    return _conn


# ── claim / fencing ──────────────────────────────────────────────────────────

def try_claim(source: str, source_event_id: str, claimed_by: str, lease_seconds: int = 60, shadow: bool = False) -> str | None:
    """원자적 claim. 성공 시 claim_token(UUID) 반환.
    기존 행이 없으면 신규 claim, 있으면(P0-2 수정, 260715 Codex 2차 리뷰 반영)
    stale(PROCESSING+lease만료)인지 그 자리에서 확인해 원자적으로 재claim까지
    시도한다 — 별도 스윕 잡 없이 다음 요청(poller 5분 주기 등)이 자연히 크래시
    복구를 수행하게 됨(reclaim_stale()을 아무도 호출하지 않아 claim 직후 crash가
    영구 skip으로 남는 문제 수정).
    claim 실패(진짜 진행중/완료/억제 대상)면 None.

    shadow=True(260715 Codex 4차 리뷰): shadow 모드는 실제 claim 경쟁·잠금 동작을
    관측하는 게 목적이라 try_claim() 자체는 그대로 실행하되, 생성되는 행에
    migration_tag='SHADOW_SEEN'을 남긴다. 이 태그가 있는 행은 이 함수의 stale
    reclaim WHERE절에서 영구히 제외된다 — shadow 관측 중엔 handle_comment()(레거시
    경로)가 이미 실제로 Reply/Telegram/Airtable을 처리했으므로, 나중에 enforce가
    이 행을 "죽은 걸로 착각해 재claim"하면 이미 보낸 걸 또 보내게 된다."""
    token = uuid.uuid4().hex
    now = _now_iso()
    lease = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    tag = "SHADOW_SEEN" if shadow else None
    with _LOCK:
        cur = _c().execute(
            """INSERT OR IGNORE INTO comment_events
               (source, source_event_id, status, claim_token, claimed_by,
                claimed_at, lease_expires_at, updated_at, migration_tag)
               VALUES (?, ?, 'PROCESSING', ?, ?, ?, ?, ?, ?)""",
            (source, source_event_id, token, claimed_by, now, lease, now, tag),
        )
        _c().commit()
        if cur.rowcount == 1:
            logger.info(f"[CommentEventStore] claim 성공(신규{'·shadow' if shadow else ''}) | {source}:{source_event_id} | by={claimed_by}")
            return token

        if shadow:
            # shadow는 신규 claim 실패(이미 행 존재) 시 재claim 시도 자체를 하지 않는다 —
            # 관측만이 목적이라, 이미 있는 행(진짜든 shadow든)을 건드릴 이유가 없음.
            logger.debug(f"[CommentEventStore] shadow would_claim=False(이미 행 존재) | {source}:{source_event_id}")
            return None

        # 기존 행 존재 — stale(PROCESSING+lease만료)이면 그 자리에서 원자적 재claim 시도.
        # WHERE 절에 status/lease 조건을 포함시켜, 두 호출자가 동시에 시도해도 하나만 성공.
        # migration_tag IS NULL 조건으로 shadow/migration 태그가 붙은 행은 절대 재claim 제외.
        cur2 = _c().execute(
            """UPDATE comment_events
               SET claim_token=?, claimed_by=?, claimed_at=?, lease_expires_at=?, updated_at=?,
                   private_reply_status = CASE WHEN private_reply_status='STARTED' THEN 'UNKNOWN' ELSE private_reply_status END,
                   telegram_status = CASE WHEN telegram_status='STARTED' THEN 'UNKNOWN' ELSE telegram_status END,
                   manual_review_required = CASE
                       WHEN private_reply_status='STARTED' OR telegram_status='STARTED' THEN 1
                       ELSE manual_review_required
                   END
               WHERE source=? AND source_event_id=? AND status='PROCESSING'
                 AND lease_expires_at < ? AND migration_tag IS NULL""",
            (token, claimed_by, now, lease, now, source, source_event_id, now),
        )
        _c().commit()
        if cur2.rowcount == 1:
            logger.warning(f"[CommentEventStore] stale reclaim 성공 | {source}:{source_event_id} | by={claimed_by}")
            return token

    logger.debug(f"[CommentEventStore] 이미 claim됨(skip) | {source}:{source_event_id} | by={claimed_by}")
    return None


def reclaim_stale(source: str, max_age_seconds: int = 60) -> list[tuple[str, str]]:
    """수동/일괄 스윕용(운영 점검·테스트) — 실제 런타임 크래시 복구는 try_claim()
    자체에 내장되어 있어 이 함수 호출 없이도 다음 claim 시도에서 자연히 일어난다."""
    now_dt = datetime.now(timezone.utc)
    now_iso = _now_iso()
    with _LOCK:
        rows = _c().execute(
            """SELECT source_event_id FROM comment_events
               WHERE source=? AND status='PROCESSING' AND lease_expires_at < ?""",
            (source, now_iso),
        ).fetchall()
        recovered: list[tuple[str, str]] = []
        for row in rows:
            sid = row["source_event_id"]
            new_token = uuid.uuid4().hex
            new_lease = (now_dt + timedelta(seconds=max_age_seconds)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            _c().execute(
                """UPDATE comment_events
                   SET claim_token=?, lease_expires_at=?, updated_at=?,
                       private_reply_status = CASE WHEN private_reply_status='STARTED' THEN 'UNKNOWN' ELSE private_reply_status END,
                       telegram_status = CASE WHEN telegram_status='STARTED' THEN 'UNKNOWN' ELSE telegram_status END,
                       manual_review_required = CASE
                           WHEN private_reply_status='STARTED' OR telegram_status='STARTED' THEN 1
                           ELSE manual_review_required
                       END
                   WHERE source=? AND source_event_id=?""",
                (new_token, new_lease, now_iso, source, sid),
            )
            recovered.append((sid, new_token))
        _c().commit()
    if recovered:
        logger.warning(f"[CommentEventStore] stale lease 회수 {len(recovered)}건 | source={source}")
    return recovered


def _fenced_update(source: str, source_event_id: str, claim_token: str, set_clause: str, params: tuple) -> bool:
    """claim_token 일치 시에만 갱신. rowcount==1이면 True, 0이면 fenced-out(False)."""
    now = _now_iso()
    with _LOCK:
        cur = _c().execute(
            f"UPDATE comment_events SET updated_at=?, {set_clause} "
            f"WHERE source=? AND source_event_id=? AND claim_token=?",
            (now, *params, source, source_event_id, claim_token),
        )
        _c().commit()
        ok = cur.rowcount == 1
    if not ok:
        logger.warning(
            f"[CommentEventStore] fencing 거절(이미 reclaim됨) | {source}:{source_event_id}"
        )
    return ok


# ── effect(Private Reply / Telegram) 상태 ───────────────────────────────────

def mark_effect_started(source: str, source_event_id: str, claim_token: str, effect: str) -> bool:
    assert effect in _VALID_EFFECTS
    col = f"{effect}_status"
    return _fenced_update(source, source_event_id, claim_token, f"{col}=?", ("STARTED",))


def mark_effect_done(source: str, source_event_id: str, claim_token: str, effect: str) -> bool:
    assert effect in _VALID_EFFECTS
    col = f"{effect}_status"
    return _fenced_update(source, source_event_id, claim_token, f"{col}=?", ("DONE",))


def mark_effect_unknown(source: str, source_event_id: str, claim_token: str, effect: str) -> bool:
    assert effect in _VALID_EFFECTS
    col = f"{effect}_status"
    return _fenced_update(
        source, source_event_id, claim_token,
        f"{col}=?, manual_review_required=1", ("UNKNOWN",),
    )


# ── Airtable 기록 상태 ────────────────────────────────────────────────────────

def mark_airtable_retry_pending(source: str, source_event_id: str, claim_token: str, retry_task_id: int) -> bool:
    return _fenced_update(
        source, source_event_id, claim_token,
        "airtable_status=?, retry_task_id=?", ("RETRY_PENDING", retry_task_id),
    )


def mark_airtable_done(source: str, source_event_id: str, claim_token: str) -> bool:
    """단일 UPDATE로 airtable_status/status를 함께 반영(260715 Codex 2차 리뷰 반영) —
    이전엔 두 번의 별도 UPDATE라 중간에 crash하면 airtable_status=DONE인데
    status=PROCESSING으로 갈라져 영구 고착될 수 있었음."""
    return _fenced_update(
        source, source_event_id, claim_token,
        "airtable_status=?, status=?", ("DONE", "COMPLETED"),
    )


def mark_airtable_retry_completed(source: str, source_event_id: str) -> bool:
    """P0(260715 Codex 3차 리뷰) — retry_queue 비동기 핸들러 전용 완료 반영.
    claim_token으로 fencing하지 않는다: retry payload에 담긴 claim_token은 enqueue
    시점의 것인데, 그 사이 lease가 만료돼 poller 등이 stale reclaim(P0-2)을 하면
    token이 바뀌어버려 claim_token 기반 마킹은 항상 fenced-out된다("다음 시도에
    자연 복구된다"던 이전 주석은 틀렸음 — 재개 경로는 airtable_status=RETRY_PENDING을
    보면 재시도 자체를 스킵하므로 아무도 다시 안 건드림).
    대신 (source, source_event_id) + airtable_status='RETRY_PENDING' 조건으로
    전이한다 — retry_queue 태스크가 실제 Airtable 쓰기를 성공시켰다는 사실 자체가
    소유권 증명이며, claim_token 세대교체와 무관하게 유효해야 한다."""
    now = _now_iso()
    with _LOCK:
        cur = _c().execute(
            """UPDATE comment_events SET airtable_status=?, status=?, updated_at=?
               WHERE source=? AND source_event_id=? AND airtable_status='RETRY_PENDING'""",
            ("DONE", "COMPLETED", now, source, source_event_id),
        )
        _c().commit()
        return cur.rowcount == 1


def mark_retry_enqueue_failed(source: str, source_event_id: str, claim_token: str, error: str) -> bool:
    return _fenced_update(
        source, source_event_id, claim_token,
        "airtable_status=?, last_error=?", ("RETRY_ENQUEUE_FAILED", error[:500]),
    )


def mark_dead(source: str, source_event_id: str) -> None:
    """comment_retry_dead_monitor 전용 — claim_token 불필요(event 소유권과 무관한 별도 판정,
    retry_queue가 유일한 dead 판정 source of truth)."""
    now = _now_iso()
    with _LOCK:
        _c().execute(
            "UPDATE comment_events SET status='DEAD', updated_at=? "
            "WHERE source=? AND source_event_id=?",
            (now, source, source_event_id),
        )
        _c().commit()


def find_by_retry_task_id(retry_task_id: int) -> tuple[str, str] | None:
    """comment_retry_dead_monitor 전용 — retry_task_id로 (source, source_event_id) 역조회."""
    with _LOCK:
        row = _c().execute(
            "SELECT source, source_event_id FROM comment_events WHERE retry_task_id=?",
            (retry_task_id,),
        ).fetchone()
    return (row["source"], row["source_event_id"]) if row else None


def get_status(source: str, source_event_id: str) -> dict | None:
    with _LOCK:
        row = _c().execute(
            "SELECT * FROM comment_events WHERE source=? AND source_event_id=?",
            (source, source_event_id),
        ).fetchone()
    return dict(row) if row else None


# ── dead-monitor 알림 dedup (간소화 버전 — 상세: 설계문서 §5) ──────────────────

def try_claim_dead_alert(retry_task_id: int) -> bool:
    """dead 알림을 이미 시도했는지 원자적 확인. True=최초(알림 진행), False=이미 처리."""
    with _LOCK:
        cur = _c().execute(
            "INSERT OR IGNORE INTO comment_dead_alerts (retry_task_id, status) VALUES (?, 'PENDING')",
            (retry_task_id,),
        )
        _c().commit()
        inserted = cur.rowcount == 1
        if not inserted:
            row = _c().execute(
                "SELECT status FROM comment_dead_alerts WHERE retry_task_id=?", (retry_task_id,)
            ).fetchone()
            return row is not None and row["status"] == "PENDING"
    return True


def mark_dead_alert_sent(retry_task_id: int) -> None:
    now = _now_iso()
    with _LOCK:
        _c().execute(
            "UPDATE comment_dead_alerts SET status='SENT', alerted_at=? WHERE retry_task_id=?",
            (now, retry_task_id),
        )
        _c().commit()
