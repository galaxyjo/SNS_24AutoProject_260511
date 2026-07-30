"""tests/test_dm_multi_account_send.py — 7단계(Multi-account DM Routing, 260730).

_resolve_dm_send_target()이 account_code_ref를 계정별 발송 대상(URL+Token)으로
정확히 해석하는지, 그리고 실패 시 전역 계정 fallback 경로가 그대로 유지되는지
검증한다. 실제 네트워크·Airtable 호출 없이 전부 monkeypatch.

modules.dm.dm_auto_reply를 정상 경로로 import하면 modules/dm/__init__.py가
dm_receiver.py를 통해 runtime_boot_policy.json을 확인하려다 이 환경에서
PermissionError를 던진다(기존에 반복 문서화된 환경제약, 이 파일과 무관) —
이 파일은 그 제약이 없는 환경(CI/회장 터미널)에서 실행하기 위해 작성한다.
"""

import pytest

import modules.dm.dm_auto_reply as dm_auto_reply


class _FakeRepo:
    def __init__(self, accounts: dict):
        self._accounts = accounts

    def get_publish_account(self, account_code_ref):
        return self._accounts.get(account_code_ref)


class _FakeCred:
    def __init__(self, ig_user_id, access_token):
        self.ig_user_id = ig_user_id
        self.access_token = access_token


@pytest.fixture(autouse=True)
def _restore_repo(monkeypatch):
    original = dm_auto_reply._repo
    yield
    dm_auto_reply._repo = original


def test_empty_account_code_ref_returns_none(monkeypatch):
    dm_auto_reply._repo = _FakeRepo({})
    assert dm_auto_reply._resolve_dm_send_target("") is None


def test_account_not_found_returns_none(monkeypatch):
    dm_auto_reply._repo = _FakeRepo({})
    assert dm_auto_reply._resolve_dm_send_target("IDN-999999") is None


def test_unresolvable_credential_returns_none(monkeypatch):
    dm_auto_reply._repo = _FakeRepo({
        "IDN-999999": {"api_provider": "instagram_login", "credential_key": "GHOST", "fb_page_id": ""},
    })

    def _raise(*a, **k):
        raise Exception("no such key")

    monkeypatch.setattr("modules.common.credential_resolver.resolve_credential", _raise)
    assert dm_auto_reply._resolve_dm_send_target("IDN-999999") is None


def test_instagram_login_uses_direct_graph_instagram_endpoint(monkeypatch):
    """instagram_login(예: aijomoojin)은 Page Token 교환 없이 graph.instagram.com에 직접 요청한다."""
    dm_auto_reply._repo = _FakeRepo({
        "IDN-000036": {"api_provider": "instagram_login", "credential_key": "AI", "fb_page_id": ""},
    })
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: _FakeCred("999999", "fake-ai-token"),
    )

    result = dm_auto_reply._resolve_dm_send_target("IDN-000036")

    assert result == {"url": "https://graph.instagram.com/v25.0/999999/messages", "token": "fake-ai-token"}


def test_facebook_login_without_fb_page_id_returns_none(monkeypatch):
    """fb_page_id 데이터 계약이 없으면 계정별 라우팅을 시도하지 않고 fallback으로 보낸다."""
    dm_auto_reply._repo = _FakeRepo({
        "IDN-000041": {"api_provider": "facebook_login", "credential_key": "YUNA", "fb_page_id": ""},
    })
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: _FakeCred("111111", "fake-yuna-token"),
    )

    assert dm_auto_reply._resolve_dm_send_target("IDN-000041") is None


def test_facebook_login_with_fb_page_id_exchanges_page_token(monkeypatch):
    dm_auto_reply._repo = _FakeRepo({
        "IDN-000041": {"api_provider": "facebook_login", "credential_key": "YUNA", "fb_page_id": "868456346356581"},
    })
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: _FakeCred("111111", "fake-yuna-token"),
    )

    class _FakeResp:
        def json(self):
            return {"data": [{"id": "868456346356581", "access_token": "fake-page-token"}]}

    def _fake_get(url, params=None, timeout=None):
        assert "me/accounts" in url
        return _FakeResp()

    monkeypatch.setattr(dm_auto_reply.requests, "get", _fake_get)

    result = dm_auto_reply._resolve_dm_send_target("IDN-000041")

    assert result == {"url": "https://graph.facebook.com/v25.0/868456346356581/messages", "token": "fake-page-token"}


def test_unsupported_provider_returns_none(monkeypatch):
    dm_auto_reply._repo = _FakeRepo({
        "IDN-000099": {"api_provider": "unknown_provider", "credential_key": "X", "fb_page_id": ""},
    })
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: _FakeCred("1", "t"),
    )
    assert dm_auto_reply._resolve_dm_send_target("IDN-000099") is None


def test_send_ig_reply_falls_back_to_global_when_target_unresolved(monkeypatch):
    """account_code_ref가 없거나 해석 실패해도 send_ig_reply는 기존 전역 경로로
    100% 동일하게 동작해야 한다(회귀 방지 — 이번 변경의 핵심 계약)."""
    dm_auto_reply._repo = _FakeRepo({})
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "111222333")
    monkeypatch.setattr(dm_auto_reply, "_get_page_token", lambda: "global-fallback-token")

    captured = {}

    class _FakeResp:
        ok = True

        def json(self):
            return {"message_id": "mid_123"}

    def _fake_post(url, headers=None, data=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResp()

    monkeypatch.setattr(dm_auto_reply.requests, "post", _fake_post)

    sent = dm_auto_reply.send_ig_reply("sender1", "hello", account_code_ref="")

    assert sent is True
    assert captured["url"] == "https://graph.facebook.com/v25.0/111222333/messages"
    assert captured["headers"]["Authorization"] == "Bearer global-fallback-token"


def test_send_ig_reply_still_falls_back_when_unresolved_account_is_the_fallback_owner(monkeypatch):
    """260730 DM Routing Close Gate — account_code_ref가 전역 fallback 소유 계정
    (yuna18253=GLOBAL_FALLBACK_ACCOUNT_CODE_REF) 자신이면, 해석에 실패해도 결과가
    동일하므로 기존 전역 fallback을 그대로 유지해야 한다(회귀 방지)."""
    dm_auto_reply._repo = _FakeRepo({})  # 조회 자체가 실패하는 상황을 재현
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "868456346356581")
    monkeypatch.setattr(dm_auto_reply, "_get_page_token", lambda: "global-fallback-token")

    captured = {}

    class _FakeResp:
        ok = True

        def json(self):
            return {"message_id": "mid_yuna"}

    def _fake_post(url, headers=None, data=None, timeout=None):
        captured["called"] = True
        return _FakeResp()

    monkeypatch.setattr(dm_auto_reply.requests, "post", _fake_post)

    sent = dm_auto_reply.send_ig_reply(
        "sender1", "hello",
        account_code_ref=dm_auto_reply.GLOBAL_FALLBACK_ACCOUNT_CODE_REF,
    )

    assert sent is True
    assert captured.get("called") is True


def test_send_ig_reply_skips_fallback_for_other_account_when_unresolved(monkeypatch):
    """260730 DM Routing Close Gate — account_code_ref가 있고(계정이 이미 식별됨) 그
    계정이 aijomoojin 등 전역 fallback 소유자(yuna18253)가 아닌데 해석에 실패하면,
    전역 fallback으로 실제 발송을 시도하지 않고 즉시 False를 반환해야 한다
    (호출자가 retry_queue로 위임)."""
    dm_auto_reply._repo = _FakeRepo({})  # 조회 실패 → target=None

    called = {"post": False}

    def _fake_post(*a, **k):
        called["post"] = True
        raise AssertionError("전역 fallback으로 실제 발송을 시도하면 안 된다")

    monkeypatch.setattr(dm_auto_reply.requests, "post", _fake_post)

    sent = dm_auto_reply.send_ig_reply("sender1", "hello", account_code_ref="IDN-000036")

    assert sent is False
    assert called["post"] is False
