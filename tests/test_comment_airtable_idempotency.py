"""tests/test_comment_airtable_idempotency.py — FP-047 Airtable 3-way 조회 + retry 경로 테스트."""

import pytest
from cryptography.fernet import Fernet

from modules.comment import comment_auto_reply
from modules.comment import comment_event_store as ces


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "comment_events_test.db"
    monkeypatch.setattr(ces, "_DB_PATH", db_path)
    monkeypatch.setattr(ces, "_conn", None)
    yield


@pytest.fixture(autouse=True)
def _enc_key(monkeypatch):
    """260716 A-2 — retry payload 암호화 키. 개발자 로컬 .env 값에 의존하지 않도록
    테스트마다 명시적으로 새 키를 설정(ambient .env 상태와 무관하게 결정적이어야 함)."""
    monkeypatch.setenv("COMMENT_PAYLOAD_ENC_KEY", Fernet.generate_key().decode())


class _FakeRepo:
    """find_lead_interaction_by_source_event: NOT_FOUND=None, FOUND=str, LOOKUP_FAILED=예외."""

    def __init__(self):
        self.created = []
        self.existing = {}
        self.lookup_should_fail = False

    def find_lead_interaction_by_source_event(self, source, source_event_id):
        if self.lookup_should_fail:
            raise ConnectionError("simulated network failure")
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


class TestIdempotentCreate:
    def test_not_found_creates_new_record(self, fake_repo):
        comment_auto_reply._create_lead_interaction_idempotent("buyer1", "가격문의", "c1")
        assert len(fake_repo.created) == 1

    def test_found_skips_creation(self, fake_repo):
        fake_repo.existing[("instagram_comment", "c1")] = "rec_existing"
        comment_auto_reply._create_lead_interaction_idempotent("buyer1", "가격문의", "c1")
        assert len(fake_repo.created) == 0, "이미 존재하면 새로 생성하면 안 됨(중복 방지)"

    def test_lookup_failed_propagates_exception(self, fake_repo):
        """LOOKUP_FAILED를 NOT_FOUND로 취급해서 생성을 진행하면 안 된다 — 예외가 그대로 올라와야 함."""
        fake_repo.lookup_should_fail = True
        with pytest.raises(ConnectionError):
            comment_auto_reply._create_lead_interaction_idempotent("buyer1", "가격문의", "c1")
        assert len(fake_repo.created) == 0


class TestRecordCommentRetryPath:
    def test_success_marks_airtable_done(self, fake_repo):
        token = ces.try_claim("instagram_comment", "c1", "webhook")
        comment_auto_reply._record_comment(token, "buyer1", "가격문의", "c1", "media1")
        status = ces.get_status("instagram_comment", "c1")
        assert status["airtable_status"] == "DONE"
        assert status["status"] == "COMPLETED"

    def test_failure_enqueues_retry_task(self, fake_repo, monkeypatch):
        """Airtable 쓰기 실패 시 retry_queue에 위임되고 airtable_status=RETRY_PENDING이어야 한다."""
        def _boom(*a, **k):
            raise ConnectionError("airtable down")
        monkeypatch.setattr(fake_repo, "create_lead_interaction", _boom)

        enqueued = []

        class _FakeRQ:
            def enqueue(self, task_type, payload):
                enqueued.append((task_type, payload))
                return 777

        monkeypatch.setattr(
            "modules.common.retry_queue.get_retry_queue", lambda: _FakeRQ()
        )

        token = ces.try_claim("instagram_comment", "c1", "webhook")
        result = comment_auto_reply._record_comment(token, "buyer1", "가격문의", "c1", "media1")

        assert result is True, "retry_queue가 payload를 durable 보유하므로 durably_accepted=True여야 함"
        assert len(enqueued) == 1
        assert enqueued[0][0] == "comment_airtable_record"
        status = ces.get_status("instagram_comment", "c1")
        assert status["airtable_status"] == "RETRY_PENDING"
        assert status["retry_task_id"] == 777

    def test_enqueue_itself_failing_returns_false(self, fake_repo, monkeypatch):
        """P0(260715 Codex 4차 리뷰) — Airtable도 실패, retry_queue.enqueue() 자체도
        실패(fail-closed)하면 _record_comment()는 반드시 False를 반환해야 한다.
        이전엔 이 신호가 호출부까지 전달 안 돼서 process_comment_event가 ACCEPTED로
        잘못 보고했음(webhook 200 + poller 캐시 = 복구 기회 상실)."""
        def _boom(*a, **k):
            raise ConnectionError("airtable down")
        monkeypatch.setattr(fake_repo, "create_lead_interaction", _boom)

        class _FakeRQ:
            def enqueue(self, task_type, payload):
                raise RuntimeError("retry_queue.db locked")

        monkeypatch.setattr("modules.common.retry_queue.get_retry_queue", lambda: _FakeRQ())

        token = ces.try_claim("instagram_comment", "c1", "webhook")
        result = comment_auto_reply._record_comment(token, "buyer1", "가격문의", "c1", "media1")

        assert result is False
        status = ces.get_status("instagram_comment", "c1")
        assert status["airtable_status"] == "RETRY_ENQUEUE_FAILED"

    def test_process_comment_event_reflects_enqueue_failure_end_to_end(self, fake_repo, monkeypatch):
        """_record_comment의 False가 _handle_comment_impl → process_comment_event까지
        정확히 전파돼 REJECTED_NOT_READY로 나오는지 end-to-end 확인."""
        def _boom(*a, **k):
            raise ConnectionError("airtable down")
        monkeypatch.setattr(fake_repo, "create_lead_interaction", _boom)

        class _FakeRQ:
            def enqueue(self, task_type, payload):
                raise RuntimeError("retry_queue.db locked")

        monkeypatch.setattr("modules.common.retry_queue.get_retry_queue", lambda: _FakeRQ())
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
        monkeypatch.setattr(comment_auto_reply, "_retry_handlers_registered", True)
        monkeypatch.setattr(comment_auto_reply, "_send_telegram_comment", lambda *a: None)
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")

        result = comment_auto_reply.process_comment_event(
            "c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook",
        )
        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY

    def test_retry_handler_replays_successfully(self, fake_repo):
        """_retry_record_comment는 Airtable 쓰기만 재시도 — Reply/Telegram은 이 경로에서 호출되지 않는다."""
        token = ces.try_claim("instagram_comment", "c1", "webhook")
        ces.mark_airtable_retry_pending("instagram_comment", "c1", token, 777)

        comment_auto_reply._retry_record_comment({
            "claim_token": token,
            "comment_id":  "c1",
            "username":    "buyer1",
            "text_enc":    comment_auto_reply._encrypt_payload_text("가격문의"),
            "enc_version": 1,
            "media_id":    "media1",
        })

        assert len(fake_repo.created) == 1
        status = ces.get_status("instagram_comment", "c1")
        assert status["airtable_status"] == "DONE"

    def test_mark_airtable_done_fencing_failure_returns_false_and_converges(self, fake_repo):
        """P0(260715 Codex 5차 리뷰) — Airtable 생성은 성공했는데 mark_airtable_done()의
        fencing이 실패(claim_token 노후화)하면 False를 반환해야 한다(이전엔 무시하고
        항상 True). False로 재시도를 유도하면, 다음 시도(재claim)가 idempotent 조회로
        중복 없이 상태를 COMPLETED까지 수렴시킬 수 있어야 한다."""
        token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)

        # mark_airtable_done 호출 시점에 이미 다른 worker가 reclaim해서 token이
        # 무효화된 상황을 시뮬레이션: 실제 claim_token 대신 위조값을 넘겨 fencing 실패 유도
        import time as _time
        _time.sleep(0.05)
        stale_reclaim_token = ces.try_claim("instagram_comment", "c1", "poller")  # lease 만료로 재claim, token 변경
        assert stale_reclaim_token is not None and stale_reclaim_token != token

        # 원래 token(이제 노후화됨)으로 _record_comment 실행 — Airtable 쓰기는 성공하지만
        # mark_airtable_done(옛 token)은 fencing 실패해야 함
        result = comment_auto_reply._record_comment(token, "buyer1", "가격문의", "c1", "media1")

        assert result is False, "fencing 실패는 durably_accepted=False로 보고해 재시도를 유도해야 함"
        assert len(fake_repo.created) == 1, "Airtable 레코드 자체는 정상 생성됨(중복 아님)"

        # 재시도(새 token으로 재개) — idempotent 조회가 기존 레코드를 찾아 중복 생성 안 하고 수렴
        result2 = comment_auto_reply._record_comment(stale_reclaim_token, "buyer1", "가격문의", "c1", "media1")
        assert result2 is True
        assert len(fake_repo.created) == 1, "재시도해도 레코드가 중복 생성되면 안 됨"
        status = ces.get_status("instagram_comment", "c1")
        assert status["status"] == "COMPLETED", "결국 정상 수렴해야 함"

    def test_mark_airtable_retry_pending_fencing_failure_returns_false(self, fake_repo, monkeypatch):
        """enqueue 자체는 성공(retry_queue.db가 payload를 durable 보유)했지만
        mark_airtable_retry_pending()의 fencing이 실패한 경우도 False를 반환해
        거짓 ACCEPTED를 방지해야 한다."""
        def _boom(*a, **k):
            raise ConnectionError("airtable down")
        monkeypatch.setattr(fake_repo, "create_lead_interaction", _boom)

        enqueued = []

        class _FakeRQ:
            def enqueue(self, task_type, payload):
                enqueued.append((task_type, payload))
                return 777

        monkeypatch.setattr("modules.common.retry_queue.get_retry_queue", lambda: _FakeRQ())

        token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)
        import time as _time
        _time.sleep(0.05)
        ces.try_claim("instagram_comment", "c1", "poller")  # stale reclaim — 원래 token 무효화

        result = comment_auto_reply._record_comment(token, "buyer1", "가격문의", "c1", "media1")

        assert result is False, "retry_pending 마킹이 fencing 실패하면 False로 재시도 유도해야 함"
        assert len(enqueued) == 1, "enqueue 자체는 이미 성공(durable) — 이건 그대로 유지"

    def test_retry_handler_completes_even_after_claim_token_went_stale(self, fake_repo):
        """P0(260715 Codex 3차 리뷰) — retry_queue 백오프 대기 중 lease가 만료돼 다른
        worker가 stale reclaim(P0-2)하면 payload의 claim_token은 무효화된다. 그래도
        실제 Airtable 쓰기가 성공하면 event_store 완료 반영까지 되어야 한다(이전엔
        claim_token fencing 때문에 여기서 실패해 영구히 RETRY_PENDING에 고착됐음)."""
        import time as _time

        token = ces.try_claim("instagram_comment", "c1", "webhook", lease_seconds=0)
        ces.mark_airtable_retry_pending("instagram_comment", "c1", token, 777)
        _time.sleep(0.05)

        # 다른 worker(poller)가 lease 만료를 감지해 stale reclaim — claim_token이 바뀜
        new_token = ces.try_claim("instagram_comment", "c1", "poller")
        assert new_token is not None and new_token != token

        # retry_queue가 원래 token(payload에 저장된 옛 값)으로 재시도 실행
        comment_auto_reply._retry_record_comment({
            "claim_token": token,  # 옛(무효화된) token — 더 이상 사용 안 함
            "comment_id":  "c1",
            "username":    "buyer1",
            "text_enc":    comment_auto_reply._encrypt_payload_text("가격문의"),
            "enc_version": 1,
            "media_id":    "media1",
        })

        assert len(fake_repo.created) == 1, "Airtable 쓰기 자체는 성공해야 함"
        status = ces.get_status("instagram_comment", "c1")
        assert status["airtable_status"] == "DONE", "claim_token이 노후화됐어도 완료로 반영돼야 함"
        assert status["status"] == "COMPLETED"

    def test_retry_handler_no_duplicate_on_ambiguous_success(self, fake_repo):
        """create는 실제로 성공했는데 응답이 유실된 것처럼 보이는 상황 — 재시도해도 중복 생성 안 됨."""
        # 1차: 성공적으로 생성됨(정상 흐름을 시뮬레이션)
        fake_repo.existing[("instagram_comment", "c1")] = "rec_already_created"

        token = ces.try_claim("instagram_comment", "c1", "webhook")
        ces.mark_airtable_retry_pending("instagram_comment", "c1", token, 777)

        # 2차: retry handler가 재실행됨(응답 유실로 착각했던 상황 재현)
        comment_auto_reply._retry_record_comment({
            "claim_token": token,
            "comment_id":  "c1",
            "username":    "buyer1",
            "text_enc":    comment_auto_reply._encrypt_payload_text("가격문의"),
            "enc_version": 1,
            "media_id":    "media1",
        })

        assert len(fake_repo.created) == 0, "이미 존재하는데 재시도로 중복 생성되면 안 됨"
