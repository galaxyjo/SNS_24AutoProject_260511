"""tests/test_dm_account_routing.py — Bundle B(260726) 웹훅 레벨 통합검증.
Codex 요구사항: 킬스위치 기본 OFF, recipient.id 혼합배치 무누출, 역조회 실패시
fail-open(DM 처리는 계속), is_echo에서 역조회 안 함, 댓글 Caller payload 무변경.
실제 Airtable/네트워크 호출 없이 dm_receiver 모듈 함수를 monkeypatch.

ERR-082(260727): Signature 검증 삽입 이후 모든 POST는 Route 전용 App Secret으로
서명해야 한다(_signed_post 헬퍼) — 이 파일은 계정 Routing 행위 자체의 회귀만
검증하고, Signature 보안 매트릭스 자체는 tests/test_dm_receiver_webhook.py가 담당."""

import hashlib
import hmac
import json

import pytest

import modules.dm.dm_receiver as dm_receiver
from modules.infra.repository_interface import (
    RepositoryUnavailableError,
    RepositoryValidationError,
)

GALAXY_SECRET = "test-galaxy-secret"


@pytest.fixture
def client(monkeypatch):
    dm_receiver.app.config["TESTING"] = True
    monkeypatch.setattr(dm_receiver, "WEBHOOK_APP_SECRET", GALAXY_SECRET)
    return dm_receiver.app.test_client()


def _signed_post(client, path, payload, secret=GALAXY_SECRET):
    body = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return client.post(path, data=body, content_type="application/json",
                        headers={"X-Hub-Signature-256": sig})


def _dm_payload(sender="sender1", recipient="17841476202821375", text="안녕하세요"):
    messaging = {"sender": {"id": sender}, "message": {"text": text}}
    if recipient is not None:
        messaging["recipient"] = {"id": recipient}
    return {"object": "instagram", "entry": [{"messaging": [messaging]}]}


def _stub_common(monkeypatch, dm_calls):
    monkeypatch.setattr(dm_receiver, "record_interaction",
                         lambda *a, **k: dm_calls.append((a, k)) or "rec1")
    monkeypatch.setattr(dm_receiver, "send_telegram", lambda *a, **k: None)
    monkeypatch.setattr(dm_receiver, "is_repeat_inquiry", lambda *a, **k: False)
    monkeypatch.setattr(dm_receiver, "detect_order", lambda *a, **k: False)
    monkeypatch.setattr(dm_receiver, "detect_price_inquiry", lambda *a, **k: False)


class TestKillSwitchDefaultOff:
    def test_flag_false_no_lookup_attempted_and_empty_account_code_ref(self, client, monkeypatch):
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", False)
        lookup_calls = []
        monkeypatch.setattr(dm_receiver._repo, "get_publish_account_by_ig_user_id",
                             lambda *a, **k: lookup_calls.append(a) or None)
        dm_calls = []
        _stub_common(monkeypatch, dm_calls)

        resp = _signed_post(client, "/webhook", _dm_payload())
        assert resp.status_code == 200
        assert lookup_calls == [], "킬스위치 꺼짐 상태에서는 역조회 자체를 시도하면 안 됨"
        assert len(dm_calls) == 1
        assert dm_calls[0][1]["account_code_ref"] == ""


class TestAccountResolution:
    def test_flag_true_resolves_correct_account_code(self, client, monkeypatch):
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", True)
        monkeypatch.setattr(
            dm_receiver._repo, "get_publish_account_by_ig_user_id",
            lambda ig_user_id: {"account_code": "IDN-000041", "api_provider": "facebook_login",
                                  "ig_user_id": ig_user_id, "credential_key": "YUNA"}
            if ig_user_id == "17841476202821375" else None,
        )
        dm_calls = []
        _stub_common(monkeypatch, dm_calls)

        resp = _signed_post(client, "/webhook", _dm_payload(recipient="17841476202821375"))
        assert resp.status_code == 200
        assert dm_calls[0][1]["account_code_ref"] == "IDN-000041"

    def test_mixed_recipients_no_cross_event_leakage(self, client, monkeypatch):
        """같은 요청 안에 서로 다른 recipient의 messaging 이벤트가 섞여도, 각각
        자기 recipient의 account_code만 받아야 한다(앞 이벤트 값이 새면 안 됨)."""
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", True)

        def _lookup(ig_user_id):
            mapping = {
                "17841476202821375": "IDN-000041",   # yuna18253
                "17841467725643424": "IDN-000036",   # aijomoojin
            }
            code = mapping.get(ig_user_id)
            return {"account_code": code, "api_provider": "x", "ig_user_id": ig_user_id,
                    "credential_key": "x"} if code else None

        monkeypatch.setattr(dm_receiver._repo, "get_publish_account_by_ig_user_id", _lookup)
        dm_calls = []
        _stub_common(monkeypatch, dm_calls)

        payload = {
            "object": "instagram",
            "entry": [{
                "messaging": [
                    {"sender": {"id": "s1"}, "recipient": {"id": "17841476202821375"},
                     "message": {"text": "yuna에게"}},
                    {"sender": {"id": "s2"}, "recipient": {"id": "17841467725643424"},
                     "message": {"text": "aijomoojin에게"}},
                ],
            }],
        }
        resp = _signed_post(client, "/webhook", payload)
        assert resp.status_code == 200
        assert len(dm_calls) == 2
        codes = [k["account_code_ref"] for _, k in dm_calls]
        assert codes == ["IDN-000041", "IDN-000036"], "각 이벤트가 자기 recipient의 account_code만 받아야 함(교차오염 없음)"

    def test_cache_reused_for_same_recipient_within_request(self, client, monkeypatch):
        """같은 요청 안에 동일 recipient가 여러 번 나오면 조회는 1번만 해야 한다."""
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", True)
        lookup_calls = []

        def _lookup(ig_user_id):
            lookup_calls.append(ig_user_id)
            return {"account_code": "IDN-000041", "api_provider": "x",
                    "ig_user_id": ig_user_id, "credential_key": "x"}

        monkeypatch.setattr(dm_receiver._repo, "get_publish_account_by_ig_user_id", _lookup)
        dm_calls = []
        _stub_common(monkeypatch, dm_calls)

        payload = {
            "object": "instagram",
            "entry": [{
                "messaging": [
                    {"sender": {"id": "s1"}, "recipient": {"id": "17841476202821375"}, "message": {"text": "hi1"}},
                    {"sender": {"id": "s2"}, "recipient": {"id": "17841476202821375"}, "message": {"text": "hi2"}},
                ],
            }],
        }
        resp = _signed_post(client, "/webhook", payload)
        assert resp.status_code == 200
        assert lookup_calls == ["17841476202821375"], "동일 recipient는 요청당 1회만 조회해야 함"
        assert len(dm_calls) == 2


class TestFailOpen:
    def test_recipient_missing_dm_still_processed(self, client, monkeypatch):
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", True)
        lookup_calls = []
        monkeypatch.setattr(dm_receiver._repo, "get_publish_account_by_ig_user_id",
                             lambda *a, **k: lookup_calls.append(a) or None)
        dm_calls = []
        _stub_common(monkeypatch, dm_calls)

        resp = _signed_post(client, "/webhook", _dm_payload(recipient=None))
        assert resp.status_code == 200
        assert lookup_calls == [], "recipient 자체가 없으면 조회 시도 안 함"
        assert dm_calls[0][1]["account_code_ref"] == ""

    def test_ambiguous_lookup_result_does_not_block_dm(self, client, monkeypatch):
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", True)

        def _boom(*a, **k):
            raise RepositoryValidationError("ambiguous")

        monkeypatch.setattr(dm_receiver._repo, "get_publish_account_by_ig_user_id", _boom)
        dm_calls = []
        _stub_common(monkeypatch, dm_calls)

        resp = _signed_post(client, "/webhook", _dm_payload())
        assert resp.status_code == 200, "계정 조회 모호성 오류가 DM 처리 자체를 막으면 안 됨"
        assert dm_calls[0][1]["account_code_ref"] == ""

    def test_network_error_does_not_block_dm(self, client, monkeypatch):
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", True)

        def _boom(*a, **k):
            raise RepositoryUnavailableError("timeout")

        monkeypatch.setattr(dm_receiver._repo, "get_publish_account_by_ig_user_id", _boom)
        dm_calls = []
        _stub_common(monkeypatch, dm_calls)

        resp = _signed_post(client, "/webhook", _dm_payload())
        assert resp.status_code == 200, "계정 조회 네트워크 오류가 DM 처리 자체를 막으면 안 됨"
        assert dm_calls[0][1]["account_code_ref"] == ""

    def test_account_not_found_does_not_block_dm(self, client, monkeypatch):
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", True)
        monkeypatch.setattr(dm_receiver._repo, "get_publish_account_by_ig_user_id", lambda *a, **k: None)
        dm_calls = []
        _stub_common(monkeypatch, dm_calls)

        resp = _signed_post(client, "/webhook", _dm_payload())
        assert resp.status_code == 200
        assert dm_calls[0][1]["account_code_ref"] == ""


class TestIsEchoSkipsLookup:
    def test_is_echo_message_never_triggers_lookup(self, client, monkeypatch):
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", True)
        lookup_calls = []
        monkeypatch.setattr(dm_receiver._repo, "get_publish_account_by_ig_user_id",
                             lambda *a, **k: lookup_calls.append(a) or None)
        dm_calls = []
        _stub_common(monkeypatch, dm_calls)

        payload = {
            "object": "instagram",
            "entry": [{
                "messaging": [{
                    "sender": {"id": "s1"}, "recipient": {"id": "17841476202821375"},
                    "message": {"text": "echo", "is_echo": True},
                }],
            }],
        }
        resp = _signed_post(client, "/webhook", payload)
        assert resp.status_code == 200
        assert lookup_calls == [], "is_echo 이벤트는 계정 역조회 자체를 시도하면 안 됨"
        assert dm_calls == []


class TestCommentCallerUnaffected:
    def test_comment_event_call_unchanged_by_bundle_b(self, client, monkeypatch):
        """댓글 경로는 Bundle B 변경과 무관하게 기존 인자 그대로 process_comment_event를
        호출해야 한다(계정 관련 인자 유입 없음)."""
        from modules.comment.comment_auto_reply import CommentProcessResult
        calls = []

        def _fake(*a, **k):
            calls.append((a, k))
            return CommentProcessResult.ACCEPTED

        monkeypatch.setattr(dm_receiver, "process_comment_event", _fake)

        payload = {
            "object": "instagram",
            "entry": [{
                "changes": [{"field": "comments", "value": {
                    "id": "c1", "text": "가격문의",
                    "from": {"username": "b1", "id": "u1"},
                    "media": {"id": "media1"},
                }}],
            }],
        }
        resp = _signed_post(client, "/webhook", payload)
        assert resp.status_code == 200
        assert len(calls) == 1
        args, kwargs = calls[0]
        assert args == ("c1", "b1", "가격문의", "media1")
        assert kwargs == {"ingress": "webhook", "commenter_id": "u1"}
        assert "account_code_ref" not in kwargs, "댓글 Caller에 계정 관련 인자가 유입되면 안 됨"
