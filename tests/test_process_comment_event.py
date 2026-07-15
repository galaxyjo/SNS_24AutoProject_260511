"""tests/test_process_comment_event.py — FP-047 단일 진입점(process_comment_event) 배선 테스트.
comment_event_store 원자성 자체는 tests/test_comment_event_store.py에서 검증됨 —
여기서는 킬스위치 모드 분기와 웹훅+폴러 이중진입 dedup만 확인한다."""

import pytest

from modules.comment import comment_auto_reply
from modules.comment import comment_event_store as ces


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "comment_events_test.db"
    monkeypatch.setattr(ces, "_DB_PATH", db_path)
    monkeypatch.setattr(ces, "_conn", None)
    yield


@pytest.fixture(autouse=True)
def _stub_effects(monkeypatch):
    """실제 Telegram/Private Reply/Airtable 호출 대신 호출 횟수만 기록."""
    calls = {"telegram": 0, "private_reply": 0, "record": 0}

    def _fake_telegram(claim_token, comment_id, username, text, tag):
        calls["telegram"] += 1

    def _fake_record(claim_token, username, text, comment_id, media_id):
        calls["record"] += 1
        return True  # durably_accepted(260715 Codex 4차 리뷰) — 성공 케이스 시뮬레이션

    def _fake_try_private_reply(claim_token, comment_id, username, media_id, cooldown_key):
        calls["private_reply"] += 1

    monkeypatch.setattr(comment_auto_reply, "_send_telegram_comment", _fake_telegram)
    monkeypatch.setattr(comment_auto_reply, "_record_comment", _fake_record)
    monkeypatch.setattr(comment_auto_reply, "_try_private_reply", _fake_try_private_reply)
    return calls


@pytest.fixture
def _enforce_ready(monkeypatch):
    """enforce 모드가 실제로 event_store 경로를 타려면 (1) 캠페인 게시물이어야 하고
    (2) retry handler가 등록돼 있어야 한다(P0-5, 260715 — 전역이 아니라 캠페인
    게시물 단위로 스코핑, handler 미등록 시 fail-fast로 legacy 폴백)."""
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
    monkeypatch.setattr(comment_auto_reply, "_retry_handlers_registered", True)


class TestKillSwitchModes:
    def test_disabled_mode_processes_without_event_store(self, monkeypatch, _stub_effects):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "disabled")
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media1", ingress="webhook")
        assert _stub_effects["telegram"] == 1
        assert _stub_effects["record"] == 1
        # disabled 모드에서는 event_store에 아무 흔적도 안 남아야 한다
        assert ces.get_status("instagram_comment", "c1") is None

    def test_shadow_mode_observes_but_still_processes_both_times(self, monkeypatch, _stub_effects):
        """shadow는 관측만 — claim 결과와 무관하게 기존 경로가 항상 실행된다(중복 가능, 의도된 동작)."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media1", ingress="webhook")
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media1", ingress="poller")
        assert _stub_effects["telegram"] == 2, "shadow는 로직을 바꾸지 않으므로 기존처럼 두 번 다 처리돼야 함"
        # 그러나 event_store 자체엔 claim 시도 흔적이 남아있어야 함(관측 목적)
        status = ces.get_status("instagram_comment", "c1")
        assert status is not None

    def test_enforce_mode_dedups_webhook_and_poller(self, monkeypatch, _stub_effects, _enforce_ready):
        """FP-047 핵심 시나리오 — 같은 댓글이 webhook과 poller 양쪽에서 들어와도 1번만 처리."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media1", ingress="webhook")
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media1", ingress="poller")
        assert _stub_effects["telegram"] == 1, "enforce에서는 정확히 1번만 처리돼야 함"
        assert _stub_effects["record"] == 1

    def test_enforce_mode_different_comments_both_process(self, monkeypatch, _stub_effects, _enforce_ready):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media1", ingress="webhook")
        comment_auto_reply.process_comment_event("c2", "buyer2", "가격이요", "media1", ingress="poller")
        assert _stub_effects["telegram"] == 2

    def test_default_mode_is_disabled_when_env_unset(self, monkeypatch, _stub_effects):
        monkeypatch.delenv("COMMENT_EVENT_STORE_MODE", raising=False)
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media1", ingress="webhook")
        assert ces.get_status("instagram_comment", "c1") is None, "env 미설정 시 기본값은 disabled여야 함"

    def test_invalid_mode_string_falls_back_to_disabled(self, monkeypatch, _stub_effects):
        """P0(260715) — 오타/잘못된 값이 조용히 enforce로 새면 안 된다."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforc")  # 오타
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media1", ingress="webhook")
        assert ces.get_status("instagram_comment", "c1") is None, "잘못된 값은 disabled로 폴백해야 함"


class TestP0_ReturnValueDistinguishesInProgress:
    """P0(260715 Codex 3차 리뷰) — try_claim()이 None인 이유가 "완료"와 "남이 처리중"
    으로 갈리는데, 이전엔 둘 다 그냥 return(암묵적 None)이라 poller가 구분 못 했다."""

    def test_first_caller_gets_accepted(self, monkeypatch, _stub_effects, _enforce_ready):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")
        assert result == comment_auto_reply.CommentProcessResult.ACCEPTED

    def test_second_caller_while_still_processing_gets_in_progress_not_duplicate(
        self, monkeypatch, _stub_effects, _enforce_ready
    ):
        """claim은 됐지만 아직 안 끝난 상태(유효 lease)에서 두번째 진입 — IN_PROGRESS여야
        하고, 이걸 DUPLICATE_COMPLETED로 오인해서 poller가 영구 캐시하면 안 된다."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        # claim만 하고 실제 처리는 안 끝낸 상태를 시뮬레이션(effect 함수들은 이미 no-op으로 스텁됨)
        ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=60)

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="poller")
        assert result == comment_auto_reply.CommentProcessResult.IN_PROGRESS

    def test_completed_event_returns_duplicate_completed(self, monkeypatch, _stub_effects, _enforce_ready):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        token = ces.try_claim("instagram_comment", "c1", "webhook")
        ces.mark_airtable_done("instagram_comment", "c1", token)  # status=COMPLETED

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="poller")
        assert result == comment_auto_reply.CommentProcessResult.DUPLICATE_COMPLETED


class TestP0_5_CampaignScoping:
    """enforce가 전역이 아니라 캠페인 게시물에만 적용돼야 한다(260715 Codex 2차 리뷰)."""

    def test_enforce_skips_event_store_for_non_campaign_media(self, monkeypatch, _stub_effects):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: False)
        monkeypatch.setattr(comment_auto_reply, "_retry_handlers_registered", True)

        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-not-campaign", ingress="webhook")
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-not-campaign", ingress="poller")

        assert _stub_effects["telegram"] == 2, "캠페인 게시물이 아니면 enforce여도 dedup 안 걸리고 기존처럼 처리돼야 함"
        assert ces.get_status("instagram_comment", "c1") is None, "캠페인 아닌 댓글은 event_store에 흔적이 없어야 함"

    def test_enforce_applies_dedup_only_for_campaign_media(self, monkeypatch, _stub_effects, _enforce_ready):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")
        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="poller")
        assert _stub_effects["telegram"] == 1
        assert ces.get_status("instagram_comment", "c1") is not None


class TestP0_HandlerRegistrationFailFast:
    def test_enforce_rejects_processing_when_handler_not_registered(self, monkeypatch, _stub_effects):
        """P0(260715 Codex 3차 리뷰) — legacy 폴백은 fail-open이라 반대. handler
        미등록이면 처리 자체를 거부(fail-closed)해야 한다 — 무보호로 계속 흘려보내면 안 됨."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
        monkeypatch.setattr(comment_auto_reply, "_retry_handlers_registered", False)

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY
        assert _stub_effects["telegram"] == 0, "handler 미등록이면 아무 처리도 하면 안 됨(fail-closed)"
        assert ces.get_status("instagram_comment", "c1") is None


class TestLegacyHandleCommentUnaffected:
    def test_handle_comment_still_works_directly(self, _stub_effects):
        """기존 handle_comment() 직접 호출 경로(레거시 진입점)는 그대로 동작해야 한다."""
        comment_auto_reply.handle_comment("c1", "buyer1", "예쁘네요", "media1")
        assert _stub_effects["telegram"] == 1
        assert _stub_effects["record"] == 1
