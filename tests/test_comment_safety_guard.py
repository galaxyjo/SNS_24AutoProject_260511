"""comment_safety_guard.py 단위테스트 — 캠페인 allowlist / 쿨다운 / 일일예산 / circuit breaker."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from modules.comment import comment_safety_guard as guard


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "_CAMPAIGN_CONFIG_PATH", tmp_path / "campaign.json")
    monkeypatch.setattr(guard, "_COOLDOWN_STATE_PATH", tmp_path / "cooldown.json")
    monkeypatch.setattr(guard, "_BUDGET_STATE_PATH", tmp_path / "budget.json")
    guard._circuit_failure_count = 0
    guard._circuit_open_until = 0.0
    yield


# ── 캠페인 게시물 allowlist ──────────────────────────────────────────

def test_is_campaign_post_false_when_config_missing():
    assert guard.is_campaign_post("media-1") is False


def test_is_campaign_post_true_only_for_listed_media():
    guard._CAMPAIGN_CONFIG_PATH.write_text(
        json.dumps({"media_ids": ["media-1"]}), encoding="utf-8"
    )
    assert guard.is_campaign_post("media-1") is True
    assert guard.is_campaign_post("media-2") is False


def test_is_campaign_post_false_for_empty_media_id():
    assert guard.is_campaign_post("") is False


# ── 사용자별 쿨다운 ───────────────────────────────────────────────────

def test_cooldown_blocks_repeat_user_within_window(monkeypatch):
    monkeypatch.setattr(guard, "COOLDOWN_HOURS", 24)
    assert guard.is_user_in_cooldown("buyer1") is False
    guard.mark_user_replied("buyer1")
    assert guard.is_user_in_cooldown("buyer1") is True


def test_cooldown_expires_after_window(monkeypatch):
    monkeypatch.setattr(guard, "COOLDOWN_HOURS", 24)
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    guard._save_json(guard._COOLDOWN_STATE_PATH, {"buyer1": old_ts})
    assert guard.is_user_in_cooldown("buyer1") is False


# ── 일일 예산 ─────────────────────────────────────────────────────────

def test_daily_budget_enforced(monkeypatch):
    monkeypatch.setattr(guard, "DAILY_BUDGET", 2)
    assert guard.consume_daily_budget() is True
    assert guard.consume_daily_budget() is True
    assert guard.consume_daily_budget() is False


# ── 상태 파일 손상 시 fail-closed (Codex 리뷰 반영) ─────────────────────

def test_is_campaign_post_fails_closed_when_config_corrupted():
    guard._CAMPAIGN_CONFIG_PATH.write_text("{not valid json", encoding="utf-8")
    assert guard.is_campaign_post("media-1") is False


def test_cooldown_fails_closed_when_state_corrupted():
    guard._COOLDOWN_STATE_PATH.write_text("{not valid json", encoding="utf-8")
    assert guard.is_user_in_cooldown("buyer1") is True


def test_daily_budget_fails_closed_when_state_corrupted():
    guard._BUDGET_STATE_PATH.write_text("{not valid json", encoding="utf-8")
    assert guard.consume_daily_budget() is False


def test_mark_user_replied_recovers_from_corrupted_state():
    guard._COOLDOWN_STATE_PATH.write_text("{not valid json", encoding="utf-8")
    guard.mark_user_replied("buyer1")
    assert guard.is_user_in_cooldown("buyer1") is True


def test_save_json_writes_atomically_no_leftover_tmp_file():
    guard.mark_user_replied("buyer1")
    tmp_path = guard._COOLDOWN_STATE_PATH.with_suffix(
        guard._COOLDOWN_STATE_PATH.suffix + ".tmp"
    )
    assert guard._COOLDOWN_STATE_PATH.exists()
    assert not tmp_path.exists()


# ── Circuit Breaker ───────────────────────────────────────────────────

def test_circuit_breaker_opens_after_threshold(monkeypatch):
    monkeypatch.setattr(guard, "CIRCUIT_FAILURE_THRESHOLD", 3)
    monkeypatch.setattr(guard, "CIRCUIT_COOLDOWN_MINUTES", 30)
    assert guard.circuit_is_open() is False
    guard.record_circuit_failure()
    guard.record_circuit_failure()
    assert guard.circuit_is_open() is False
    guard.record_circuit_failure()
    assert guard.circuit_is_open() is True


def test_circuit_breaker_resets_on_success(monkeypatch):
    monkeypatch.setattr(guard, "CIRCUIT_FAILURE_THRESHOLD", 3)
    guard.record_circuit_failure()
    guard.record_circuit_failure()
    guard.record_circuit_success()
    guard.record_circuit_failure()
    guard.record_circuit_failure()
    assert guard.circuit_is_open() is False
