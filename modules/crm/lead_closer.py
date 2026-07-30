# modules/crm/lead_closer.py
# 팔로업 완료 → CLOSE 상태 전환 + Telegram 알림

import os
import requests

from modules.common.logger import get_logger
from modules.infra.airtable_repository import AirtableRepository

logger = get_logger(__name__)

_repo = AirtableRepository()


def _retry_mark_closed(payload: dict) -> None:
    """retry_queue 핸들러 — CLOSE 마킹 재시도."""
    _repo.mark_lead_closed(payload["record_id"])


def register_retry_handlers(rq) -> None:
    """260730(ERR-097 계열) — launcher 시작 시 즉시(eager) 호출해야 함(rq.start() 이전).
    실패 시점에만 지연등록하면 재시작 후 pending task가 handler를 못 찾고 dead 처리됨
    (comment_airtable_record/FP-047과 동일 계약)."""
    rq.register("lead_mark_closed", _retry_mark_closed)


def mark_lead_closed(record_id: str) -> None:
    """CLOSE 상태 전환 — bridge_status=closed, lead_status=converted, closed_at 기록.

    ERR-087: 현재 Production Caller는 없으나(dm_followup_scheduler.py 미연동), 향후
    연동 시 재실행 주기가 없는 호출부라면 실패가 영구 유실되므로 retry_queue에
    위임한다. 실패 시 "CLOSE 완료" 알림도 보내지 않는다(상태-알림 불일치 방지)."""
    if not record_id:
        logger.warning("[Closer] record_id 없음 — skip")
        return
    try:
        _repo.mark_lead_closed(record_id)
        logger.info(f"[Closer] CLOSE 처리 완료 | record={record_id}")
    except Exception as exc:
        logger.error(f"[Closer] CLOSE 처리 실패 — retry queue 등록 | record={record_id} | {exc}")
        from modules.common.retry_queue import get_retry_queue

        rq = get_retry_queue()
        rq.register("lead_mark_closed", _retry_mark_closed)
        rq.start()
        rq.enqueue("lead_mark_closed", {"record_id": record_id})
        return
    _send_telegram_closed(record_id)


def _send_telegram_closed(record_id: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return
    msg = (
        "✅ *거래 완료 (CLOSE)*\n"
        "─────────\n"
        f"\U0001f4cb `{record_id}`"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg, "parse_mode": "Markdown"},
            timeout=8,
        )
        logger.info(f"[Closer] Telegram CLOSE 알림 전송 | record={record_id}")
    except Exception as exc:
        logger.warning(f"[Closer] Telegram 알림 실패 | {exc}")
