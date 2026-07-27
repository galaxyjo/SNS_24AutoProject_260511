# modules/dm/dm_receiver.py
# Instagram Messaging Webhook 수신 서버 (Meta Graph API)
# ngrok URL: https://danuta-overdramatic-whirly.ngrok-free.dev/webhook

# load_dotenv(override=True) 를 다른 모듈 import 전에 호출해야
# 이미 OS 환경에 캐시된 구버전 값을 .env 최신값으로 덮어씀
import os
from dotenv import load_dotenv
load_dotenv(override=True)

import logging
import requests
from datetime import datetime, timezone

from flask import Flask, request, jsonify, abort

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import (
    LeadInteractionCreate,
    RepositoryError,
    RepositoryValidationError,
)

from modules.dm.dm_auto_reply import detect_price_inquiry, handle_price_inquiry, _mask_igsid, _telegram_preview
from modules.dm.dm_followup_scheduler import start_scheduler
from modules.crm.lead_scorer import is_repeat_inquiry, calc_score, update_lead_score
from modules.crm.order_detector import detect_order, handle_order_conversion
from modules.comment.comment_auto_reply import process_comment_event, CommentProcessResult

PAGE_TOKEN        = os.getenv("INSTA_ACCESS_TOKEN")
IG_USER_ID        = os.getenv("INSTA_IG_USER_ID")
VERIFY_TOKEN      = os.getenv("WEBHOOK_VERIFY_TOKEN", "snssecret2024")
WEBHOOK_PORT      = int(os.getenv("WEBHOOK_PORT", "5000"))

# Bundle B(260726) 킬스위치 — false(기본값)면 아래 계정 역조회·account_code_ref 기록을
# 전혀 수행하지 않고 기존 DM 경로와 완전히 동일하게 동작한다(Codex/GPT 승인 조건).
DM_ACCOUNT_ROUTING_ENABLED = os.getenv("DM_ACCOUNT_ROUTING_ENABLED", "false").lower() == "true"

_repo = AirtableRepository()

_TG_TOKEN         = os.getenv("TELEGRAM_BOT_TOKEN")
_TG_CHAT          = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

from modules.ingest.domeggook_ingest import domeggook_ingest_bp
app.register_blueprint(domeggook_ingest_bp)


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def send_telegram(sender_igsid: str, message_text: str) -> None:
    """ERR-066: IGSID/원문 무마스킹 노출 수정(260715) — dm_auto_reply의 기존 마스킹
    유틸을 재사용. cross-module private import는 긴급수정 허용 범위, 장기적으로는
    공용 유틸로 승격 검토 대상(Codex 리뷰 260715)."""
    if not _TG_TOKEN or not _TG_CHAT:
        return
    text = (
        f"\U0001f4e9 *Instagram DM 수신*\n"
        f"─────────────────\n"
        f"\U0001f464 `{_mask_igsid(sender_igsid)}`\n"
        f"\U0001f4ac {_telegram_preview(message_text)}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            json={"chat_id": _TG_CHAT, "text": text, "parse_mode": "Markdown"},
            timeout=8,
        )
        logger.info(f"[Telegram] 수신 알림 전송 | from={_mask_igsid(sender_igsid)}")
    except Exception as exc:
        logger.warning(f"[Telegram] 알림 실패 | {exc}")


def record_interaction(sender_igsid: str, message_text: str, account_code_ref: str = "") -> str:
    """수신된 DM 1건을 Lead_Interactions에 기록하고 record_id를 반환한다.
    account_code_ref는 선택값(Bundle B) — 비어있으면 기존과 완전히 동일하게 동작한다."""
    create_data = LeadInteractionCreate(
        igsid=sender_igsid,
        source="instagram_dm",
        interaction_type="dm_received",
        occurred_at=_now_iso(),
        inquiry_message=message_text,
    )
    if account_code_ref:
        create_data["account_code_ref"] = account_code_ref
    record_id = _repo.create_lead_interaction(create_data)
    logger.info(f"[Lead_Interactions] CREATED | from={sender_igsid} | record={record_id}")
    return record_id


def _resolve_dm_account_code_ref(recipient_id: str | None) -> str:
    """Bundle B(260726) — recipient.id로 Account_Registry를 역조회해 account_code_ref를 얻는다.
    킬스위치가 꺼져있거나 조회에 실패해도 예외를 전파하지 않는다(fail-open) —
    이 함수의 결과와 무관하게 DM 생성·자동응답은 항상 계속돼야 한다."""
    if not DM_ACCOUNT_ROUTING_ENABLED:
        return ""
    if not recipient_id:
        logger.error("[AccountRouting] ACCOUNT_ROUTING_RECIPIENT_MISSING")
        return ""
    try:
        account = _repo.get_publish_account_by_ig_user_id(recipient_id)
    except RepositoryValidationError as exc:
        logger.error(f"[AccountRouting] ACCOUNT_ROUTING_AMBIGUOUS | recipient_id={recipient_id} | {exc}")
        return ""
    except RepositoryError as exc:
        logger.exception(f"[AccountRouting] ACCOUNT_ROUTING_LOOKUP_FAILED | recipient_id={recipient_id} | {exc}")
        return ""
    if account is None:
        logger.error(f"[AccountRouting] ACCOUNT_ROUTING_NOT_FOUND | recipient_id={recipient_id}")
        return ""
    return account["account_code"]


# ── Webhook 엔드포인트 ────────────────────────────────────────────────────────

@app.get("/webhook")
def verify_webhook():
    """Meta App Dashboard Webhook 등록 시 호출되는 검증 핸들러."""
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("[Webhook] 검증 성공 → challenge 반환")
        return challenge, 200

    logger.warning(f"[Webhook] 검증 실패 | mode={mode} | token={token}")
    abort(403)


@app.post("/webhook")
def receive_webhook():
    """Instagram DM 수신 → 기록 → 단가 문의 감지 → 자동 응답."""
    data = request.get_json(silent=True)
    if not data:
        abort(400)

    if data.get("object") != "instagram":
        return jsonify({"status": "ignored"}), 200

    # P0(260715 Codex 3·4차 리뷰): poller의 5분 주기 스윕은 완전한 안전망이 아니다
    # (최근 게시물 조회 범위 밖/댓글이 다음 폴링 전 삭제됨/Graph API 반복실패 등) —
    # 댓글 이벤트가 durable하게 접수되지 않았으면 200으로 뭉개지 않고 Meta의 자체
    # 재전송을 유도한다("빠른 200"의 전제는 먼저 영속 저장이 됐다는 것).
    # IN_PROGRESS(활성 worker만 보유, durable 백업 없음)도 실패로 취급 — 200으로 뭉개면
    # Meta 재전송이라는 유일한 복구 경로까지 스스로 차단하게 된다. RETRY_OWNED(retry_queue.db가
    # payload를 durable 보유)만 200 가능.
    #
    # 2단계 처리(260715 Codex 4차 리뷰): 댓글을 먼저 전부 처리해 durable-accept 여부를
    # 확정한 뒤에만 messaging(DM)을 처리한다 — 한 요청에 댓글 실패+DM 성공이 섞여 있는데
    # 그대로 503을 반환하면, Meta가 전체 배치를 재전송하면서 이미 처리된 DM까지 다시
    # 처리돼 DM 쪽에 새로운 중복(Airtable 재기록·Telegram 재알림 등)을 만들 수 있다.
    durable_accept_failed = False
    _account_code_cache: dict[str, str] = {}  # Bundle B — 요청 단위 recipient.id 캐시(중복 조회 방지)
    _NON_DURABLE_RESULTS = (CommentProcessResult.REJECTED_NOT_READY, CommentProcessResult.IN_PROGRESS)

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            val          = change.get("value", {})
            cid          = val.get("id", "")
            ctext        = val.get("text", "").strip()
            cfrom        = val.get("from", {})
            cusername    = cfrom.get("username", "") or cfrom.get("id", "")
            ccommenter_id = cfrom.get("id", "")
            cmedia       = val.get("media", {}).get("id", "")
            if not cid or not ctext:
                continue
            logger.info(f"[Comment/WH] from=@{cusername} | text={ctext[:100]}")
            try:
                result = process_comment_event(cid, cusername, ctext, cmedia, ingress="webhook", commenter_id=ccommenter_id)
                if result in _NON_DURABLE_RESULTS:
                    durable_accept_failed = True
            except Exception as exc:
                logger.error(f"[Comment/WH] 처리 실패(durable accept 실패, 재전송 유도) | cid={cid} | {exc}")
                durable_accept_failed = True

    if durable_accept_failed:
        # DM(messaging)은 아직 손대지 않았으므로, 재전송돼도 DM 쪽 중복 처리는 일어나지 않는다.
        return jsonify({"status": "durable_accept_failed"}), 503

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id    = messaging.get("sender", {}).get("id")
            recipient_id = messaging.get("recipient", {}).get("id")
            message    = messaging.get("message", {})
            text       = message.get("text", "").strip()
            received_at = datetime.now(timezone.utc)

            if message.get("is_echo") or not sender_id or not text:
                continue

            # ERR-066: app.log는 Telegram보다 오래 보존·검색·백업되므로 원문 미포함(260715)
            logger.info(f"[DM] from={_mask_igsid(sender_id)} | text_len={len(text)}")

            # Bundle B(260726) — 계정 역조회는 DM 생성/자동응답과 완전히 분리된 예외 경계.
            # 이 블록의 실패가 아래 DM 처리를 절대 막지 않는다(fail-open).
            if recipient_id in _account_code_cache:
                account_code_ref = _account_code_cache[recipient_id]
            else:
                account_code_ref = _resolve_dm_account_code_ref(recipient_id)
                if recipient_id:
                    _account_code_cache[recipient_id] = account_code_ref

            try:
                record_id = record_interaction(sender_id, text, account_code_ref=account_code_ref)
                send_telegram(sender_id, text)
            except Exception as exc:
                logger.error(f"[Airtable] 기록 실패 | sender_id={sender_id} | {exc}")
                continue

            # Lead 스코어링
            try:
                repeat    = is_repeat_inquiry(sender_id)
                has_order = detect_order(text)
                has_price = detect_price_inquiry(text)
                score, grade = calc_score(
                    is_repeat=repeat,
                    has_order_keyword=has_order,
                    has_price_keyword=has_price,
                )
                update_lead_score(record_id, score, grade)
                logger.info(f"[Scorer] score={score} grade={grade} | from={sender_id}")
            except Exception as exc:
                logger.warning(f"[Scorer] 스코어링 실패 | {exc}")

            # 주문 전환 감지 (단가 자동응답보다 우선)
            if detect_order(text):
                logger.info(f"[Order] 주문 의사 감지 | from={sender_id}")
                try:
                    handle_order_conversion(record_id, sender_id, text)
                except Exception as exc:
                    logger.error(f"[Order] 전환 처리 실패 | sender_id={sender_id} | {exc}")

            # 단가 문의 감지 → 자동 응답 (주문이 아닌 경우)
            elif detect_price_inquiry(text):
                logger.info(f"[AutoReply] 단가 문의 감지 | from={sender_id}")
                try:
                    handle_price_inquiry(record_id, sender_id, text, received_at)
                except Exception as exc:
                    logger.error(f"[AutoReply] 처리 실패 | sender_id={sender_id} | {exc}")

    return jsonify({"status": "ok"}), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok", "ig_user_id": IG_USER_ID}), 200


# ── 진입점 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"[Webhook] 서버 시작 | port={WEBHOOK_PORT}")
    logger.info("[Webhook] ngrok: https://danuta-overdramatic-whirly.ngrok-free.dev/webhook")
    start_scheduler()
    app.run(host="0.0.0.0", port=WEBHOOK_PORT, debug=False)
