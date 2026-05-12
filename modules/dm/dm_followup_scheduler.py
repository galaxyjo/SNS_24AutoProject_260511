# modules/dm/dm_followup_scheduler.py
# 자동응답 후 팔로업 DM 스케줄러 (APScheduler BackgroundScheduler)
# bridge_status='auto_replied' 레코드를 5분마다 폴링 → relay_scheduled_at 도래 시 팔로업 DM 발송

import os
import json as _json
import logging
import requests
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

FOLLOWUP_DELAY_MINUTES = int(os.getenv("FOLLOWUP_DELAY_MINUTES", "1440"))  # 기본 24시간

FOLLOWUP_TEMPLATE = (
    "안녕하세요! 지난번 단가 문의 감사드립니다 😊\n"
    "혹시 추가 궁금하신 사항이나 주문 의향이 있으시면 편하게 말씀해주세요!\n"
    "특별 할인 조건도 협의 가능합니다 🎁"
)

_scheduler: BackgroundScheduler | None = None


# ── Airtable 헬퍼 ─────────────────────────────────────────────────────────────

def _at_headers() -> dict:
    return {
        "Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY", ""),
        "Content-Type": "application/json; charset=utf-8",
    }


def _at_patch(record_id: str, fields: dict) -> None:
    base = os.getenv("AIRTABLE_BASE_ID", "")
    body = _json.dumps({"fields": fields}, ensure_ascii=False).encode("utf-8")
    resp = requests.patch(
        f"https://api.airtable.com/v0/{base}/Lead_Interactions/{record_id}",
        headers=_at_headers(),
        data=body,
        timeout=15,
    )
    if not resp.ok:
        logger.error(f"[Followup] Airtable PATCH 실패 | {resp.status_code} {resp.text[:200]}")


def _at_get_due_records() -> list[dict]:
    """bridge_status='auto_replied' 이고 relay_scheduled_at <= now 인 레코드를 조회한다."""
    base = os.getenv("AIRTABLE_BASE_ID", "")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    formula = f"AND({{bridge_status}}='auto_replied', {{relay_scheduled_at}}<='{now_iso}')"
    try:
        resp = requests.get(
            f"https://api.airtable.com/v0/{base}/Lead_Interactions",
            headers={"Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY", "")},
            params={
                "filterByFormula": formula,
                "sort[0][field]": "relay_scheduled_at",
                "sort[0][direction]": "asc",
                "maxRecords": 20,
            },
            timeout=15,
        )
        return resp.json().get("records", [])
    except Exception as exc:
        logger.error(f"[Followup] 폴링 조회 실패 | {exc}")
        return []


# ── Page Messages API ─────────────────────────────────────────────────────────

def _get_page_token() -> str:
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
    return user_token


def send_followup_ig_dm(igsid: str) -> bool:
    page_id    = os.getenv("FACEBOOK_PAGE_ID", "")
    page_token = _get_page_token()

    body = _json.dumps({
        "recipient":      {"id": igsid},
        "message":        {"text": FOLLOWUP_TEMPLATE},
        "messaging_type": "MESSAGE_TAG",
        "tag":            "CONFIRMED_EVENT_UPDATE",
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
        logger.info(f"[Followup] IG DM 발송 완료 | to={igsid} | msg_id={msg_id}")
        return True

    logger.error(f"[Followup] IG DM 발송 실패 | {resp.status_code} | {resp.text[:300]}")
    return False


# ── Telegram 알림 ─────────────────────────────────────────────────────────────

def send_telegram_followup(igsid: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return
    text = (
        f"\U0001f4e8 *팔로업 DM 발송 완료*\n"
        f"─────────\n"
        f"\U0001f464 `{igsid}`\n"
        f"\U0001f4ac {FOLLOWUP_TEMPLATE[:80]}..."
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "Markdown"},
            timeout=8,
        )
        logger.info(f"[Followup] Telegram 팔로업 알림 전송 | to={igsid}")
    except Exception as exc:
        logger.warning(f"[Followup] Telegram 알림 실패 | {exc}")


# ── 스케줄 등록 ───────────────────────────────────────────────────────────────

def set_followup_schedule(record_id: str) -> None:
    """auto_reply 완료 직후 relay_scheduled_at = now + FOLLOWUP_DELAY_MINUTES 으로 설정한다."""
    scheduled_at = (
        datetime.now(timezone.utc) + timedelta(minutes=FOLLOWUP_DELAY_MINUTES)
    ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    _at_patch(record_id, {"relay_scheduled_at": scheduled_at})
    logger.info(
        f"[Followup] 팔로업 예약 | record={record_id} | at={scheduled_at} "
        f"(+{FOLLOWUP_DELAY_MINUTES}min)"
    )


# ── 폴링 잡 ──────────────────────────────────────────────────────────────────

def process_due_followups() -> None:
    """5분마다 실행: 팔로업 발송 시각이 된 레코드를 처리한다."""
    records = _at_get_due_records()
    if not records:
        return

    logger.info(f"[Followup] 처리 대상 {len(records)}건")

    for rec in records:
        record_id = rec["id"]
        fields    = rec.get("fields", {})
        igsid     = fields.get("inquiry_user_handle", "")

        if not igsid:
            logger.warning(f"[Followup] igsid 없음 — skip | record={record_id}")
            _at_patch(record_id, {"bridge_status": "followup_error", "last_error_msg": "igsid missing"})
            continue

        sent = send_followup_ig_dm(igsid)

        _at_patch(record_id, {
            "bridge_status": "followup_sent" if sent else "followup_error",
            "last_error_msg": "" if sent else "IG DM send failed",
        })

        if sent:
            send_telegram_followup(igsid)


# ── 스케줄러 시작 ─────────────────────────────────────────────────────────────

def start_scheduler() -> BackgroundScheduler:
    """BackgroundScheduler를 시작하고 반환한다. 이미 실행 중이면 기존 인스턴스를 반환."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        process_due_followups,
        trigger="interval",
        minutes=5,
        id="followup_poll",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(f"[Followup] 스케줄러 시작 | 폴링 간격=5분 | 팔로업 딜레이={FOLLOWUP_DELAY_MINUTES}분")
    return _scheduler
