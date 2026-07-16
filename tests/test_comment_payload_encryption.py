"""tests/test_comment_payload_encryption.py — 260716 A-2: retry payload(db/retry_queue.db)
댓글 원문 암호화. ERR-066(DM 채널 IGSID·원문 무마스킹)과 같은 클래스 문제를
comment_airtable_record retry payload에 대해 Fernet 암호화로 해소한다(Codex 260716
리뷰: 단순 마스킹은 재처리에 필요한 원문을 잃어버리므로 금지, 암호화만 허용)."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from modules.comment import comment_auto_reply
from modules.comment import comment_event_store as ces


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "comment_events_test.db"
    monkeypatch.setattr(ces, "_DB_PATH", db_path)
    monkeypatch.setattr(ces, "_conn", None)
    yield


@pytest.fixture
def enc_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("COMMENT_PAYLOAD_ENC_KEY", key)
    return key


class _FakeRepo:
    """find_lead_interaction_by_source_event: NOT_FOUND=None, FOUND=str, LOOKUP_FAILED=예외."""

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


class TestEncryptDecryptRoundTrip:
    def test_round_trip_recovers_original_text(self, enc_key):
        original = "재고 있나요? 010-1234-5678로 연락주세요"
        enc = comment_auto_reply._encrypt_payload_text(original)
        assert enc != original
        assert original not in enc
        assert comment_auto_reply._decrypt_payload_text(enc) == original

    def test_missing_key_raises_on_encrypt(self, monkeypatch):
        monkeypatch.delenv("COMMENT_PAYLOAD_ENC_KEY", raising=False)
        with pytest.raises(RuntimeError):
            comment_auto_reply._encrypt_payload_text("text")

    def test_wrong_key_fails_decrypt(self, enc_key, monkeypatch):
        enc = comment_auto_reply._encrypt_payload_text("secret")
        monkeypatch.setenv("COMMENT_PAYLOAD_ENC_KEY", Fernet.generate_key().decode())
        with pytest.raises(InvalidToken):
            comment_auto_reply._decrypt_payload_text(enc)


class TestVerifyPayloadCipher:
    """register_retry_handlers()가 launcher 시작 시 1회 호출 — 결과는 로그로만 남기고
    launcher 기동은 막지 않는다(회장 260716 결정: comment 처리만 게이팅, FB크롤링/IG업로드
    등 무관 서비스는 blast radius 밖)."""

    def test_valid_key_verifies_true(self, enc_key):
        assert comment_auto_reply._verify_payload_cipher() is True

    def test_missing_key_verifies_false(self, monkeypatch):
        monkeypatch.delenv("COMMENT_PAYLOAD_ENC_KEY", raising=False)
        assert comment_auto_reply._verify_payload_cipher() is False

    def test_invalid_key_format_verifies_false(self, monkeypatch):
        monkeypatch.setenv("COMMENT_PAYLOAD_ENC_KEY", "not-a-valid-fernet-key")
        assert comment_auto_reply._verify_payload_cipher() is False


class TestRetryPayloadStoresEncryptedText:
    def test_airtable_failure_enqueues_encrypted_payload_not_plaintext(self, fake_repo, enc_key, monkeypatch):
        """260716 회장 지시(A-2) — retry_queue.db에 원문이 그대로 들어가면 안 된다."""

        def _boom(*a, **k):
            raise ConnectionError("airtable down")

        monkeypatch.setattr(fake_repo, "create_lead_interaction", _boom)

        enqueued = []

        class _FakeRQ:
            def enqueue(self, task_type, payload):
                enqueued.append((task_type, payload))
                return 1

        monkeypatch.setattr("modules.common.retry_queue.get_retry_queue", lambda: _FakeRQ())

        token = ces.try_claim("instagram_comment", "c1", "webhook")
        secret_text = "여기로 연락주세요 010-9999-8888"
        result = comment_auto_reply._record_comment(token, "buyer1", secret_text, "c1", "media1")

        assert result is True
        payload = enqueued[0][1]
        assert "text" not in payload, "평문 text 키가 payload에 남아있으면 안 됨"
        assert payload["enc_version"] == 1
        assert secret_text not in payload["text_enc"]
        assert comment_auto_reply._decrypt_payload_text(payload["text_enc"]) == secret_text

    def test_missing_key_at_enqueue_time_treated_as_enqueue_failure(self, fake_repo, monkeypatch):
        """키가 없으면 암호화가 dict 빌드 도중(= rq.enqueue() 호출 전) 실패해야 한다 —
        기존 enqueue 실패 fail-closed 경로(mark_retry_enqueue_failed)를 그대로 재사용,
        신규 상태 불필요(Codex 260716 리뷰 반영)."""
        monkeypatch.delenv("COMMENT_PAYLOAD_ENC_KEY", raising=False)

        def _boom(*a, **k):
            raise ConnectionError("airtable down")

        monkeypatch.setattr(fake_repo, "create_lead_interaction", _boom)

        class _FakeRQ:
            def __init__(self):
                self.calls = 0

            def enqueue(self, task_type, payload):
                self.calls += 1
                return 1

        rq = _FakeRQ()
        monkeypatch.setattr("modules.common.retry_queue.get_retry_queue", lambda: rq)

        token = ces.try_claim("instagram_comment", "c1", "webhook")
        result = comment_auto_reply._record_comment(token, "buyer1", "비밀문의", "c1", "media1")

        assert result is False
        assert rq.calls == 0, "암호화가 실패했으면 enqueue()까지 도달하면 안 됨(원문이 큐에 안 들어감)"
        status = ces.get_status("instagram_comment", "c1")
        assert status["airtable_status"] == "RETRY_ENQUEUE_FAILED"


class TestRetryRecordCommentDecryption:
    def test_decrypts_and_records(self, fake_repo, enc_key):
        enc = comment_auto_reply._encrypt_payload_text("가격 문의합니다")
        comment_auto_reply._retry_record_comment({
            "claim_token": "tok",
            "comment_id":  "c1",
            "username":    "buyer1",
            "text_enc":    enc,
            "enc_version": 1,
            "media_id":    "media1",
        })
        assert fake_repo.created[0]["inquiry_message"] == "가격 문의합니다"

    def test_legacy_plaintext_only_payload_is_rejected(self, fake_repo):
        """260716 2차 리뷰(Codex) — 260716 실측으로 db/retry_queue.db에
        comment_airtable_record 행 0건을 확인했으므로 구형 평문 payload를 지원할 이유가
        없다. text_enc/enc_version 없이 text만 있는 payload는 빈 문자열로 조용히
        처리되면 안 되고 예외로 거부돼야 한다."""
        with pytest.raises(ValueError):
            comment_auto_reply._retry_record_comment({
                "claim_token": "tok",
                "comment_id":  "c1",
                "username":    "buyer1",
                "text":        "구형 평문 페이로드",
                "media_id":    "media1",
            })
        assert fake_repo.created == [], "검증 실패한 payload로 Airtable에 기록되면 안 됨"

    def test_payload_missing_both_text_keys_is_rejected(self, fake_repo):
        """text_enc도 text도 없는 손상된 payload가 빈 문자열로 Airtable에 '기록완료'
        처리되면 실제 리드 내용이 조용히 유실된다 — 예외로 거부돼야 한다."""
        with pytest.raises(ValueError):
            comment_auto_reply._retry_record_comment({
                "claim_token": "tok",
                "comment_id":  "c1",
                "username":    "buyer1",
                "media_id":    "media1",
            })
        assert fake_repo.created == []

    def test_payload_with_both_text_and_text_enc_is_rejected(self, fake_repo, enc_key):
        """text_enc(신규)와 text(구형)가 동시에 있는 payload는 손상/오염 신호 —
        어느 쪽이 진짜인지 임의로 고르지 말고 거부해야 한다."""
        enc = comment_auto_reply._encrypt_payload_text("정상 원문")
        with pytest.raises(ValueError):
            comment_auto_reply._retry_record_comment({
                "claim_token": "tok",
                "comment_id":  "c1",
                "username":    "buyer1",
                "text_enc":    enc,
                "enc_version": 1,
                "text":        "섞여있으면 안 되는 평문",
                "media_id":    "media1",
            })
        assert fake_repo.created == []

    def test_unsupported_enc_version_is_rejected(self, fake_repo, enc_key):
        """향후 포맷이 바뀌어 enc_version이 달라진 payload를 현재 버전 복호화 로직으로
        조용히 잘못 처리하면 안 된다 — 지원하지 않는 버전은 명시적으로 거부."""
        enc = comment_auto_reply._encrypt_payload_text("정상 원문")
        with pytest.raises(ValueError):
            comment_auto_reply._retry_record_comment({
                "claim_token": "tok",
                "comment_id":  "c1",
                "username":    "buyer1",
                "text_enc":    enc,
                "enc_version": 99,
                "media_id":    "media1",
            })
        assert fake_repo.created == []

    def test_decrypt_failure_raises_not_swallowed(self, fake_repo, enc_key, monkeypatch):
        """복호화 실패는 enqueue 실패와 다르다 — 여기서 예외를 삼키면 retry_queue의
        기존 backoff→3회 초과 시 dead 전환→comment_retry_dead_monitor Slack 알림
        인프라를 안 타게 된다(Codex 260716 리뷰 반영, retry_queue.py:145-156이 핸들러
        예외를 이미 이 방식으로 처리하므로 여기서 예외를 삼키면 그 인프라가 무력화됨)."""
        enc = comment_auto_reply._encrypt_payload_text("암호화된 원문")
        monkeypatch.setenv("COMMENT_PAYLOAD_ENC_KEY", Fernet.generate_key().decode())  # 다른 키로 교체(키 손상/교체 시뮬레이션)

        with pytest.raises(InvalidToken):
            comment_auto_reply._retry_record_comment({
                "claim_token": "tok",
                "comment_id":  "c1",
                "username":    "buyer1",
                "text_enc":    enc,
                "enc_version": 1,
                "media_id":    "media1",
            })
        assert fake_repo.created == [], "복호화 실패 시 Airtable에 기록되면 안 됨"


class TestEnforceModeGatedByCipher:
    def test_enforce_rejects_when_cipher_not_verified(self, monkeypatch):
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
        monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda media_id: True)
        monkeypatch.setattr(comment_auto_reply, "_retry_handlers_registered", True)
        monkeypatch.setattr(comment_auto_reply, "_cipher_verified", False)

        result = comment_auto_reply.process_comment_event(
            "c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook"
        )

        assert result == comment_auto_reply.CommentProcessResult.REJECTED_NOT_READY

    def test_shadow_mode_unaffected_by_cipher_state(self, monkeypatch):
        """shadow는 실제 side effect가 이미 실행되는 모드(FP-047 설계)라 cipher 게이트
        대상이 아니다 — enforce 전제조건이므로 shadow/disabled에는 적용하지 않는다."""
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        monkeypatch.setattr(comment_auto_reply, "_cipher_verified", False)
        monkeypatch.setattr(comment_auto_reply, "handle_comment", lambda *a, **k: None)

        result = comment_auto_reply.process_comment_event(
            "c1", "buyer1", "예쁘네요", "media-campaign", ingress="webhook"
        )

        assert result == comment_auto_reply.CommentProcessResult.LEGACY
