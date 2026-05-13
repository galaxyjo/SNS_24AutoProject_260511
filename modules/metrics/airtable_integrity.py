"""
modules/metrics/airtable_integrity.py — Airtable 필드 무결성 체크

Instagram_Posts 테이블에서 post_status='posted' 이면서
ig_media_id 가 비어 있는 레코드를 감지해 Slack으로 알린다.

이 레코드들은 engagement_tracker / auto_liker 에서 처리되지 않으므로
조기에 발견해 수동 보정 또는 재업로드가 필요하다.

사용법:
    from modules.metrics.airtable_integrity import check_ig_media_id
    check_ig_media_id()   # 스케줄러 잡에서 주기적으로 호출
"""

from modules.common.logger import get_logger

logger = get_logger(__name__)


def check_ig_media_id() -> dict:
    """
    post_status='posted' 이면서 ig_media_id 가 없는 레코드를 반환한다.

    반환: {"missing": int, "record_ids": list[str]}
    """
    try:
        from modules.common.airtable_bridge import get_table
        table   = get_table("Instagram_Posts")
        records = table.all(
            formula="AND({post_status}='posted', {ig_media_id}='')"
        )
    except Exception as exc:
        logger.error(f"[Integrity] Airtable 조회 실패 | {exc}")
        return {"missing": 0, "record_ids": []}

    record_ids = [r["id"] for r in records]
    count = len(record_ids)

    if count == 0:
        logger.info("[Integrity] ig_media_id 누락 없음 — 정상")
        return {"missing": 0, "record_ids": []}

    logger.warning(f"[Integrity] ig_media_id 누락 | {count}건 | {record_ids[:5]}")
    _notify(count, record_ids)
    return {"missing": count, "record_ids": record_ids}


def _notify(count: int, record_ids: list[str]) -> None:
    try:
        from services.slack_notifier import send_alert
        sample = "\n".join(f"• `{rid}`" for rid in record_ids[:10])
        suffix = f"\n_...외 {count - 10}건_" if count > 10 else ""
        send_alert(
            title=f"[Airtable 무결성] ig_media_id 누락 {count}건",
            body=(
                f"*post_status=posted* 이면서 *ig_media_id* 가 없는 레코드입니다.\n"
                f"engagement_tracker / auto_liker 에서 처리되지 않습니다.\n\n"
                f"{sample}{suffix}"
            ),
            level="warning",
        )
    except Exception as exc:
        logger.debug(f"[Integrity] Slack 알림 실패 | {exc}")
