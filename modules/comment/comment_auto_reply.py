# modules/comment/comment_auto_reply.py
# 댓글 키워드 감지 → 자동 답글 + Airtable 기록 + Telegram 알림

import os
import json as _json
import logging
import requests
from datetime import datetime, timezone

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import LeadInteractionCreate

logger = logging.getLogger(__name__)

_repo = AirtableRepository()

_AUTO_REPLY_ENABLED = os.getenv("COMMENT_AUTO_REPLY_ENABLED", "false").lower() == "true"

# ── 키워드 ─────────────────────────────────────────────────────────────────────

PRICE_KEYWORDS = [
    "단가", "가격", "얼마", "비용", "견적", "원가", "도매가", "최저가",
    "price", "cost", "how much", "quote",
]

NEGATIVE_KEYWORDS = [
    "사기", "불만", "환불", "별로", "최악", "구매하지마", "사지마",
    "스팸", "신고", "짝퉁", "가짜", "허위", "불량",
]

# 단가 댓글 → DM 유도 답글 (공개 댓글이므로 가격 직접 노출 지양)
PRICE_REPLY = (
    "안녕하세요 \U0001f60a 단가 및 상세 조건은 DM으로 문의해 주시면 "
    "빠르게 안내드리겠습니다 \U0001f4e9"
)


# ── 감지 함수 ─────────────────────────────────────────────────────────────────

def detect_price_comment(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in PRICE_KEYWORDS)


def detect_negative_comment(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in NEGATIVE_KEYWORDS)


# ── Graph API: 댓글 답글 ──────────────────────────────────────────────────────

def _get_page_token() -> str:
    user_token = os.getenv("INSTA_ACCESS_TOKEN", "")
    page_id    = os.getenv("FACEBOOK_PAGE_ID", "")
    try:
        r = requests.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"access_token": user_token, "fields": "id,access_token"},
            timeout=10,
        )
        for page in r.json().get("data", []):
            if page.get("id") == page_id:
                return page["access_token"]
    except Exception as exc:
        logger.warning(f"[Comment] Page token 조회 실패 | {exc}")
    return user_token


def reply_to_comment(comment_id: str, message: str) -> bool:
    """Instagram 댓글에 답글을 단다. POST /{comment-id}/replies"""
    token = _get_page_token()
    body  = _json.dumps({"message": message}, ensure_ascii=False).encode("utf-8")
    try:
        resp = requests.post(
            f"https://graph.facebook.com/v19.0/{comment_id}/replies",
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json; charset=utf-8",
            },
            data=body,
            timeout=15,
        )
        if resp.ok:
            logger.info(f"[Comment] 답글 발송 완료 | comment_id={comment_id}")
            return True
        logger.error(f"[Comment] 답글 발송 실패 | {resp.status_code} {resp.text[:200]}")
    except Exception as exc:
        logger.error(f"[Comment] 답글 예외 | {exc}")
    return False


# ── Airtable 기록 (Lead_Interactions, channel=instagram_comment) ───────────────

def _record_comment(username: str, text: str, comment_id: str, media_id: str) -> None:
    try:
        _repo.create_lead_interaction(LeadInteractionCreate(
            igsid=username,
            source="instagram_comment",
            interaction_type="comment_received",
            occurred_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            inquiry_message=text,
        ))
        logger.info(f"[Comment] Airtable 기록 완료 | from={username}")
    except Exception as exc:
        logger.warning(f"[Comment] Airtable 기록 예외 | {exc}")


# ── Telegram 알림 ─────────────────────────────────────────────────────────────

def _send_telegram_comment(username: str, text: str, tag: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return

    icons = {"price": "\U0001f4b0", "negative": "\U0001f6a8", "new": "\U0001f4ac"}
    labels = {"price": "단가 문의 댓글", "negative": "부정 댓글 감지!", "new": "신규 댓글"}
    icon   = icons.get(tag, "\U0001f4ac")
    label  = labels.get(tag, "신규 댓글")

    msg = (
        f"{icon} *{label}*\n"
        f"─────────────────\n"
        f"\U0001f464 @{username}\n"
        f"\U0001f4ac {text[:200]}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg, "parse_mode": "Markdown"},
            timeout=8,
        )
    except Exception as exc:
        logger.warning(f"[Comment] Telegram 알림 실패 | {exc}")


# ── 메인 처리 ─────────────────────────────────────────────────────────────────

def handle_comment(
    comment_id: str,
    username: str,
    text: str,
    media_id: str,
) -> None:
    """신규 댓글 1건 처리 — 키워드 감지 → 답글/알림 → Airtable 기록."""
    logger.info(f"[Comment] 처리 | comment={comment_id} | from=@{username} | text={text[:80]}")

    if detect_negative_comment(text):
        _send_telegram_comment(username, text, "negative")
        _record_comment(username, text, comment_id, media_id)
        return

    if detect_price_comment(text):
        if _AUTO_REPLY_ENABLED:
            reply_to_comment(comment_id, PRICE_REPLY)
        _send_telegram_comment(username, text, "price")
    else:
        _send_telegram_comment(username, text, "new")

    _record_comment(username, text, comment_id, media_id)
