# modules/crm/daily_report.py
# 매일 18:00 KST(09:00 UTC) Telegram으로 Lead 일일 현황 리포트 발송

import os
import requests
from datetime import datetime, timezone, timedelta

from modules.common.logger import get_logger
from modules.infra.airtable_repository import AirtableRepository

logger = get_logger(__name__)

_repo = AirtableRepository()


def _fetch_today_leads() -> dict:
    """오늘 0시(KST) 이후 생성된 Lead_Interactions 집계."""
    now_utc   = datetime.now(timezone.utc)
    kst_today = (now_utc + timedelta(hours=9)).replace(hour=0, minute=0, second=0, microsecond=0)
    utc_start = (kst_today - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    try:
        records = _repo.fetch_today_lead_stats(utc_start, limit=200)
    except Exception as exc:
        logger.error(f"[Report] Airtable 조회 실패 | {exc}")
        return {}

    stats = {"total": 0, "new": 0, "qualified": 0, "converted": 0,
             "hot": 0, "warm": 0, "cold": 0}
    stats["total"] = len(records)

    for rec in records:
        status = rec.get("lead_status", "new")
        grade  = rec.get("lead_grade", "cold")
        if status in stats:
            stats[status] += 1
        if grade in stats:
            stats[grade] += 1

    return stats


def send_daily_report() -> None:
    """일일 Lead 현황을 Telegram으로 발송한다."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        logger.warning("[Report] Telegram 미설정 — 리포트 생략")
        return

    stats = _fetch_today_leads()
    if not stats:
        return

    total     = stats["total"]
    converted = stats["converted"]
    rate      = f"{converted / total * 100:.1f}%" if total > 0 else "0.0%"
    date_kst  = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")

    msg = (
        f"\U0001f4ca *일일 Lead 리포트* ({date_kst})\n"
        f"─────────────────────\n"
        f"\U0001f4e5 총 신규 문의: *{total}건*\n"
        f"\U00002705 전환(주문): *{converted}건* ({rate})\n"
        f"─────────────────────\n"
        f"\U0001f525 Hot: {stats['hot']}건\n"
        f"\U0001f324 Warm: {stats['warm']}건\n"
        f"❄️ Cold: {stats['cold']}건\n"
        f"─────────────────────\n"
        f"\U0001f4cc Qualified: {stats['qualified']}건"
    )

    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg, "parse_mode": "Markdown"},
            timeout=8,
        )
        logger.info("[Report] Telegram 리포트 전송 완료")
    except Exception as exc:
        logger.warning(f"[Report] Telegram 전송 실패 | {exc}")

    # Slack 발송 (SLACK_WEBHOOK_URL 설정 시)
    try:
        from services.slack_notifier import notify_daily_report
        notify_daily_report(stats, date_kst)
        logger.info("[Report] Slack 리포트 전송 완료")
    except Exception as exc:
        logger.warning(f"[Report] Slack 전송 실패 | {exc}")
