"""tests/test_comment_airtable_preflight.py — 260716 FP-047/Package1 enforce 전제조건 B:
Airtable Lead_Interactions.source_event_id 필드 존재 startup preflight."""

import pytest

from modules.comment import comment_auto_reply
from modules.comment import comment_event_store as ces


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "comment_events_test.db"
    monkeypatch.setattr(ces, "_DB_PATH", db_path)
    monkeypatch.setattr(ces, "_conn", None)
    yield


class _FakeRepo:
    def __init__(self, *, exists: bool = True, raise_exc: Exception | None = None):
        self._exists = exists
        self._raise_exc = raise_exc
        self.calls = []

    def verify_field_exists(self, table, field_name):
        self.calls.append((table, field_name))
        if self._raise_exc:
            raise self._raise_exc
        return self._exists


class TestVerifyAirtablePreflight:
    def test_field_present_sets_true(self, monkeypatch):
        repo = _FakeRepo(exists=True)
        monkeypatch.setattr(comment_auto_reply, "_repo", repo)

        assert comment_auto_reply._verify_airtable_preflight() is True
        assert repo.calls == [("Lead_Interactions", "source_event_id")]

    def test_field_missing_sets_false(self, monkeypatch):
        repo = _FakeRepo(exists=False)
        monkeypatch.setattr(comment_auto_reply, "_repo", repo)

        assert comment_auto_reply._verify_airtable_preflight() is False

    def test_lookup_failure_sets_false_not_raises(self, monkeypatch):
        """조회 자체가 실패해도(네트워크 등) launcher 기동을 막으면 안 되므로, 이 함수는
        예외를 삼키고 False로 fail-closed 처리한다(cipher 검증과 동일 원칙)."""
        repo = _FakeRepo(raise_exc=ConnectionError("airtable down"))
        monkeypatch.setattr(comment_auto_reply, "_repo", repo)

        assert comment_auto_reply._verify_airtable_preflight() is False


class TestEnforceModeGatedByAirtablePreflight:
    def test_enforce_rejects_when_preflight_not_ok(self, monkeypatch):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
        monkeypatch.setattr(comment_auto_reply, "_retry_handlers_registered", True)
        monkeypatch.setattr(comment_auto_reply, "_cipher_verified", True)
        monkeypatch.setattr(comment_auto_reply, "_airtable_preflight_ok", False)

        result = comment_auto_reply.process_comment_event(
            "c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook"
        )

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY

    def test_enforce_accepts_when_all_preconditions_ok(self, monkeypatch):
        """A-2(cipher)와 B(airtable preflight) 둘 다 통과해야 enforce가 정상 진입한다."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
        monkeypatch.setattr(comment_auto_reply, "_retry_handlers_registered", True)
        monkeypatch.setattr(comment_auto_reply, "_cipher_verified", True)
        monkeypatch.setattr(comment_auto_reply, "_airtable_preflight_ok", True)
        monkeypatch.setattr(comment_auto_reply, "_send_telegram_comment", lambda *a: None)
        monkeypatch.setattr(comment_auto_reply, "_record_comment", lambda *a: True)
        monkeypatch.setattr(comment_auto_reply, "_try_private_reply", lambda *a: None)

        result = comment_auto_reply.process_comment_event(
            "c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook"
        )

        assert result == comment_auto_reply.CommentProcessResult.ACCEPTED

    def test_shadow_mode_unaffected_by_preflight_state(self, monkeypatch):
        """B는 enforce 전제조건이라 shadow/disabled에는 적용하지 않는다(A-2와 동일 원칙)."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        monkeypatch.setattr(comment_auto_reply, "_airtable_preflight_ok", False)
        monkeypatch.setattr(comment_auto_reply, "handle_comment", lambda *a, **k: None)

        result = comment_auto_reply.process_comment_event(
            "c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook"
        )

        assert result == comment_auto_reply.CommentProcessResult.LEGACY
