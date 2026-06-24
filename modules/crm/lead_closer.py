# modules/crm/lead_closer.py
# 팔로업 완료 → CLOSE 상태 전환 + Telegram 알림

import os
import requests

from modules.common.logger import get_logger
from modules.infra.airtable_repository import AirtableRepository

logger = get_logger(__name__)

_repo = AirtableRepository()


def mark_lead_closed(record_id: str) -> None:
    """CLOSE 상태 전환 — bridge_status=closed, lead_status=converted, closed_at 기록."""
    if not record_id:
        logger.warning("[Closer] record_id 없음 — skip")
        return
    try:
        _repo.mark_lead_closed(record_id)
        logger.info(f"[Closer] CLOSE 처리 완료 | record={record_id}")
    except Exception as exc:
        logger.error(f"[Closer] CLOSE 처리 실패 | {exc}")
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
