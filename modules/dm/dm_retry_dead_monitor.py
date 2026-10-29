"""
dm_retry_dead_monitor.py — DM 관련 retry_queue dead 건 능동 알림 (261029 STEP 2 SLA·장애 알림)

retry_queue.py는 3회 실패한 작업을 자기 DB만 status='dead'로 바꾸고 콜백하지 않는다.
이 모듈은 댓글용 comment_retry_dead_monitor와 같은 패턴으로 retry_queue.db를 읽기 전용으로 조회해
DM 자동응답(ig_auto_reply)·팔로업(ig_followup)·DM 저장(dm_record_interaction)의 dead를 한 번씩 알린다.

- 과거에 이미 dead였던 작업이 한꺼번에 알림으로 쏟아지지 않도록, 이 모듈이 로드된 시각(= launcher 기동)
  이후에 생성된 작업만 대상으로 한다.
- 알림 중복 방지는 기존 comment_event_store.try_claim_dead_alert(retry_task_id)를 재사용한다
  (retry_task_id는 큐 전체에서 유일하므로 댓글 알림과 섞이지 않는다).
- 알림 본문에는 계정코드·이벤트 앞 6자·작업 유형·task id만 담는다(발신자 ID·메시지 원문·예외 문구 금지).
- 알림 전달(Slack, 실패 시 Telegram 대체)에 실패하면 PENDING으로 남아 다음 주기에 다시 시도한다.
"""

import json
import sqlite3
from datetime import datetime, timezone

from modules.comment import comment_event_store as event_store
from modules.common.logger import get_logger
from modules.common.retry_queue import _DB_PATH as _RETRY_DB_PATH
from modules.dm.dm_auto_reply import _alert_dm

logger = get_logger(__name__)

_TASK_TYPES = ("ig_auto_reply", "ig_followup", "dm_record_interaction")
# retry_tasks.created_at은 SQLite datetime('now') = UTC 'YYYY-MM-DD HH:MM:SS' 형식
_STARTED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _fetch_dead_tasks(since: str) -> list[dict]:
    """retry_queue.db를 읽기 전용(mode=ro)으로 조회 — retry_queue.py 코드는 건드리지 않음."""
    if not _RETRY_DB_PATH.exists():
        return []
    conn = sqlite3.connect(f"file:{_RETRY_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        marks = ",".join("?" for _ in _TASK_TYPES)
        rows = conn.execute(
            f"SELECT id, task_type, payload FROM retry_tasks "
            f"WHERE task_type IN ({marks}) AND status='dead' AND created_at >= ?",
            (*_TASK_TYPES, since),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


_STUCK_ALERTED: set[tuple[str, str]] = set()
_STUCK_SECONDS = 180


def check_stuck_sending(older_than_seconds: int = _STUCK_SECONDS) -> int:
    """발송 중(SENDING)으로 오래 멈춘 DM 이벤트(작업 스레드가 선점 뒤 죽은 경우 등)를 한 번씩 알린다.
    프로세스 안 메모리로 중복 알림을 막으므로 재시작하면 다시 알릴 수 있다(누락보다 중복이 안전)."""
    alerted = 0
    try:
        stuck = event_store.list_stale_effects("instagram_dm:", "private_reply", "SENDING", older_than_seconds)
    except Exception as exc:
        logger.warning(f"[DmDeadMonitor] 멈춘 SENDING 조회 실패 | exception_type={type(exc).__name__}")
        return 0
    for source, mid in stuck:
        if (source, mid) in _STUCK_ALERTED:
            continue
        if _alert_dm("발송 중 멈춤(SENDING)", source, mid,
                     f"{older_than_seconds}초 넘게 발송 중 상태 — 작업이 중단됐을 수 있음", manual=True, level="error"):
            _STUCK_ALERTED.add((source, mid))
            alerted += 1
    return alerted


def check_dead_dm_tasks(since: str | None = None) -> int:
    """기동 이후 새로 dead가 된 DM 작업을 알린다. 반환: 이번 실행에서 알림이 전달된 dead 건수.
    같은 주기에 멈춘 SENDING 이벤트도 점검한다(별도 건수는 로그로만 남긴다)."""
    stuck = check_stuck_sending()
    if stuck:
        logger.warning(f"[DmDeadMonitor] 멈춘 SENDING 알림 {stuck}건")
    dead_tasks = _fetch_dead_tasks(since or _STARTED_AT)
    alerted = 0
    for task in dead_tasks:
        tid = task["id"]
        if not event_store.try_claim_dead_alert(tid):
            continue
        try:
            payload = json.loads(task.get("payload") or "{}")
        except Exception:
            payload = {}
        account = payload.get("account_code_ref") or "UNRESOLVED"
        event = payload.get("dm_event")
        mid = event[1] if isinstance(event, (list, tuple)) and len(event) >= 2 else ""
        delivered = _alert_dm(
            "retry 영구 실패(dead)", f"instagram_dm:{account}", mid,
            f"task={task['task_type']} | task_id={tid} | 재시도 3회 소진", manual=True, level="error",
        )
        if delivered:
            event_store.mark_dead_alert_sent(tid)
            alerted += 1
            logger.warning(f"[DmDeadMonitor] dead 알림 전달 | task_id={tid} | type={task['task_type']}")
        else:
            logger.warning(f"[DmDeadMonitor] 알림 전달 실패 — 다음 주기 재시도 | task_id={tid}")
    return alerted
