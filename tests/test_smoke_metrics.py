"""
tests/test_smoke_metrics.py — metrics 모듈 smoke tests

crawl_monitor / kpi_collector._utc_start — 외부 서비스 없이 순수 로직 검증.
"""

import pytest
from datetime import datetime, timezone

import modules.metrics.crawl_monitor as cm_mod
from modules.metrics.kpi_collector import _utc_start


# ── crawl_monitor ─────────────────────────────────────────────────────────────

def test_record_crawl_creates_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(cm_mod, "DB_PATH", tmp_path / "crawl.db")
    results = [
        {"image_url": "https://scontent.example.com/img1.jpg", "content": "text"},
        {"image_url": "",                                        "content": "text only"},
        {"image_url": "https://scontent.example.com/img2.jpg", "content": "text"},
    ]
    cm_mod.record_crawl(results, target_url="https://facebook.com/groups/test")
    stats = cm_mod.get_recent_stats(limit=5)
    assert len(stats) == 1
    assert stats[0]["total"] == 3
    assert stats[0]["with_image"] == 2
    assert stats[0]["without_image"] == 1
    assert stats[0]["image_rate"] == pytest.approx(66.7, abs=0.1)


def test_record_crawl_empty_results(tmp_path, monkeypatch):
    monkeypatch.setattr(cm_mod, "DB_PATH", tmp_path / "crawl2.db")
    cm_mod.record_crawl([], target_url="https://facebook.com/groups/test")
    stats = cm_mod.get_recent_stats()
    assert stats[0]["image_rate"] == 0.0
    assert stats[0]["total"] == 0


def test_get_summary_aggregates(tmp_path, monkeypatch):
    monkeypatch.setattr(cm_mod, "DB_PATH", tmp_path / "crawl3.db")
    cm_mod.record_crawl(
        [{"image_url": "url1"}, {"image_url": ""}], target_url="u1"
    )
    cm_mod.record_crawl(
        [{"image_url": "url2"}, {"image_url": "url3"}], target_url="u2"
    )
    summary = cm_mod.get_summary(hours=24)
    assert summary["runs"] == 2
    assert summary["total"] == 4
    assert summary["with_image"] == 3
    assert summary["without_image"] == 1
    assert summary["image_rate"] == pytest.approx(75.0)


def test_get_summary_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(cm_mod, "DB_PATH", tmp_path / "crawl4.db")
    summary = cm_mod.get_summary(hours=24)
    assert summary == {
        "hours": 24, "runs": 0, "total": 0,
        "with_image": 0, "without_image": 0, "image_rate": 0.0,
    }


def test_get_recent_stats_order(tmp_path, monkeypatch):
    monkeypatch.setattr(cm_mod, "DB_PATH", tmp_path / "crawl5.db")
    cm_mod.record_crawl([{"image_url": "a"}], target_url="url_first")
    cm_mod.record_crawl([{"image_url": "b"}, {"image_url": ""}], target_url="url_second")
    stats = cm_mod.get_recent_stats(limit=10)
    # 최신순 반환 — 두 번째 크롤이 먼저
    assert stats[0]["target_url"] == "url_second"
    assert stats[1]["target_url"] == "url_first"


# ── kpi_collector._utc_start ──────────────────────────────────────────────────

def test_utc_start_all_returns_none():
    assert _utc_start("all") is None


def test_utc_start_unknown_returns_none():
    assert _utc_start("unknown_period") is None


def test_utc_start_today_returns_string():
    result = _utc_start("today")
    assert isinstance(result, str)
    assert "T" in result  # ISO 형식


def test_utc_start_7d_is_before_today():
    today = _utc_start("today")
    seven = _utc_start("7d")
    assert seven < today


def test_utc_start_30d_is_before_7d():
    seven  = _utc_start("7d")
    thirty = _utc_start("30d")
    assert thirty < seven
