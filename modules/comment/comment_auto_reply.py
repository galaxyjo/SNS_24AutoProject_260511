# modules/comment/comment_auto_reply.py
# 댓글 키워드 감지 → 자동 답글 + Airtable 기록 + Telegram 알림

import os
import json as _json
import logging
import random
import requests
from datetime import datetime, timezone
from enum import Enum

from modules.comment import comment_safety_guard as guard
from modules.comment import comment_event_store as event_store
from modules.comment import comment_poll_targets as poll_targets
from modules.comment.comment_campaign_config import CampaignConfigError, load_campaign_media_ids
from modules.common.meta_graph import messaging_graph_url
from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import LeadInteractionCreate

logger = logging.getLogger(__name__)

_repo = AirtableRepository()

_AUTO_REPLY_ENABLED = os.getenv("COMMENT_AUTO_REPLY_ENABLED", "false").lower() == "true"

# FP-047: disabled(기본)=기존 동작 그대로 / shadow=관측만 / enforce=실제 dedup 게이트
_EVENT_SOURCE = "instagram_comment"

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
# FP-047: 최초 처리(claim_token 있음, enforce)는 실패 시 retry_queue로 위임하고
# Reply/Telegram을 다시 실행하지 않는다. claim_token 없음(disabled/shadow)은
# 기존 동작(실패 시 로그만, 유실 가능 — FP-047 자체가 이 상태)을 그대로 유지한다.

def _create_lead_interaction_idempotent(username: str, text: str, comment_id: str) -> None:
    """3-way 조회 후 생성 — LOOKUP_FAILED(예외)는 그대로 전파해 재시도 대상으로 남긴다."""
    existing = _repo.find_lead_interaction_by_source_event(_EVENT_SOURCE, comment_id)
    if existing:
        logger.info(f"[Comment] Airtable 이미 존재(FOUND) — 생성 스킵 | comment={comment_id} | record={existing}")
        return
    _repo.create_lead_interaction(LeadInteractionCreate(
        igsid=username,
        source=_EVENT_SOURCE,
        interaction_type="comment_received",
        occurred_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        inquiry_message=text,
        source_event_id=comment_id,
    ))


def _record_comment(claim_token: str | None, username: str, text: str, comment_id: str, media_id: str) -> bool:
    """반환값: durably_accepted(260715 Codex 4차 리뷰) — Airtable 기록 성공 또는
    retry_queue 정상 enqueue면 True. enqueue 자체가 실패(fail-closed)했을 때만 False —
    이전엔 이 실패가 호출부에 전달되지 않아 webhook이 200을, poller가 캐시를 하는
    "durable-accept 실패인데 성공으로 보고" 문제가 있었음."""
    if not claim_token:
        # 레거시 경로(disabled/shadow) — 기존 동작 그대로, retry 없음(FP-047 자체 재현).
        try:
            _repo.create_lead_interaction(LeadInteractionCreate(
                igsid=username,
                source=_EVENT_SOURCE,
                interaction_type="comment_received",
                occurred_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                inquiry_message=text,
            ))
            logger.info(f"[Comment] Airtable 기록 완료 | from={username}")
        except Exception as exc:
            logger.warning(f"[Comment] Airtable 기록 예외 | {exc}")
        return True  # 레거시 경로는 애초에 durable-accept 개념이 없음(LEGACY 결과로 취급됨)

    try:
        _create_lead_interaction_idempotent(username, text, comment_id)
        marked = event_store.mark_airtable_done(_EVENT_SOURCE, comment_id, claim_token)
        if not marked:
            # P0(260715 Codex 5차 리뷰): Airtable 쓰기 자체는 성공했지만 fencing 실패
            # (그 사이 다른 worker가 reclaim해서 claim_token이 바뀜) — 이 상태를 True로
            # 보고하면 webhook 200/poller 캐시로 이 comment_id를 "끝난 일"로 치부해버려서,
            # status=PROCESSING에 영구 고착된 이 행을 아무도 다시 안 보게 된다.
            # False를 반환해 caller가 재시도하게 하면, 다음 시도가 claim(재발급된 새
            # token)한 뒤 _create_lead_interaction_idempotent()의 3-way 조회가 이미
            # 생성된 레코드를 FOUND로 찾아 중복 없이 mark_airtable_done()을 다시 시도해
            # 정상적으로 COMPLETED까지 수렴한다.
            logger.warning(f"[Comment] Airtable 기록 성공했으나 event_store fencing 실패(재시도로 수렴 유도) | comment={comment_id}")
            return False
        logger.info(f"[Comment] Airtable 기록 완료 | from={username} | comment={comment_id}")
        return True
    except Exception as exc:
        logger.warning(f"[Comment] Airtable 기록 실패 → retry_queue 위임 | comment={comment_id} | {exc}")
        try:
            from modules.common.retry_queue import get_retry_queue
            rq = get_retry_queue()
            task_id = rq.enqueue("comment_airtable_record", {
                "claim_token": claim_token,
                "comment_id":  comment_id,
                "username":    username,
                "text":        text,
                "media_id":    media_id,
            })
            marked = event_store.mark_airtable_retry_pending(_EVENT_SOURCE, comment_id, claim_token, task_id)
            if not marked:
                # enqueue 자체는 성공(retry_queue.db가 payload를 durably 보유)했지만
                # fencing 실패로 retry_task_id/airtable_status=RETRY_PENDING이 이
                # 행에 기록 안 됨 — find_by_retry_task_id()로 DEAD 동기화도 안 되고,
                # mark_airtable_retry_completed()의 매칭 조건도 영영 안 맞는다. False를
                # 반환해 재시도를 유도(3-way 조회가 중복은 막아줌, 원래 enqueue된
                # task는 나중에 실행돼도 이미 완료된 상태라 무해하게 no-op).
                logger.warning(f"[Comment] retry enqueue 성공했으나 event_store fencing 실패(재시도로 수렴 유도) | comment={comment_id}")
                return False
            return True  # retry_queue.db가 payload를 durably 보유 — 크래시와 무관하게 완료 보장
        except Exception as enqueue_exc:
            # fail-closed: enqueue 자체가 실패하면 "성공한 셈" 치지 않는다 — lease 만료 후
            # try_claim()의 stale reclaim으로 재회수 가능하도록 상태만 남긴다.
            logger.error(f"[Comment] retry_queue enqueue 실패 | comment={comment_id} | {enqueue_exc}")
            event_store.mark_retry_enqueue_failed(_EVENT_SOURCE, comment_id, claim_token, str(enqueue_exc))
            return False


def _retry_record_comment(payload: dict) -> None:
    """retry_queue 핸들러 전용 — Airtable 쓰기만 재시도(Reply/Telegram 재실행 없음).
    P0(260715 Codex 3차 리뷰): payload의 claim_token은 enqueue 시점 값이라 그 사이
    lease 만료→stale reclaim(P0-2)이 일어나면 무효화된다 — claim_token 기반
    mark_airtable_done() 대신, airtable_status='RETRY_PENDING' 조건만으로 전이하는
    mark_airtable_retry_completed()를 사용해 세대교체와 무관하게 완료를 반영한다."""
    comment_id = payload["comment_id"]
    _create_lead_interaction_idempotent(payload["username"], payload["text"], comment_id)
    ok = event_store.mark_airtable_retry_completed(_EVENT_SOURCE, comment_id)
    if not ok:
        # RETRY_PENDING이 아닌 상태(이미 다른 경로로 DONE 처리됐거나 예상 밖 상태 전이) —
        # Airtable 쓰기(또는 3-way 조회로 스킵) 자체는 이미 안전하게 끝났으므로 데이터
        # 유실/중복은 아니다. 진단용으로만 남김.
        logger.warning(f"[Comment] retry 완료했으나 event_store 상태가 RETRY_PENDING이 아님(진단필요) | comment={comment_id}")


# ── Telegram 알림 ─────────────────────────────────────────────────────────────

def _send_telegram_comment(claim_token: str | None, comment_id: str, username: str, text: str, tag: str) -> None:
    """claim_token이 있으면(enforce 모드) 발송 직전/직후 event_store에 at-most-once 상태 기록.
    None이면(disabled/shadow) 기존 동작 그대로."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return

    if claim_token:
        # P0-3(260715 Codex 2차 리뷰): mark_effect_started() 반환값을 반드시 확인 —
        # False면 그 사이 다른 worker가 reclaim해서 이 claim_token은 이미 fenced-out된
        # 것이므로, 발송 자체를 하지 않고 즉시 중단한다(그러지 않으면 손님한테 중복발송).
        if not event_store.mark_effect_started(_EVENT_SOURCE, comment_id, claim_token, "telegram"):
            logger.warning(f"[Comment] fencing 실패 — Telegram 발송 중단 | comment={comment_id}")
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
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg, "parse_mode": "Markdown"},
            timeout=8,
        )
        if claim_token:
            if resp.ok:
                event_store.mark_effect_done(_EVENT_SOURCE, comment_id, claim_token, "telegram")
            else:
                # P0(추가, 260715): HTTP 실패 응답도 확인 없이 DONE으로 기록되던 문제 수정
                logger.warning(f"[Comment] Telegram 발송 실패(HTTP {resp.status_code}) | comment={comment_id}")
                event_store.mark_effect_unknown(_EVENT_SOURCE, comment_id, claim_token, "telegram")
    except Exception as exc:
        logger.warning(f"[Comment] Telegram 알림 실패 | {exc}")
        if claim_token:
            # 전송 결과가 모호함(네트워크 예외) — UNKNOWN으로 즉시 격리(자동 재발송 금지).
            event_store.mark_effect_unknown(_EVENT_SOURCE, comment_id, claim_token, "telegram")


# ── Private Reply 안전 게이트 ────────────────────────────────────────────────

def _try_private_reply(claim_token: str | None, comment_id: str, username: str, media_id: str, cooldown_key: str) -> None:
    """캠페인 게시물·쿨다운·일일예산·circuit breaker를 모두 통과해야 Private Reply 발송.
    cooldown_key: 가능하면 IG scoped ID(from.id) — username은 사용자가 바꾸면 쿨다운이 우회됨.
    claim_token: enforce 모드에서 event_store에 at-most-once 상태 기록(FP-047).

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

        if claim_token:
            # P0-3(260715 Codex 2차 리뷰): fencing 실패 시 즉시 중단 — 안 그러면 이미
            # reclaim된(다른 worker가 넘겨받은) 이벤트에 대해서도 손님에게 발송해버릴 수 있음.
            if not event_store.mark_effect_started(_EVENT_SOURCE, comment_id, claim_token, "private_reply"):
                logger.warning(f"[Comment] fencing 실패 — Private Reply 발송 중단 | comment={comment_id}")
                return

        if reply_privately_to_comment(comment_id, _build_price_reply(username)):
            guard.mark_user_replied(cooldown_key)
            guard.record_circuit_success()
            if claim_token:
                event_store.mark_effect_done(_EVENT_SOURCE, comment_id, claim_token, "private_reply")
        else:
            guard.record_circuit_failure()
            if claim_token:
                # 명확한 실패(예외 아닌 정상 응답) — UNKNOWN으로 격리해 재시도 시 자동
                # 재발송되지 않게 한다(at-most-once 정책, Gate G 쿨다운과는 별개 보호).
                event_store.mark_effect_unknown(_EVENT_SOURCE, comment_id, claim_token, "private_reply")


# ── 메인 처리 ─────────────────────────────────────────────────────────────────

_TERMINAL_EFFECT_STATUSES = ("DONE", "UNKNOWN")  # 재개 시 다시 실행하면 안 되는 상태


def _handle_comment_impl(
    claim_token: str | None,
    comment_id: str,
    username: str,
    text: str,
    media_id: str,
    commenter_id: str = "",
) -> bool:
    """신규 댓글 1건 처리 — 키워드 감지 → 답글/알림 → Airtable 기록.
    claim_token: FP-047 enforce 모드에서만 채워짐(event_store 소유권 증명, fencing 조건).
    commenter_id: IG scoped ID(from.id). 미제공 시 username으로 폴백(comment_poller가 항상 채워줌).
    반환값: durably_accepted — Airtable 기록이 성공했거나 retry_queue에 정상 enqueue돼
    최종적으로는 반드시 반영될 것이 보장되면 True. enqueue 자체가 실패(fail-closed)
    했으면 False(260715 Codex 4차 리뷰 — 이전엔 이 실패가 호출부에 전달 안 돼서
    ACCEPTED로 잘못 보고됐음).

    P0-4(260715 Codex 2차 리뷰): claim_token이 stale reclaim으로 발급된 것일 수 있다
    (이전 worker가 이미 일부 effect를 완료한 뒤 crash) — 재실행 전 기존 상태를 먼저
    조회해 이미 DONE/UNKNOWN인 effect는 건너뛴다. 그러지 않으면 재개 시 이미 보낸
    Telegram/Private Reply/Airtable 기록을 중복 실행하게 된다."""
    logger.info(f"[Comment] 처리 | comment={comment_id} | from=@{username} | text={text[:80]}")
    cooldown_key = commenter_id or username

    existing = event_store.get_status(_EVENT_SOURCE, comment_id) if claim_token else None

    def _telegram_settled() -> bool:
        return bool(existing) and existing["telegram_status"] in _TERMINAL_EFFECT_STATUSES

    def _private_reply_settled() -> bool:
        return bool(existing) and existing["private_reply_status"] in _TERMINAL_EFFECT_STATUSES

    def _airtable_settled() -> bool:
        # DONE=완료 / RETRY_PENDING=이미 retry_queue가 소유(재개 시 또 enqueue하면 중복 태스크
        # 생성됨) — 둘 다 재시도 금지. RETRY_ENQUEUE_FAILED/PENDING(최초시도 전)은 재개 시
        # 다시 시도해야 함(fail-closed였던 걸 이번 기회에 정상 경로로 되돌림).
        return bool(existing) and existing["airtable_status"] in ("DONE", "RETRY_PENDING")

    def _send_telegram_if_pending(tag: str) -> None:
        if _telegram_settled():
            logger.info(f"[Comment] Telegram 이미 처리됨(재개 스킵) | comment={comment_id}")
            return
        _send_telegram_comment(claim_token, comment_id, username, text, tag)

    def _record_comment_if_pending() -> bool:
        if _airtable_settled():
            logger.info(f"[Comment] Airtable 이미 완료됨(재개 스킵) | comment={comment_id}")
            return True
        return _record_comment(claim_token, username, text, comment_id, media_id)

    if detect_negative_comment(text):
        _send_telegram_if_pending("negative")
        return _record_comment_if_pending()

    if detect_price_comment(text):
        if _AUTO_REPLY_ENABLED and not _private_reply_settled():
            _try_private_reply(claim_token, comment_id, username, media_id, cooldown_key)
        elif _AUTO_REPLY_ENABLED:
            logger.info(f"[Comment] Private Reply 이미 처리됨(재개 스킵) | comment={comment_id}")
        _send_telegram_if_pending("price")
    else:
        _send_telegram_if_pending("new")

    return _record_comment_if_pending()


def handle_comment(
    comment_id: str,
    username: str,
    text: str,
    media_id: str,
    commenter_id: str = "",
) -> None:
    """레거시 진입점 — claim_token 없이 처리(event_store dedup 미적용, 기존 동작 그대로).
    신규 코드(comment_poller.py/dm_receiver.py)는 process_comment_event()를 써야 한다.
    기존 테스트(tests/test_comment_auto_reply.py)가 이 시그니처를 직접 사용하므로 유지."""
    _handle_comment_impl(None, comment_id, username, text, media_id, commenter_id)


_VALID_MODES = ("disabled", "shadow", "enforce")
_retry_handlers_registered = False  # register_retry_handlers()가 실제로 호출됐는지 추적(fail-fast용)


def _get_event_store_mode() -> str:
    """P0(260715 Codex 2차 리뷰): 잘못된/오타 값이 조용히 enforce로 새는 것 방지 —
    허용값이 아니면 가장 안전한 disabled로 폴백하고 경고를 남긴다."""
    raw = os.getenv("COMMENT_EVENT_STORE_MODE", "disabled").lower()
    if raw not in _VALID_MODES:
        logger.warning(f"[Comment] COMMENT_EVENT_STORE_MODE 값이 유효하지 않음(disabled로 폴백) | value={raw!r}")
        return "disabled"
    return raw


class CommentProcessResult(Enum):
    """P0(260715 Codex 3차 리뷰) — 호출부(poller/webhook)가 캐시·ACK 여부를 올바르게
    판단하려면 "예외 없이 끝났다"만으로는 부족하다. 완료 상태와 진행중 상태를
    구분해야 poller가 IN_PROGRESS를 영구 캐시해버리는 실수를 막을 수 있다."""
    ACCEPTED             = "accepted"              # 이번 호출이 claim에 성공해 실제로 처리 시작(Airtable도 durable 확정)
    DUPLICATE_COMPLETED  = "duplicate_completed"   # 이미 완료/억제된 이벤트 — 확정적 종결, 캐시해도 됨
    RETRY_OWNED          = "retry_owned"           # 다른 worker가 claim했지만 Airtable 쓰기는 retry_queue.db가
                                                     # durable하게 보유 중(260715 Codex 4차 리뷰) — 200/캐시 가능
    IN_PROGRESS          = "in_progress"           # 다른 worker가 활성 처리중(유효 lease, durable 백업 없음) — 미확정, 503/캐시 금지
    LEGACY               = "legacy"                # disabled/shadow/non-campaign — event_store 미사용(기존 동작 그대로)
    REJECTED_NOT_READY   = "rejected_not_ready"     # enforce인데 handler 미등록/durable-accept 실패 — fail-closed, 재시도 필요


def _blocked_by_allowlist_gating(media_id: str) -> bool:
    """260715 Codex 6차 리뷰 P0-1 — comment_poll_targets가 도입된 뒤에도, poller의
    fetch 대상만 ACTIVE로 제한했을 뿐 이 단일 진입점(webhook+poller 공용)은
    is_campaign_post()만 확인해 PENDING_BASELINE media도 webhook 경로로 들어오면
    실제 처리(Airtable/Telegram/Private Reply)까지 흘러갈 수 있었다.

    260716 Codex 8차 리뷰(실제 재현 확인) — 두 가지를 추가로 고쳤다:
    P0(1): guard.is_campaign_post()는 "캠페인 아님"과 "JSON 손상/파일 소실"과
    "JSON에서 제거됨"을 전부 False로 뭉뚱그린다. 이 게이트가 그 결과만 보고
    "캠페인과 무관하니 통과"로 처리하면, 설정이 손상되거나 media가 목록에서
    빠져도(과거 ACTIVE였던 것 포함) poll_targets를 아예 확인 안 하고 실처리로
    샐 수 있었다. 그래서 이제 load_campaign_media_ids()를 직접 불러 3가지를
    구분한다: (a) JSON 자체를 못 읽음 → 전체 차단(fail-closed) (b) JSON에는
    없지만 poll_targets에 이력이 있는 media(과거 추적 대상이었다가 제거됨) →
    PAUSED 의미를 지켜 차단 (c) JSON에도 없고 이력도 없는 media → 원래부터
    무관하므로 통과(기존 동작 그대로).
    P0(2): poll_targets에 이력이 있는 media(state가 뭐든)는 COMMENT_POLL_ALLOWLIST_MODE
    플래그와 무관하게 이 게이트를 적용한다 — Phase B(baseline dry-run/apply/verify)가
    아직 flag를 켜기 전(legacy+shadow) 상태에서 진행될 수 있는데, 그동안 apply가
    막 만들어낸 PENDING_BASELINE 행도 flag가 꺼져 있다는 이유로 무방비였다(웹훅으로
    들어온 새 댓글이 SHADOW_SEEN 태그로 영구 고착되는 사고가 이 경로로도 재현 가능
    했음). flag는 이제 poller의 "무엇을 폴링할지"만 결정하고, 이 안전 불변식은
    poll_targets 이력이 있는 media라면 항상 적용된다."""
    try:
        campaign_media_ids = load_campaign_media_ids()
    except CampaignConfigError as exc:
        logger.error(f"[Comment] 캠페인 설정 손상 — 상태 확인 불가, fail-closed | media={media_id} | {exc}")
        return True

    try:
        target = poll_targets.get_target(media_id)
    except Exception as exc:
        logger.error(f"[Comment] poll_target 조회 실패 — fail-closed | media={media_id} | {exc}")
        return True

    if target is not None:
        # 260716 Codex 9차 리뷰 P0(실제 재현 확인) — DB 상태만 보고 JSON 현재
        # 소속을 확인 안 하면 경쟁 구간이 생긴다: media가 JSON에서 막 제거됐는데
        # sync_from_campaign_json()이 아직 한 번도 안 돌아서 poll_targets 행이
        # 여전히 ACTIVE로 남아있는 그 사이에 webhook이 도착하면, "이력이 있으니
        # DB 상태만 본다"는 이전 로직은 이걸 통과시켜버렸다. 이 함수가 이미 방금
        # 로드한 campaign_media_ids(현재 JSON의 실시간 스냅샷)로 매 호출마다
        # 다시 확인하면, sync 주기를 기다릴 필요 없이 이 순간 즉시 차단된다.
        if media_id not in campaign_media_ids:
            return True
        return target.get("state") != "ACTIVE"

    if media_id not in campaign_media_ids:
        return False  # 캠페인도 아니고 poll_targets 이력도 없음 — 원래부터 무관

    # 캠페인 목록엔 있지만 poll_targets 행이 아직 없음(sync가 이 media를 아직 한
    # 번도 못 봄). allowlist 운영 중인데 행이 없는 건 비정상 상태이므로 fail-closed.
    # legacy 전용(baseline 작업 자체를 아직 시작 안 함)이면 원래 동작 그대로 통과.
    return poll_targets.is_allowlist_gating_enabled()


def process_comment_event(
    comment_id: str,
    username: str,
    text: str,
    media_id: str,
    ingress: str,
    commenter_id: str = "",
) -> CommentProcessResult:
    """FP-047 단일 진입점 — comment_poller.py(ingress="poller")와 dm_receiver.py
    (ingress="webhook")는 이 함수만 호출해야 한다(handle_comment 직접 호출 금지).
    COMMENT_EVENT_STORE_MODE로 동작 전환:
      disabled(기본) — event_store 미사용, 기존 동작 그대로(현재 상태)
      shadow         — try_claim()은 실행하되(관측만), 기존 처리 경로 그대로 실행
      enforce        — 캠페인 게시물(guard.is_campaign_post)에 한해서만 실제 dedup
                        게이트 적용(P0-5, 260715 — "제한 Canary"가 실제로 제한적이려면
                        전역이 아니라 게시물 단위 스코핑이 필요). 캠페인 게시물이 아니면
                        enforce여도 disabled처럼 동작(claim 자체를 시도하지 않음).
    반환값(CommentProcessResult): 호출부가 "다시 봐야 하는지" 판단하는 근거 —
    IN_PROGRESS는 아직 미확정 상태이므로 poller 캐시에 넣으면 안 되고, webhook도
    이걸 근거로 200 ACK 여부를 판단해야 한다(durable accept가 안 됐으면 재전송 유도)."""
    # 260716 Codex 7차 리뷰 P0-1/P0-3: allowlist gating은 COMMENT_EVENT_STORE_MODE와
    # 무관한 최상위 안전장치여야 한다 — mode 분기(특히 disabled)보다 먼저, 그리고
    # event_store에 어떤 행도 만들기 전에 검사한다.
    # P0-1(실제 재현 확인): 이전엔 shadow 분기 안에서 try_claim(shadow=True)을 먼저
    # 실행한 뒤에 이 게이트를 봤음 — PENDING_BASELINE media에 새 댓글이 오면 그 순간
    # migration_tag='SHADOW_SEEN'인 행이 이미 생겨버리고, try_claim()의 stale reclaim
    # WHERE절이 migration_tag IS NULL만 재claim 대상으로 삼기 때문에, 이 media가 나중에
    # baseline을 거쳐 ACTIVE+enforce가 돼도 이 특정 댓글은 영원히 재claim이 안 돼
    # status=PROCESSING/IN_PROGRESS에 영구 고착됐다(사실상 응답 영구 유실). 그래서
    # claim을 시도하기 전에 이 게이트를 통과시켜, PENDING 대상은 event row 자체를
    # 아예 만들지 않는다.
    # P0-3(실제 재현 확인): disabled 모드는 이 게이트 없이 무조건 handle_comment()를
    # 호출했음 — allowlist gating이 켜져 있어도 event-store 모드가 disabled면 완전히
    # 우회돼 PENDING_BASELINE media도 실처리됐다.
    if _blocked_by_allowlist_gating(media_id):
        logger.warning(f"[Comment] allowlist gating: media 미활성 — event row 생성 전 차단(fail-closed) | media={media_id}")
        return CommentProcessResult.REJECTED_NOT_READY

    mode = _get_event_store_mode()

    if mode == "disabled":
        handle_comment(comment_id, username, text, media_id, commenter_id)
        return CommentProcessResult.LEGACY

    if mode == "enforce" and not guard.is_campaign_post(media_id):
        # enforce가 전역이 아니라 캠페인 게시물에만 적용되도록 스코핑 — 그 외는 손대지 않음.
        handle_comment(comment_id, username, text, media_id, commenter_id)
        return CommentProcessResult.LEGACY

    if mode == "enforce" and not _retry_handlers_registered:
        # P0(260715 Codex 3차 리뷰): legacy 폴백은 fail-open이었음(설계 의도와 다르게
        # 조용히 무보호 상태로 계속 처리됨) — enforce를 명시적으로 요청한 상태에서
        # 전제조건(handler 등록)이 깨졌으면 아예 처리를 거부한다(fail-closed).
        # 손님 응대 자체가 잠시 멈추더라도, 무보호 상태로 계속 흘려보내는 것보다 낫다.
        logger.error("[Comment] enforce 모드인데 comment_airtable_record 핸들러 미등록 — 처리 거부(fail-closed)")
        return CommentProcessResult.REJECTED_NOT_READY

    if mode == "shadow":
        # shadow=True(260715 Codex 4차 리뷰) — 이 claim은 migration_tag='SHADOW_SEEN'으로
        # 남아 나중에 enforce의 stale reclaim 대상에서 영구 제외된다(shadow 중엔 아래
        # handle_comment()가 이미 실제로 Reply/Telegram/Airtable을 처리하므로, enforce가
        # 이 행을 "죽은 것"으로 오인해 재claim하면 이미 보낸 걸 또 보내게 됨).
        # (allowlist gating 통과 여부는 함수 맨 위에서 이미 확인됨 — 여기 도달했다는
        # 것 자체가 "PENDING_BASELINE 캠페인 media가 아니다"를 의미)
        token = event_store.try_claim(_EVENT_SOURCE, comment_id, claimed_by=ingress, shadow=True)
        logger.info(f"[Comment] shadow would_claim={token is not None} | comment={comment_id} | ingress={ingress}")
        handle_comment(comment_id, username, text, media_id, commenter_id)
        return CommentProcessResult.LEGACY

    token = event_store.try_claim(_EVENT_SOURCE, comment_id, claimed_by=ingress)

    # enforce (캠페인 게시물 + handler 등록 확인됨)
    if token is None:
        # P0(260715 Codex 3·4차 리뷰): None인 이유를 세분화한다 —
        # RETRY_PENDING(retry_queue.db가 payload를 durable 보유)만 200/캐시 가능(RETRY_OWNED).
        # 그 외 순수 PROCESSING(활성 worker만 들고 있고 durable 백업 없음)은 caller가
        # 확정 상태로 오인해 캐시/200하면, 그 worker가 crash했을 때 Meta 재전송이라는
        # 복구 수단까지 스스로 차단해버리게 된다 — IN_PROGRESS로 반환해 503 유도.
        existing = event_store.get_status(_EVENT_SOURCE, comment_id)
        if existing and existing["airtable_status"] == "RETRY_PENDING":
            logger.info(f"[Comment] enforce: retry_queue durable 소유(RETRY_OWNED) | comment={comment_id} | ingress={ingress}")
            return CommentProcessResult.RETRY_OWNED
        if existing and existing["status"] == "PROCESSING":
            logger.info(f"[Comment] enforce: 활성 worker 처리중, durable 백업 없음(IN_PROGRESS) | comment={comment_id} | ingress={ingress}")
            return CommentProcessResult.IN_PROGRESS
        logger.info(f"[Comment] enforce dedup skip(완료/억제됨) | comment={comment_id} | ingress={ingress}")
        return CommentProcessResult.DUPLICATE_COMPLETED

    durably_accepted = _handle_comment_impl(token, comment_id, username, text, media_id, commenter_id)
    if not durably_accepted:
        # P0(260715 Codex 4차 리뷰): retry_queue enqueue 자체가 실패한 경우 —
        # ACCEPTED로 잘못 보고하면 webhook은 200, poller는 캐시해서 복구 기회가 사라진다.
        return CommentProcessResult.REJECTED_NOT_READY
    return CommentProcessResult.ACCEPTED


def register_retry_handlers(rq) -> None:
    """FP-047 — launcher 시작 시 즉시(eager) 호출해야 함(rq.start() 이전).
    기존 ig_auto_reply/ig_followup처럼 실패 시점에 지연등록하면, 재시작 후 pending
    task가 handler를 못 찾고 dead 처리될 위험이 있음(설계문서 §6 "런타임 제약 재확인")."""
    global _retry_handlers_registered
    rq.register("comment_airtable_record", _retry_record_comment)
    _retry_handlers_registered = True
