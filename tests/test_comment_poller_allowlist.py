"""tests/test_comment_poller_allowlist.py — Package 1 Phase A 검증:
- COMMENT_POLL_ALLOWLIST_MODE 플래그 기본값(legacy)이 실제로 기존 동작 그대로인지
- allowlist 모드에서 comment_poll_targets(ACTIVE)를 감시 대상으로 사용하는지
- fetch_all_comments()의 전체 페이지네이션 + 페이지 상한 초과 시 CommentFetchIncomplete
- media 1개 실패가 다른 media 처리를 막지 않음(격리) + 연속 실패 카운트
- 캠페인 설정 손상 시 이번 주기 전체 스킵(fail-closed)
(260715, Codex 5·6차 리뷰)

260715 주의: airtable_repository가 import 시점에 실제 .env를 load_dotenv(override=True)
하므로, get_recent_media_ids()/get_comments()/fetch_all_comments()를 monkeypatch하지
않은 채 poll_new_comments()를 호출하면 실제 Graph API를 호출해버린다(6차 리뷰 준비
중 실제로 한 번 발생 — 읽기 전용 GET이라 피해는 없었으나 재발 방지 위해 이 파일의
모든 테스트는 반드시 셋 다 명시적으로 patch한다). 260716: _poll_legacy()가
fetch_all_comments() 대신 get_comments()(첫 페이지만)를 쓰도록 되돌린 뒤 이 가드가
get_comments()를 놓치고 있어서 실제로 한 번 더 발생함 — 세 함수 모두 가드 대상."""

import pytest

from modules.comment import comment_poller
from modules.comment.comment_auto_reply import CommentProcessResult


def _unmocked_guard(name):
    def _raise(*a, **k):
        raise AssertionError(f"이 테스트는 {name}()를 명시적으로 patch해야 함")
    return _raise


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(comment_poller, "CACHE_PATH", tmp_path / "processed_comment_ids.json")
    monkeypatch.setattr(
        comment_poller, "process_comment_event",
        lambda cid, *a, **k: CommentProcessResult.ACCEPTED,
    )
    # 실수로 실제 Graph API를 부르지 않도록 두 진입점을 막아둔다(각 테스트가 필요시
    # 재정의). fetch_all_comments()는 여기서 막지 않음 — TestFetchAllCommentsPagination이
    # 그 함수 자체(내부적으로 _fetch_comments_page만 mock)를 테스트하기 때문에, 여기서
    # 미리 stub으로 덮어쓰면 그 테스트들이 실제 구현을 검증할 수 없게 된다. 나머지
    # 클래스는 fetch_all_comments를 필요할 때마다 각자 명시적으로 patch한다.
    monkeypatch.setattr(comment_poller, "get_recent_media_ids", _unmocked_guard("get_recent_media_ids"))
    monkeypatch.setattr(comment_poller, "get_comments", _unmocked_guard("get_comments"))


class TestRolloutFlagDefault:
    def test_default_mode_is_legacy(self):
        assert comment_poller.comment_poll_targets.is_allowlist_gating_enabled() is False

    def test_legacy_mode_uses_get_recent_media_ids_not_poll_targets(self, monkeypatch):
        """플래그 기본값(legacy)에서는 comment_poll_targets를 전혀 건드리지 않아야 한다 —
        Phase A 코드가 배포돼도 poll_targets가 비어있는 것과 무관하게 기존 폴링이
        그대로 동작해야 하기 때문(260715 Codex 6차 리뷰 P0-2)."""
        monkeypatch.setattr(comment_poller, "get_recent_media_ids", lambda: ["legacy-media"])

        touched_poll_targets = []
        monkeypatch.setattr(
            comment_poller.comment_poll_targets, "sync_from_campaign_json",
            lambda: touched_poll_targets.append(1) or True,
        )

        def _fake_get_comments(media_id):
            assert media_id == "legacy-media"
            return []

        monkeypatch.setattr(comment_poller, "get_comments", _fake_get_comments)

        comment_poller.poll_new_comments()
        assert touched_poll_targets == [], "legacy 모드에서는 comment_poll_targets를 호출하면 안 됨"

    def test_legacy_mode_uses_single_page_get_comments_not_full_pagination(self, monkeypatch):
        """P0(260716 Codex 7차 리뷰, 실제 재현 확인) — legacy 모드가 fetch_all_comments()
        (전체 페이지네이션)를 쓰면, 이미 감시 중이던 media에 쌓여있던 2페이지 이후
        과거 댓글이 재시작 한 번으로 전부 "신규"가 돼 실제 발송 사고가 난다.
        반드시 get_comments()(첫 페이지만)를 그대로 써야 한다."""
        monkeypatch.setattr(comment_poller, "get_recent_media_ids", lambda: ["legacy-media"])
        monkeypatch.setattr(
            comment_poller, "fetch_all_comments",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("legacy 모드는 fetch_all_comments를 호출하면 안 됨")),
        )
        monkeypatch.setattr(comment_poller, "get_comments", lambda media_id: [
            {"id": "c1", "text": "hi", "username": "u", "from": {"id": "u1"}},
        ])
        comment_poller.poll_new_comments()  # 예외 없이 끝나야 함(fetch_all_comments 미호출 확인)


@pytest.fixture(autouse=True)
def _force_allowlist_mode(monkeypatch, request):
    """이 파일의 TestActiveMediaLoop만 allowlist 모드를 강제한다."""
    if "TestActiveMediaLoop" in request.node.nodeid:
        monkeypatch.setattr(comment_poller.comment_poll_targets, "is_allowlist_gating_enabled", lambda: True)


class TestFetchAllCommentsPagination:
    def test_follows_paging_next_until_exhausted(self, monkeypatch):
        pages = [
            {"data": [{"id": "c1"}], "paging": {"next": "http://fake/page2"}},
            {"data": [{"id": "c2"}], "paging": {"next": "http://fake/page3"}},
            {"data": [{"id": "c3"}], "paging": {}},
        ]
        calls = []

        def _fake_page(url, params=None):
            calls.append(url)
            return pages[len(calls) - 1]

        monkeypatch.setattr(comment_poller, "_fetch_comments_page", _fake_page)
        result = comment_poller.fetch_all_comments("media1")
        assert [c["id"] for c in result] == ["c1", "c2", "c3"]
        assert len(calls) == 3

    def test_raises_incomplete_when_max_pages_exceeded(self, monkeypatch):
        def _fake_page(url, params=None):
            return {"data": [{"id": "x"}], "paging": {"next": "http://fake/next"}}

        monkeypatch.setattr(comment_poller, "_fetch_comments_page", _fake_page)
        with pytest.raises(comment_poller.CommentFetchIncomplete):
            comment_poller.fetch_all_comments("media1", max_pages=2)


class TestSameCycleDuplicate:
    def test_duplicate_id_across_pages_processed_once(self, monkeypatch):
        """P0-5(260715 Codex 6차 리뷰) — 페이지 경계에서 같은 comment_id가 겹쳐도
        같은 주기 안에서는 1번만 처리돼야 한다. allowlist 경로(fetch_all_comments가
        실제로 쓰이는 경로)로 검증 — legacy는 260716부터 get_comments(단일 페이지)만
        쓰므로 페이지 경계 중복 시나리오 자체가 legacy에는 해당 안 됨."""
        monkeypatch.setattr(comment_poller.comment_poll_targets, "is_allowlist_gating_enabled", lambda: True)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "sync_from_campaign_json", lambda: True)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "get_active_media_ids", lambda: ["m1"])
        monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_success", lambda m: None)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_failure", lambda m: 1)
        monkeypatch.setattr(comment_poller, "fetch_all_comments", lambda media_id, max_pages=None: [
            {"id": "dup", "text": "hi", "username": "u", "from": {"id": "u1"}},
            {"id": "dup", "text": "hi", "username": "u", "from": {"id": "u1"}},
        ])
        calls = []
        monkeypatch.setattr(
            comment_poller, "process_comment_event",
            lambda cid, *a, **k: (calls.append(cid), CommentProcessResult.ACCEPTED)[1],
        )
        comment_poller.poll_new_comments()
        assert calls == ["dup"], "같은 주기 안에서 같은 comment_id가 두 번 처리됨"


class TestActiveMediaLoop:
    def test_uses_poll_targets_active_media_not_recent_media(self, monkeypatch):
        """get_recent_media_ids()가 절대 호출되면 안 된다(allowlist 모드에서는 무관 경로)."""
        monkeypatch.setattr(
            comment_poller, "get_recent_media_ids",
            lambda: (_ for _ in ()).throw(AssertionError("allowlist 모드에서 get_recent_media_ids가 호출됨")),
        )
        monkeypatch.setattr(comment_poller.comment_poll_targets, "sync_from_campaign_json", lambda: True)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "get_active_media_ids", lambda: ["active1"])
        monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_success", lambda m: None)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_failure", lambda m: 1)

        seen_media = []

        def _fake_fetch(media_id, max_pages=None):
            seen_media.append(media_id)
            return [{"id": "c1", "text": "hi", "username": "u", "from": {"id": "u1"}}]

        monkeypatch.setattr(comment_poller, "fetch_all_comments", _fake_fetch)

        comment_poller.poll_new_comments()
        assert seen_media == ["active1"]

    def test_corrupted_campaign_config_skips_entire_cycle(self, monkeypatch):
        monkeypatch.setattr(comment_poller.comment_poll_targets, "sync_from_campaign_json", lambda: False)
        fetch_called = []
        monkeypatch.setattr(comment_poller, "fetch_all_comments", lambda *a, **k: fetch_called.append(1))

        comment_poller.poll_new_comments()
        assert fetch_called == [], "캠페인 설정이 손상됐으면 아무 media도 조회하면 안 됨(fail-closed)"

    def test_one_media_failure_does_not_block_others(self, monkeypatch):
        monkeypatch.setattr(comment_poller.comment_poll_targets, "sync_from_campaign_json", lambda: True)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "get_active_media_ids", lambda: ["bad", "good"])

        successes = []
        failures = []
        monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_success", lambda m: successes.append(m))
        monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_failure", lambda m: (failures.append(m), 1)[1])

        def _fake_fetch(media_id, max_pages=None):
            if media_id == "bad":
                raise RuntimeError("api down")
            return [{"id": "c-good", "text": "hi", "username": "u", "from": {"id": "u1"}}]

        monkeypatch.setattr(comment_poller, "fetch_all_comments", _fake_fetch)

        comment_poller.poll_new_comments()
        assert successes == ["good"]
        assert failures == ["bad"]

    def test_consecutive_failure_triggers_slack_alert_once(self, monkeypatch):
        monkeypatch.setattr(comment_poller.comment_poll_targets, "sync_from_campaign_json", lambda: True)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "get_active_media_ids", lambda: ["bad"])
        monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_failure", lambda m: 3)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "get_target", lambda m: {"last_alerted_at": None})
        marked = []
        monkeypatch.setattr(comment_poller.comment_poll_targets, "mark_alerted", lambda m: marked.append(m))

        def _fake_fetch(media_id, max_pages=None):
            raise RuntimeError("api down")

        monkeypatch.setattr(comment_poller, "fetch_all_comments", _fake_fetch)

        alerted = []
        import services.slack_notifier as sn
        monkeypatch.setattr(sn, "send_alert", lambda title, body="", level="warning": (alerted.append((title, body)), True)[1])

        comment_poller.poll_new_comments()
        assert marked == ["bad"]
        assert len(alerted) == 1

    def test_slack_send_failure_does_not_mark_alerted(self, monkeypatch):
        """P1(260715 Codex 6차 리뷰) — Slack 전송 자체가 실패(False 반환)했으면
        mark_alerted()를 호출하면 안 된다(안 그러면 이번 실패 streak는 영원히
        재알림 기회를 잃는다)."""
        monkeypatch.setattr(comment_poller.comment_poll_targets, "sync_from_campaign_json", lambda: True)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "get_active_media_ids", lambda: ["bad"])
        monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_failure", lambda m: 3)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "get_target", lambda m: {"last_alerted_at": None})
        marked = []
        monkeypatch.setattr(comment_poller.comment_poll_targets, "mark_alerted", lambda m: marked.append(m))
        monkeypatch.setattr(comment_poller, "fetch_all_comments", lambda media_id, max_pages=None: (_ for _ in ()).throw(RuntimeError("api down")))

        import services.slack_notifier as sn
        monkeypatch.setattr(sn, "send_alert", lambda title, body="", level="warning": False)

        comment_poller.poll_new_comments()
        assert marked == [], "Slack 전송 실패면 mark_alerted 호출 금지"

    def test_already_alerted_media_not_alerted_again(self, monkeypatch):
        monkeypatch.setattr(comment_poller.comment_poll_targets, "sync_from_campaign_json", lambda: True)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "get_active_media_ids", lambda: ["bad"])
        monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_failure", lambda m: 5)
        monkeypatch.setattr(comment_poller.comment_poll_targets, "get_target", lambda m: {"last_alerted_at": "2026-07-15T00:00:00Z"})
        marked = []
        monkeypatch.setattr(comment_poller.comment_poll_targets, "mark_alerted", lambda m: marked.append(m))

        def _fake_fetch(media_id, max_pages=None):
            raise RuntimeError("api down")

        monkeypatch.setattr(comment_poller, "fetch_all_comments", _fake_fetch)

        alerted = []
        import services.slack_notifier as sn
        monkeypatch.setattr(sn, "send_alert", lambda title, body="", level="warning": (alerted.append((title, body)), True)[1])

        comment_poller.poll_new_comments()
        assert marked == [], "이미 알림 보낸 상태면 다시 mark_alerted 호출하면 안 됨"
        assert alerted == []
