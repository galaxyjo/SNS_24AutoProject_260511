"""261102 STEP 1-C — 5분 폴러(_job_insta_upload) 예약시각·하루 상한 Gate 검증.

실제 Airtable·게시·자격증명 없음 — 전부 Mock. claim_post_for_upload 호출 여부를
"게시 경로 진입" 증거로 쓴다(False를 반환해 publish 직전에서 멈춤).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

BKK = timezone(timedelta(hours=7))


def _at(hour, minute):
    return datetime(2026, 11, 2, hour, minute, tzinfo=BKK)


@pytest.fixture
def launcher(monkeypatch):
    monkeypatch.delenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", raising=False)
    monkeypatch.delenv("POLLER_SLOT_GATE_ENABLED", raising=False)
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
    from launcher import main as m
    return m


class _Stop(BaseException):
    """publish_single 모의 — claim 이후(=슬롯 소비 후) 실제 게시 직전에서 잡 실행을 끊는다."""


# ── 순수 함수 ────────────────────────────────────────────────────────────────
def test_blank_post_hours_keeps_legacy_behavior(launcher):
    assert launcher._poller_slot_allowed({"post_hours": ""}, _at(3, 30)) == (True, "NO_POST_HOURS")
    assert launcher._poller_slot_allowed({}, _at(3, 30)) == (True, "NO_POST_HOURS")


def test_before_first_slot_blocked_and_due_slot_allowed(launcher):
    acct = {"post_hours": "6,10,19", "daily_post_limit": 3}
    assert launcher._poller_slot_allowed(acct, _at(5, 59)) == (False, "BEFORE_FIRST_SLOT")
    assert launcher._poller_slot_allowed(acct, _at(6, 0)) == (True, "SLOT_DUE")


def test_missed_window_is_caught_up_later(launcher):
    """정각 창(00~04분)을 놓쳐도 같은 시각 이후 폴링에서 보충된다(누락 아님)."""
    acct = {"post_hours": "6,10,19", "daily_post_limit": 3}
    assert launcher._poller_slot_allowed(acct, _at(6, 40), 0) == (True, "SLOT_DUE")
    assert launcher._poller_slot_allowed(acct, _at(6, 40), 1) == (False, "SLOT_CONSUMED")


def test_actual_daily_count_capped_by_limit_not_just_slot_count(launcher):
    """daily_post_limit는 슬롯 수 절단 + 실제 소비 건수 비교로 하루 게시 건수를 막는다."""
    acct = {"post_hours": "6,10,19,22", "daily_post_limit": 3}
    assert launcher._poller_slot_allowed(acct, _at(23, 0), 2)[0] is True
    assert launcher._poller_slot_allowed(acct, _at(23, 0), 3) == (False, "SLOT_CONSUMED")  # 22시 슬롯은 상한 밖


@pytest.mark.parametrize("raw", ["abc", "25", "-1"])
def test_invalid_post_hours_fail_closed(launcher, raw):
    ok, reason = launcher._poller_slot_allowed({"post_hours": raw, "daily_post_limit": 3}, _at(6, 0))
    assert ok is False and reason.startswith("post_hours")


# ── _job_insta_upload 통합(Mock) ─────────────────────────────────────────────
def _setup(monkeypatch, m, tmp_path, *, post_hours, limit=3, codes=("IDN-000041",), now=None, claim=True):
    monkeypatch.setattr(m, "_POLLER_SLOT_STATE_PATH", tmp_path / "poller_slot_state.json")
    calls = SimpleNamespace(claim=[], mark=[], publish=[])
    records = [
        {"post_id": f"rec{i}", "image_url": "http://img", "caption": "c", "hashtag": "",
         "account_code_ref": code}
        for i, code in enumerate(codes)
    ]

    class Repo:
        def fetch_pending_posts(self, limit=50):
            return [dict(r) for r in records]

        def get_publish_account(self, code):
            return {"account_code": code, "api_provider": "facebook_login", "ig_user_id": "x",
                    "credential_key": "YUNA", "automation_enabled": True,
                    "post_hours": post_hours, "daily_post_limit": limit}

        def claim_post_for_upload(self, post_id):
            calls.claim.append(post_id)
            return claim

        def mark_post_result(self, post_id, result):
            calls.mark.append(post_id)

    def _publish(post_id, *a, **k):
        calls.publish.append(post_id)
        raise _Stop()

    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: Repo())
    monkeypatch.setattr("modules.common.canary_classification.validate_publication_candidate",
                        lambda *a, **k: None)
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: SimpleNamespace(ig_user_id="x", access_token="t"),
    )
    monkeypatch.setattr(m, "publish_single", _publish)
    if now is not None:
        class _DT(datetime):
            @classmethod
            def now(cls, tz=None):
                return now
        monkeypatch.setattr(m, "datetime", _DT)
    return calls


def _run(m):
    try:
        m._job_insta_upload()
    except _Stop:
        pass


def test_flag_off_ignores_post_hours(monkeypatch, launcher, tmp_path):
    calls = _setup(monkeypatch, launcher, tmp_path, post_hours="6,10,19", now=_at(3, 30))
    _run(launcher)
    assert calls.claim == ["rec0"]                       # 기존 동작: 시각 무관 게시 경로 진입
    assert not (tmp_path / "poller_slot_state.json").exists()


def test_flag_on_blocks_before_first_slot_without_state_change(monkeypatch, launcher, tmp_path):
    monkeypatch.setenv("POLLER_SLOT_GATE_ENABLED", "true")
    calls = _setup(monkeypatch, launcher, tmp_path, post_hours="6,10,19", now=_at(3, 30))
    _run(launcher)
    assert calls.claim == [] and calls.mark == [] and calls.publish == []


def test_flag_on_blank_post_hours_unchanged(monkeypatch, launcher, tmp_path):
    monkeypatch.setenv("POLLER_SLOT_GATE_ENABLED", "true")
    calls = _setup(monkeypatch, launcher, tmp_path, post_hours="", now=_at(3, 30))
    _run(launcher)
    assert calls.claim == ["rec0"]


def test_flag_on_one_per_account_per_poll(monkeypatch, launcher, tmp_path):
    """같은 폴링에서 같은 계정의 서로 다른 ready 2건 중 1건만 claim(다른 계정은 진행)."""
    monkeypatch.setenv("POLLER_SLOT_GATE_ENABLED", "true")
    calls = _setup(monkeypatch, launcher, tmp_path, post_hours="10", now=_at(10, 1),
                   codes=("IDN-000041", "IDN-000041", "IDN-000011"), claim=False)
    _run(launcher)
    assert calls.claim == ["rec0", "rec2"]


def test_restart_in_same_slot_does_not_publish_second_record(monkeypatch, launcher, tmp_path):
    """슬롯 1개 소비 후 프로세스가 재시작돼도(상태 파일만 남음) 같은 슬롯의 다른 ready는 게시되지 않는다."""
    monkeypatch.setenv("POLLER_SLOT_GATE_ENABLED", "true")
    calls = _setup(monkeypatch, launcher, tmp_path, post_hours="10", now=_at(10, 1))
    _run(launcher)
    assert calls.claim == ["rec0"] and calls.publish == ["rec0"]
    # "재시작": 메모리 상태 없이 같은 파일로 다시 한 번 폴링 — 이번엔 다른 ready 레코드
    calls2 = _setup(monkeypatch, launcher, tmp_path, post_hours="10", now=_at(10, 3), codes=("IDN-000041",))
    calls2_state = (tmp_path / "poller_slot_state.json").read_text(encoding="utf-8")
    assert '"n": 1' in calls2_state
    monkeypatch.setattr(launcher, "_POLLER_SLOT_STATE_PATH", tmp_path / "poller_slot_state.json")
    _run(launcher)
    assert calls2.claim == [] and calls2.publish == []


def test_second_slot_opens_after_next_hour(monkeypatch, launcher, tmp_path):
    monkeypatch.setenv("POLLER_SLOT_GATE_ENABLED", "true")
    _setup(monkeypatch, launcher, tmp_path, post_hours="10,14", now=_at(10, 1))
    _run(launcher)
    calls = _setup(monkeypatch, launcher, tmp_path, post_hours="10,14", now=_at(14, 2))
    _run(launcher)
    assert calls.claim == ["rec0"]                       # 14시 슬롯은 새로 열린다


def test_state_resets_on_new_day(monkeypatch, launcher, tmp_path):
    monkeypatch.setenv("POLLER_SLOT_GATE_ENABLED", "true")
    _setup(monkeypatch, launcher, tmp_path, post_hours="10", now=_at(10, 1))
    _run(launcher)
    nxt = datetime(2026, 11, 3, 10, 1, tzinfo=BKK)
    calls = _setup(monkeypatch, launcher, tmp_path, post_hours="10", now=nxt)
    _run(launcher)
    assert calls.claim == ["rec0"]


def test_corrupt_state_file_fails_closed(monkeypatch, launcher, tmp_path):
    monkeypatch.setenv("POLLER_SLOT_GATE_ENABLED", "true")
    calls = _setup(monkeypatch, launcher, tmp_path, post_hours="10", now=_at(10, 1))
    (tmp_path / "poller_slot_state.json").write_text("{not json", encoding="utf-8")
    _run(launcher)
    assert calls.claim == [] and calls.publish == []