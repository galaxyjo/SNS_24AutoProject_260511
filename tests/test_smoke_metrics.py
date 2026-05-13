"""
tests/test_smoke_metrics.py — metrics 모듈 smoke tests

crawl_monitor / kpi_collector._utc_start / airtable_integrity — 외부 서비스 없이 순수 로직 검증.
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


# ── airtable_integrity ────────────────────────────────────────────────────────

def test_check_ig_media_id_no_missing(monkeypatch):
    """Airtable가 빈 목록 반환 → 누락 없음."""
    import modules.metrics.airtable_integrity as ai_mod
    monkeypatch.setattr(
        ai_mod, "check_ig_media_id",
        lambda: {"missing": 0, "record_ids": []},
    )
    result = ai_mod.check_ig_media_id()
    assert result["missing"] == 0
    assert result["record_ids"] == []


def test_check_ig_media_id_airtable_error(monkeypatch):
    """Airtable 조회 실패 시 missing=0 반환 (에러 전파 없음)."""
    from modules.common import airtable_bridge
    def _bad_get_table(_):
        raise RuntimeError("connection error")
    monkeypatch.setattr(airtable_bridge, "get_table", _bad_get_table)

    from modules.metrics.airtable_integrity import check_ig_media_id
    result = check_ig_media_id()
    assert result["missing"] == 0


def test_check_ig_media_id_with_missing(monkeypatch):
    """누락 레코드가 있을 때 count와 record_ids 반환."""
    from modules.common import airtable_bridge

    fake_records = [
        {"id": "recAAA", "fields": {"post_status": "posted", "ig_media_id": ""}},
        {"id": "recBBB", "fields": {"post_status": "posted", "ig_media_id": ""}},
    ]

    class _FakeTable:
        def all(self, formula=None):
            return fake_records

    monkeypatch.setattr(airtable_bridge, "get_table", lambda _: _FakeTable())

    # Slack 발송 억제
    import services.slack_notifier as sn
    monkeypatch.setattr(sn, "send_alert", lambda **kw: True)

    from modules.metrics import airtable_integrity
    import importlib
    importlib.reload(airtable_integrity)

    result = airtable_integrity.check_ig_media_id()
    assert result["missing"] == 2
    assert "recAAA" in result["record_ids"]
    assert "recBBB" in result["record_ids"]
