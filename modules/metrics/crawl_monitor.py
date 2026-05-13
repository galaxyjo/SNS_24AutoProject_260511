"""
modules/metrics/crawl_monitor.py — FB 크롤링 이미지 비율 모니터

크롤 1회 완료 시 결과를 SQLite에 기록하고, 대시보드용 통계를 반환한다.

사용법:
    from modules.metrics.crawl_monitor import record_crawl, get_recent_stats

    record_crawl(results, target_url="https://facebook.com/...")
    stats = get_recent_stats(limit=20)
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from modules.common.logger import get_logger

logger = get_logger(__name__)

DB_PATH = Path(__file__).resolve().parents[2] / "db" / "crawl_stats.db"


def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS crawl_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            crawled_at    TEXT    NOT NULL,
            target_url    TEXT    NOT NULL DEFAULT '',
            total         INTEGER NOT NULL DEFAULT 0,
            with_image    INTEGER NOT NULL DEFAULT 0,
            without_image INTEGER NOT NULL DEFAULT 0,
            image_rate    REAL    NOT NULL DEFAULT 0.0
        )
    """)
    con.commit()
    con.close()


def record_crawl(results: list[dict], target_url: str = "") -> None:
    """크롤 1회 결과를 기록한다. facebook_crawler.run() 완료 후 호출."""
    _ensure_db()
    total         = len(results)
    with_image    = sum(1 for r in results if r.get("image_url"))
    without_image = total - with_image
    image_rate    = round(with_image / total * 100, 1) if total else 0.0
    crawled_at    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            "INSERT INTO crawl_log (crawled_at, target_url, total, with_image, without_image, image_rate) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (crawled_at, target_url, total, with_image, without_image, image_rate),
        )
        con.commit()
        con.close()
        logger.info(
            f"[CrawlMonitor] 기록 | url={target_url[:60]} | "
            f"total={total} | with_image={with_image} | rate={image_rate}%"
        )
    except Exception as exc:
        logger.error(f"[CrawlMonitor] 기록 실패 | {exc}")


def get_recent_stats(limit: int = 48) -> list[dict]:
    """최근 N건 크롤 기록 반환 (최신순)."""
    _ensure_db()
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute(
            "SELECT crawled_at, target_url, total, with_image, without_image, image_rate "
            "FROM crawl_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        con.close()
        return [
            {
                "crawled_at":    r[0],
                "target_url":    r[1],
                "total":         r[2],
                "with_image":    r[3],
                "without_image": r[4],
                "image_rate":    r[5],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(f"[CrawlMonitor] 조회 실패 | {exc}")
        return []


def get_summary(hours: int = 24) -> dict:
    """최근 N시간 집계 요약 반환."""
    _ensure_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        con = sqlite3.connect(DB_PATH)
        row = con.execute(
            "SELECT COUNT(*), SUM(total), SUM(with_image), SUM(without_image) "
            "FROM crawl_log WHERE crawled_at >= ?",
            (cutoff,),
        ).fetchone()
        con.close()
        runs, total, with_img, without_img = row if row else (0, 0, 0, 0)
        total      = total      or 0
        with_img   = with_img   or 0
        without_img = without_img or 0
        return {
            "hours":          hours,
            "runs":           runs or 0,
            "total":          total,
            "with_image":     with_img,
            "without_image":  without_img,
            "image_rate":     round(with_img / total * 100, 1) if total else 0.0,
        }
    except Exception as exc:
        logger.error(f"[CrawlMonitor] 요약 조회 실패 | {exc}")
        return {"hours": hours, "runs": 0, "total": 0, "with_image": 0, "without_image": 0, "image_rate": 0.0}
