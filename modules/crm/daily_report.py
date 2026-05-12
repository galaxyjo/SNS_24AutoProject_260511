# modules/crm/daily_report.py
# 매일 18:00 KST(09:00 UTC) Telegram으로 Lead 일일 현황 리포트 발송

import os
import logging
import requests
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def _fetch_today_leads() -> dict:
    """오늘 0시(KST) 이후 생성된 Lead_Interactions 집계."""
    base = os.getenv("AIRTABLE_BASE_ID", "")
    now_utc    = datetime.now(timezone.utc)
    # KST 기준 오늘 00:00 → UTC 전날 15:00
    kst_today  = (now_utc + timedelta(hours=9)).replace(hour=0, minute=0, second=0, microsecond=0)
    utc_start  = (kst_today - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    formula = f"{{relay_scheduled_at}}>='{utc_start}'"
    try:
        resp = requests.get(
            f"https://api.airtable.com/v0/{base}/Lead_Interactions",
            headers={"Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY", "")},
            params={"filterByFormula": formula, "maxRecords": 200},
            timeout=15,
        )
        records = resp.json().get("records", [])
    except Exception as exc:
        logger.error(f"[Report] Airtable 조회 실패 | {exc}")
        return {}

    stats = {"total": 0, "new": 0, "qualified": 0, "converted": 0,
             "hot": 0, "warm": 0, "cold": 0}
    stats["total"] = len(records)

    for rec in records:
        f      = rec.get("fields", {})
        status = f.get("lead_status", "new")
        grade  = f.get("lead_grade", "cold")
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
        logger.info("[Report] 일일 리포트 전송 완료")
    except Exception as exc:
        logger.warning(f"[Report] 전송 실패 | {exc}")
