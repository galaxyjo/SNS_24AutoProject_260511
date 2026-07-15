"""tests/test_fp047_crash_recovery.py — P0-2/P0-3/P0-4(260715 Codex 2차 리뷰) 검증.

시나리오: claim → 일부 effect 완료 → crash(lease 만료) → 재진입(poller 등)이
try_claim()으로 자동 reclaim → 이미 끝난 effect는 재실행 안 하고, 아직 안 끝난
것만 마저 처리해야 한다. fencing에 걸린 worker는 즉시 중단해야 한다."""

import time

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
def _enable_auto_reply(monkeypatch):
    monkeypatch.setattr(comment_auto_reply, "_AUTO_REPLY_ENABLED", True)


class _FakeRepo:
    def __init__(self):
        self.created = []
        self.existing = {}

    def find_lead_interaction_by_source_event(self, source, source_event_id):
        return self.existing.get((source, source_event_id))

    def create_lead_interaction(self, data):
        rec_id = f"rec{len(self.created)}"
        self.created.append(data)
        self.existing[(data["source"], data["source_event_id"])] = rec_id
        return rec_id


@pytest.fixture
def fake_repo(monkeypatch):
    repo = _FakeRepo()
    monkeypatch.setattr(comment_auto_reply, "_repo", repo)
    return repo


class TestP0_3_FencingAbort:
    def test_fenced_out_worker_does_not_send_telegram(self, monkeypatch, fake_repo):
        """claim_token이 이미 reclaim되어 무효화된 상태 — 발송 자체가 일어나면 안 된다."""
        sent = []
        monkeypatch.setattr(comment_auto_reply, "TELEGRAM_BOT_TOKEN", None, raising=False)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake")

        def _fake_post(url, json=None, timeout=None):
            sent.append(json)
            class R:
                ok = True
                status_code = 200
            return R()
        monkeypatch.setattr(comment_auto_reply.requests, "post", _fake_post)

        real_token = ces.try_claim("instagram_comment", "c1", "webhook")
        # 이 token은 이제 유효하지 않다고 가정(위조된 값으로 시뮬레이션)
        forged_token = "forged-invalid-token"

        comment_auto_reply._send_telegram_comment(forged_token, "c1", "buyer1", "안녕하세요", "new")
        assert sent == [], "fencing 실패 시 실제 발송이 일어나면 안 됨"

    def test_fenced_out_worker_does_not_send_private_reply(self, monkeypatch, fake_repo):
        sent = []
        monkeypatch.setattr(
            comment_auto_reply, "reply_privately_to_comment",
            lambda cid, msg: sent.append(msg) or True,
        )
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
        monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: False)
        monkeypatch.setattr(comment_auto_reply.guard, "is_user_in_cooldown", lambda k: False)
        monkeypatch.setattr(comment_auto_reply.guard, "consume_daily_budget", lambda: True)

        ces.try_claim("instagram_comment", "c1", "webhook")
        forged_token = "forged-invalid-token"

        comment_auto_reply._try_private_reply(forged_token, "c1", "buyer1", "media1", "buyer1")
        assert sent == [], "fencing 실패 시 Private Reply 발송이 일어나면 안 됨"


class TestP0_4_ResumeSkipsCompletedEffects:
    def test_resume_does_not_resend_telegram_already_done(self, monkeypatch, fake_repo):
        """이전 worker가 Telegram은 이미 DONE으로 남기고 crash — 재개 시 재발송 금지."""
        calls = {"telegram": 0}
        monkeypatch.setattr(
            comment_auto_reply, "_send_telegram_comment",
            lambda *a: calls.__setitem__("telegram", calls["telegram"] + 1),
        )

        token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)
        ces.mark_effect_done("instagram_comment", "c1", token, "telegram")
        time.sleep(0.05)

        # 재진입 — stale reclaim으로 새 token 발급됨
        new_token = ces.try_claim("instagram_comment", "c1", "poller")
        assert new_token is not None and new_token != token

        comment_auto_reply._handle_comment_impl(new_token, "c1", "buyer1", "예쁘네요", "media1")
        assert calls["telegram"] == 0, "이미 DONE인 Telegram을 재개 시 다시 보내면 안 됨"

    def test_resume_does_not_reenqueue_when_retry_already_pending(self, monkeypatch, fake_repo):
        """Airtable 쓰기가 이미 retry_queue에 위임된 상태(RETRY_PENDING) — 재개 시 또
        enqueue하면 같은 comment_id에 대해 retry task가 중복 생성된다. 스킵돼야 한다."""
        calls = {"record": 0}
        monkeypatch.setattr(
            comment_auto_reply, "_record_comment",
            lambda *a: calls.__setitem__("record", calls["record"] + 1),
        )
        monkeypatch.setattr(comment_auto_reply, "_send_telegram_comment", lambda *a: None)

        token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)
        ces.mark_airtable_retry_pending("instagram_comment", "c1", token, 999)
        time.sleep(0.05)

        new_token = ces.try_claim("instagram_comment", "c1", "poller")
        assert new_token is not None and new_token != token
        comment_auto_reply._handle_comment_impl(new_token, "c1", "buyer1", "예쁘네요", "media1")
        assert calls["record"] == 0, "RETRY_PENDING(이미 retry_queue가 소유)인데 재개 시 또 enqueue하면 안 됨"

    def test_resume_still_processes_untouched_airtable(self, monkeypatch, fake_repo):
        """실제 코드 순서상 Telegram이 Airtable보다 먼저 실행되므로, 'Telegram DONE +
        Airtable 미시도(crash)' 가 현실적인 재개 시나리오다 — Airtable만 마저 실행돼야 한다."""
        calls = {"telegram": 0, "record": 0}
        monkeypatch.setattr(
            comment_auto_reply, "_send_telegram_comment",
            lambda *a: calls.__setitem__("telegram", calls["telegram"] + 1),
        )
        monkeypatch.setattr(
            comment_auto_reply, "_record_comment",
            lambda *a: calls.__setitem__("record", calls["record"] + 1),
        )

        token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)
        ces.mark_effect_done("instagram_comment", "c1", token, "telegram")
        time.sleep(0.05)

        new_token = ces.try_claim("instagram_comment", "c1", "poller")
        comment_auto_reply._handle_comment_impl(new_token, "c1", "buyer1", "예쁘네요", "media1")
        assert calls["telegram"] == 0, "이미 DONE인 Telegram은 재개 시 스킵돼야 함"
        assert calls["record"] == 1, "아직 미시도인 Airtable은 재개 시 실행돼야 함"
