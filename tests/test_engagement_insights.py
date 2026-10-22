"""261022 STEP 3-B — engagement_tracker Insights 경로 Target Test.

Flag OFF = 레거시 동작 그대로 / Flag ON = 대상 레코드는 계정 토큰으로 v26 Insights 1회,
레거시 조회에서 제외 / 필수 지표 누락·오류·빈 응답이면 쓰지 않음 / 계정 토큰 혼입 차단.
실제 Airtable·Meta 호출 없음 — 전부 Mock.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from modules.interaction_engine import engagement_tracker as et

NOW = datetime.now(timezone.utc)
RECENT = (NOW - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
OLD = (NOW - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

FULL = {"reach": 10, "saved": 2, "shares": 1, "profile_visits": 3, "likes": 4, "comments": 5, "views": 99}

ACCOUNTS = {
    "IDN-000036": {"account_code": "IDN-000036", "api_provider": "facebook_login",
                   "ig_user_id": "ig36", "credential_key": "AI"},
    "IDN-000041": {"account_code": "IDN-000041", "api_provider": "facebook_login",
                   "ig_user_id": "ig41", "credential_key": "YUNA"},
}
CREDS = {"AI": ("ig36", "tok-AI"), "YUNA": ("ig41", "tok-YUNA")}


def _rec(rid, acct, created=RECENT, media=None, collected=None):
    fields = {"ig_media_id": media or f"m-{rid}", "account_code_ref": acct}
    if collected:
        fields["insights_collected_at"] = collected
    return {"id": rid, "createdTime": created, "fields": fields}


class _Resp:
    def __init__(self, status, payload, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


def _insights_payload(values):
    return {"data": [{"name": k, "period": "lifetime", "values": [{"value": v}]} for k, v in values.items()]}


@pytest.fixture
def env(monkeypatch):
    calls = SimpleNamespace(insights=[], legacy=[], updates=[], get_account=[])

    class Table:
        def __init__(self, records):
            self.records = records

        def all(self, formula=None):
            return list(self.records)

        def update(self, rid, fields):
            calls.updates.append((rid, dict(fields)))

    class Repo:
        def get_publish_account(self, code):
            calls.get_account.append(code)
            return dict(ACCOUNTS[code]) if code in ACCOUNTS else None

    state = SimpleNamespace(records=[], insights_response=lambda url, params: _Resp(200, _insights_payload(FULL)),
                            creds=dict(CREDS))

    def _get(url, params=None, timeout=None):
        if url.endswith("/insights"):
            calls.insights.append((url, dict(params)))
            return state.insights_response(url, params)
        calls.legacy.append((url, params.get("access_token")))
        return _Resp(200, {"like_count": 7, "comments_count": 8})

    def _resolve(key):
        ig, tok = state.creds[key]
        return SimpleNamespace(ig_user_id=ig, access_token=tok)

    monkeypatch.setattr(et, "get_table", lambda name: Table(state.records))
    monkeypatch.setattr(et.requests, "get", _get)
    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: Repo())
    monkeypatch.setattr("modules.common.credential_resolver.resolve_credential", _resolve)
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "tok-LEGACY")
    monkeypatch.delenv("INSIGHTS_ACCOUNT_CODES", raising=False)
    monkeypatch.delenv("INSIGHTS_INCLUDE_VIEWS", raising=False)
    return SimpleNamespace(calls=calls, state=state, mp=monkeypatch)


# ── Flag OFF: 레거시 그대로 ───────────────────────────────────────────────────
@pytest.mark.parametrize("flag", [None, "", " , "])
def test_flag_off_is_legacy_only(env, flag):
    if flag is not None:
        env.mp.setenv("INSIGHTS_ACCOUNT_CODES", flag)
    env.state.records = [_rec("r1", "IDN-000036"), _rec("r2", "IDN-000041")]
    result = et.update_engagement_metrics()
    assert result == {"updated": 2, "skipped": 0, "failed": 0}
    assert env.calls.insights == []
    assert [t for _, t in env.calls.legacy] == ["tok-LEGACY", "tok-LEGACY"]
    assert all(set(f) == {"like_count", "comments_count"} for _, f in env.calls.updates)


def test_flag_off_without_legacy_token_returns_early(env):
    env.mp.delenv("INSTA_ACCESS_TOKEN", raising=False)
    env.mp.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    env.state.records = [_rec("r1", "IDN-000036")]
    assert et.update_engagement_metrics() == {"updated": 0, "skipped": 0, "failed": 0}
    assert env.calls.insights == [] and env.calls.legacy == []


# ── Flag ON: 대상은 Insights 1회, 레거시 제외 ─────────────────────────────────
def test_target_uses_insights_once_and_is_excluded_from_legacy(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    env.state.records = [_rec("t1", "IDN-000036"), _rec("o1", "IDN-000041"), _rec("old", "IDN-000036", created=OLD)]
    result = et.update_engagement_metrics()

    assert [u for u, _ in env.calls.insights] == ["https://graph.facebook.com/v26.0/m-t1/insights"]
    assert [m for m, _ in env.calls.legacy] == [f"{et.IG_API}/m-o1", f"{et.IG_API}/m-old"]
    assert result["insights_updated"] == 1 and result["updated"] == 2

    rid, fields = env.calls.updates[0]
    assert rid == "t1"
    assert fields["insights_reach"] == 10 and fields["insights_saved"] == 2
    assert fields["insights_shares"] == 1 and fields["insights_profile_visits"] == 3
    assert fields["like_count"] == 4 and fields["comments_count"] == 5
    assert fields["insights_collected_at"].endswith("Z")
    assert "insights_views" not in fields


def test_metric_list_without_views_by_default(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    env.state.records = [_rec("t1", "IDN-000036")]
    et.update_engagement_metrics()
    metric = env.calls.insights[0][1]["metric"].split(",")
    assert metric == ["reach", "saved", "shares", "profile_visits", "likes", "comments"]


def test_request_uses_lifetime_period_like_canary(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    env.state.records = [_rec("t1", "IDN-000036")]
    et.update_engagement_metrics()
    assert env.calls.insights[0][1]["period"] == "lifetime"


def test_usage_header_is_logged_without_business_id(env, caplog):
    import json as _json
    import logging
    usage = {"9876543210": [{"type": "instagram", "call_count": 3, "total_cputime": 2,
                             "total_time": 4, "estimated_time_to_regain_access": 0}]}
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    env.state.insights_response = lambda u, p: _Resp(
        200, _insights_payload(FULL), headers={"x-business-use-case-usage": _json.dumps(usage)})
    env.state.records = [_rec("t1", "IDN-000036")]
    with caplog.at_level(logging.INFO):
        et.update_engagement_metrics()
    assert "[Insights] usage | m-t1 | call_count=3 total_cputime=2 total_time=4 regain_min=0" in caplog.text
    assert "9876543210" not in caplog.text and "tok-AI" not in caplog.text


def test_views_included_only_when_flag_true(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    env.mp.setenv("INSIGHTS_INCLUDE_VIEWS", "true")
    env.state.records = [_rec("t1", "IDN-000036")]
    et.update_engagement_metrics()
    assert "views" in env.calls.insights[0][1]["metric"].split(",")
    assert env.calls.updates[0][1]["insights_views"] == 99


def test_views_missing_is_not_a_failure(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    env.mp.setenv("INSIGHTS_INCLUDE_VIEWS", "true")
    no_views = {k: v for k, v in FULL.items() if k != "views"}
    env.state.insights_response = lambda u, p: _Resp(200, _insights_payload(no_views))
    env.state.records = [_rec("t1", "IDN-000036")]
    result = et.update_engagement_metrics()
    assert result["insights_updated"] == 1
    assert "insights_views" not in env.calls.updates[0][1]


# ── 계정 토큰 격리 ───────────────────────────────────────────────────────────
def test_each_account_uses_its_own_token(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036,IDN-000041")
    env.state.records = [_rec("a", "IDN-000036"), _rec("b", "IDN-000041"), _rec("c", "IDN-000036")]
    et.update_engagement_metrics()
    tokens = {u.split("/")[-2]: p["access_token"] for u, p in env.calls.insights}
    assert tokens == {"m-a": "tok-AI", "m-b": "tok-YUNA", "m-c": "tok-AI"}
    assert env.calls.legacy == []
    assert env.calls.get_account.count("IDN-000036") == 1        # 계정당 1회 조회(캐시)


def test_ig_mismatch_skips_without_write_or_legacy_fallback(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    env.state.creds["AI"] = ("ig-OTHER", "tok-AI")
    env.state.records = [_rec("t1", "IDN-000036")]
    result = et.update_engagement_metrics()
    assert env.calls.insights == [] and env.calls.legacy == [] and env.calls.updates == []
    assert result["insights_failed"] == 1


def test_unresolved_account_skips(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-999999")
    env.state.records = [_rec("t1", "IDN-999999")]
    result = et.update_engagement_metrics()
    assert env.calls.insights == [] and env.calls.updates == [] and env.calls.legacy == []
    assert result["insights_failed"] == 1


# ── 원자 저장: 실패 시 기존 값 유지 ───────────────────────────────────────────
@pytest.mark.parametrize("response", [
    _Resp(400, {"error": {"code": 10, "message": "no permission"}}),
    _Resp(200, {"data": []}),
    _Resp(200, _insights_payload({k: v for k, v in FULL.items() if k != "shares"})),
    _Resp(200, _insights_payload(dict(FULL, reach=None))),
])
def test_error_empty_or_missing_metric_writes_nothing(env, response):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    env.state.insights_response = lambda u, p: response
    env.state.records = [_rec("t1", "IDN-000036")]
    result = et.update_engagement_metrics()
    assert env.calls.updates == []
    assert env.calls.legacy == []
    assert result["insights_failed"] == 1 and result["insights_updated"] == 0


def test_request_exception_writes_nothing(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")

    def _boom(u, p):
        raise ConnectionError("down")
    env.state.insights_response = _boom
    env.state.records = [_rec("t1", "IDN-000036")]
    assert et.update_engagement_metrics()["insights_failed"] == 1
    assert env.calls.updates == []


# ── 6시간 간격 ───────────────────────────────────────────────────────────────
def test_recently_collected_is_skipped_by_both_paths(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    recent = (NOW - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    stale = (NOW - timedelta(hours=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    env.state.records = [_rec("fresh", "IDN-000036", collected=recent), _rec("due", "IDN-000036", collected=stale)]
    result = et.update_engagement_metrics()
    assert [u.split("/")[-2] for u, _ in env.calls.insights] == ["m-due"]
    assert env.calls.legacy == []
    assert result["insights_throttled"] == 1 and result["insights_updated"] == 1


def test_flag_on_without_legacy_token_still_collects_insights(env):
    env.mp.setenv("INSIGHTS_ACCOUNT_CODES", "IDN-000036")
    env.mp.delenv("INSTA_ACCESS_TOKEN", raising=False)
    env.mp.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    env.state.records = [_rec("t1", "IDN-000036"), _rec("o1", "IDN-000041")]
    result = et.update_engagement_metrics()
    assert result["insights_updated"] == 1 and result["updated"] == 0
    assert env.calls.legacy == []
