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
from modules.infra.repository_interface import LeadInteractionCreate

from modules.dm.dm_auto_reply import detect_price_inquiry, handle_price_inquiry
from modules.dm.dm_followup_scheduler import start_scheduler
from modules.crm.lead_scorer import is_repeat_inquiry, calc_score, update_lead_score
from modules.crm.order_detector import detect_order, handle_order_conversion
from modules.comment.comment_auto_reply import handle_comment

PAGE_TOKEN        = os.getenv("INSTA_ACCESS_TOKEN")
IG_USER_ID        = os.getenv("INSTA_IG_USER_ID")
VERIFY_TOKEN      = os.getenv("WEBHOOK_VERIFY_TOKEN", "snssecret2024")
WEBHOOK_PORT      = int(os.getenv("WEBHOOK_PORT", "5000"))

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
    if not _TG_TOKEN or not _TG_CHAT:
        return
    text = (
        f"\U0001f4e9 *Instagram DM 수신*\n"
        f"─────────────────\n"
        f"\U0001f464 `{sender_igsid}`\n"
        f"\U0001f4ac {message_text[:200]}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            json={"chat_id": _TG_CHAT, "text": text, "parse_mode": "Markdown"},
            timeout=8,
        )
        logger.info(f"[Telegram] 수신 알림 전송 | from={sender_igsid}")
    except Exception as exc:
        logger.warning(f"[Telegram] 알림 실패 | {exc}")


def record_interaction(sender_igsid: str, message_text: str) -> str:
    """수신된 DM 1건을 Lead_Interactions에 기록하고 record_id를 반환한다."""
    record_id = _repo.create_lead_interaction(LeadInteractionCreate(
        igsid=sender_igsid,
        source="instagram_dm",
        interaction_type="dm_received",
        occurred_at=_now_iso(),
        inquiry_message=message_text,
    ))
    logger.info(f"[Lead_Interactions] CREATED | from={sender_igsid} | record={record_id}")
    return record_id


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

    for entry in data.get("entry", []):
        # ── comments webhook 이벤트 처리 ──────────────────────────────────────
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
                handle_comment(cid, cusername, ctext, cmedia, commenter_id=ccommenter_id)
            except Exception as exc:
                logger.error(f"[Comment/WH] 처리 실패 | cid={cid} | {exc}")

        for messaging in entry.get("messaging", []):
            sender_id  = messaging.get("sender", {}).get("id")
            message    = messaging.get("message", {})
            text       = message.get("text", "").strip()
            received_at = datetime.now(timezone.utc)

            if message.get("is_echo") or not sender_id or not text:
                continue

            logger.info(f"[DM] from={sender_id} | text={text[:100]}")

            try:
                record_id = record_interaction(sender_id, text)
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
