"""261015 Threads 장기 토큰 자동 갱신 — modules.common.threads_token + launcher 잡 등록.

네트워크는 전부 가짜(requests.get monkeypatch). DB는 tmp_path에만 만든다.
"""

from datetime import datetime, timedelta

import pytest

import modules.common.threads_token as tt

SEED = "THAAseedtoken0000000000000000"
NEW = "THAAnewtoken11111111111111111"


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.content = b"x"

    def json(self):
        return self._body


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("YUNA_THREADS_ACCESS_TOKEN", SEED)
    return tmp_path / "threads_token.db"


def _fake_get(calls, resp):
    def _get(url, params=None, timeout=None):
        calls.append({"url": url, "params": dict(params or {})})
        return resp
    return _get


def test_seed_from_env_when_db_empty(db):
    assert tt.get_threads_token("YUNA", db_path=db) == SEED
    assert tt.get_token_status("YUNA", db_path=db)["source"] == "env"


def test_first_refresh_calls_official_endpoint_and_stores(db, monkeypatch):
    calls = []
    monkeypatch.setattr(tt.requests, "get", _fake_get(calls, _Resp(200, {"access_token": NEW, "token_type": "bearer", "expires_in": 5183944})))
    now = datetime(2026, 10, 17, 3, 30)
    assert tt.refresh_threads_token("YUNA", now=now, db_path=db) == "refreshed"
    assert calls[0]["url"] == "https://graph.threads.net/refresh_access_token"
    assert calls[0]["params"] == {"grant_type": "th_refresh_token", "access_token": SEED}
    assert tt.get_threads_token("YUNA", db_path=db) == NEW
    st = tt.get_token_status("YUNA", db_path=db)
    assert st["source"] == "db" and st["expires_at"].startswith("2026-12-1")


def test_not_due_within_7_days(db, monkeypatch):
    calls = []
    monkeypatch.setattr(tt.requests, "get", _fake_get(calls, _Resp(200, {"access_token": NEW, "expires_in": 5183944})))
    t0 = datetime(2026, 10, 17, 3, 30)
    tt.refresh_threads_token("YUNA", now=t0, db_path=db)
    assert tt.refresh_threads_token("YUNA", now=t0 + timedelta(days=6), db_path=db) == "not_due"
    assert len(calls) == 1
    assert tt.refresh_threads_token("YUNA", now=t0 + timedelta(days=7), db_path=db) == "refreshed"
    assert calls[-1]["params"]["access_token"] == NEW   # 갱신된 토큰으로 다음 갱신


def test_failure_keeps_existing_token(db, monkeypatch):
    calls = []
    monkeypatch.setattr(tt.requests, "get", _fake_get(calls, _Resp(400, {"error": {"message": "too new"}})))
    assert tt.refresh_threads_token("YUNA", now=datetime(2026, 10, 15, 20, 0), db_path=db) == "failed"
    assert tt.get_threads_token("YUNA", db_path=db) == SEED
    assert tt.get_token_status("YUNA", db_path=db)["source"] == "env"


def test_network_exception_is_failed_not_raised(db, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("down")
    monkeypatch.setattr(tt.requests, "get", boom)
    assert tt.refresh_threads_token("YUNA", db_path=db) == "failed"


def test_no_token_returns_no_token(tmp_path, monkeypatch):
    monkeypatch.delenv("NONE_THREADS_ACCESS_TOKEN", raising=False)
    assert tt.refresh_threads_token("NONE", db_path=tmp_path / "t.db") == "no_token"


def test_token_never_logged(db, monkeypatch):
    lines = []
    monkeypatch.setattr(tt.logger, "info", lambda m, *a, **k: lines.append(m))
    monkeypatch.setattr(tt.logger, "error", lambda m, *a, **k: lines.append(m))
    monkeypatch.setattr(tt.requests, "get", _fake_get([], _Resp(200, {"access_token": NEW, "expires_in": 5183944})))
    tt.refresh_threads_token("YUNA", now=datetime(2026, 10, 17), db_path=db)
    monkeypatch.setattr(tt.requests, "get", _fake_get([], _Resp(400, {"error": {"message": "x"}})))
    tt.refresh_threads_token("YUNA", now=datetime(2026, 10, 30), db_path=db)
    joined = "\n".join(lines)
    assert SEED not in joined and NEW not in joined and lines


class TestSchedulerRegistration:
    def test_flag_off_registers_no_job(self, monkeypatch):
        monkeypatch.delenv("THREADS_TOKEN_REFRESH_ENABLED", raising=False)
        from launcher import main as launcher_main
        sched = launcher_main._build_scheduler()
        assert "threads_token_refresh" not in {j.id for j in sched.get_jobs()}

    def test_flag_on_registers_one_daily_job(self, monkeypatch):
        monkeypatch.setenv("THREADS_TOKEN_REFRESH_ENABLED", "true")
        from launcher import main as launcher_main
        sched = launcher_main._build_scheduler()
        jobs = [j for j in sched.get_jobs() if j.id == "threads_token_refresh"]
        assert len(jobs) == 1 and jobs[0].max_instances == 1

    def test_flag_does_not_change_other_jobs(self, monkeypatch):
        from launcher import main as launcher_main
        monkeypatch.delenv("THREADS_TOKEN_REFRESH_ENABLED", raising=False)
        off = {j.id for j in launcher_main._build_scheduler().get_jobs()}
        monkeypatch.setenv("THREADS_TOKEN_REFRESH_ENABLED", "true")
        on = {j.id for j in launcher_main._build_scheduler().get_jobs()}
        assert on - off == {"threads_token_refresh"} and off <= on

    def test_job_noop_when_flag_off(self, monkeypatch):
        from launcher import main as launcher_main
        monkeypatch.delenv("THREADS_TOKEN_REFRESH_ENABLED", raising=False)
        called = []
        monkeypatch.setattr(tt, "refresh_threads_token", lambda k, **kw: called.append(k) or "refreshed")
        launcher_main._job_threads_token_refresh()
        assert called == []
