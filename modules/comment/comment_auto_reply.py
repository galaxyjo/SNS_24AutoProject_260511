# modules/comment/comment_auto_reply.py
# 댓글 키워드 감지 → 자동 답글 + Airtable 기록 + Telegram 알림

import os
import json as _json
import logging
import random
import requests
from datetime import datetime, timezone

from modules.comment import comment_safety_guard as guard
from modules.common.meta_graph import messaging_graph_url
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

# 단가 댓글 → Private Reply 문구 (가격 직접 노출 지양)
# 이 메시지 자체가 이미 DM이므로 "DM으로 문의해주세요"는 말이 안 됨(Codex 리뷰 260714 발견·정정) —
# Meta 공식 사양상 발송만으로는 24시간 창이 안 열리고 손님이 "답장"해야 열리므로, 문구는 답장을 유도해야 함.
# 동일 문구 반복·옵트아웃 미포함 시 스팸탐지에 걸릴 수 있다는 건 Meta 1차 공식 문서로 직접 확인한 사실은 아니고
# 제3자 블로그(ManyChat 등) 종합 업계 권장사항임 — "메타 필수 규정"으로 과신하지 말 것(Codex 리뷰 260714 반영).
# 그래도 문구 다양화 + 개인화 + 옵트아웃 자체는 UX상 해롭지 않아 반영.
PRICE_REPLY_TEMPLATES = [
    "안녕하세요 \U0001f60a 답장 주시면 단가를 바로 안내드릴게요! (원치 않으시면 답장 안 하셔도 괜찮아요)",
    "문의 감사합니다 \U0001f64c 이 메시지에 답장해 주시면 자세한 단가·조건을 안내드릴게요! (원하지 않으시면 그냥 넘어가셔도 됩니다)",
    "답장 한 번만 주시면 바로 단가 상담 도와드릴게요 \U0001f60a (언제든 대화 중단하셔도 무방합니다)",
    "문의주셔서 감사해요 \U0001f4ae 답장 주시면 정확한 단가를 편하게 안내해드릴게요! (원치 않으시면 무시하셔도 됩니다)",
]


def _build_price_reply(username: str) -> str:
    """문구 다양화 + 개인화 + 옵트아웃 안내가 포함된 Private Reply 메시지를 무작위로 하나 생성."""
    greeting = f"@{username}님, " if username else ""
    return greeting + random.choice(PRICE_REPLY_TEMPLATES)


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
            messaging_graph_url("me/accounts"),
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
            messaging_graph_url(f"{comment_id}/replies"),
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


def reply_privately_to_comment(comment_id: str, message: str) -> bool:
    """댓글에 비공개로 답장한다(Private Reply).
    이 프로젝트가 쓰는 제품 라인은 "Messenger Platform for Instagram"(Facebook Login) — 그 계약은
    POST /{page-id}/messages, body={"recipient": {"comment_id": ...}, "message": {"text": ...}}
    (developers.facebook.com/docs/messenger-platform/instagram/features/private-replies/, 260714 3차 확인).
    "Instagram API with Instagram Login" 제품의 /{ig-user-id}/messages 계약과는 다르므로 혼동 주의
    — 처음엔 /{comment-id}/private_replies(다른 구 엔드포인트)로 잘못 구현했다가 Codex 리뷰로 정정,
    이후 Codex가 ig-user-id로 재차 지적했으나 이 문서로 page-id가 맞음을 재확인(Codex 3차 리뷰 대응).
    발송 자체로는 24시간 상담창이 열리지 않는다 — 손님이 이 메시지에 답장해야 창이 열린다(Meta 공식 사양).
    이 함수 호출은 반드시 comment_safety_guard.REPLY_LOCK 안에서 이뤄져야 함(웹훅 스레드/폴러 스레드 동시성 방지)."""
    page_id = os.getenv("FACEBOOK_PAGE_ID", "")
    token = _get_page_token()
    body  = _json.dumps({
        "recipient": {"comment_id": comment_id},
        "message":   {"text": message},
    }, ensure_ascii=False).encode("utf-8")
    try:
        resp = requests.post(
            messaging_graph_url(f"{page_id}/messages"),
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json; charset=utf-8",
            },
            data=body,
            timeout=15,
        )
        if resp.ok:
            msg_id = resp.json().get("message_id", "")
            logger.info(f"[Comment] Private Reply 발송 완료 | comment_id={comment_id} | msg_id={msg_id}")
            return True
        logger.error(f"[Comment] Private Reply 발송 실패 | {resp.status_code} {resp.text[:200]}")
    except Exception as exc:
        logger.error(f"[Comment] Private Reply 예외 | {exc}")
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


# ── Private Reply 안전 게이트 ────────────────────────────────────────────────

def _try_private_reply(comment_id: str, username: str, media_id: str, cooldown_key: str) -> None:
    """캠페인 게시물·쿨다운·일일예산·circuit breaker를 모두 통과해야 Private Reply 발송.
    cooldown_key: 가능하면 IG scoped ID(from.id) — username은 사용자가 바꾸면 쿨다운이 우회됨.

    댓글 웹훅(Flask 요청 스레드)과 comment_poller(APScheduler 스레드)가 같은 프로세스에서 동시에
    이 함수를 호출할 수 있어(TOCTOU), 체크→발송→소비 전체를 guard.REPLY_LOCK으로 직렬화한다.
    발송(네트워크 호출, 최대 15초)까지 락 안에 포함되므로 처리량은 낮지만(초당 요청이 아니라
    일일 예산 30건 수준의 트래픽이라 문제 없음), 예산·쿨다운 상태의 정확성을 우선한다."""
    with guard.REPLY_LOCK:
        if not guard.is_campaign_post(media_id):
            logger.info(f"[Comment] 캠페인 게시물 아님 — Private Reply 스킵 | media={media_id}")
            return
        if guard.circuit_is_open():
            logger.warning("[Comment] circuit breaker open — Private Reply 스킵")
            return
        if guard.is_user_in_cooldown(cooldown_key):
            logger.info(f"[Comment] 쿨다운 중 — Private Reply 스킵 | user={username}")
            return
        if not guard.consume_daily_budget():
            logger.warning("[Comment] 일일 예산 소진 — Private Reply 스킵")
            return

        if reply_privately_to_comment(comment_id, _build_price_reply(username)):
            guard.mark_user_replied(cooldown_key)
            guard.record_circuit_success()
        else:
            guard.record_circuit_failure()


# ── 메인 처리 ─────────────────────────────────────────────────────────────────

def handle_comment(
    comment_id: str,
    username: str,
    text: str,
    media_id: str,
    commenter_id: str = "",
) -> None:
    """신규 댓글 1건 처리 — 키워드 감지 → 답글/알림 → Airtable 기록.
    commenter_id: IG scoped ID(from.id). 미제공 시 username으로 폴백(comment_poller가 항상 채워줌)."""
    logger.info(f"[Comment] 처리 | comment={comment_id} | from=@{username} | text={text[:80]}")
    cooldown_key = commenter_id or username

    if detect_negative_comment(text):
        _send_telegram_comment(username, text, "negative")
        _record_comment(username, text, comment_id, media_id)
        return

    if detect_price_comment(text):
        if _AUTO_REPLY_ENABLED:
            _try_private_reply(comment_id, username, media_id, cooldown_key)
        _send_telegram_comment(username, text, "price")
    else:
        _send_telegram_comment(username, text, "new")

    _record_comment(username, text, comment_id, media_id)
