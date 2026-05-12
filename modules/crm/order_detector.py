# modules/crm/order_detector.py
# 주문 의사 키워드 감지 → lead_status=converted + Telegram 전환 알림

import os
import json as _json
import logging
import requests
from datetime import datetime, timezone

from modules.common.logger import get_logger
logger = get_logger(__name__)

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
    """주문 의사 감지 → Airtable lead_status/bridge_status=converted 업데이트 + Telegram 알림.

    converted_at 필드는 선택사항 — Airtable에 없으면 경고 후 무시.
    """
    base = os.getenv("AIRTABLE_BASE_ID", "")
    headers = {
        "Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY", ""),
        "Content-Type": "application/json; charset=utf-8",
    }

    # 1차: 핵심 상태 업데이트 (기존 필드)
    body_core = _json.dumps({
        "fields": {
            "lead_status":   "converted",
            "bridge_status": "converted",
        }
    }, ensure_ascii=False).encode("utf-8")

    try:
        resp = requests.patch(
            f"https://api.airtable.com/v0/{base}/Lead_Interactions/{record_id}",
            headers=headers,
            data=body_core,
            timeout=15,
        )
        if resp.ok:
            logger.info(f"[Order] 전환 처리 완료 | record={record_id} from={sender_igsid}")
        else:
            logger.error(f"[Order] PATCH 실패 | {resp.status_code} {resp.text[:200]}")
    except Exception as exc:
        logger.error(f"[Order] 전환 처리 예외 | {exc}")

    # 2차: converted_at 선택 필드 (Airtable에 Date/time 필드 추가 시 활성화)
    body_opt = _json.dumps({
        "fields": {
            "converted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }, ensure_ascii=False).encode("utf-8")
    try:
        resp2 = requests.patch(
            f"https://api.airtable.com/v0/{base}/Lead_Interactions/{record_id}",
            headers=headers,
            data=body_opt,
            timeout=15,
        )
        if not resp2.ok:
            logger.debug(f"[Order] converted_at 필드 없음(선택 필드) | {resp2.status_code}")
    except Exception:
        pass

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
