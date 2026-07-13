"""tests/test_dm_rules.py — modules/dm/rules.py 단위 테스트"""

import pytest
from modules.dm.rules import RuleResult, evaluate, get_default_policy


# ── RuleResult ────────────────────────────────────────────────────────────────

class TestRuleResult:
    def test_passed_true_is_truthy(self):
        assert RuleResult(True)

    def test_passed_false_is_falsy(self):
        assert not RuleResult(False)

    def test_reason_stored(self):
        r = RuleResult(True, reason="test_reason")
        assert r.reason == "test_reason"

    def test_default_reason_empty(self):
        r = RuleResult(True)
        assert r.reason == ""


# ── get_default_policy ────────────────────────────────────────────────────────

class TestGetDefaultPolicy:
    def test_has_banned_key(self):
        p = get_default_policy()
        assert "banned" in p

    def test_has_allowed_key(self):
        p = get_default_policy()
        assert "allowed" in p

    def test_banned_contains_spam(self):
        assert "spam" in get_default_policy()["banned"]

    def test_allowed_contains_문의(self):
        assert "문의" in get_default_policy()["allowed"]


# ── evaluate ─────────────────────────────────────────────────────────────────

class TestEvaluate:
    def test_allowed_word_passes(self):
        result = evaluate("가격 문의드립니다")
        assert result.passed is True
        assert "allowed" in result.reason

    def test_banned_word_blocked(self):
        result = evaluate("이건 스팸입니다")
        assert result.passed is False
        assert "banned" in result.reason

    def test_neutral_text_passes(self):
        result = evaluate("안녕하세요 반갑습니다")
        assert result.passed is True
        assert result.reason == "no_match"

    def test_empty_string_passes(self):
        result = evaluate("")
        assert result.passed is True

    def test_none_safe(self):
        result = evaluate(None)
        assert result.passed is True

    def test_allowed_takes_priority_over_banned(self):
        # "문의" (allowed) + "spam" (banned) 동시 포함 → allowed 우선 통과
        result = evaluate("spam 문의드립니다")
        assert result.passed is True
        assert "allowed" in result.reason

    def test_custom_policy_banned(self):
        policy = {"banned": {"test_word"}, "allowed": set()}
        result = evaluate("this is a test_word message", policy=policy)
        assert result.passed is False

    def test_custom_policy_allowed(self):
        policy = {"banned": set(), "allowed": {"hello"}}
        result = evaluate("hello world", policy=policy)
        assert result.passed is True

    def test_case_insensitive(self):
        result = evaluate("SPAM 메시지")
        assert result.passed is False

    def test_english_banned_scam(self):
        result = evaluate("this is a scam offer")
        assert result.passed is False

    def test_english_allowed_contact(self):
        result = evaluate("please contact us")
        assert result.passed is True


# ── hook integration (dm_auto_reply 연동) ─────────────────────────────────────

class TestAutoReplyHook:
    @pytest.fixture(autouse=True)
    def _clear_awaiting_product_cache(self):
        """모듈 전역 _AWAITING_PRODUCT_DEDUP가 테스트 간 오염되지 않도록 매 테스트 전후 초기화.
        초기화 안 하면 이전 테스트가 남긴 (sender, 문의문) 키 때문에 이후 테스트가
        실제 발송 경로를 안 타고 중복skip으로 빠져도 assertion이 우연히 통과할 수 있다."""
        from modules.dm import dm_auto_reply
        dm_auto_reply._AWAITING_PRODUCT_DEDUP.clear()
        yield
        dm_auto_reply._AWAITING_PRODUCT_DEDUP.clear()

    def test_handle_price_inquiry_blocked_by_rule(self, monkeypatch):
        """banned 메시지 수신 시 handle_price_inquiry가 조기 반환되어야 한다."""
        from modules.dm import dm_auto_reply

        called = []

        monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: called.append("price") or 10000.0)

        from datetime import datetime, timezone
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test",
            sender_igsid="ig_test",
            inquiry_text="스팸 메시지입니다",
            received_at=datetime.now(timezone.utc),
        )

        assert "price" not in called, "banned 메시지에서 get_base_price 호출됨 — 필터가 동작하지 않음"

    def test_handle_price_inquiry_passes_allowed_price_disabled(self, monkeypatch):
        """Gate C 기본값(PRICE_AUTO_REPLY_ENABLED=false)에서는 필터를 통과해도
        get_base_price를 호출하지 않고 상품확인 요청 템플릿으로 응답해야 한다."""
        from modules.dm import dm_auto_reply

        called = []
        sent_messages = []

        monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
        monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: called.append("price") or None)
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg: sent_messages.append(msg) or True)
        monkeypatch.setattr(dm_auto_reply, "update_lead_replied", lambda *a, **k: None)
        monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

        from datetime import datetime, timezone
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test",
            sender_igsid="ig_test",
            inquiry_text="가격 문의드립니다",
            received_at=datetime.now(timezone.utc),
        )

        assert "price" not in called, "Gate C: PRICE_AUTO_REPLY_ENABLED=false인데 get_base_price가 호출됨"
        assert sent_messages == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE], "상품확인 요청 템플릿이 발송되지 않음"

    def test_handle_price_inquiry_calls_price_when_enabled(self, monkeypatch):
        """PRICE_AUTO_REPLY_ENABLED=true면 allowed 메시지가 get_base_price까지 진행되어야 한다
        (P1-B Post/Product 매핑 완료 후 재활성화될 레거시 경로 회귀 방지)."""
        from modules.dm import dm_auto_reply

        called = []

        monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", True)
        monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: called.append("price") or None)
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: True)

        from datetime import datetime, timezone
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test",
            sender_igsid="ig_test",
            inquiry_text="가격 문의드립니다",
            received_at=datetime.now(timezone.utc),
        )

        assert "price" in called, "PRICE_AUTO_REPLY_ENABLED=true인데 get_base_price 미호출 — 필터가 잘못 차단함"

    def test_awaiting_product_does_not_mark_replied_or_schedule_followup(self, monkeypatch):
        """PRICE_AUTO_REPLY_ENABLED=false 경로는 bridge_status를 auto_replied로 바꾸지 않고
        팔로업도 예약하지 않아야 한다 (상품 미확정 상태에서 "지난번 단가 문의" 팔로업 오발송 방지)."""
        from modules.dm import dm_auto_reply
        from modules.dm import dm_followup_scheduler

        replied_calls = []
        followup_calls = []

        monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: True)
        monkeypatch.setattr(dm_auto_reply, "update_lead_replied", lambda *a, **k: replied_calls.append(1))
        monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
        monkeypatch.setattr(dm_followup_scheduler, "set_followup_schedule", lambda *a, **k: followup_calls.append(1))

        from datetime import datetime, timezone
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test", sender_igsid="ig_test",
            inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
        )

        assert replied_calls == [], "상품확인 대기 경로에서 update_lead_replied가 호출됨"
        assert followup_calls == [], "상품확인 대기 경로에서 팔로업이 예약됨"

    def test_send_failure_does_not_mark_replied_or_schedule_followup(self, monkeypatch):
        """IG DM 발송 실패 시 '답변완료' 상태전환·팔로업예약·Telegram 알림이 되면 안 된다."""
        from modules.dm import dm_auto_reply
        from modules.dm import dm_followup_scheduler
        from modules.common import retry_queue as retry_queue_mod

        replied_calls = []
        followup_calls = []
        telegram_calls = []

        class _FakeRQ:
            def register(self, *a, **k): pass
            def start(self): pass
            def enqueue(self, *a, **k): pass

        monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", True)
        monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: 10000.0)
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: False)
        monkeypatch.setattr(dm_auto_reply, "update_lead_replied", lambda *a, **k: replied_calls.append(1))
        monkeypatch.setattr(dm_auto_reply, "send_telegram_autoreply", lambda *a, **k: telegram_calls.append(1))
        monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: _FakeRQ())
        monkeypatch.setattr(dm_followup_scheduler, "set_followup_schedule", lambda *a, **k: followup_calls.append(1))

        from datetime import datetime, timezone
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test", sender_igsid="ig_test",
            inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
        )

        assert replied_calls == [], "발송 실패했는데 update_lead_replied가 호출됨"
        assert followup_calls == [], "발송 실패했는데 팔로업이 예약됨"
        assert telegram_calls == [], "발송 실패했는데 Telegram 완료 알림이 발송됨"

    def test_telegram_price_pending_masks_igsid_and_pii(self, monkeypatch):
        """send_telegram_price_pending은 IGSID를 마스킹하고 PII 패턴 제거 후 20자로 잘라야 한다."""
        from modules.dm import dm_auto_reply

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "test_chat")

        sent_payloads = []

        class _Resp:
            ok = True

        def _fake_post(url, json=None, timeout=None):
            sent_payloads.append(json)
            return _Resp()

        monkeypatch.setattr(dm_auto_reply.requests, "post", _fake_post)

        dm_auto_reply.send_telegram_price_pending(
            "1234567890abcdef", "제 번호는 010-1234-5678 입니다 연락주세요"
        )

        assert sent_payloads, "Telegram 발송 시도가 없었음"
        text = sent_payloads[0]["text"]
        assert "1234567890abcdef" not in text, "IGSID가 마스킹 없이 그대로 노출됨"
        assert "010-1234-5678" not in text, "전화번호가 마스킹되지 않음"

    def test_awaiting_product_dedup_blocks_same_message_within_3_minutes(self, monkeypatch):
        """같은 sender가 3분 내 완전히 같은 문의를 반복(웹훅 재전송 등)하면 중복발송을 막아야 한다."""
        from modules.dm import dm_auto_reply

        send_calls = []

        monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: send_calls.append(1) or True)
        monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test", sender_igsid="ig_dedup_test",
            inquiry_text="가격 문의드립니다", received_at=now,
        )
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test2", sender_igsid="ig_dedup_test",
            inquiry_text="가격 문의드립니다", received_at=now,
        )

        assert len(send_calls) == 1, "3분 내 동일 문의 재수신인데 상품확인 요청이 또 발송됨"

    def test_awaiting_product_dedup_allows_different_message_from_same_sender(self, monkeypatch):
        """같은 buyer가 3분 내 다른 상품을 문의하면 매출 문의이므로 반드시 응답해야 한다
        (sender 단위로만 막으면 두번째 문의가 유실되는 회귀 방지)."""
        from modules.dm import dm_auto_reply

        send_calls = []

        monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: send_calls.append(1) or True)
        monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test", sender_igsid="ig_dedup_test",
            inquiry_text="A상품 가격이 얼마예요", received_at=now,
        )
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test2", sender_igsid="ig_dedup_test",
            inquiry_text="B상품 단가 문의드려요", received_at=now,
        )

        assert len(send_calls) == 2, "같은 buyer의 다른 상품 문의가 중복으로 취급되어 응답이 유실됨"

    def test_awaiting_product_dedup_released_on_send_failure(self, monkeypatch):
        """발송 실패로 선점만 걸리고 실제로는 안 나간 경우, 재시도(같은 문의 재수신)를
        중복으로 오인해서 막으면 안 된다."""
        from modules.dm import dm_auto_reply
        from modules.common import retry_queue as retry_queue_mod

        class _FakeRQ:
            def register(self, *a, **k): pass
            def start(self): pass
            def enqueue(self, *a, **k): pass

        send_results = [False, True]  # 1차 실패, 2차 성공
        send_calls = []

        monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
        monkeypatch.setattr(
            dm_auto_reply, "send_ig_reply",
            lambda *a, **k: (send_calls.append(1), send_results.pop(0))[1],
        )
        monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
        monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: _FakeRQ())

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test", sender_igsid="ig_dedup_test",
            inquiry_text="가격이요", received_at=now,
        )
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test2", sender_igsid="ig_dedup_test",
            inquiry_text="가격이요", received_at=now,
        )

        assert len(send_calls) == 2, "1차 발송 실패 후 재시도가 중복으로 막힘 — 선점 해제 안 됨"

    def test_awaiting_product_dedup_released_on_exception(self, monkeypatch):
        """send_ig_reply가 False가 아니라 예외(네트워크 오류 등)를 던져도
        선점이 해제되어 재시도가 중복으로 막히면 안 된다."""
        from modules.dm import dm_auto_reply

        call_count = {"n": 0}

        def _raise_then_succeed(sid, msg):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionError("simulated network failure")
            return True

        monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", _raise_then_succeed)
        monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        with pytest.raises(ConnectionError):
            dm_auto_reply.handle_price_inquiry(
                record_id="rec1", sender_igsid="ig_exc_test",
                inquiry_text="가격이요", received_at=now,
            )

        # 재시도 — 선점이 해제됐으면 두 번째 호출이 통과해야 한다.
        dm_auto_reply.handle_price_inquiry(
            record_id="rec2", sender_igsid="ig_exc_test",
            inquiry_text="가격이요", received_at=now,
        )

        assert call_count["n"] == 2, "예외 발생 후 재시도가 중복으로 막힘 — 선점 해제 안 됨"

    def test_awaiting_product_dedup_concurrent_requests_send_once(self, monkeypatch):
        """동시에 들어온 두 요청(같은 sender+같은 문의)은 Lock으로 보호되어 1번만 발송돼야 한다."""
        import threading
        from modules.dm import dm_auto_reply

        send_calls = []
        send_lock = threading.Lock()

        def _fake_send(sid, msg):
            with send_lock:
                send_calls.append(1)
            return True

        monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", _fake_send)
        monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        barrier = threading.Barrier(2)

        def _worker(rec_id):
            barrier.wait(timeout=5)
            dm_auto_reply.handle_price_inquiry(
                record_id=rec_id, sender_igsid="ig_concurrent_test",
                inquiry_text="가격이요", received_at=now,
            )

        t1 = threading.Thread(target=_worker, args=("rec1",))
        t2 = threading.Thread(target=_worker, args=("rec2",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert len(send_calls) == 1, "동시 요청인데 2번 발송됨 — Lock 보호가 동작하지 않음"
