"""
services/telegram_notifier.py — Telegram Bot 운영 알림 (261106, 회장 확정: 운영 알림은 무조건 Telegram)

환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (미설정이면 get_notify_fn() 이 None → 알림 생략)

Telegram 응답의 ok=true 일 때만 성공으로 본다(HTTP 200 만으로 판단하지 않음).
토큰이 들어 있는 URL·예외 문구는 기록하지 않는다(상태코드·예외 클래스명만).
"""

import os
from typing import Callable, Optional

import requests

from modules.common.logger import get_logger

logger = get_logger(__name__)


def send_message(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        logger.warning("[Telegram] TELEGRAM_BOT_TOKEN/CHAT_ID 미설정 — 알림 생략")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": str(text)[:3500]},
            timeout=8,
        )
        ok = False
        try:
            ok = resp.status_code == 200 and resp.json().get("ok") is True
        except ValueError:
            ok = False
        if not ok:
            logger.warning("[Telegram] 발송 실패 | status_code=%s", resp.status_code)
            return False
        logger.info("[Telegram] 발송 성공 | status_code=%s", resp.status_code)
        return True
    except Exception as exc:  # noqa: BLE001 — 예외 문구에 토큰 URL 이 섞일 수 있어 클래스명만 남긴다
        logger.warning("[Telegram] 발송 예외 | exception_type=%s", type(exc).__name__)
        return False


def get_notify_fn() -> Optional[Callable[[str], bool]]:
    """notify(single_string) -> bool. 설정이 없으면 None."""
    if not (os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")):
        return None
    return send_message
