"""tests/test_dm_followup_fallback_gate.py — 260730 DM Routing Close Gate.

dm_followup_scheduler.py::_send_ig_dm()이 dm_auto_reply.py::send_ig_reply()와
동일한 fallback 차단 정책을 따르는지 검증한다(REUSE 계약 확인). 실제 네트워크
호출 없이 전부 monkeypatch.

modules.dm.dm_followup_scheduler를 정상 경로로 import하면 modules/dm/__init__.py가
dm_receiver.py를 통해 runtime_boot_policy.json을 확인하려다 이 환경에서
PermissionError를 던진다(기존에 반복 문서화된 환경제약, 이 파일과 무관) —
이 파일은 그 제약이 없는 환경(CI/회장 터미널)에서 실행하기 위해 작성한다.
"""

import pytest

import modules.dm.dm_auto_reply as dm_auto_reply
import modules.dm.dm_followup_scheduler as dm_followup_scheduler


class _FakeRepo:
    def __init__(self, accounts: dict):
        self._accounts = accounts

    def get_publish_account(self, account_code_ref):
        return self._accounts.get(account_code_ref)


@pytest.fixture(autouse=True)
def _restore_repo():
    original = dm_auto_reply._repo
    yield
    dm_auto_reply._repo = original


def test_send_ig_dm_skips_fallback_for_other_account_when_unresolved(monkeypatch):
    """account_code_ref가 aijomoojin 등 전역 fallback 소유자(yuna18253)가 아닌데
    해석에 실패하면, 전역 fallback으로 실제 발송을 시도하지 않고 즉시 False를
    반환해야 한다(호출자가 retry_queue로 위임)."""
    dm_auto_reply._repo = _FakeRepo({})  # 조회 실패 → target=None

    called = {"post": False}

    def _fake_post(*a, **k):
        called["post"] = True
        raise AssertionError("전역 fallback으로 실제 발송을 시도하면 안 된다")

    monkeypatch.setattr(dm_followup_scheduler.requests, "post", _fake_post)

    sent = dm_followup_scheduler._send_ig_dm("sender1", "hello", account_code_ref="IDN-000036")

    assert sent is False
    assert called["post"] is False


def test_send_ig_dm_still_falls_back_when_unresolved_account_is_the_fallback_owner(monkeypatch):
    """account_code_ref가 전역 fallback 소유 계정(yuna18253) 자신이면, 해석에
    실패해도 결과가 동일하므로 기존 전역 fallback을 그대로 유지해야 한다(회귀 방지)."""
    dm_auto_reply._repo = _FakeRepo({})
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "868456346356581")
    monkeypatch.setattr(dm_followup_scheduler, "_get_page_token", lambda: "global-fallback-token")

    captured = {}

    class _FakeResp:
        ok = True

        def json(self):
            return {"message_id": "mid_yuna"}

    def _fake_post(url, headers=None, data=None, timeout=None):
        captured["called"] = True
        return _FakeResp()

    monkeypatch.setattr(dm_followup_scheduler.requests, "post", _fake_post)

    sent = dm_followup_scheduler._send_ig_dm(
        "sender1", "hello",
        account_code_ref=dm_auto_reply.GLOBAL_FALLBACK_ACCOUNT_CODE_REF,
    )

    assert sent is True
    assert captured.get("called") is True


def test_send_ig_dm_falls_back_to_global_when_account_code_ref_empty(monkeypatch):
    """account_code_ref가 없는(레거시/미해석) DM은 기존처럼 전역 fallback을
    그대로 유지해야 한다(회귀 방지)."""
    dm_auto_reply._repo = _FakeRepo({})
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "111222333")
    monkeypatch.setattr(dm_followup_scheduler, "_get_page_token", lambda: "global-fallback-token")

    captured = {}

    class _FakeResp:
        ok = True

        def json(self):
            return {"message_id": "mid_legacy"}

    def _fake_post(url, headers=None, data=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResp()

    monkeypatch.setattr(dm_followup_scheduler.requests, "post", _fake_post)

    sent = dm_followup_scheduler._send_ig_dm("sender1", "hello", account_code_ref="")

    assert sent is True
    assert captured["url"] == "https://graph.facebook.com/v25.0/111222333/messages"
    assert captured["headers"]["Authorization"] == "Bearer global-fallback-token"
