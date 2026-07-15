"""tests/test_comment_poll_targets.py — comment_poll_targets 상태머신 검증
(260715 Package 1 Phase A, Codex 5차 리뷰 합의 사항)."""

import json

import pytest

from modules.comment import comment_poll_targets as pt
from modules.comment import comment_campaign_config as cfg


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(pt, "_DB_PATH", tmp_path / "poll_targets_test.db")
    monkeypatch.setattr(pt, "_conn", None)
    monkeypatch.setattr(cfg, "_CONFIG_PATH", tmp_path / "campaign.json")
    yield


def _write_campaign(media_ids):
    cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": media_ids}), encoding="utf-8")


class TestSync:
    def test_new_media_becomes_pending_baseline(self):
        _write_campaign(["m1", "m2"])
        assert pt.sync_from_campaign_json() is True
        assert pt.get_target("m1")["state"] == "PENDING_BASELINE"
        assert pt.get_target("m2")["state"] == "PENDING_BASELINE"

    def test_active_media_removed_from_json_becomes_paused_immediately(self):
        _write_campaign(["m1"])
        pt.sync_from_campaign_json()
        # m1을 수동으로 ACTIVE까지 승격(baseline 절차 우회 — 이 테스트는 sync 동작만 검증)
        pt.apply_baseline("m1", "2026-07-16T00:00:00+00:00", 0, "hash")
        pt.verify_baseline("m1")
        assert pt.activate("m1") is True
        assert pt.get_target("m1")["state"] == "ACTIVE"

        _write_campaign([])  # m1 제거
        assert pt.sync_from_campaign_json() is True
        assert pt.get_target("m1")["state"] == "PAUSED"

    def test_readded_paused_media_goes_back_to_pending_baseline_not_active(self):
        _write_campaign(["m1"])
        pt.sync_from_campaign_json()
        pt.apply_baseline("m1", "2026-07-16T00:00:00+00:00", 0, "hash")
        pt.verify_baseline("m1")
        pt.activate("m1")
        assert pt.get_target("m1")["state"] == "ACTIVE"

        _write_campaign([])
        pt.sync_from_campaign_json()
        assert pt.get_target("m1")["state"] == "PAUSED"

        _write_campaign(["m1"])  # 재등록
        pt.sync_from_campaign_json()
        row = pt.get_target("m1")
        assert row["state"] == "PENDING_BASELINE", "재등록은 곧바로 ACTIVE로 복귀하면 안 됨(재baseline 강제)"
        assert row["baseline_verified_at"] is None, "이전 baseline 메타데이터는 초기화돼야 함"

    def test_corrupted_json_fails_closed_without_mutating_table(self):
        _write_campaign(["m1"])
        pt.sync_from_campaign_json()
        cfg._CONFIG_PATH.write_text("{not valid json", encoding="utf-8")
        assert pt.sync_from_campaign_json() is False
        assert pt.get_target("m1")["state"] == "PENDING_BASELINE", "손상된 JSON으로 기존 상태를 건드리면 안 됨"

    def test_get_active_media_ids_only_returns_active(self):
        _write_campaign(["m1", "m2"])
        pt.sync_from_campaign_json()
        pt.apply_baseline("m1", "2026-07-16T00:00:00+00:00", 0, "hash")
        pt.verify_baseline("m1")
        pt.activate("m1")
        assert pt.get_active_media_ids() == ["m1"]


class TestBaselineLifecycle:
    def test_activate_without_verify_fails(self):
        _write_campaign(["m1"])
        pt.sync_from_campaign_json()
        assert pt.activate("m1") is False
        assert pt.get_target("m1")["state"] == "PENDING_BASELINE"

    def test_apply_without_prior_sync_fails(self):
        # m1이 poll_targets에 없는 상태에서 apply 시도 — WHERE state='PENDING_BASELINE' 매칭 안 됨
        assert pt.apply_baseline("m1", "2026-07-16T00:00:00+00:00", 0, "hash") is False

    def test_verify_without_apply_fails(self):
        _write_campaign(["m1"])
        pt.sync_from_campaign_json()
        assert pt.verify_baseline("m1") is False

    def test_full_lifecycle_reaches_active(self):
        _write_campaign(["m1"])
        pt.sync_from_campaign_json()
        assert pt.apply_baseline("m1", "2026-07-16T00:00:00+00:00", 3, "abc123") is True
        assert pt.verify_baseline("m1") is True
        assert pt.activate("m1") is True
        row = pt.get_target("m1")
        assert row["state"] == "ACTIVE"
        assert row["baseline_comment_count"] == 3
        assert row["baseline_source_hash"] == "abc123"


class TestFailureTracking:
    def test_record_poll_failure_increments_and_resets_on_success(self):
        _write_campaign(["m1"])
        pt.sync_from_campaign_json()
        assert pt.record_poll_failure("m1") == 1
        assert pt.record_poll_failure("m1") == 2
        pt.record_poll_success("m1")
        assert pt.get_target("m1")["consecutive_failures"] == 0

    def test_mark_alerted_persists(self):
        _write_campaign(["m1"])
        pt.sync_from_campaign_json()
        assert pt.get_target("m1")["last_alerted_at"] is None
        pt.mark_alerted("m1")
        assert pt.get_target("m1")["last_alerted_at"] is not None
