"""STEP 3-G+ (260902) — launcher/main.py::_job_yuna_friend_request + 스케줄 등록 검증.

실제 브라우저/Airtable/Meta 호출 없이 Mock 으로만 확인한다. Runtime 상태변경 없음.

Target Test (GPT 260902 지시문):
  1. crawler 시간과 friend job 시간이 겹치지 않는다
  2. friend job 은 friend_canary_from_group 에 max_requests=1 을 넘긴다
  3. 하루 누적이 한도(10)면 friend_canary_from_group 을 호출하지 않는다
  4. checkpoint 결과면 그 실행은 즉시 끝나고 Slack 경고를 보낸다
"""

from datetime import datetime, timedelta

import pytest


@pytest.fixture
def launcher_main(monkeypatch):
    monkeypatch.setenv("OUTBOUND_FRIEND_SCHEDULE_ENABLED", "true")
    from launcher import main as m
    return m


def _patch_limits(monkeypatch, friend_cap=10):
    class _Repo:
        def get_account_outbound_limits(self, code):
            return {"follow": 20, "friend": friend_cap, "comment": 0}

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _Repo()
    )


def _patch_env(monkeypatch, launcher_main, busy=False, hour=12):
    """260903 24시간 분산: AdsPower idle + 활동시간대 안으로 고정."""
    monkeypatch.setattr(launcher_main, "_adspower_busy", lambda *a, **k: busy)

    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 3, hour, 0, 0)
    monkeypatch.setattr(launcher_main, "datetime", _DT)


def _patch_daily_count(monkeypatch, n, blocked=""):
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_connector._friend_daily_count",
        lambda code: n,
    )
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_connector._friend_daily_blocked",
        lambda code: blocked,
    )


# ── Target Test 1 : 크롤과의 충돌은 AdsPower 양보로 처리 (jitter 도입으로 고정위상 폐기) ──
def test_yields_when_adspower_busy(monkeypatch, launcher_main):
    """AdsPower 프로필을 크롤 등이 쓰는 중이면 이번 회차를 양보한다."""
    _patch_limits(monkeypatch)
    _patch_daily_count(monkeypatch, 3)
    _patch_env(monkeypatch, launcher_main, busy=True)
    called = []
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run",
        lambda *a, **kw: called.append(kw) or {"status": "done"},
    )
    launcher_main._job_yuna_friend_request.__wrapped__()
    assert called == []


def test_skips_outside_active_hours(monkeypatch, launcher_main):
    """활동시간대(08~23시) 밖이면 발송하지 않는다 — 새벽 발송은 봇 시그널."""
    _patch_limits(monkeypatch)
    _patch_daily_count(monkeypatch, 3)
    _patch_env(monkeypatch, launcher_main, busy=False, hour=3)
    called = []
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run",
        lambda *a, **kw: called.append(kw) or {"status": "done"},
    )
    launcher_main._job_yuna_friend_request.__wrapped__()
    assert called == []


def test_passes_max_requests_1_and_not_dry_run(monkeypatch, launcher_main):
    _patch_limits(monkeypatch)
    _patch_daily_count(monkeypatch, 3)
    _patch_env(monkeypatch, launcher_main)
    seen = {}

    def _fake(account_code=None, **kw):
        seen.update(kw)
        seen["account_code"] = account_code
        return {"status": "done", "daily_count": 4, "sent": 1, "groups_visited": ["PG-016"]}

    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run", _fake
    )
    launcher_main._job_yuna_friend_request.__wrapped__()

    assert seen["max_per_run"] == 1          # 실행당 1건 (24시간 분산)
    assert seen["dry_run"] is False
    assert seen["account_code"] == "IDN-000041"


# ── Target Test 3 : 한도 도달이면 canary 미호출 ─────────────────────────────
def test_daily_limit_reached_no_canary_call(monkeypatch, launcher_main):
    _patch_limits(monkeypatch, friend_cap=10)
    _patch_daily_count(monkeypatch, 10)
    called = []
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run",
        lambda *a, **k: called.append(1),
    )
    launcher_main._job_yuna_friend_request.__wrapped__()
    assert called == []


def test_day_blocked_skips_before_canary(monkeypatch, launcher_main):
    """제한 신호가 뜬 날: 같은 날 이후 friend slot 은 실제 요청 함수를 호출하지 않는다."""
    _patch_daily_count(monkeypatch, 2, blocked="checkpoint:security_check")
    called = []
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run",
        lambda *a, **k: called.append(1),
    )
    # Airtable 조회조차 하면 안 됨(차단 확인이 최우선)
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository",
        lambda: (_ for _ in ()).throw(AssertionError("blocked 상태에서 Airtable 조회 금지")),
    )
    launcher_main._job_yuna_friend_request.__wrapped__()
    assert called == []


def test_not_blocked_proceeds_to_canary(monkeypatch, launcher_main):
    """정상 상태(차단 아님) → 다음 friend slot 실행 가능."""
    _patch_limits(monkeypatch)
    _patch_daily_count(monkeypatch, 3, blocked="")
    _patch_env(monkeypatch, launcher_main)
    called = []
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run",
        lambda *a, **kw: called.append(kw) or {
            "status": "done", "friend": {"result": "success", "daily_count": 4, "sent": 1}},
    )
    launcher_main._job_yuna_friend_request.__wrapped__()
    assert len(called) == 1 and called[0]["max_per_run"] == 1


def test_cap_zero_fail_closed_no_canary_call(monkeypatch, launcher_main):
    _patch_limits(monkeypatch, friend_cap=0)
    _patch_daily_count(monkeypatch, 0)
    called = []
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run",
        lambda *a, **k: called.append(1),
    )
    launcher_main._job_yuna_friend_request.__wrapped__()
    assert called == []


# ── Target Test 4 : checkpoint → 즉시 종료 + Slack 경고 ─────────────────────
def test_checkpoint_result_alerts_and_stops(monkeypatch, launcher_main):
    _patch_limits(monkeypatch)
    _patch_daily_count(monkeypatch, 2)
    _patch_env(monkeypatch, launcher_main)
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run",
        lambda *a, **kw: {"status": "stopped", "reason": "checkpoint:login_approval",
                          "daily_count": 2, "sent": 0},
    )
    alerts = []
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: alerts.append(msg))
    launcher_main._job_yuna_friend_request.__wrapped__()
    assert alerts and "checkpoint" in alerts[0]


def test_success_result_sends_info_slack(monkeypatch, launcher_main):
    _patch_limits(monkeypatch)
    _patch_daily_count(monkeypatch, 2)
    _patch_env(monkeypatch, launcher_main)
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run",
        lambda *a, **kw: {"status": "done", "daily_count": 3, "sent": 1,
                          "groups_visited": ["PG-023"]},
    )
    alerts = []
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: alerts.append(msg))
    launcher_main._job_yuna_friend_request.__wrapped__()
    assert alerts and "성공" in alerts[0]


# ── Flag OFF / 등록 여부 ────────────────────────────────────────────────────
def test_flag_off_skips_job_body(monkeypatch):
    monkeypatch.setenv("OUTBOUND_FRIEND_SCHEDULE_ENABLED", "false")
    from launcher import main as m

    called = []
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_pipeline.friend_daily_run",
        lambda *a, **k: called.append(1),
    )
    m._job_yuna_friend_request.__wrapped__()
    assert called == []


def test_scheduler_registers_friend_job_when_flag_on(launcher_main):
    sched = launcher_main._build_scheduler()
    try:
        job = sched.get_job("yuna_friend_request")
        assert job is not None
        # 크롤 잡도 같이 등록돼 있어야(회귀 확인)
        assert sched.get_job("fb_crawl") is not None
    finally:
        try:
            sched.shutdown(wait=False)
        except Exception:
            pass


def test_scheduler_omits_friend_job_when_flag_off(monkeypatch):
    monkeypatch.setenv("OUTBOUND_FRIEND_SCHEDULE_ENABLED", "false")
    from launcher import main as m

    sched = m._build_scheduler()
    try:
        assert sched.get_job("yuna_friend_request") is None
        assert sched.get_job("fb_crawl") is not None
    finally:
        try:
            sched.shutdown(wait=False)
        except Exception:
            pass
