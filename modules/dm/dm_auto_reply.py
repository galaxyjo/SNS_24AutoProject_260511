# modules/dm/dm_auto_reply.py
# 단가 문의 키워드 감지 → 10% 마진 가격 자동 응답

import os
import json as _json
import logging
import threading
import requests
from datetime import datetime, timezone

from modules.common.logger import get_logger
from modules.common.meta_graph import messaging_graph_url, instagram_login_graph_url
from modules.infra.airtable_repository import AirtableRepository

logger = get_logger(__name__)

_repo = AirtableRepository()

MARGIN_RATE = 0.10

# 260730 DM Routing Close Gate — 전역 FACEBOOK_PAGE_ID/INSTA_ACCESS_TOKEN이 실제로
# 가리키는 계정(회장 승인 정책). 계정 해석 실패 시 이 계정만 결과가 동일하므로
# 전역 fallback을 유지하고, 그 외 계정은 fallback 시도 없이 retry_queue로 보낸다.
GLOBAL_FALLBACK_ACCOUNT_CODE_REF = os.getenv("GLOBAL_FALLBACK_ACCOUNT_CODE_REF", "IDN-000041")

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

# 261029 STEP 2 — reply_mode=template_en 계정(영어 B2B, 예: 051) 전용 영어 템플릿
# (키워드로 응답 대상을 정하지 않는다 — 계정 reply_mode가 응답 여부·언어를 결정)
PRODUCT_CONFIRM_TEMPLATE_EN = (
    "Hi, thanks for your wholesale inquiry! 😊\n"
    "To give you accurate pricing, please send us the product link, name or a screenshot, "
    "plus the quantity you need and your destination country. We'll get back to you shortly."
)

# PRICE_AUTO_REPLY_ENABLED=false일 때 가격 대신 발송하는 접수·상품확인 요청
PRODUCT_CONFIRM_TEMPLATE = (
    "안녕하세요! 문의 감사합니다 😊\n"
    "정확한 단가 안내를 위해 문의하신 상품의 게시물 링크나 번호, "
    "또는 스크린샷을 보내주시면 확인 후 빠르게 안내드리겠습니다!"
)


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

# Telegram PII 마스킹 (RFC §10 — 전화번호/이메일 등 패턴 제거 후 20자 미리보기)
# 260716: 댓글 채널(comment_auto_reply.py)도 재사용하게 되면서 modules.common.pii_mask로
# 실제 구현을 옮기고, 여기서는 기존 호출부(dm_receiver.py 등) 호환을 위해 별칭만 유지.
from modules.common.pii_mask import mask_igsid as _mask_igsid, telegram_preview as _telegram_preview


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


# 260730 — persona 경로(reply_mode=persona) 전용 중복방지. generate_reply()(Gemini)
# 호출이 수십 초 걸릴 수 있어, 그 사이 같은 발신자가 보낸 후속 문의가
# _has_recent_auto_replied()(Airtable 쿼리 — 아직 첫 응답의 auto_replied 반영 전)를
# 통과해 실제 가격 안내가 중복 발송되는 것을 실측으로 확인(10.6-4D)하고 추가했다.
# 상품확인 템플릿 경로(_AWAITING_PRODUCT_DEDUP)와 달리 문의문이 달라도 같은 발신자면
# 중복으로 본다 — 실제 가격을 안내하는 경로라 더 보수적으로 막는다.
_PERSONA_REPLY_DEDUP: dict[str, datetime] = {}
_PERSONA_REPLY_DEDUP_MINUTES = 3
_PERSONA_REPLY_DEDUP_LOCK = threading.Lock()


def _try_reserve_persona_reply_slot(sender_igsid: str) -> bool:
    """True=선점 성공(발송 진행), False=3분 내 동일 발신자 처리 중/완료라 skip."""
    now = datetime.now(timezone.utc)
    with _PERSONA_REPLY_DEDUP_LOCK:
        last = _PERSONA_REPLY_DEDUP.get(sender_igsid)
        if last is not None and (now - last).total_seconds() < _PERSONA_REPLY_DEDUP_MINUTES * 60:
            return False
        _PERSONA_REPLY_DEDUP[sender_igsid] = now
        if len(_PERSONA_REPLY_DEDUP) > 5000:
            stale = [k for k, v in _PERSONA_REPLY_DEDUP.items() if (now - v).total_seconds() > 3600]
            for k in stale:
                del _PERSONA_REPLY_DEDUP[k]
        return True


def _release_persona_reply_slot(sender_igsid: str) -> None:
    """발송 실패/예외/가격조회 실패 시 선점 해제 — 정당한 재시도까지 막지 않도록."""
    with _PERSONA_REPLY_DEDUP_LOCK:
        _PERSONA_REPLY_DEDUP.pop(sender_igsid, None)


# 261029 STEP 2 SLA 정정(회장 확정: 수신 DM 60초 이내 응답, 정상 메시지에 60분 대기 금지) —
# template_en 전용 계정+발신자 단위 burst guard: 같은 바이어의 연속 메시지가 BURST_SECONDS 안이면 1회만
# 응답한다. 같은 mid의 중복은 영속 저장소가 따로 막는다. 전달 여부가 불명(UNKNOWN)인 바이어는 별도로
# UNKNOWN_HOLD_MINUTES 동안 자동응답을 멈춘다(정책: 불확실하면 중복 자동 발송 금지, 즉시 알림).
# 메모리 기반이라 재시작 시 초기화된다(영속 중복 방지는 P0-1 Durable Inbox 범위).
_TEMPLATE_EN_BURST_SECONDS = int(os.getenv("TEMPLATE_EN_BURST_SECONDS", "60"))
_TEMPLATE_EN_UNKNOWN_HOLD_MINUTES = 60
_TEMPLATE_EN_DEDUP: dict[tuple, datetime] = {}
_TEMPLATE_EN_HOLD: dict[tuple, datetime] = {}
_TEMPLATE_EN_DEDUP_LOCK = threading.Lock()


def _try_reserve_template_en_slot(account_code_ref: str, sender_igsid: str) -> bool:
    """True=선점 성공(발송 진행), False=UNKNOWN hold 또는 burst 이내라 skip."""
    key = (account_code_ref, sender_igsid)
    now = datetime.now(timezone.utc)
    with _TEMPLATE_EN_DEDUP_LOCK:
        held = _TEMPLATE_EN_HOLD.get(key)
        if held is not None:
            if (now - held).total_seconds() < _TEMPLATE_EN_UNKNOWN_HOLD_MINUTES * 60:
                return False
            del _TEMPLATE_EN_HOLD[key]
        last = _TEMPLATE_EN_DEDUP.get(key)
        if last is not None and (now - last).total_seconds() < _TEMPLATE_EN_BURST_SECONDS:
            return False
        _TEMPLATE_EN_DEDUP[key] = now
        if len(_TEMPLATE_EN_DEDUP) > 5000:
            stale = [k for k, v in _TEMPLATE_EN_DEDUP.items()
                     if (now - v).total_seconds() > max(_TEMPLATE_EN_BURST_SECONDS, 1) * 2]
            for k in stale:
                del _TEMPLATE_EN_DEDUP[k]
        return True


def _release_template_en_slot(account_code_ref: str, sender_igsid: str) -> None:
    """발송 실패/예외 시 선점 해제 — 정당한 재시도까지 막지 않도록."""
    with _TEMPLATE_EN_DEDUP_LOCK:
        _TEMPLATE_EN_DEDUP.pop((account_code_ref, sender_igsid), None)


def _hold_template_en_after_unknown(account_code_ref: str, sender_igsid: str) -> None:
    """전달 여부 불명(UNKNOWN) — 같은 계정+발신자의 자동응답을 UNKNOWN_HOLD_MINUTES 동안 멈춘다."""
    with _TEMPLATE_EN_DEDUP_LOCK:
        _TEMPLATE_EN_HOLD[(account_code_ref, sender_igsid)] = datetime.now(timezone.utc)


# ── 261029 SLA·장애 알림 단일 경로 ───────────────────────────────────────────────
# 수신 DM은 DM_REPLY_SLA_SECONDS(기본 60초) 안에 응답한다. 알림은 기존 services/slack_notifier.send_alert로
# 통일하고, 전달에 실패하면 ERROR 로그(error.log→헬스 모니터에 노출)와 기존 Telegram 경로로 대체 통지한다.
# 알림에는 계정코드·mid 앞 6자·유형·시간·수동 확인 여부만 담는다(발신자 ID·메시지 원문·예외 문구 금지).
DM_REPLY_SLA_SECONDS = int(os.getenv("DM_REPLY_SLA_SECONDS", "60"))
_ALERT_THROTTLE_SECONDS = 60
_ALERT_LAST: dict[tuple, datetime] = {}
_ALERT_LOCK = threading.Lock()


def _telegram_alert(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text},
            timeout=8,
        )
        return bool(getattr(r, "ok", False))
    except Exception as exc:
        logger.warning(f"[AutoReply] Telegram 대체 알림 실패 | exception_type={type(exc).__name__}")
        return False


def _alert_dm(kind: str, source: str, mid: str, detail: str, manual: bool = True,
              level: str = "error", throttle: bool = False) -> bool:
    """DM 장애/SLA 알림. 반환: Slack 또는 Telegram 대체 경로로 전달되었는가."""
    account = source.split(":", 1)[1] if ":" in source else (source or "UNRESOLVED")
    if throttle:
        now = datetime.now(timezone.utc)
        with _ALERT_LOCK:
            last = _ALERT_LAST.get((kind, account))
            if last is not None and (now - last).total_seconds() < _ALERT_THROTTLE_SECONDS:
                return True
            _ALERT_LAST[(kind, account)] = now
    mid_part = f"{str(mid)[:6]}***" if mid else "none"
    title = f"[DM] {kind}"
    body = (f"account={account} | event={mid_part} | type={kind} | {detail} | "
            f"수동 확인 {'필요' if manual else '불필요'}")
    ok = False
    try:
        from services.slack_notifier import send_alert
        ok = bool(send_alert(title, body, level))
    except Exception as exc:
        logger.warning(f"[AutoReply] Slack 알림 예외 | exception_type={type(exc).__name__}")
    if ok:
        return True
    logger.error(f"[AutoReply] DM_ALERT_DELIVERY_FAILED — Slack 알림 전달 실패, Telegram 대체 | type={kind} | account={account}")
    return _telegram_alert(f"{title}\n{body}")


def _check_reply_sla(received_at, dm_event, via: str) -> None:
    """발송 성공 직후 호출: Webhook 수신(received_at) → 발송 성공까지 소요 시간을 기록하고,
    SLA를 넘으면(영속 이벤트가 있는 경로에서만) 알림을 보낸다."""
    try:
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=timezone.utc)
        latency = (datetime.now(timezone.utc) - received_at).total_seconds()
    except Exception:
        return
    logger.info(f"[DM_SLA] latency_sec={latency:.1f} via={via}")
    if dm_event and latency > DM_REPLY_SLA_SECONDS:
        _alert_dm("SLA 초과", dm_event[0], dm_event[1],
                  f"응답 지연 {int(latency)}초(기준 {DM_REPLY_SLA_SECONDS}초, {via})", manual=False, level="warning")


# ── 공개 함수 ─────────────────────────────────────────────────────────────────

def detect_price_inquiry(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in PRICE_KEYWORDS)


def _get_persona_kwargs(account_code_ref: str) -> dict:
    """260730 10.5-5단계(Persona 연결) — account_code_ref로 연결된 Persona_Profile을
    조회해 generate_reply()에 넘길 tone_style/greeting_template/followup_template을
    구한다. account_code_ref가 없거나 연결된(active) Persona가 없거나 조회 실패 시
    전부 빈 문자열(기존 동작 100% 동일, Fail-open)."""
    empty = {"tone_style": "", "greeting_template": "", "followup_template": ""}
    if not account_code_ref:
        return empty
    try:
        persona = _repo.get_persona_by_account_code(account_code_ref)
    except Exception as exc:
        logger.warning(f"[AutoReply] Persona 조회 실패 — 기본 프롬프트 사용 | account_code_ref={account_code_ref} | {exc}")
        return empty
    if persona is None:
        return empty
    return {
        "tone_style": persona.get("tone_style", ""),
        "greeting_template": persona.get("greeting_template", ""),
        "followup_template": persona.get("followup_template", ""),
    }


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
        messaging_graph_url("me/accounts"),
        params={"access_token": user_token, "fields": "id,access_token"},
        timeout=10,
    )
    for page in r.json().get("data", []):
        if page.get("id") == page_id:
            return page["access_token"]
    return user_token  # fallback


def _resolve_dm_send_target(account_code_ref: str) -> dict | None:
    """260730 Multi-account DM Routing — account_code_ref로 계정별 발송 대상(URL+Token)을
    계산한다. account_code_ref가 없거나 조회·자격증명·Page 교환 중 하나라도 실패하면
    None을 반환하고, 호출자는 기존 전역 계정(INSTA_ACCESS_TOKEN/FACEBOOK_PAGE_ID)으로
    fallback한다(회장 승인 정책 — 계정 미해석이 답장 자체를 막지 않음)."""
    if not account_code_ref:
        return None
    try:
        account = _repo.get_publish_account(account_code_ref)
        if account is None:
            return None
        from modules.common.credential_resolver import resolve_credential
        cred = resolve_credential(account["credential_key"])
    except Exception as exc:
        logger.warning(f"[AutoReply] 계정별 credential 해석 실패 — 전역 fallback | account_code_ref={account_code_ref} | {exc}")
        return None

    provider = account.get("api_provider", "")
    if provider == "instagram_login":
        # facebook_login과 달리 Page Token 교환 없이 IG 토큰을 그대로 사용한다(ERR-077 실측).
        return {"url": instagram_login_graph_url(f"{cred.ig_user_id}/messages"), "token": cred.access_token}

    if provider == "facebook_login":
        page_id = account.get("fb_page_id", "")
        if not page_id:
            logger.warning(f"[AutoReply] fb_page_id 미설정 — 전역 fallback | account_code_ref={account_code_ref}")
            return None
        try:
            r = requests.get(
                messaging_graph_url("me/accounts"),
                params={"access_token": cred.access_token, "fields": "id,access_token"},
                timeout=10,
            )
            for page in r.json().get("data", []):
                if page.get("id") == page_id:
                    return {"url": messaging_graph_url(f"{page_id}/messages"), "token": page["access_token"]}
        except Exception as exc:
            logger.warning(f"[AutoReply] Page Token 교환 실패 — 전역 fallback | account_code_ref={account_code_ref} | {exc}")
        return None

    logger.warning(f"[AutoReply] 미지원 api_provider — 전역 fallback | account_code_ref={account_code_ref} | provider={provider!r}")
    return None


# 261029 Codex 반영 — 발송 실패의 '확정 미발송' 여부를 호출자가 판단할 수 있도록 마지막 발송 시도의
# HTTP 상태를 스레드별로 남긴다. None=정보 없음, 0=요청을 보내지 않음, 그 외=HTTP 상태 코드.
_SEND_TLS = threading.local()


def _last_send_failure_is_definite() -> bool:
    """False 반환이 '미발송이 확정'인 경우만 True: 요청을 보내지 않았거나(0) 4xx 응답.
    5xx·알 수 없음(None)은 Meta가 메시지를 처리했는지 알 수 없으므로 모호한 실패로 본다."""
    st = getattr(_SEND_TLS, "status", None)
    return isinstance(st, int) and (st == 0 or 400 <= st < 500)


def send_ig_reply(sender_igsid: str, message: str, account_code_ref: str = "") -> bool:
    """Page Messages API(또는 instagram_login 직접 경로)로 Instagram DM을 전송한다.

    /{ig-user-id}/messages 는 Instagram Messaging 제품 심사 필요.
    /{page-id}/messages + Page Access Token 이 facebook_login의 올바른 경로.
    account_code_ref가 계정별 발송 대상으로 해석되면 그 경로를 쓰고, 아니면 기존
    전역 계정으로 fallback한다(동작 100% 보존).
    """
    _SEND_TLS.status = 0   # 요청을 보내기 전 단계의 실패(대상 해석 실패 등)는 '미발송 확정'
    target = _resolve_dm_send_target(account_code_ref)
    if target:
        url, page_token = target["url"], target["token"]
    elif account_code_ref != GLOBAL_FALLBACK_ACCOUNT_CODE_REF:
        # 260730 DM Routing Close Gate: 계정이 이미 식별됐는데(account_code_ref 있음)
        # 해석에 실패했고, 그 계정이 전역 fallback 목적지(yuna18253) 본인이 아니면
        # 전역 발송을 시도하지 않는다 — 다른 계정 손님에게 yuna18253 Page Token으로
        # 발송을 시도해 오계정 전달·무의미한 API 호출이 발생하는 것을 막는다.
        # 261029 STEP 2 Codex 반영 — 계정 참조 공란(미식별)도 같은 정책으로 차단한다
        # (_retry_send_ig_reply도 이 함수를 호출하므로 retry 재생 경계까지 함께 막힌다).
        logger.error(
            f"[AutoReply] 계정별 발송 대상 해석 실패 — 전역 fallback은 다른 계정(yuna18253) "
            f"소유라 발송 생략, retry_queue 위임 | account_code_ref={account_code_ref}"
        )
        return False
    else:
        page_id = os.getenv("FACEBOOK_PAGE_ID", "")
        page_token = _get_page_token()
        url = messaging_graph_url(f"{page_id}/messages")

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
        url,
        headers=headers,
        data=body,
        timeout=15,
    )

    _SEND_TLS.status = getattr(resp, "status_code", None)
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


def _notify_dm_manual_review(source: str, mid: str, reason: str) -> bool:
    """UNKNOWN/STARTED/SENDING으로 남아 자동 재발송이 중단된 DM을 운영자가 놓치지 않도록 알린다
    (기존 Slack 재사용 + 실패 시 ERROR 로그·Telegram 대체)."""
    return _alert_dm("수동 확인 필요", source, mid, reason, manual=True, level="warning")


def _retry_send_ig_reply(payload: dict) -> None:
    """retry_queue 핸들러 — IG DM 재전송.

    payload에 dm_event=[source, mid, claim_token](261029 STEP 2, DM_EVENT_DEDUP_ENABLED=true였을 때만
    포함)가 있으면 영속 이벤트 상태를 확인한다: DONE이면 이미 발송된 것이라 보내지 않고 끝내고,
    UNKNOWN이면 모호한 이전 실패라 자동 재발송하지 않는다(수동 확인). 재시도 중 예외는 UNKNOWN으로
    기록해 큐의 다음 시도가 중복 발송하지 못하게 한다. 이벤트가 없는 옛 payload는 기존 동작 그대로."""
    raw_event = payload.get("dm_event")
    event = tuple(raw_event) if isinstance(raw_event, (list, tuple)) and len(raw_event) == 3 else None
    if event:
        try:
            from modules.comment import comment_event_store as _store
            row = _store.get_status(event[0], event[1])
        except Exception as exc:
            # 상태를 확인할 수 없으면 보내지 않고 실패로 돌려 큐가 나중에 다시 시도하게 한다(Fail-closed).
            raise RuntimeError(f"DM_EVENT_STORE_ERROR — retry 발송 보류: {exc}") from exc
        if not row or row.get("claim_token") != event[2]:
            # Codex 독립 검수 반영 — 이벤트 행이 없거나 claim이 바뀐(stale reclaim) 옛 payload는 발송하지 않는다.
            logger.warning(f"[AutoReply] DM_RETRY_FENCED — 이벤트 행 없음 또는 claim 불일치, 발송 안 함 | source={event[0]}")
            return
        state = row.get("private_reply_status", "NOT_APPLICABLE")
        if state == "DONE":
            logger.info(f"[AutoReply] retry skip — 이미 발송 완료(DONE) | source={event[0]}")
            return
        if state in ("UNKNOWN", "SENDING"):
            # UNKNOWN=이전 발송 결과 모호, SENDING=다른 실행이 발송 중이거나 발송 중 중단 — 둘 다 자동 재발송 금지.
            logger.warning(f"[AutoReply] DM_RETRY_STATE_HOLD — 이전 발송 상태={state}, 자동 재발송 안 함 | source={event[0]}")
            if state == "SENDING":
                _notify_dm_manual_review(event[0], event[1], "발송 진행 중 상태(SENDING)로 남아 retry를 중단 — 중단된 발송인지 확인 필요")
            return
        # 261029 Codex 반영 — get_status 후 mark_effect_started 조합은 동시 실행에서 둘 다 통과할 수 있어,
        # 상태 조건이 포함된 단일 UPDATE(try_begin_effect)로 발송 선점을 원자적으로 하나만 획득한다.
        try:
            began = _store.try_begin_effect(event[0], event[1], event[2], "private_reply", ("STARTED", "NOT_APPLICABLE"))
        except Exception as exc:
            raise RuntimeError(f"DM_EVENT_STORE_ERROR — retry 발송 보류: {exc}") from exc
        if not began:
            logger.warning(f"[AutoReply] DM_RETRY_FENCED — 발송 선점 실패(동시 실행 또는 소유권 상실), 발송 안 함 | source={event[0]}")
            return
    _SEND_TLS.status = None
    try:
        ok = send_ig_reply(payload["sender_igsid"], payload["message"], payload.get("account_code_ref", ""))
    except Exception:
        if event:
            try:
                from modules.comment import comment_event_store as _store
                _store.mark_effect_unknown(event[0], event[1], event[2], "private_reply")
                _hold_template_en_after_unknown(payload.get("account_code_ref", ""), payload.get("sender_igsid", ""))
                _notify_dm_manual_review(event[0], event[1], "retry 발송 중 예외 — 전달 여부 불명(UNKNOWN), 큐 재시도 중단")
            except Exception as exc:
                logger.warning(f"[AutoReply] retry 이벤트 UNKNOWN 표시 실패(무시) | {exc}")
        raise
    if not ok:
        if event:
            try:
                from modules.comment import comment_event_store as _store
                if _last_send_failure_is_definite():
                    _store.finish_effect_failed(event[0], event[1], event[2], "private_reply")   # SENDING→STARTED: 재시도 허용
                else:
                    # 5xx 등 모호한 실패 — Meta가 메시지를 처리했는지 알 수 없으므로 자동 재발송하지 않는다.
                    _store.mark_effect_unknown(event[0], event[1], event[2], "private_reply")
                    _hold_template_en_after_unknown(payload.get("account_code_ref", ""), payload.get("sender_igsid", ""))
                    _notify_dm_manual_review(event[0], event[1], "retry 발송 응답이 모호(5xx 등) — 전달 여부 불명(UNKNOWN), 자동 재발송 중단")
                    return
            except Exception as exc:
                logger.warning(f"[AutoReply] retry 실패 분류 표시 실패(무시) | {exc}")
        raise RuntimeError("IG DM send failed")
    if event:
        try:
            from modules.comment import comment_event_store as _store
            _store.mark_effect_done(event[0], event[1], event[2], "private_reply")
        except Exception as exc:
            logger.warning(f"[AutoReply] retry 이벤트 DONE 표시 실패(무시) | {exc}")
        raw_received = payload.get("received_at")
        if raw_received:
            try:
                _check_reply_sla(datetime.fromisoformat(raw_received), event, "retry")
            except Exception as exc:
                logger.warning(f"[AutoReply] retry SLA 측정 실패(무시) | {exc}")


def register_retry_handlers(rq) -> None:
    """260730(ERR-097 계열) — launcher 시작 시 즉시(eager) 호출해야 함(rq.start() 이전).
    실패 시점에만 지연등록하면 재시작 후 pending task가 handler를 못 찾고 dead 처리됨
    (comment_airtable_record/FP-047과 동일 계약)."""
    rq.register("ig_auto_reply", _retry_send_ig_reply)


def handle_price_inquiry(
    record_id: str,
    sender_igsid: str,
    inquiry_text: str,
    received_at: datetime,
    account_code_ref: str = "",
    is_order: bool = False,
    dm_event: tuple | None = None,
) -> None:
    """단가 문의 감지 → 계정별 reply_mode에 따라 자동 응답 → Lead 업데이트 → 팔로업 예약 → Telegram 알림.

    is_order=True(261029 회장 확정): 주문 의사로 감지된 DM — template_en 계정만 영어 자동응답을
    추가로 보내고, 기존 계정(041·036 등)은 기존 주문 처리 우선 정책대로 여기서는 응답하지 않는다.

    dm_event=(source, mid, claim_token)(261029 STEP 2, DM_EVENT_DEDUP_ENABLED=true일 때만 전달):
    발송 직전/직후 comment_event_store에 at-most-once 상태(private_reply 컬럼)를 기록한다.
    STARTED/UNKNOWN/DONE이 남은 이벤트는 자동 재발송하지 않고 HOLD한다."""
    from modules.dm.dm_followup_scheduler import set_followup_schedule
    from modules.common.retry_queue import get_retry_queue

    # 260730 — 계정별 reply_mode(Account_Registry.reply_mode: template/persona/disabled).
    # 계정 미지정·조회실패·공란은 전부 기존 전역 PRICE_AUTO_REPLY_ENABLED 동작으로
    # fallback한다(Fail-open, 기존 동작 100% 보존).
    reply_mode = ""
    try:
        account = _repo.get_publish_account(account_code_ref) if account_code_ref else None
        if account:
            reply_mode = account.get("reply_mode", "")
    except Exception as exc:
        logger.warning(f"[AutoReply] 계정 reply_mode 조회 실패 — 전역 기본값 사용 | {exc}")
    if not reply_mode and account_code_ref != GLOBAL_FALLBACK_ACCOUNT_CODE_REF:
        # 261029 A-3c(a) Fail-closed — 계정 미식별(공란)·조회 실패·reply_mode 미설정 계정은
        # 전역 기본값(template=한국어 상품확인 요청)으로 떨어지지 않고 응답을 생략한다.
        # 전역 fallback 계정(IDN-000041)만 기존 동작을 유지한다. 접수 기록·운영자
        # Telegram 알림은 호출 전에 이미 끝났으므로 문의는 유실되지 않는다.
        logger.warning(
            f"[AutoReply] ACCOUNT_UNRESOLVED_REPLY_SKIPPED — 응답 생략 | "
            f"account_code_ref={account_code_ref or 'unknown'} | sender={_mask_igsid(sender_igsid)}"
        )
        return
    if not reply_mode:
        reply_mode = "persona" if PRICE_AUTO_REPLY_ENABLED else "template"

    if reply_mode != "template_en":
        # 261029 STEP 2 정정(회장 확정) — 041·036 등 기존 계정은 가격 문의 전용 응답 정책을 그대로
        # 유지한다(이전에는 dm_receiver가 하던 가격 키워드 판정을 처리기 안으로 옮긴 것, 동작 불변).
        # template_en 계정은 키워드와 무관하게 모든 DM에 계정 정책(reply_mode)을 적용한다.
        if is_order:
            logger.info(f"[AutoReply] 주문 의사 DM — 기존 계정은 주문 처리 우선, 자동응답 생략 | account_code_ref={account_code_ref or 'unknown'}")
            return
        if not detect_price_inquiry(inquiry_text):
            logger.info(f"[AutoReply] 가격 문의 아님 — 기존 계정 정책상 응답 생략 | account_code_ref={account_code_ref or 'unknown'}")
            return
        # 금지어 필터는 기존 계정에만 유지한다. template_en은 Spam 필터링 DEFER 동안 적용하지 않는다.
        from modules.dm.rules import evaluate as _rule_evaluate
        _rule = _rule_evaluate(inquiry_text)
        if not _rule:
            reason = getattr(_rule, "reason", "unknown")
            logger.info(f"[AutoReply] 메시지 필터 차단 | reason={reason} | sender={sender_igsid}")
            return
        # 최근 auto_replied 중복 확인(발신자 전용 조회)은 기존 계정에만 적용한다 — template_en은
        # 계정+발신자 단위 60분 cooldown을 쓰며, 다른 계정의 응답이 이 계정의 응답을 막으면 안 된다.
        # 가격 문의가 아닌 DM은 위에서 반환되므로 불필요한 Airtable 읽기도 줄어든다.
        if _has_recent_auto_replied(sender_igsid, minutes=3):
            logger.info(f"[AutoReply] duplicate skip | record={record_id} sender={sender_igsid} status=auto_replied")
            return
    # Lead_Interactions.reply_mode_used 선택지에 template_en이 없으므로 기록은 template으로 남긴다.
    reply_mode_logged = "template" if reply_mode == "template_en" else reply_mode

    if reply_mode == "disabled":
        logger.info(f"[AutoReply] reply_mode=disabled — 응답 생략 | account_code_ref={account_code_ref or 'unknown'}")
        try:
            _repo.record_reply_observability(record_id, reply_mode_used="disabled", send_status="skipped")
        except Exception as exc:
            logger.warning(f"[AutoReply] Observability 기록 실패(무시) | {exc}")
        return

    reply_price = None
    persona_code_ref = ""
    prompt_version = ""
    persona_check_pass = False

    if reply_mode in ("template", "template_en"):
        # Gate C: 상품(Post/Product) 매핑 전까지 가격 숫자는 절대 자동발송하지 않는다.
        # Buyer 응답 자체는 유지 — 접수 확인 + 상품확인 요청으로 대체.
        # bridge_status가 auto_replied로 안 바뀌어 _has_recent_auto_replied가 이 경로를
        # 못 잡으므로, (sender, 문의문) 단위로 발송 전에 먼저 선점해 웹훅재전송/동시진입
        # 중복발송을 막는다 — 같은 buyer의 다른 상품 문의는 키가 달라 차단되지 않는다.
        if reply_mode == "template_en":
            # 261029 STEP 2 SLA 정정(회장 확정) — 계정+발신자 60초 burst guard(+UNKNOWN 60분 hold). 같은 바이어의 연속
            # 연속 메시지에 영어 템플릿이 반복 발송되지 않게 한다(메모리 기반, 재시작 시 초기화).
            if not _try_reserve_template_en_slot(account_code_ref, sender_igsid):
                logger.info(f"[AutoReply] template_en 중복 skip(burst {_TEMPLATE_EN_BURST_SECONDS}초 또는 UNKNOWN hold) | sender={_mask_igsid(sender_igsid)}")
                return
        elif not _try_reserve_awaiting_product_slot(sender_igsid, inquiry_text):
            logger.info(f"[AutoReply] 상품확인 요청 중복 skip(3분 이내, 동일 문의) | sender={_mask_igsid(sender_igsid)}")
            return
        reply_msg = PRODUCT_CONFIRM_TEMPLATE_EN if reply_mode == "template_en" else PRODUCT_CONFIRM_TEMPLATE
        logger.info(f"[AutoReply] reply_mode={reply_mode} — 상품확인 요청으로 대체 | sender={_mask_igsid(sender_igsid)}")
    else:  # reply_mode == "persona"
        if not _try_reserve_persona_reply_slot(sender_igsid):
            logger.info(f"[AutoReply] persona 응답 중복 skip(3분 이내, 처리 중/완료) | sender={_mask_igsid(sender_igsid)}")
            return
        base_price = get_base_price()
        if base_price is None:
            logger.warning("[AutoReply] 기준 가격 없음 — 자동 응답 생략")
            _release_persona_reply_slot(sender_igsid)
            return

        reply_price = round(base_price * (1 + MARGIN_RATE))
        prompt_version = "gemini-persona-v1"
        try:
            from modules.dm.ai_reply_generator import generate_reply
            persona_kwargs = _get_persona_kwargs(account_code_ref)
            persona_check_pass = bool(
                persona_kwargs.get("tone_style")
                or persona_kwargs.get("greeting_template")
                or persona_kwargs.get("followup_template")
            )
            if persona_check_pass:
                try:
                    persona = _repo.get_persona_by_account_code(account_code_ref)
                    persona_code_ref = persona.get("persona_code", "") if persona else ""
                except Exception:
                    persona_code_ref = ""
            reply_msg = generate_reply(inquiry_text, base_price, MARGIN_RATE, **persona_kwargs)
            logger.info(f"[AutoReply] AI 응답 생성 사용 | account_code_ref={account_code_ref or 'unknown'}")
        except Exception as exc:
            logger.warning(f"[AutoReply] AI 응답 실패 — 템플릿 폴백 | {exc}")
            reply_msg = REPLY_TEMPLATE.format(price=reply_price)

    if dm_event:
        # 영속 중복 방지 — 이전 처리에서 발송 상태가 남아 있으면 자동 재발송하지 않는다(수동 확인).
        _src, _mid, _tok = dm_event

        def _release_reserved_slot():
            if reply_mode == "template_en":
                _release_template_en_slot(account_code_ref, sender_igsid)
            elif reply_price is None:
                _release_awaiting_product_slot(sender_igsid, inquiry_text)
            else:
                _release_persona_reply_slot(sender_igsid)

        try:
            from modules.comment import comment_event_store as _store
            _state = (_store.get_status(_src, _mid) or {}).get("private_reply_status", "NOT_APPLICABLE")
            if _state in ("STARTED", "UNKNOWN", "DONE"):
                logger.warning(f"[AutoReply] DM_REPLY_STATE_HOLD — 이전 발송 상태={_state}, 자동 재발송 안 함 | source={_src}")
                if _state in ("STARTED", "UNKNOWN"):
                    _notify_dm_manual_review(_src, _mid, f"이전 발송 결과가 불명확({_state})해 자동 재발송을 중단")
                _release_reserved_slot()
                return
            if not _store.mark_effect_started(_src, _mid, _tok, "private_reply"):
                logger.warning(f"[AutoReply] DM_EVENT_FENCED — 소유권 상실, 응답 HOLD | source={_src}")
                _release_reserved_slot()
                return
        except Exception as exc:
            logger.error(f"[AutoReply] DM_EVENT_STORE_ERROR — 응답 HOLD | {exc}")
            _release_reserved_slot()
            return

    _SEND_TLS.status = None   # 이전 호출의 상태가 새어 들어오지 않도록 초기화(실제 발송 함수가 다시 채운다)
    try:
        sent = send_ig_reply(sender_igsid, reply_msg, account_code_ref)
    except Exception:
        if dm_event:
            try:
                from modules.comment import comment_event_store as _store
                _store.mark_effect_unknown(dm_event[0], dm_event[1], dm_event[2], "private_reply")
                _hold_template_en_after_unknown(account_code_ref, sender_igsid)
                _notify_dm_manual_review(dm_event[0], dm_event[1], "자동응답 발송 중 예외 — 전달 여부 불명(UNKNOWN)")
            except Exception as exc:
                logger.warning(f"[AutoReply] 이벤트 UNKNOWN 표시 실패(무시) | {exc}")
        # send_ig_reply가 False가 아니라 예외(네트워크 오류 등)를 던지는 경우에도
        # 선점을 남겨두면 3분간 정당한 재시도까지 "중복"으로 막힌다. 최소한 해제 후
        # 그대로 재발생시켜 상위(dm_receiver.py)의 기존 예외 처리로 넘긴다.
        # 261029 Codex 반영 — 영속 이벤트(dm_event)가 있는 경로에서 예외는 '전달 여부 불명(UNKNOWN)'이므로
        # 중복 방지 슬롯을 유지한다(해제하면 같은 바이어의 다음 DM이 새 이벤트로 중복 응답할 수 있음).
        # dm_event가 없는 기존 경로(플래그 OFF)는 종전대로 해제한다.
        if not dm_event:
            if reply_mode == "template_en":
                _release_template_en_slot(account_code_ref, sender_igsid)
            elif reply_price is None:
                _release_awaiting_product_slot(sender_igsid, inquiry_text)
            else:
                _release_persona_reply_slot(sender_igsid)
        raise

    if not sent:
        # 미발송이 확정된 경우에만 슬롯을 해제한다. 모호한 실패(5xx 등, UNKNOWN)는 슬롯을 유지한다.
        if not (dm_event and not _last_send_failure_is_definite()):
            if reply_mode == "template_en":
                _release_template_en_slot(account_code_ref, sender_igsid)
            elif reply_price is None:
                # 선점은 이미 걸어뒀는데 실제 발송은 실패했으므로 해제 — 정당한 재시도가
                # "3분 내 중복"으로 오인되어 막히지 않도록 한다.
                _release_awaiting_product_slot(sender_igsid, inquiry_text)
            else:
                _release_persona_reply_slot(sender_igsid)
        if dm_event and not _last_send_failure_is_definite():
            # 5xx 등 모호한 실패 — 전달 여부를 알 수 없으므로 retry를 등록하지 않고 수동 확인 대상으로 둔다.
            try:
                from modules.comment import comment_event_store as _store
                _store.mark_effect_unknown(dm_event[0], dm_event[1], dm_event[2], "private_reply")
            except Exception as exc:
                logger.warning(f"[AutoReply] 이벤트 UNKNOWN 표시 실패(무시) | {exc}")
            _hold_template_en_after_unknown(account_code_ref, sender_igsid)
            _notify_dm_manual_review(dm_event[0], dm_event[1], "자동응답 발송 응답이 모호(5xx 등) — 전달 여부 불명(UNKNOWN), retry 미등록")
            logger.warning(f"[AutoReply] 모호한 발송 실패 — retry 미등록, 수동 확인 | to={_mask_igsid(sender_igsid)}")
        else:
            rq = get_retry_queue()
            rq.register("ig_auto_reply", _retry_send_ig_reply)
            rq.start()
            retry_payload = {"sender_igsid": sender_igsid, "message": reply_msg, "account_code_ref": account_code_ref}
            if dm_event:
                retry_payload["dm_event"] = list(dm_event)   # retry 경계에서도 영속 이벤트 상태를 확인하게 한다
                retry_payload["received_at"] = received_at.isoformat()   # retry 성공 시 SLA 측정용
            rq.enqueue("ig_auto_reply", retry_payload)
            logger.warning(f"[AutoReply] DM 발송 실패 → retry queue 등록 | to={sender_igsid}")
        try:
            _repo.record_reply_observability(
                record_id, reply_mode_used=reply_mode_logged, persona_code_ref=persona_code_ref,
                send_status="failed", prompt_version=prompt_version, persona_check_pass=persona_check_pass,
            )
        except Exception as exc:
            logger.warning(f"[AutoReply] Observability 기록 실패(무시) | {exc}")
        # 실제 발송이 안 됐으므로 "답변완료" 상태전환·팔로업예약·알림 전부 생략한다.
        # (재시도 성공 시 상태를 소급 반영하는 로직은 P0-1/Gate F의 Outbox·재조정 설계 범위)
        return

    if dm_event:
        try:
            from modules.comment import comment_event_store as _store
            _store.mark_effect_done(dm_event[0], dm_event[1], dm_event[2], "private_reply")
        except Exception as exc:
            logger.warning(f"[AutoReply] 이벤트 DONE 표시 실패(무시) | {exc}")
    _check_reply_sla(received_at, dm_event, "first")

    try:
        _repo.record_reply_observability(
            record_id, reply_mode_used=reply_mode_logged, persona_code_ref=persona_code_ref,
            send_status="sent", prompt_version=prompt_version, persona_check_pass=persona_check_pass,
        )
    except Exception as exc:
        logger.warning(f"[AutoReply] Observability 기록 실패(무시) | {exc}")

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
