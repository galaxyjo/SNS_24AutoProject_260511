"""
comment_retry_dead_monitor.py — FP-047 dead task 능동 알림 (간소화 MVP 버전)

retry_queue.py는 comment_airtable_record 태스크가 3회 실패하면 자기 DB만
status='dead'로 바꾸고 핸들러에 콜백하지 않는다(retry_queue.py 코드는 건드리지
않음 — 설계문서 §5). 이 잡이 주기적으로 retry_queue.db를 읽기 전용으로 조회해
dead 건을 찾아 Slack 1회 알림 + comment_event_store.status='DEAD' 반영을 같은
pass에서 처리한다.

간소화(MVP): 설계문서 §5의 완전한 CLAIMED/SENT 원자적 상태머신 대신, APScheduler
max_instances=1(_job_dome_export와 동일 패턴)로 동시실행 자체를 막고, 알림
dedup은 comment_event_store.try_claim_dead_alert()의 단순 PENDING 체크로
처리한다 — 프로세스 내 단일 인스턴스 배포 전제(현재 운영 형태)에서는 충분,
다중 프로세스 배포로 바뀌면 원자적 claim으로 강화 필요(fast-follow).
"""

import sqlite3

from modules.comment import comment_event_store as event_store
from modules.common.logger import get_logger
from modules.common.retry_queue import _DB_PATH as _RETRY_DB_PATH

logger = get_logger(__name__)

_TASK_TYPE = "comment_airtable_record"


def _fetch_dead_tasks() -> list[dict]:
    """retry_queue.db를 읽기 전용으로 조회 — retry_queue.py 코드는 건드리지 않음.
    P0(260715 Codex 2차 리뷰): "읽기전용"이라고 문서화만 하고 실제로는 일반
    read-write 커넥션이었음 — SQLite URI mode=ro로 드라이버 레벨에서 강제."""
    if not _RETRY_DB_PATH.exists():
        return []
    conn = sqlite3.connect(f"file:{_RETRY_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, payload, last_error FROM retry_tasks WHERE task_type=? AND status='dead'",
            (_TASK_TYPE,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def check_dead_comment_tasks() -> int:
    """dead 상태인 comment_airtable_record 태스크를 확인해 Slack 알림 + event_store 동기화.
    반환: 이번 실행에서 새로 알림 보낸 건수."""
    dead_tasks = _fetch_dead_tasks()
    if not dead_tasks:
        return 0

    alerted = 0
    for task in dead_tasks:
        tid = task["id"]

        # 1. DEAD 반영은 Slack 성공 여부와 무관하게 먼저(무조건·멱등)
        found = event_store.find_by_retry_task_id(tid)
        if found:
            event_store.mark_dead(*found)

        # 2. 알림 dedup — 이미 시도했으면 skip
        if not event_store.try_claim_dead_alert(tid):
            continue

        # 3. Slack 알림(성공시에만 SENT 기록 — 실패하면 다음 주기 재시도)
        try:
            from services.slack_notifier import send_alert
            comment_ref = f"{found[1]}" if found else f"retry_task_id={tid}"
            ok = send_alert(
                title="댓글 Airtable 기록 영구 실패(dead)",
                body=f"comment={comment_ref} | 재시도 3회 소진 | last_error={task.get('last_error', '')[:200]}",
                level="error",
            )
        except Exception as exc:
            logger.warning(f"[CommentDeadMonitor] Slack 알림 예외 | task_id={tid} | {exc}")
            ok = False

        if ok:
            event_store.mark_dead_alert_sent(tid)
            alerted += 1
            logger.warning(f"[CommentDeadMonitor] dead 알림 발송 | task_id={tid}")
        else:
            logger.warning(f"[CommentDeadMonitor] Slack 알림 실패 — 다음 주기 재시도 | task_id={tid}")

    return alerted
