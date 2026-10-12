"""261012 P3 — AdsPower 일일 Open 카운터(start_browser 성공 시만 +1)와
크롤 잡 상한(_job_fb_crawl). AdsPower·Facebook·Airtable·Slack 실호출 0건(mock).
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


_OK = {"code": 0, "data": {"debug_port": "9222"}}
_LIMIT = {"code": -1, "msg": "Exceeding open daily limit"}


def test_counter_increments_only_on_success(monkeypatch):
    assert fc.adspower_opens_today() == 0
    _patch_start(monkeypatch, _OK)
    assert fc.start_browser("u1") == "9222"
    assert fc.start_browser("u1") == "9222"
    assert fc.adspower_opens_today() == 2

    _patch_start(monkeypatch, _LIMIT)
    with pytest.raises(RuntimeError):
        fc.start_browser("u1")
    assert fc.adspower_opens_today() == 2


def test_date_rollover_resets(monkeypatch):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    fc._ADSPOWER_OPEN_DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
    fc._ADSPOWER_OPEN_DAILY_PATH.write_text(json.dumps({"date": yesterday, "count": 19}), encoding="utf-8")
    assert fc.adspower_opens_today() == 0
    _patch_start(monkeypatch, _OK)
    fc.start_browser("u1")
    assert json.loads(fc._ADSPOWER_OPEN_DAILY_PATH.read_text(encoding="utf-8"))["count"] == 1


def test_counter_write_failure_does_not_block_open(monkeypatch):
    _patch_start(monkeypatch, _OK)

    def _boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(type(fc._ADSPOWER_OPEN_DAILY_PATH), "write_text", _boom)
    assert fc.start_browser("u1") == "9222"


@pytest.fixture
def m():
    from launcher import main as _m
    return _m


KW = {"target_publish_account_code_ref": "IDN-000041", "data_classification": "production"}


def test_crawl_skips_at_or_above_ceiling(monkeypatch, m):
    calls = []
    monkeypatch.setattr(fc, "run_all_accounts", lambda **k: calls.append(k) or {"account1": 1})
    monkeypatch.setattr(fc, "adspower_opens_today", lambda: m._CRAWL_OPEN_CEILING)
    m._job_fb_crawl(**KW)
    assert calls == []


def test_crawl_runs_below_ceiling(monkeypatch, m):
    calls = []
    monkeypatch.setattr(fc, "run_all_accounts", lambda **k: calls.append(k) or {"account1": 1})
    monkeypatch.setattr(fc, "adspower_opens_today", lambda: m._CRAWL_OPEN_CEILING - 1)
    m._job_fb_crawl(**KW)
    assert len(calls) == 1


def test_default_ceiling_is_10(m):
    assert m._CRAWL_OPEN_CEILING == 10


def test_friend_path_not_gated(monkeypatch):
    # 친구요청 경로는 get_driver → start_browser 를 그대로 쓰며 크롤 상한을 보지 않는다.
    fc._ADSPOWER_OPEN_DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    fc._ADSPOWER_OPEN_DAILY_PATH.write_text(json.dumps({"date": today, "count": 15}), encoding="utf-8")
    _patch_start(monkeypatch, _OK)
    assert fc.start_browser("k1bto3j4") == "9222"
    assert fc.adspower_opens_today() == 16
