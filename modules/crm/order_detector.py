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


def _retry_mark_converted(payload: dict) -> None:
    """retry_queue 핸들러 — 주문 전환 마킹 재시도."""
    _repo.mark_lead_converted(payload["record_id"])


def register_retry_handlers(rq) -> None:
    """260730(ERR-097 계열) — launcher 시작 시 즉시(eager) 호출해야 함(rq.start() 이전).
    실패 시점에만 지연등록하면 재시작 후 pending task가 handler를 못 찾고 dead 처리됨
    (comment_airtable_record/FP-047과 동일 계약)."""
    rq.register("order_mark_converted", _retry_mark_converted)


def handle_order_conversion(record_id: str, sender_igsid: str, text: str) -> None:
    """주문 의사 감지 → lead_status/bridge_status=converted 업데이트 + Telegram 알림.

    ERR-088: DM 웹훅은 재실행 주기가 없어(크롤 배치와 달리) 실패를 로그만 남기고
    넘어가면 전환 데이터가 영구 유실된다 — retry_queue에 위임해 최소한 재시도
    기회를 남긴다."""
    try:
        _repo.mark_lead_converted(record_id)
        logger.info(f"[Order] 전환 처리 완료 | record={record_id} from={sender_igsid}")
    except Exception as exc:
        logger.error(f"[Order] 전환 처리 실패 — retry queue 등록 | record={record_id} | {exc}")
        from modules.common.retry_queue import get_retry_queue

        rq = get_retry_queue()
        rq.register("order_mark_converted", _retry_mark_converted)
        rq.start()
        rq.enqueue("order_mark_converted", {"record_id": record_id})
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
