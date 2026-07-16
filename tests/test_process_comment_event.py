"""tests/test_process_comment_event.py — FP-047 단일 진입점(process_comment_event) 배선 테스트.
comment_event_store 원자성 자체는 tests/test_comment_event_store.py에서 검증됨 —
여기서는 킬스위치 모드 분기와 웹훅+폴러 이중진입 dedup만 확인한다."""

import json

import pytest

from modules.comment import comment_auto_reply
from modules.comment import comment_event_store as ces
from modules.comment import comment_poll_targets as pt
from modules.comment import comment_campaign_config as cfg


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "comment_events_test.db"
    monkeypatch.setattr(ces, "_DB_PATH", db_path)
    monkeypatch.setattr(ces, "_conn", None)
    # 260716 Codex 8차 리뷰 — _blocked_by_allowlist_gating()이 이제 flag와 무관하게
    # 항상 load_campaign_media_ids()/poll_targets.get_target()을 직접 호출하므로,
    # 이 파일의 기존(allowlist gating과 무관한) 테스트들이 실제 운영 파일/DB를 건드리지
    # 않도록 격리하고, 기본값은 "빈 캠페인 + poll_targets 이력 없음"으로 맞춰
    # 게이트가 항상 False(미차단)를 반환하게 한다(기존 동작과 동일하게 유지).
    monkeypatch.setattr(pt, "_DB_PATH", db_path)
    monkeypatch.setattr(pt, "_conn", None)
    monkeypatch.setattr(cfg, "_CONFIG_PATH", tmp_path / "campaign.json")
    cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": []}), encoding="utf-8")
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
    (2) retry handler가 등록돼 있어야 하고(P0-5, 260715 — 전역이 아니라 캠페인
    게시물 단위로 스코핑, handler 미등록 시 fail-fast로 legacy 폴백) (3) 260716부터는
    retry payload 암호화 키 검증(_cipher_verified)과 (4) Airtable source_event_id 필드
    존재 확인(_airtable_preflight_ok)도 통과해야 한다(A-2/B, 안 통과 시 REJECTED_NOT_READY로
    댓글 처리만 거부 — launcher 전체는 무관)."""
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
    monkeypatch.setattr(comment_auto_reply, "_retry_handlers_registered", True)
    monkeypatch.setattr(comment_auto_reply, "_cipher_verified", True)
    monkeypatch.setattr(comment_auto_reply, "_airtable_preflight_ok", True)


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


class TestAllowlistGating:
    """260715 Codex 6차 리뷰 P0-1 — poller의 ACTIVE 제한을 webhook 경로가 우회해
    PENDING_BASELINE media에 실처리가 흘러가는 걸 막는 단일 진입점 게이트."""

    def test_gating_disabled_by_default_shadow_still_processes(self, monkeypatch, _stub_effects):
        """플래그 기본값(legacy)에서는 poll_targets를 아예 확인하지 않고 기존처럼 처리."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")
        assert result == comment_auto_reply.CommentProcessResult.LEGACY
        assert _stub_effects["telegram"] == 1

    def test_shadow_never_creates_event_row_for_pending_baseline_media(self, monkeypatch, _stub_effects):
        """P0(260716 Codex 7차 리뷰, 실제 재현 확인) — 게이트가 try_claim(shadow=True)
        보다 나중에 실행되면, PENDING_BASELINE media 댓글이 SHADOW_SEEN 태그를 남기고,
        나중에 이 media가 ACTIVE+enforce가 돼도 그 태그 때문에 영원히 재claim이
        안 돼(stale reclaim WHERE절이 migration_tag IS NULL만 허용) 응답이 영구
        유실된다. 게이트가 claim보다 먼저 실행되면 애초에 행 자체가 안 생겨야 한다."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "is_allowlist_gating_enabled", lambda: True)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "PENDING_BASELINE"})

        comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert ces.get_status("instagram_comment", "c1") is None, "PENDING_BASELINE media는 event_store에 흔적을 남기면 안 됨"

    def test_pending_baseline_comment_becomes_processable_once_active(self, monkeypatch, _stub_effects, _enforce_ready):
        """위 시나리오의 끝까지 확인 — PENDING일 때 막힌 댓글이, 나중에 ACTIVE+enforce가
        되면 (SHADOW_SEEN 태그로 영구 고착되지 않고) 정상적으로 처리돼야 한다."""
        cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": ["media-campaign"]}), encoding="utf-8")
        monkeypatch.setattr(comment_auto_reply.poll_targets, "is_allowlist_gating_enabled", lambda: True)
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "PENDING_BASELINE"})
        result_pending = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")
        assert result_pending == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY

        # media가 baseline을 거쳐 ACTIVE가 되고, 운영 모드도 enforce로 전환됨
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "ACTIVE"})
        result_active = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="poller")

        assert result_active == comment_auto_reply.CommentProcessResult.ACCEPTED, "PENDING 시기에 막힌 댓글도 ACTIVE 전환 후엔 정상 처리돼야 함(영구 고착 금지)"
        assert _stub_effects["telegram"] == 1

    def test_disabled_mode_also_blocked_by_gating(self, monkeypatch, _stub_effects):
        """P0(260716 Codex 7차 리뷰) — allowlist gating은 event-store 모드와 무관한
        최상위 안전장치여야 한다. disabled 모드라고 이 게이트를 우회하면 안 됨."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "disabled")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "is_allowlist_gating_enabled", lambda: True)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "PENDING_BASELINE"})

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY
        assert _stub_effects["telegram"] == 0, "disabled 모드여도 PENDING_BASELINE 캠페인 media는 실처리되면 안 됨"

    def test_shadow_blocks_pending_baseline_campaign_media_when_gating_enabled(self, monkeypatch, _stub_effects):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "is_allowlist_gating_enabled", lambda: True)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "PENDING_BASELINE"})

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY
        assert _stub_effects["telegram"] == 0, "PENDING_BASELINE media는 webhook 경로로 들어와도 실처리되면 안 됨"

    def test_shadow_allows_active_campaign_media_when_gating_enabled(self, monkeypatch, _stub_effects):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": ["media-campaign"]}), encoding="utf-8")
        monkeypatch.setattr(comment_auto_reply.poll_targets, "is_allowlist_gating_enabled", lambda: True)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "ACTIVE"})

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.LEGACY
        assert _stub_effects["telegram"] == 1

    def test_shadow_missing_poll_target_row_fails_closed(self, monkeypatch, _stub_effects):
        """media가 캠페인 JSON에는 있지만(sync가 아직 이 media를 못 봄) poll_targets
        행 자체가 없는 비정상 상태 — allowlist 운영 중이면 fail-closed돼야 한다.
        260716: guard.is_campaign_post 목킹이 아니라 실제 캠페인 JSON에 media_id를
        넣어야 한다(게이트가 이제 load_campaign_media_ids()를 직접 호출하므로)."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": ["media-campaign"]}), encoding="utf-8")
        monkeypatch.setattr(comment_auto_reply.poll_targets, "is_allowlist_gating_enabled", lambda: True)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: None)

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY
        assert _stub_effects["telegram"] == 0

    def test_corrupted_campaign_json_fails_closed_even_with_gating_disabled(self, monkeypatch, _stub_effects):
        """P0(260716 Codex 8차 리뷰) — JSON 손상은 "캠페인 아님"과 다르다. 손상 시엔
        allowlist gating 플래그 상태와 무관하게 전체 차단해야 한다(상태를 신뢰할
        근거 자체가 없으므로)."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        cfg._CONFIG_PATH.write_text("{not valid json", encoding="utf-8")

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY
        assert _stub_effects["telegram"] == 0

    def test_media_removed_from_json_with_paused_history_stays_blocked(self, monkeypatch, _stub_effects):
        """media가 캠페인 JSON에서 빠지고 poll_targets도 이미 PAUSED로 동기화된
        (정상 경로) 경우 계속 차단돼야 한다. is_campaign_post()만 보면 "무관한
        media"로 오인해 통과시켜버림."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": []}), encoding="utf-8")  # media-campaign 없음
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "PAUSED"})

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY
        assert _stub_effects["telegram"] == 0

    def test_media_just_removed_from_json_still_blocked_before_db_resync(self, monkeypatch, _stub_effects):
        """P0(260716 Codex 9차 리뷰, 실제 재현 확인) — media가 방금 JSON에서
        제거됐지만 sync_from_campaign_json()이 아직 한 번도 안 돌아 poll_targets가
        여전히 ACTIVE로 남아있는 경쟁 구간. 이전 코드는 "DB에 이력이 있으니 DB
        상태만 본다"고 판단해 이 경우를 통과시켜버렸다(테스트 이름은 이 시나리오를
        검증한다고 돼 있었지만 실제로는 PAUSED를 mock해 이 race window 자체를
        검증하지 못했음 — 이번에 제대로 된 ACTIVE+JSON-empty 조합으로 검증)."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": []}), encoding="utf-8")  # media-campaign 방금 제거됨
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "ACTIVE"})  # sync 전이라 아직 ACTIVE

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY, "JSON에서 빠졌으면 DB가 아직 ACTIVE여도 즉시 차단해야 함"
        assert _stub_effects["telegram"] == 0

    def test_pending_baseline_blocked_even_when_allowlist_flag_still_off(self, monkeypatch, _stub_effects):
        """P0(260716 Codex 8차 리뷰) — Phase B(baseline dry-run/apply/verify)는
        COMMENT_POLL_ALLOWLIST_MODE=legacy(기본값)인 상태에서 진행될 수 있다.
        그 작업 도중 apply가 막 만든 PENDING_BASELINE 행은 flag가 꺼져 있어도
        보호돼야 한다 — 그러지 않으면 이 시기에 도착한 새 댓글이 SHADOW_SEEN
        태그로 영구 고착되는 사고가 재현된다."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        assert comment_auto_reply.poll_targets.is_allowlist_gating_enabled() is False  # 기본값 확인
        cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": ["media-campaign"]}), encoding="utf-8")
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "PENDING_BASELINE"})

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY
        assert ces.get_status("instagram_comment", "c1") is None, "PENDING_BASELINE media는 flag 상태와 무관하게 event row를 만들면 안 됨"
        assert _stub_effects["telegram"] == 0

    def test_gating_does_not_affect_non_campaign_media(self, monkeypatch, _stub_effects):
        """gating이 켜져있어도 캠페인 게시물이 아니면 이 게이트와 무관 — 기존 동작 그대로."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: False)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "is_allowlist_gating_enabled", lambda: True)

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-not-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.LEGACY
        assert _stub_effects["telegram"] == 1

    def test_enforce_blocks_pending_baseline_campaign_media_when_gating_enabled(self, monkeypatch, _stub_effects, _enforce_ready):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        monkeypatch.setattr(comment_auto_reply.poll_targets, "is_allowlist_gating_enabled", lambda: True)
        monkeypatch.setattr(comment_auto_reply.poll_targets, "get_target", lambda media_id: {"state": "PENDING_BASELINE"})

        result = comment_auto_reply.process_comment_event("c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook")

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY
        assert _stub_effects["telegram"] == 0
        assert ces.get_status("instagram_comment", "c1") is None, "REJECTED_NOT_READY는 claim 자체를 시도하지 않아야 함"
        assert ces.get_status("instagram_comment", "c1") is None


class TestLegacyHandleCommentUnaffected:
    def test_handle_comment_still_works_directly(self, _stub_effects):
        """기존 handle_comment() 직접 호출 경로(레거시 진입점)는 그대로 동작해야 한다."""
        comment_auto_reply.handle_comment("c1", "buyer1", "예쁘네요", "media1")
        assert _stub_effects["telegram"] == 1
        assert _stub_effects["record"] == 1
