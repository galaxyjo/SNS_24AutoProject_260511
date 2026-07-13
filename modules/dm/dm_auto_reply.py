# modules/dm/dm_auto_reply.py
# 단가 문의 키워드 감지 → 10% 마진 가격 자동 응답

import os
import re
import json as _json
import logging
import threading
import requests
from datetime import datetime, timezone

from modules.common.logger import get_logger
from modules.infra.airtable_repository import AirtableRepository

logger = get_logger(__name__)

_repo = AirtableRepository()

MARGIN_RATE = 0.10

# Gate C — Price Safety Interlock (docs/design/DM_RELAY_COMMERCE_RFC.md §17)
# Post/Product 매핑(P1-B) 전까지는 상품을 특정할 수 없으므로 기본값 false.
PRICE_AUTO_REPLY_ENABLED = os.getenv("PRICE_AUTO_REPLY_ENABLED", "false").lower() == "true"

PRICE_KEYWORDS = [
    "단가", "가격", "얼마", "비용", "견적", "원가", "도매가", "최저가",
    "price", "cost", "how much", "quote",
]

REPLY_TEMPLATE = (
    "안녕하세요! 문의 감사합니다 😊\n"
    "단가 기준가는 {price:,.0f}원입니다.\n"
    "수량·조건에 따라 협의 가능하오니 편하게 말씀해주세요!"
)

# PRICE_AUTO_REPLY_ENABLED=false일 때 가격 대신 발송하는 접수·상품확인 요청
PRODUCT_CONFIRM_TEMPLATE = (
    "안녕하세요! 문의 감사합니다 😊\n"
    "정확한 단가 안내를 위해 문의하신 상품의 게시물 링크나 번호, "
    "또는 스크린샷을 보내주시면 확인 후 빠르게 안내드리겠습니다!"
)


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

# Telegram PII 마스킹 (RFC §10 — 전화번호/이메일 등 패턴 제거 후 20자 미리보기)
_PII_PATTERNS = [
    re.compile(r'01[0-9]-?\d{3,4}-?\d{4}'),
    re.compile(r'\d{2,4}-\d{3,4}-\d{4}'),
    re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
]


def _mask_igsid(igsid: str) -> str:
    return f"{igsid[:4]}***" if igsid and len(igsid) > 4 else "***"


def _telegram_preview(text: str, limit: int = 20) -> str:
    masked = text or ""
    for pat in _PII_PATTERNS:
        masked = pat.sub("***", masked)
    return masked[:limit]


def _has_recent_auto_replied(sender_igsid: str, minutes: int = 3) -> bool:
    """sender_igsid 기준 최근 N분 이내 auto_replied 레코드 존재 여부 확인."""
    try:
        return _repo.has_recent_auto_reply(sender_igsid, within_minutes=minutes)
    except Exception as exc:
        logger.warning(f"[AutoReply] 중복 체크 실패 — 발송 허용 | {exc}")
        return False


# Gate C 상품확인 대기 경로 전용 임시 중복방지 (Airtable 스키마 변경 없음)
# bridge_status를 auto_replied로 바꾸지 않으므로 _has_recent_auto_replied가 이 경로를
# 못 잡는다 — 웹훅 재전송으로 같은 문의가 중복 발송되는 것만 막고, 같은 buyer의 다른
# 상품 문의(=매출 문의)까지 막으면 안 되므로 키를 (sender, 정규화된 문의문)으로 잡는다.
# 발송 전에 먼저 선점해서 동시 진입 시 이중발송을 막고, 발송 실패 시 선점을 해제해서
# 정당한 재시도까지 막지 않는다. 재시작 시 초기화됨(근본 해결은 P0-1 Durable Inbox).
_AWAITING_PRODUCT_DEDUP: dict[tuple, datetime] = {}
_AWAITING_PRODUCT_DEDUP_MINUTES = 3
_AWAITING_PRODUCT_DEDUP_LOCK = threading.Lock()


def _awaiting_product_key(sender_igsid: str, inquiry_text: str) -> tuple:
    return (sender_igsid, (inquiry_text or "").strip().lower())


def _try_reserve_awaiting_product_slot(sender_igsid: str, inquiry_text: str) -> bool:
    """True=선점 성공(발송 진행), False=3분 내 동일 문의 중복이라 skip.
    조회·선점·정리를 Lock으로 묶어 동시 요청이 둘 다 통과하는 것을 막는다."""
    key = _awaiting_product_key(sender_igsid, inquiry_text)
    now = datetime.now(timezone.utc)
    with _AWAITING_PRODUCT_DEDUP_LOCK:
        last = _AWAITING_PRODUCT_DEDUP.get(key)
        if last is not None and (now - last).total_seconds() < _AWAITING_PRODUCT_DEDUP_MINUTES * 60:
            return False
        _AWAITING_PRODUCT_DEDUP[key] = now
        if len(_AWAITING_PRODUCT_DEDUP) > 5000:
            cutoff = now
            stale = [k for k, v in _AWAITING_PRODUCT_DEDUP.items() if (cutoff - v).total_seconds() > 3600]
            for k in stale:
                del _AWAITING_PRODUCT_DEDUP[k]
        return True


def _release_awaiting_product_slot(sender_igsid: str, inquiry_text: str) -> None:
    """발송 실패/예외 시 선점 해제 — 재시도가 중복으로 취급되어 막히지 않도록."""
    key = _awaiting_product_key(sender_igsid, inquiry_text)
    with _AWAITING_PRODUCT_DEDUP_LOCK:
        _AWAITING_PRODUCT_DEDUP.pop(key, None)


# ── 공개 함수 ─────────────────────────────────────────────────────────────────

def detect_price_inquiry(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in PRICE_KEYWORDS)


def get_base_price() -> float | None:
    """Instagram_Posts 중 price>0 최신값. 없으면 DEFAULT_BASE_PRICE env 폴백."""
    try:
        price = _repo.get_base_price()
        if price is not None:
            logger.info(f"[AutoReply] Airtable 기준가 조회 성공 | price={price}")
            return price
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
    _repo.update_lead_replied(record_id, delay_sec)
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


def send_telegram_price_pending(sender_igsid: str, inquiry: str) -> None:
    """PRICE_AUTO_REPLY_ENABLED=false 상태에서 가격문의 접수 시 운영자 수동안내 필요 알림."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return
    text = (
        f"\U0001f4b0 *가격 문의 접수 (상품확인 대기)*\n"
        f"─────────\n"
        f"\U0001f464 `{_mask_igsid(sender_igsid)}`\n"
        f"\U0001f4ac 문의: {_telegram_preview(inquiry)}\n"
        f"⚠️ 자동가격 응답 비활성 — 상품 확인 후 수동으로 원가+10% 안내 필요"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "Markdown"},
            timeout=8,
        )
        logger.info(f"[AutoReply] Telegram 상품확인대기 알림 전송 | to={_mask_igsid(sender_igsid)}")
    except Exception as exc:
        logger.warning(f"[AutoReply] Telegram 알림 실패 | {exc}")


def _retry_send_ig_reply(payload: dict) -> None:
    """retry_queue 핸들러 — IG DM 재전송."""
    if not send_ig_reply(payload["sender_igsid"], payload["message"]):
        raise RuntimeError("IG DM send failed")


def handle_price_inquiry(
    record_id: str,
    sender_igsid: str,
    inquiry_text: str,
    received_at: datetime,
) -> None:
    """단가 문의 감지 → 10% 마진 가격으로 자동 응답 → Lead 업데이트 → 팔로업 예약 → Telegram 알림."""
    if _has_recent_auto_replied(sender_igsid, minutes=3):
        logger.info(f"[AutoReply] duplicate skip | record={record_id} sender={sender_igsid} status=auto_replied")
        return
    from modules.dm.rules import evaluate as _rule_evaluate
    _rule = _rule_evaluate(inquiry_text)
    if not _rule:
        reason = getattr(_rule, "reason", "unknown")
        logger.info(f"[AutoReply] 메시지 필터 차단 | reason={reason} | sender={sender_igsid}")
        return

    from modules.dm.dm_followup_scheduler import set_followup_schedule
    from modules.common.retry_queue import get_retry_queue

    reply_price = None
    if not PRICE_AUTO_REPLY_ENABLED:
        # Gate C: 상품(Post/Product) 매핑 전까지 가격 숫자는 절대 자동발송하지 않는다.
        # Buyer 응답 자체는 유지 — 접수 확인 + 상품확인 요청으로 대체.
        # bridge_status가 auto_replied로 안 바뀌어 _has_recent_auto_replied가 이 경로를
        # 못 잡으므로, (sender, 문의문) 단위로 발송 전에 먼저 선점해 웹훅재전송/동시진입
        # 중복발송을 막는다 — 같은 buyer의 다른 상품 문의는 키가 달라 차단되지 않는다.
        if not _try_reserve_awaiting_product_slot(sender_igsid, inquiry_text):
            logger.info(f"[AutoReply] 상품확인 요청 중복 skip(3분 이내, 동일 문의) | sender={_mask_igsid(sender_igsid)}")
            return
        reply_msg = PRODUCT_CONFIRM_TEMPLATE
        logger.info(f"[AutoReply] PRICE_AUTO_REPLY_ENABLED=false — 상품확인 요청으로 대체 | sender={_mask_igsid(sender_igsid)}")
    else:
        base_price = get_base_price()
        if base_price is None:
            logger.warning("[AutoReply] 기준 가격 없음 — 자동 응답 생략")
            return

        reply_price = round(base_price * (1 + MARGIN_RATE))
        try:
            from modules.dm.ai_reply_generator import generate_reply
            reply_msg = generate_reply(inquiry_text, base_price, MARGIN_RATE)
            logger.info("[AutoReply] AI 응답 생성 사용")
        except Exception as exc:
            logger.warning(f"[AutoReply] AI 응답 실패 — 템플릿 폴백 | {exc}")
            reply_msg = REPLY_TEMPLATE.format(price=reply_price)

    try:
        sent = send_ig_reply(sender_igsid, reply_msg)
    except Exception:
        # send_ig_reply가 False가 아니라 예외(네트워크 오류 등)를 던지는 경우에도
        # 선점을 남겨두면 3분간 정당한 재시도까지 "중복"으로 막힌다. 최소한 해제 후
        # 그대로 재발생시켜 상위(dm_receiver.py)의 기존 예외 처리로 넘긴다.
        if reply_price is None:
            _release_awaiting_product_slot(sender_igsid, inquiry_text)
        raise

    if not sent:
        if reply_price is None:
            # 선점은 이미 걸어뒀는데 실제 발송은 실패했으므로 해제 — 정당한 재시도가
            # "3분 내 중복"으로 오인되어 막히지 않도록 한다.
            _release_awaiting_product_slot(sender_igsid, inquiry_text)
        rq = get_retry_queue()
        rq.register("ig_auto_reply", _retry_send_ig_reply)
        rq.start()
        rq.enqueue("ig_auto_reply", {"sender_igsid": sender_igsid, "message": reply_msg})
        logger.warning(f"[AutoReply] DM 발송 실패 → retry queue 등록 | to={sender_igsid}")
        # 실제 발송이 안 됐으므로 "답변완료" 상태전환·팔로업예약·알림 전부 생략한다.
        # (재시도 성공 시 상태를 소급 반영하는 로직은 P0-1/Gate F의 Outbox·재조정 설계 범위)
        return

    delay_sec = int((datetime.now(timezone.utc) - received_at).total_seconds())

    if reply_price is not None:
        # 가격을 실제로 안내한 경우에만 qualified/auto_replied 전환 + 팔로업 예약
        update_lead_replied(record_id, delay_sec)
        try:
            set_followup_schedule(record_id)
        except Exception as exc:
            logger.warning(f"[AutoReply] 팔로업 예약 실패 | {exc}")
        send_telegram_autoreply(sender_igsid, inquiry_text, reply_price)
    else:
        # Gate C: 상품확인 요청만 보낸 상태 — bridge_status를 auto_replied로 바꾸지 않고
        # 팔로업도 예약하지 않는다(상품도 모르는데 "지난번 단가 문의" 팔로업이 나가는 것을 방지).
        # 중복방지 선점은 위 진입 시점에 이미 기록됐으므로 여기서 추가로 할 일 없음.
        logger.info(f"[AutoReply] 상품확인 대기 — bridge_status 미변경, 팔로업 예약 안 함 | sender={_mask_igsid(sender_igsid)}")
        send_telegram_price_pending(sender_igsid, inquiry_text)
