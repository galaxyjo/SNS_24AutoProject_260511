# modules/dm/dm_auto_reply.py
# 단가 문의 키워드 감지 → 10% 마진 가격 자동 응답

import os
import json as _json
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MARGIN_RATE = 0.10

PRICE_KEYWORDS = [
    "단가", "가격", "얼마", "비용", "견적", "원가", "도매가", "최저가",
    "price", "cost", "how much", "quote",
]

REPLY_TEMPLATE = (
    "안녕하세요! 문의 감사합니다 😊\n"
    "단가 기준가는 {price:,.0f}원입니다.\n"
    "수량·조건에 따라 협의 가능하오니 편하게 말씀해주세요!"
)


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _at_headers() -> dict:
    return {
        "Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY", ""),
        "Content-Type": "application/json; charset=utf-8",
    }


def _at_patch(table: str, record_id: str, fields: dict) -> None:
    base = os.getenv("AIRTABLE_BASE_ID", "")
    body = _json.dumps({"fields": fields}, ensure_ascii=False).encode("utf-8")
    resp = requests.patch(
        f"https://api.airtable.com/v0/{base}/{table}/{record_id}",
        headers=_at_headers(),
        data=body,
        timeout=15,
    )
    if not resp.ok:
        logger.error(f"[AutoReply] Airtable PATCH 실패 | {resp.status_code} {resp.text[:200]}")


# ── 공개 함수 ─────────────────────────────────────────────────────────────────

def detect_price_inquiry(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in PRICE_KEYWORDS)


def get_base_price() -> float | None:
    """Instagram_Posts 중 price 값이 있는 최신 레코드를 조회한다. 없으면 env 기본값."""
    base = os.getenv("AIRTABLE_BASE_ID", "")
    h = {"Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY", "")}
    try:
        r = requests.get(
            f"https://api.airtable.com/v0/{base}/Instagram_Posts",
            headers=h,
            params={
                "filterByFormula": "{price}>0",
                "sort[0][field]": "scheduled_upload_at",
                "sort[0][direction]": "desc",
                "maxRecords": 1,
            },
            timeout=10,
        )
        records = r.json().get("records", [])
        if records:
            price = records[0]["fields"].get("price")
            if price:
                logger.info(f"[AutoReply] Airtable 기준가 조회 성공 | price={price}")
                return float(price)
    except Exception as exc:
        logger.warning(f"[AutoReply] 가격 조회 실패 | {exc}")

    default = os.getenv("DEFAULT_BASE_PRICE", "")
    if default:
        logger.info(f"[AutoReply] env 기본가 사용 | DEFAULT_BASE_PRICE={default}")
        return float(default)

    return None


def _get_page_token() -> str:
    """User Token으로 Page Access Token을 발급한다 (pages_messaging 권한 사용)."""
    user_token = os.getenv("INSTA_ACCESS_TOKEN", "")
    page_id    = os.getenv("FACEBOOK_PAGE_ID", "")
    r = requests.get(
        "https://graph.facebook.com/v19.0/me/accounts",
        params={"access_token": user_token, "fields": "id,access_token"},
        timeout=10,
    )
    for page in r.json().get("data", []):
        if page.get("id") == page_id:
            return page["access_token"]
    return user_token  # fallback


def send_ig_reply(sender_igsid: str, message: str) -> bool:
    """Page Messages API로 Instagram DM을 전송한다.

    /{ig-user-id}/messages 는 Instagram Messaging 제품 심사 필요.
    /{page-id}/messages + Page Access Token 이 올바른 경로.
    """
    page_id    = os.getenv("FACEBOOK_PAGE_ID", "")
    page_token = _get_page_token()

    body = _json.dumps({
        "recipient":      {"id": sender_igsid},
        "message":        {"text": message},
        "messaging_type": "RESPONSE",
    }, ensure_ascii=False).encode("utf-8")

    headers = {
        "Authorization": "Bearer " + page_token,
        "Content-Type": "application/json; charset=utf-8",
    }

    resp = requests.post(
        f"https://graph.facebook.com/v19.0/{page_id}/messages",
        headers=headers,
        data=body,
        timeout=15,
    )

    if resp.ok:
        msg_id = resp.json().get("message_id", "")
        logger.info(f"[AutoReply] IG DM 발송 완료 | to={sender_igsid} | msg_id={msg_id}")
        return True

    logger.error(f"[AutoReply] IG DM 발송 실패 | {resp.status_code} | {resp.text[:300]}")
    return False


def update_lead_replied(record_id: str, delay_sec: int) -> None:
    _at_patch("Lead_Interactions", record_id, {
        "bridge_status":      "auto_replied",
        "lead_status":        "qualified",
        "replied_at":         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "response_delay_sec": delay_sec,
        "last_error_msg":     "",
    })
    logger.info(f"[AutoReply] Lead 상태 업데이트 | record={record_id} | qualified / auto_replied")


def send_telegram_autoreply(sender_igsid: str, inquiry: str, reply_price: float) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return
    text = (
        f"\U0001f916 *자동 응답 발송 완료*\n"
        f"─────────\n"
        f"\U0001f464 `{sender_igsid}`\n"
        f"\U0001f4ac 문의: {inquiry[:100]}\n"
        f"\U0001f4b0 응답 단가: *{reply_price:,.0f}원* (마진 10% 포함)"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "Markdown"},
            timeout=8,
        )
        logger.info(f"[AutoReply] Telegram 자동응답 알림 전송 | to={sender_igsid}")
    except Exception as exc:
        logger.warning(f"[AutoReply] Telegram 알림 실패 | {exc}")


def handle_price_inquiry(
    record_id: str,
    sender_igsid: str,
    inquiry_text: str,
    received_at: datetime,
) -> None:
    """단가 문의 감지 → 10% 마진 가격으로 자동 응답 → Lead 업데이트 → 팔로업 예약 → Telegram 알림."""
    from modules.dm.dm_followup_scheduler import set_followup_schedule

    base_price = get_base_price()
    if base_price is None:
        logger.warning("[AutoReply] 기준 가격 없음 — 자동 응답 생략")
        return

    reply_price = round(base_price * (1 + MARGIN_RATE))
    reply_msg   = REPLY_TEMPLATE.format(price=reply_price)

    sent = send_ig_reply(sender_igsid, reply_msg)

    delay_sec = int((datetime.now(timezone.utc) - received_at).total_seconds())
    update_lead_replied(record_id, delay_sec)

    # 팔로업 DM 시각 예약 (relay_scheduled_at = now + FOLLOWUP_DELAY_MINUTES)
    try:
        set_followup_schedule(record_id)
    except Exception as exc:
        logger.warning(f"[AutoReply] 팔로업 예약 실패 | {exc}")

    if sent:
        send_telegram_autoreply(sender_igsid, inquiry_text, reply_price)
