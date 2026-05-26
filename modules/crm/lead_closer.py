# modules/crm/lead_closer.py
# 팔로업 완료 → CLOSE 상태 전환 + Telegram 알림

import os
import json as _json
import requests
from datetime import datetime, timezone

from modules.common.logger import get_logger
logger = get_logger(__name__)


def mark_lead_closed(record_id: str) -> None:
    """CLOSE 상태 전환 — bridge_status=closed, lead_status=converted, closed_at 기록.

    closed_at 필드는 선택사항 — Airtable에 없으면 경고 후 무시.
    """
    if not record_id:
        logger.warning("[Closer] record_id 없음 — skip")
        return

    base = os.getenv("AIRTABLE_BASE_ID", "")
    headers = {
        "Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY", ""),
        "Content-Type": "application/json; charset=utf-8",
    }

    # 1차: 핵심 상태 업데이트 (기존 필드)
    body_core = _json.dumps({
        "fields": {
            "bridge_status": "closed",
            "lead_status":   "converted",
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
            logger.info(f"[Closer] CLOSE 처리 완료 | record={record_id}")
        else:
            logger.error(f"[Closer] PATCH 실패 | {resp.status_code} {resp.text[:200]}")
    except Exception as exc:
        logger.error(f"[Closer] PATCH 예외 | {exc}")

    # 2차: closed_at 선택 필드 (Airtable에 DateTime 필드 추가 시 활성화)
    body_opt = _json.dumps({
        "fields": {
            "closed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
            logger.debug(f"[Closer] closed_at 필드 없음(선택 필드) | {resp2.status_code}")
    except Exception:
        pass

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
