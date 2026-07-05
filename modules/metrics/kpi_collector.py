"""
modules/metrics/kpi_collector.py — KPI 통계 수집기

Airtable Lead_Interactions / Instagram_Posts 를 집계해 핵심 KPI를 반환하고,
SQLite(db/kpi_snapshots.db)에 시간별 스냅샷을 저장한다.

사용법:
    from modules.metrics.kpi_collector import collect_kpi, run_hourly_snapshot

    kpi = collect_kpi("today")   # 오늘 KST 기준
    kpi = collect_kpi("7d")      # 최근 7일
    kpi = collect_kpi("all")     # 전체
    run_hourly_snapshot()        # 스케줄러 잡 (시간별 저장)
"""

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from modules.infra.airtable_repository import AirtableRepository
from modules.common.retry_queue import get_retry_queue
from modules.common.logger import get_logger

logger = get_logger(__name__)

DB_PATH = Path(__file__).resolve().parents[2] / "db" / "kpi_snapshots.db"

BRIDGE_PIPELINE = [
    "dm_received", "auto_replied",
    "followup1_sent", "followup2_sent", "followup3_sent",
    "converted",
]


# ── 기간 계산 ─────────────────────────────────────────────────────────────────

def _utc_start(period: str) -> str | None:
    """period → UTC 시작 ISO 문자열. 'all'이면 None."""
    if period == "all":
        return None
    now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
    if period == "today":
        kst_start = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "7d":
        kst_start = now_kst - timedelta(days=7)
    elif period == "30d":
        kst_start = now_kst - timedelta(days=30)
    else:
        return None
    return (kst_start - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ── Airtable 조회 ─────────────────────────────────────────────────────────────

def _fetch_leads(start: str | None) -> list[dict]:
    try:
        repo = AirtableRepository()
        return repo.fetch_all_lead_interactions(since_utc=start)
    except Exception as exc:
        logger.error(f"[KPI] Lead_Interactions 조회 실패 | {exc}")
        return []


def _fetch_posts() -> list[dict]:
    try:
        repo = AirtableRepository()
        return repo.fetch_all_instagram_posts()
    except Exception as exc:
        logger.error(f"[KPI] Instagram_Posts 조회 실패 | {exc}")
        return []


# ── 개별 지표 계산 ────────────────────────────────────────────────────────────

def _upload_stats(posts: list[dict]) -> dict:
    total  = len(posts)
    posted = sum(1 for p in posts if p.get("post_status") == "posted")
    ready  = sum(1 for p in posts if p.get("post_status") == "ready")
    failed = sum(1 for p in posts if p.get("post_status") == "failed")
    return {
        "total":        total,
        "posted":       posted,
        "ready":        ready,
        "failed":       failed,
        "success_rate": round(posted / total * 100, 1) if total else 0.0,
    }


def _lead_stats(leads: list[dict]) -> dict:
    dm = [l for l in leads if l.get("conversation_channel") != "instagram_comment"]
    total     = len(dm)
    converted = sum(1 for l in dm if l.get("lead_status") == "converted")
    return {
        "total":           total,
        "converted":       converted,
        "conversion_rate": round(converted / total * 100, 1) if total else 0.0,
        "hot":             sum(1 for l in dm if l.get("lead_grade") == "hot"),
        "warm":            sum(1 for l in dm if l.get("lead_grade") == "warm"),
        "cold":            sum(1 for l in dm if l.get("lead_grade") == "cold"),
    }


def _followup_stats(leads: list[dict]) -> dict:
    dm    = [l for l in leads if l.get("conversation_channel") != "instagram_comment"]
    total = len(dm)
    pipe  = {s: sum(1 for l in dm if l.get("bridge_status") == s) for s in BRIDGE_PIPELINE}
    sent  = sum(pipe.get(s, 0) for s in ["followup1_sent", "followup2_sent", "followup3_sent"])
    return {
        "pipeline":      pipe,
        "followup_sent": sent,
        "followup_rate": round(sent / total * 100, 1) if total else 0.0,
    }


def _comment_stats(leads: list[dict]) -> dict:
    comments  = [l for l in leads if l.get("conversation_channel") == "instagram_comment"]
    price_kws = ["단가", "가격", "얼마", "price", "cost"]
    neg_kws   = ["사기", "불만", "최악", "환불"]
    price_cnt = sum(1 for c in comments if any(k in (c.get("inquiry_message") or "").lower() for k in price_kws))
    neg_cnt   = sum(1 for c in comments if any(k in (c.get("inquiry_message") or "") for k in neg_kws))
    return {
        "total":         len(comments),
        "price_inquiry": price_cnt,
        "negative":      neg_cnt,
    }


def _queue_stats() -> dict:
    try:
        return get_retry_queue().stats()
    except Exception as exc:
        logger.warning(f"[KPI] Queue 통계 조회 실패 | {exc}")
        return {}


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────

def collect_kpi(period: str = "today") -> dict:
    """
    period: 'today' | '7d' | '30d' | 'all'
    반환: {period, collected_at, upload, lead, followup, comment, queue}
    """
    start = _utc_start(period)
    posts = _fetch_posts()
    leads = _fetch_leads(start)

    result = {
        "period":       period,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "upload":       _upload_stats(posts),
        "lead":         _lead_stats(leads),
        "followup":     _followup_stats(leads),
        "comment":      _comment_stats(leads),
        "queue":        _queue_stats(),
    }
    logger.info(
        f"[KPI] 수집 완료 | period={period} | "
        f"leads={result['lead']['total']} | "
        f"upload_rate={result['upload']['success_rate']}% | "
        f"conv_rate={result['lead']['conversion_rate']}%"
    )
    return result


# ── SQLite 스냅샷 ─────────────────────────────────────────────────────────────

def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS kpi_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_at TEXT    NOT NULL,
            period      TEXT    NOT NULL,
            kpi_json    TEXT    NOT NULL
        )
    """)
    con.commit()
    con.close()


def save_snapshot(kpi: dict) -> None:
    """KPI dict를 SQLite에 저장."""
    _ensure_db()
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            "INSERT INTO kpi_snapshots (snapshot_at, period, kpi_json) VALUES (?, ?, ?)",
            (kpi["collected_at"], kpi["period"], json.dumps(kpi, ensure_ascii=False)),
        )
        con.commit()
        con.close()
        logger.debug(f"[KPI] 스냅샷 저장 | {kpi['collected_at']}")
    except Exception as exc:
        logger.error(f"[KPI] 스냅샷 저장 실패 | {exc}")


def load_snapshots(limit: int = 48) -> list[dict]:
    """최근 스냅샷 N건 반환 (최신순)."""
    _ensure_db()
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            "SELECT kpi_json FROM kpi_snapshots ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        con.close()
        return [json.loads(r[0]) for r in rows]
    except Exception as exc:
        logger.error(f"[KPI] 스냅샷 로드 실패 | {exc}")
        return []


# ── 스케줄러 잡 ───────────────────────────────────────────────────────────────

def run_hourly_snapshot() -> None:
    """시간별 KPI 스냅샷 수집·저장 — 스케줄러에서 호출."""
    kpi = collect_kpi("today")
    save_snapshot(kpi)
