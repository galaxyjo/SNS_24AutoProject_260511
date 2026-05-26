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

    def test_handle_price_inquiry_passes_allowed(self, monkeypatch):
        """allowed 메시지는 필터를 통과해 get_base_price까지 진행되어야 한다."""
        from modules.dm import dm_auto_reply

        called = []

        monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: called.append("price") or None)
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: True)

        from datetime import datetime, timezone
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_test",
            sender_igsid="ig_test",
            inquiry_text="가격 문의드립니다",
            received_at=datetime.now(timezone.utc),
        )

        assert "price" in called, "allowed 메시지인데 get_base_price 미호출 — 필터가 잘못 차단함"
