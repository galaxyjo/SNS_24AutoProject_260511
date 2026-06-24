# modules/crm/order_detector.py
# 주문 의사 키워드 감지 → lead_status=converted + Telegram 전환 알림

import os
import logging
import requests

from modules.common.logger import get_logger
from modules.infra.airtable_repository import AirtableRepository

logger = get_logger(__name__)

_repo = AirtableRepository()

ORDER_KEYWORDS = [
    "주문", "구매", "결제", "오더", "발주", "구입",
    "사고싶", "살게요", "살게", "살까요", "살 수 있",
    "계좌", "입금", "보내주세요",
    "order", "buy", "purchase",
]


def detect_order(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in ORDER_KEYWORDS)


def handle_order_conversion(record_id: str, sender_igsid: str, text: str) -> None:
    """주문 의사 감지 → lead_status/bridge_status=converted 업데이트 + Telegram 알림."""
    try:
        _repo.mark_lead_converted(record_id)
        logger.info(f"[Order] 전환 처리 완료 | record={record_id} from={sender_igsid}")
    except Exception as exc:
        logger.error(f"[Order] 전환 처리 실패 | {exc}")
    _send_telegram_conversion(sender_igsid, text)


def _send_telegram_conversion(sender_igsid: str, text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return
    msg = (
        "\U0001f389 *주문 전환 감지!*\n"
        "─────────────────\n"
        f"\U0001f464 `{sender_igsid}`\n"
        f"\U0001f4ac {text[:150]}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg, "parse_mode": "Markdown"},
            timeout=8,
        )
        logger.info(f"[Order] Telegram 전환 알림 전송 | to={sender_igsid}")
    except Exception as exc:
        logger.warning(f"[Order] Telegram 알림 실패 | {exc}")
