"""tests/test_comment_event_store.py — FP-047 Inbox 핵심 동작 단위테스트."""

import time
import threading

import pytest

from modules.comment import comment_event_store as ces


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """테스트마다 독립된 SQLite 파일 사용 — 테스트 간 오염 방지."""
    db_path = tmp_path / "comment_events_test.db"
    monkeypatch.setattr(ces, "_DB_PATH", db_path)
    monkeypatch.setattr(ces, "_conn", None)
    yield


class TestTryClaim:
    def test_first_claim_succeeds(self):
        token = ces.try_claim("instagram_comment", "c1", "webhook")
        assert token is not None

    def test_second_claim_same_event_fails(self):
        """웹훅+폴러가 같은 comment_id를 동시에 처리하려 하면 정확히 1번만 성공해야 한다."""
        t1 = ces.try_claim("instagram_comment", "c1", "webhook")
        t2 = ces.try_claim("instagram_comment", "c1", "poller")
        assert t1 is not None
        assert t2 is None

    def test_different_event_ids_both_succeed(self):
        t1 = ces.try_claim("instagram_comment", "c1", "webhook")
        t2 = ces.try_claim("instagram_comment", "c2", "webhook")
        assert t1 is not None and t2 is not None

    def test_concurrent_claim_same_event_only_one_wins(self):
        """스레드 동시 진입 — 정확히 1개 스레드만 claim에 성공해야 한다(원자성 확인)."""
        results = []
        lock = threading.Lock()

        def worker(ingress):
            token = ces.try_claim("instagram_comment", "c-race", ingress)
            with lock:
                results.append(token)

        threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        won = [r for r in results if r is not None]
        assert len(won) == 1, f"동시 claim 10회 중 정확히 1번만 성공해야 함, 실제={len(won)}"


class TestFencingToken:
    def test_stale_token_write_is_rejected(self):
        """다른 worker가 reclaim해서 token이 바뀐 뒤, 옛 token으로의 쓰기는 거절되어야 한다."""
        token = ces.try_claim("instagram_comment", "c1", "webhook")
        ok = ces.mark_effect_started("instagram_comment", "c1", "wrong-forged-token", "telegram")
        assert ok is False

    def test_correct_token_write_succeeds(self):
        token = ces.try_claim("instagram_comment", "c1", "webhook")
        ok = ces.mark_effect_started("instagram_comment", "c1", token, "telegram")
        assert ok is True

    def test_reclaim_issues_new_token_and_fences_old_one(self):
        old_token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)
        time.sleep(0.05)
        recovered = ces.reclaim_stale("instagram_comment", max_age_seconds=60)
        assert recovered and recovered[0][0] == "c1"
        new_token = recovered[0][1]
        assert new_token != old_token

        # 옛 token은 이제 거절
        assert ces.mark_airtable_done("instagram_comment", "c1", old_token) is False
        # 새 token은 정상 동작
        assert ces.mark_airtable_done("instagram_comment", "c1", new_token) is True


class TestTryClaimAutoReclaim:
    """P0-2 (260715 Codex 2차 리뷰) — claim 직후 crash돼도 다음 try_claim() 시도가
    자연히 stale row를 원자적으로 재claim해야 한다(별도 스윕 잡 없이)."""

    def test_try_claim_recovers_stale_row_without_explicit_reclaim(self):
        old_token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)
        assert old_token is not None
        time.sleep(0.05)

        # reclaim_stale()을 명시적으로 호출하지 않고, 다음 try_claim() 시도만으로 복구돼야 함
        new_token = ces.try_claim("instagram_comment", "c1", "poller")
        assert new_token is not None
        assert new_token != old_token

        # 옛 token은 fenced-out
        assert ces.mark_airtable_done("instagram_comment", "c1", old_token) is False
        assert ces.mark_airtable_done("instagram_comment", "c1", new_token) is True

    def test_try_claim_does_not_reclaim_fresh_lease(self):
        """lease가 아직 안 끝났으면 재claim 시도해도 실패해야 한다(진짜 진행중)."""
        token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=60)
        again = ces.try_claim("instagram_comment", "c1", "poller")
        assert again is None

    def test_concurrent_reclaim_only_one_wins(self):
        """두 호출자가 동시에 같은 stale row를 재claim하려 하면 정확히 1개만 성공해야 한다."""
        ces.try_claim("instagram_comment", "c-race", "webhook", lease_seconds=0)
        time.sleep(0.05)

        results = []
        lock = threading.Lock()

        def worker(ingress):
            token = ces.try_claim("instagram_comment", "c-race", ingress)
            with lock:
                results.append(token)

        threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        won = [r for r in results if r is not None]
        assert len(won) == 1, f"동시 재claim 10회 중 정확히 1번만 성공해야 함, 실제={len(won)}"


class TestStaleStartedRecovery:
    def test_started_effect_becomes_unknown_on_reclaim(self):
        """claim 직후 crash(STARTED에서 멈춤) 시나리오 — reclaim되면 UNKNOWN + 수동검토 플래그."""
        token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)
        ces.mark_effect_started("instagram_comment", "c1", token, "private_reply")
        time.sleep(0.05)

        ces.reclaim_stale("instagram_comment", max_age_seconds=60)
        status = ces.get_status("instagram_comment", "c1")
        assert status["private_reply_status"] == "UNKNOWN"
        assert status["manual_review_required"] == 1

    def test_not_applicable_effect_untouched_on_reclaim(self):
        """텔레그램은 안 건드렸으면 reclaim해도 NOT_APPLICABLE 그대로여야 한다."""
        token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)
        ces.mark_effect_started("instagram_comment", "c1", token, "private_reply")
        time.sleep(0.05)
        ces.reclaim_stale("instagram_comment", max_age_seconds=60)
        status = ces.get_status("instagram_comment", "c1")
        assert status["telegram_status"] == "NOT_APPLICABLE"


class TestDeadAlertDedup:
    def test_first_claim_succeeds_second_fails_until_reset(self):
        ok1 = ces.try_claim_dead_alert(42)
        assert ok1 is True
        # 아직 SENT로 안 바뀌었으니 다시 claim 시도해도 PENDING이라 True(재시도 허용)
        ok2 = ces.try_claim_dead_alert(42)
        assert ok2 is True

    def test_after_sent_no_further_alerts(self):
        ces.try_claim_dead_alert(42)
        ces.mark_dead_alert_sent(42)
        ok = ces.try_claim_dead_alert(42)
        assert ok is False


class TestFindByRetryTaskId:
    def test_round_trip(self):
        token = ces.try_claim("instagram_comment", "c1", "webhook")
        ces.mark_airtable_retry_pending("instagram_comment", "c1", token, 999)
        found = ces.find_by_retry_task_id(999)
        assert found == ("instagram_comment", "c1")

    def test_not_found_returns_none(self):
        assert ces.find_by_retry_task_id(123456) is None
