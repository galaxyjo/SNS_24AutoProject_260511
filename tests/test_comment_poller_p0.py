"""tests/test_comment_poller_p0.py — P0-1(260715 Codex 2차 리뷰) 검증:
process_comment_event()가 예외를 던지면 그 comment_id는 캐시에 남으면 안 된다
(다음 폴링에서 다시 시도돼야 함 — 성공한 셈 치고 영구 스킵되면 안 됨)."""

import pytest

from modules.comment import comment_poller
from modules.comment.comment_auto_reply import CommentProcessResult


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(comment_poller, "CACHE_PATH", tmp_path / "processed_comment_ids.json")
    # 260715 Package 1 Phase A: poll_new_comments()가 이제 comment_poll_targets(SQLite)를
    # 거치므로, 이 파일의 테스트(캐시/재시도 의미론)는 그 상태머신을 실제 DB로 검증하지
    # 않고 "media1이 항상 ACTIVE"인 것처럼 얇게 스텁한다 — 상태머신 자체는
    # test_comment_poll_targets.py가 별도로 검증.
    monkeypatch.setattr(comment_poller.comment_poll_targets, "sync_from_campaign_json", lambda: True)
    monkeypatch.setattr(comment_poller.comment_poll_targets, "get_active_media_ids", lambda: ["media1"])
    monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_success", lambda media_id: None)
    monkeypatch.setattr(comment_poller.comment_poll_targets, "record_poll_failure", lambda media_id: 1)
    monkeypatch.setattr(comment_poller, "fetch_all_comments", lambda media_id: comment_poller.get_comments(media_id))


def _fake_comments(media_id):
    return [
        {"id": "c1", "text": "예쁘네요", "username": "buyer1", "from": {"id": "u1"}},
        {"id": "c2", "text": "가격이요", "username": "buyer2", "from": {"id": "u2"}},
    ]


class TestFailureNotCached:
    def test_exception_prevents_caching(self, monkeypatch):
        """c1은 실패, c2는 성공 — c1만 다음 폴링에서 재시도 대상으로 남아야 한다."""
        monkeypatch.setattr(comment_poller, "get_recent_media_ids", lambda: ["media1"])
        monkeypatch.setattr(comment_poller, "get_comments", _fake_comments)

        def _fake_process(cid, *a, **k):
            if cid == "c1":
                raise ConnectionError("db locked")
            return CommentProcessResult.ACCEPTED

        monkeypatch.setattr(comment_poller, "process_comment_event", _fake_process)

        comment_poller.poll_new_comments()

        cached = comment_poller._load_cache()
        assert "c1" not in cached, "실패한 comment_id가 캐시에 남으면 안 됨(FP-047 재발)"
        assert "c2" in cached, "성공한 comment_id는 캐시에 남아야 함"

    def test_next_poll_retries_previously_failed_comment(self, monkeypatch):
        """1차 폴링에서 실패한 c1이 2차 폴링에서 다시 시도되는지 확인."""
        monkeypatch.setattr(comment_poller, "get_recent_media_ids", lambda: ["media1"])
        monkeypatch.setattr(comment_poller, "get_comments", _fake_comments)

        attempts = {"c1": 0}

        def _fake_process(cid, *a, **k):
            if cid == "c1":
                attempts["c1"] += 1
                if attempts["c1"] == 1:
                    raise ConnectionError("db locked")
            return CommentProcessResult.ACCEPTED

        monkeypatch.setattr(comment_poller, "process_comment_event", _fake_process)

        comment_poller.poll_new_comments()  # 1차 — c1 실패
        comment_poller.poll_new_comments()  # 2차 — c1 재시도돼야 함

        assert attempts["c1"] == 2, "실패했던 comment_id가 다음 폴링에서 재시도되지 않음"
        cached = comment_poller._load_cache()
        assert "c1" in cached, "2차에서 성공했으면 이제 캐시에 남아야 함"

    def test_in_progress_result_not_cached(self, monkeypatch):
        """P0(260715 Codex 3차 리뷰) — 다른 worker가 아직 처리중(IN_PROGRESS)이면
        예외는 아니지만 확정 상태도 아니므로 캐시하면 안 된다."""
        monkeypatch.setattr(comment_poller, "get_recent_media_ids", lambda: ["media1"])
        monkeypatch.setattr(comment_poller, "get_comments", _fake_comments)
        monkeypatch.setattr(
            comment_poller, "process_comment_event",
            lambda cid, *a, **k: CommentProcessResult.IN_PROGRESS if cid == "c1" else CommentProcessResult.ACCEPTED,
        )

        comment_poller.poll_new_comments()

        cached = comment_poller._load_cache()
        assert "c1" not in cached, "IN_PROGRESS는 아직 미확정이므로 캐시되면 안 됨"
        assert "c2" in cached

    def test_rejected_not_ready_result_not_cached(self, monkeypatch):
        monkeypatch.setattr(comment_poller, "get_recent_media_ids", lambda: ["media1"])
        monkeypatch.setattr(comment_poller, "get_comments", _fake_comments)
        monkeypatch.setattr(
            comment_poller, "process_comment_event",
            lambda cid, *a, **k: CommentProcessResult.REJECTED_NOT_READY if cid == "c1" else CommentProcessResult.ACCEPTED,
        )

        comment_poller.poll_new_comments()

        cached = comment_poller._load_cache()
        assert "c1" not in cached, "fail-closed로 거부된 건 캐시되면 안 됨(재시도 필요)"
