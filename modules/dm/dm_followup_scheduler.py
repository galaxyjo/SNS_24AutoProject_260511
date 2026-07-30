# modules/dm/dm_followup_scheduler.py
# 다단계 팔로업 DM 스케줄러 (14단계 고도화)
# bridge_status 흐름: auto_replied → followup1_sent → followup2_sent → followup3_sent
# 각 단계 간격: FOLLOWUP_STAGE_DELAY_MINUTES (기본 1440분 = 24시간)

import os
import json as _json
import logging
import requests
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from modules.common.logger import get_logger
from modules.common.meta_graph import messaging_graph_url
from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import LeadBridgeStatus, LeadInteraction

logger = get_logger(__name__)

_repo = AirtableRepository()

# 단계별 딜레이 (분) — 모든 단계 동일 간격 사용
STAGE_DELAY_MINUTES = int(os.getenv("FOLLOWUP_STAGE_DELAY_MINUTES",
                                    os.getenv("FOLLOWUP_DELAY_MINUTES", "1440")))

# bridge_status → 다음 단계 상태
STAGE_NEXT_STATUS: dict[str, str] = {
    "auto_replied":   "followup1_sent",
    "followup1_sent": "followup2_sent",
    "followup2_sent": "followup3_sent",
}

# 단계별 팔로업 메시지 (현재 bridge_status 기준)
STAGE_TEMPLATES: dict[str, str] = {
    "auto_replied": (
        "안녕하세요! 지난번 단가 문의 감사드립니다 \U0001f60a\n"
        "혹시 추가 궁금하신 사항이나 주문 의향이 있으시면 편하게 말씀해주세요!\n"
        "특별 할인 조건도 협의 가능합니다 \U0001f381"
    ),
    "followup1_sent": (
        "안녕하세요! 지난번 문의 이후에도 관심 있으신지요? \U0001f60a\n"
        "현재 소량 주문도 가능하며, 샘플 발송도 협의 가능합니다.\n"
        "언제든지 편하게 연락 주세요!"
    ),
    "followup2_sent": (
        "마지막으로 인사드립니다 \U0001f64f\n"
        "혹시 나중에 필요하실 때 언제든지 연락 주세요!\n"
        "좋은 조건으로 도움드리겠습니다. \U0001f4e6"
    ),
}

_scheduler: BackgroundScheduler | None = None

# LOST 타임아웃 (분) — 기본 72h
LOST_TIMEOUT_MINUTES = int(os.getenv("LOST_TIMEOUT_MINUTES", "4320"))


def mark_lost(record_id: str, reason: str = "followup_timeout") -> None:
    """레코드를 LOST 상태로 전환."""
    _repo.mark_lead_lost(record_id, reason)


def process_lost_candidates() -> None:
    """5분마다 실행 — LOST 전환 대상 처리 (DRY_RUN 모드)."""
    dry_run = os.getenv("LOST_DRY_RUN", "true").lower() != "false"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    records: list[LeadInteraction] = _repo.fetch_leads_due(
        [LeadBridgeStatus.FOLLOWUP3_SENT], before_iso=now_iso
    )
    if not records:
        return
    logger.info(f"[LOST] 대상 {len(records)}건 | dry_run={dry_run}")
    for rec in records:
        record_id = rec["id"]
        igsid     = rec.get("igsid", "")
        if dry_run:
            logger.warning(f"[LOST][DRY_RUN] 전환 대상 | record={record_id} | igsid={igsid}")
        else:
            mark_lost(record_id, reason="followup_timeout")
            logger.warning(f"[LOST] 전환 완료 | record={record_id} | igsid={igsid}")


# ── Page Messages API ─────────────────────────────────────────────────────────

def _get_page_token() -> str:
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
    return user_token


def _send_ig_dm(igsid: str, text: str) -> bool:
    page_id    = os.getenv("FACEBOOK_PAGE_ID", "")
    page_token = _get_page_token()

    body = _json.dumps({
        "recipient":      {"id": igsid},
        "message":        {"text": text},
        "messaging_type": "MESSAGE_TAG",
        "tag":            "CONFIRMED_EVENT_UPDATE",
    }, ensure_ascii=False).encode("utf-8")

    resp = requests.post(
        messaging_graph_url(f"{page_id}/messages"),
        headers={
            "Authorization": "Bearer " + page_token,
            "Content-Type": "application/json; charset=utf-8",
        },
        data=body,
        timeout=15,
    )
    if resp.ok:
        logger.info(f"[Followup] IG DM 발송 완료 | to={igsid} | msg_id={resp.json().get('message_id','')}")
        return True
    logger.error(f"[Followup] IG DM 발송 실패 | {resp.status_code} {resp.text[:300]}")
    return False


# ── Telegram 알림 ─────────────────────────────────────────────────────────────

def _send_telegram_followup(igsid: str, stage_label: str, preview: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return
    text = (
        f"\U0001f4e8 *팔로업 DM 발송 완료* [{stage_label}]\n"
        f"─────────\n"
        f"\U0001f464 `{igsid}`\n"
        f"\U0001f4ac {preview[:80]}..."
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "Markdown"},
            timeout=8,
        )
    except Exception as exc:
        logger.warning(f"[Followup] Telegram 알림 실패 | {exc}")


# ── 스케줄 등록 ───────────────────────────────────────────────────────────────

def set_followup_schedule(record_id: str) -> None:
    """자동응답 완료 직후 호출 — relay_scheduled_at = now + STAGE_DELAY_MINUTES."""
    scheduled_at = (
        datetime.now(timezone.utc) + timedelta(minutes=STAGE_DELAY_MINUTES)
    ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    _repo.update_followup_status(
        record_id, LeadBridgeStatus.AUTO_REPLIED, next_scheduled_at=scheduled_at
    )
    logger.info(f"[Followup] 1차 팔로업 예약 | record={record_id} | at={scheduled_at}")


# ── 폴링 잡 ──────────────────────────────────────────────────────────────────

def process_due_followups() -> None:
    """5분마다 실행 — 발송 시각 도래한 팔로업 레코드를 단계별 처리."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    records: list[LeadInteraction] = _repo.fetch_leads_due(
        [LeadBridgeStatus.AUTO_REPLIED, LeadBridgeStatus.FOLLOWUP1_SENT, LeadBridgeStatus.FOLLOWUP2_SENT],
        before_iso=now_iso,
    )
    if not records:
        return

    logger.info(f"[Followup] 처리 대상 {len(records)}건")

    for rec in records:
        record_id   = rec["id"]
        igsid       = rec.get("igsid", "")
        cur_status  = rec.get("bridge_status", "")
        next_status = STAGE_NEXT_STATUS.get(cur_status)
        template    = STAGE_TEMPLATES.get(cur_status, "")

        if not igsid or not next_status or not template:
            logger.warning(f"[Followup] 상태 불명 — skip | record={record_id} status={cur_status}")
            _repo._patch_lead_interaction(record_id, {
                "bridge_status": "followup_error",
                "last_error_msg": f"unknown stage: {cur_status}",
            })
            continue

        stage_num = {"followup1_sent": "1차", "followup2_sent": "2차", "followup3_sent": "3차"}.get(
            next_status, next_status
        )
        sent = _send_ig_dm(igsid, template)

        if not sent:
            from modules.common.retry_queue import get_retry_queue
            def _retry_followup(payload: dict) -> None:
                if not _send_ig_dm(payload["igsid"], payload["text"]):
                    raise RuntimeError("followup DM send failed")
            rq = get_retry_queue()
            rq.register("ig_followup", _retry_followup)
            rq.start()
            rq.enqueue("ig_followup", {"igsid": igsid, "text": template})
            logger.warning(f"[Followup] DM 발송 실패 → retry queue 등록 | to={igsid}")

        # 다음 단계 예약 — 3차 발송 시 LOST 타임아웃 기준 시각 설정
        if sent:
            delay = LOST_TIMEOUT_MINUTES if next_status == "followup3_sent" else STAGE_DELAY_MINUTES
            next_at = (
                datetime.now(timezone.utc) + timedelta(minutes=delay)
            ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            _repo.update_followup_status(
                record_id, LeadBridgeStatus(next_status), next_scheduled_at=next_at
            )
        else:
            _repo._patch_lead_interaction(record_id, {
                "bridge_status": "followup_error",
                "last_error_msg": "IG DM send failed",
            })

        if sent:
            _send_telegram_followup(igsid, stage_num, template)


# ── 스케줄러 시작 ─────────────────────────────────────────────────────────────

def start_scheduler() -> BackgroundScheduler:
    """BackgroundScheduler 시작. 이미 실행 중이면 기존 인스턴스 반환."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")

    # 팔로업 폴링 — 5분 간격
    _scheduler.add_job(
        process_due_followups,
        trigger="interval",
        minutes=5,
        id="followup_poll",
        replace_existing=True,
    )

    # LOST 전환 체크 — 5분 간격
    _scheduler.add_job(
        process_lost_candidates,
        trigger="interval",
        minutes=5,
        id="lost_check",
        replace_existing=True,
    )

    # 댓글 폴링 — 5분 간격
    from modules.comment.comment_poller import poll_new_comments
    _scheduler.add_job(
        poll_new_comments,
        trigger="interval",
        minutes=5,
        id="comment_poll",
        replace_existing=True,
    )

    # 일일 Lead 리포트 — 매일 09:00 UTC (18:00 KST)
    from modules.crm.daily_report import send_daily_report
    _scheduler.add_job(
        send_daily_report,
        trigger=CronTrigger(hour=9, minute=0, timezone="UTC"),
        id="daily_lead_report",
        replace_existing=True,
    )

    # ERR-089 관측 보강 — 이 스케줄러 루프 생존을 60초 간격으로 남긴다.
    _scheduler.add_job(
        lambda: logger.info("[SchedulerHeartbeat][dm] alive"),
        trigger="interval",
        seconds=60,
        id="scheduler_heartbeat_dm",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"[Followup] 스케줄러 시작 | 팔로업 폴링=5분 | 댓글 폴링=5분 | "
        f"단계 간격={STAGE_DELAY_MINUTES}분 | 일일 리포트=09:00 UTC"
    )
    return _scheduler
