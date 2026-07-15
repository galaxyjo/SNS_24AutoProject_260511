"""tests/test_fp047_shadow_isolation.py — P0(260715 Codex 4차 리뷰):
shadow 모드 claim이 SHADOW_SEEN으로 태깅되고, enforce의 stale reclaim에서
영구히 제외되는지 검증. 안 그러면 shadow 중 이미 레거시 경로로 실제 응대한
댓글을 enforce가 "죽은 것"으로 오인해 재claim → 중복 발송하게 된다."""

import time

import pytest

from modules.comment import comment_event_store as ces


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "comment_events_test.db"
    monkeypatch.setattr(ces, "_DB_PATH", db_path)
    monkeypatch.setattr(ces, "_conn", None)
    yield


class TestShadowTagging:
    def test_shadow_claim_is_tagged(self):
        token = ces.try_claim("instagram_comment", "c1", "webhook", shadow=True)
        assert token is not None
        status = ces.get_status("instagram_comment", "c1")
        assert status["migration_tag"] == "SHADOW_SEEN"

    def test_shadow_claim_does_not_retry_on_existing_row(self):
        ces.try_claim("instagram_comment", "c1", "webhook", shadow=True)
        second = ces.try_claim("instagram_comment", "c1", "poller", shadow=True)
        assert second is None, "shadow는 이미 존재하는 행을 재claim 시도하면 안 됨(관측 전용)"


class TestShadowRowNeverReclaimedByEnforce:
    def test_stale_shadow_row_is_not_reclaimed(self):
        """shadow claim이 lease 만료돼도, 뒤이은 enforce(실제) try_claim()이 이 행을
        '죽은 것'으로 오인해 재claim하면 안 된다 — 이미 legacy 경로로 실제 응대됐으므로
        재claim해서 다시 처리하면 손님한테 중복발송된다."""
        shadow_token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0, shadow=True)
        assert shadow_token is not None
        time.sleep(0.05)  # lease 만료

        enforce_token = ces.try_claim("instagram_comment", "c1", "poller")  # shadow=False(기본)
        assert enforce_token is None, "SHADOW_SEEN 태그가 붙은 행은 enforce가 재claim하면 안 됨"

        # 원래 shadow claim_token도 그대로 유효(아무도 안 건드렸으므로)
        status = ces.get_status("instagram_comment", "c1")
        assert status["claim_token"] == shadow_token
        assert status["migration_tag"] == "SHADOW_SEEN"

    def test_real_claim_after_shadow_seen_row_expired_still_blocked(self):
        """여러 번 시간이 지나도 SHADOW_SEEN 행은 계속 재claim 대상에서 제외돼야 한다."""
        ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0, shadow=True)
        time.sleep(0.05)

        for _ in range(3):
            token = ces.try_claim("instagram_comment", "c1", "poller")
            assert token is None
