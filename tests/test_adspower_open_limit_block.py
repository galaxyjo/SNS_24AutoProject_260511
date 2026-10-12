"""261012 P5 — AdsPower 한도 초과 응답의 "recovery after N hours"를 blocked_until로 기록하고,
그 시각 전에는 크롤·친구 잡이 Open을 시도하지 않는다. 실호출 0건(mock).
db 경로는 tests/conftest.py 의 _isolate_production_state_paths 로 tmp 격리된다.
"""

import json
from datetime import datetime, timedelta

import pytest

import modules.sns.facebook_crawler as fc


class _UrlResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b


def _patch_start(monkeypatch, payload):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _UrlResp(payload))


def _limit(hours):
    return {"code": -1, "msg": f"Exceeding open daily limit, recovery after {hours} hours"}


_OK = {"code": 0, "data": {"debug_port": "9222"}}


def _state():
    return json.loads(fc._ADSPOWER_OPEN_DAILY_PATH.read_text(encoding="utf-8"))


def _hours_until(s):
    return (datetime.strptime(s, "%Y-%m-%d %H:%M:%S") - datetime.now()).total_seconds() / 3600


def test_limit_response_records_blocked_until(monkeypatch):
    _patch_start(monkeypatch, _limit(17))
    with pytest.raises(RuntimeError):
        fc.start_browser("u1")
    until = fc.adspower_open_blocked_until()
    assert until and 16.9 < _hours_until(until) <= 17.0


def test_block_capped_at_24h(monkeypatch):
    _patch_start(monkeypatch, _limit(99))
    with pytest.raises(RuntimeError):
        fc.start_browser("u1")
    assert _hours_until(fc.adspower_open_blocked_until()) <= 24.0


@pytest.mark.parametrize("msg", ["Exceeding open daily limit", "some other error", "", None])
def test_unparseable_message_no_block(monkeypatch, msg):
    _patch_start(monkeypatch, {"code": -1, "msg": msg})
    with pytest.raises(RuntimeError):
        fc.start_browser("u1")
    assert fc.adspower_open_blocked_until() == ""


def test_expired_block_is_ignored():
    past = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    fc._write_open_state({"blocked_until": past})
    assert fc.adspower_open_blocked_until() == ""


def test_success_clears_block_and_keeps_count(monkeypatch):
    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    fc._write_open_state({"date": today, "count": 4, "blocked_until": future})
    _patch_start(monkeypatch, _OK)
    assert fc.start_browser("u1") == "9222"
    s = _state()
    assert s["count"] == 5 and "blocked_until" not in s


def test_limit_does_not_change_count(monkeypatch):
    today = datetime.now().strftime("%Y-%m-%d")
    fc._write_open_state({"date": today, "count": 7})
    _patch_start(monkeypatch, _limit(5))
    with pytest.raises(RuntimeError):
        fc.start_browser("u1")
    assert fc.adspower_opens_today() == 7


# ── 잡 스킵 ──

KW = {"target_publish_account_code_ref": "IDN-000041", "data_classification": "production"}


@pytest.fixture
def m(monkeypatch):
    monkeypatch.setenv("OUTBOUND_FRIEND_SCHEDULE_ENABLED", "true")
    from launcher import main as _m
    return _m


def test_crawl_skips_while_blocked(monkeypatch, m):
    calls = []
    monkeypatch.setattr(fc, "run_all_accounts", lambda **k: calls.append(k) or {})
    monkeypatch.setattr(fc, "adspower_open_blocked_until", lambda: "2099-01-01 00:00:00")
    m._job_fb_crawl(**KW)
    assert calls == []


def test_crawl_runs_when_not_blocked(monkeypatch, m):
    calls = []
    monkeypatch.setattr(fc, "run_all_accounts", lambda **k: calls.append(k) or {})
    monkeypatch.setattr(fc, "adspower_open_blocked_until", lambda: "")
    monkeypatch.setattr(fc, "adspower_opens_today", lambda: 0)
    m._job_fb_crawl(**KW)
    assert len(calls) == 1


def _in_active_hours(monkeypatch, m):
    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 3, 12, 0, 0)
    monkeypatch.setattr(m, "datetime", _DT)


def test_friend_skips_while_blocked_before_repo(monkeypatch, m):
    _in_active_hours(monkeypatch, m)
    monkeypatch.setattr(fc, "adspower_open_blocked_until", lambda: "2099-01-01 00:00:00")

    def _repo_must_not_be_called():
        raise AssertionError("차단 중에는 Airtable 조회 전에 스킵해야 한다")

    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", _repo_must_not_be_called)
    m._job_yuna_friend_request()


def test_friend_proceeds_past_gate_when_not_blocked(monkeypatch, m):
    _in_active_hours(monkeypatch, m)
    monkeypatch.setattr(fc, "adspower_open_blocked_until", lambda: "")
    reached = []
    monkeypatch.setattr(
        "modules.interaction_engine.outbound_connector._friend_daily_blocked",
        lambda code: reached.append(1) or "test-stop",
    )
    m._job_yuna_friend_request()
    assert reached == [1]
