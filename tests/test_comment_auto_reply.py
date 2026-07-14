"""comment_auto_reply.py Private Reply 파이프라인 배선 단위테스트 — 4개 안전게이트 + 성공/실패 경로."""

import json
import threading
import time as _time

import pytest

from modules.comment import comment_auto_reply


class _FakeResponse:
    def __init__(self, payload=None, *, ok=True):
        self._payload = payload or {}
        self.ok = ok
        self.status_code = 200 if ok else 400
        self.text = ""

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _enable_auto_reply(monkeypatch):
    monkeypatch.setattr(comment_auto_reply, "_AUTO_REPLY_ENABLED", True)
    monkeypatch.setattr(comment_auto_reply, "_send_telegram_comment", lambda *a: None)
    monkeypatch.setattr(comment_auto_reply, "_record_comment", lambda *a: None)


# ── 문구 다양화 / 개인화 / 옵트아웃 안내 ─────────────────────────────────────

def test_build_price_reply_includes_username_mention():
    msg = comment_auto_reply._build_price_reply("buyer1")
    assert msg.startswith("@buyer1님, ")


def test_build_price_reply_omits_mention_when_username_empty():
    msg = comment_auto_reply._build_price_reply("")
    assert not msg.startswith("@")


def test_build_price_reply_always_includes_opt_out_notice():
    for _ in range(20):
        msg = comment_auto_reply._build_price_reply("buyer1")
        assert any(kw in msg for kw in ["원치 않", "괜찮아요", "무방합니다", "넘어가셔도"])


def test_build_price_reply_rotates_across_templates():
    seen = {comment_auto_reply._build_price_reply("buyer1") for _ in range(50)}
    assert len(seen) > 1, "50회 호출했는데 항상 같은 문구만 나옴 — 랜덤화가 안 되고 있음"


def test_reply_privately_to_comment_uses_official_messages_contract(monkeypatch):
    """Meta 공식 사양(Private Replies): POST /{page-id}/messages, recipient.comment_id + message.text.
    /{comment-id}/private_replies는 다른(구 Facebook Page 댓글) 엔드포인트이므로 여기서 검증하지 않는다 — Codex 리뷰로 최초 구현 오류 확인 후 정정."""
    captured = {}
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setattr(comment_auto_reply, "_get_page_token", lambda: "page-token")

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured["body"] = json.loads(kwargs["data"])
        return _FakeResponse({"message_id": "mid"})

    monkeypatch.setattr(comment_auto_reply.requests, "post", _fake_post)

    assert comment_auto_reply.reply_privately_to_comment("c1", "hello") is True
    assert captured["url"] == "https://graph.facebook.com/v25.0/page/messages"
    assert captured["body"] == {
        "recipient": {"comment_id": "c1"},
        "message": {"text": "hello"},
    }


def test_non_campaign_post_skips_reply(monkeypatch):
    calls = []
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: False)
    monkeypatch.setattr(
        comment_auto_reply, "reply_privately_to_comment",
        lambda cid, msg: calls.append(cid) or True,
    )

    comment_auto_reply.handle_comment("c1", "buyer1", "가격 얼마예요", "media-not-campaign")

    assert calls == []


def test_campaign_post_sends_private_reply_and_marks_cooldown(monkeypatch):
    calls = []
    marked = []
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
    monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: False)
    monkeypatch.setattr(comment_auto_reply.guard, "is_user_in_cooldown", lambda u: False)
    monkeypatch.setattr(comment_auto_reply.guard, "consume_daily_budget", lambda: True)
    monkeypatch.setattr(comment_auto_reply.guard, "mark_user_replied", lambda u: marked.append(u))
    monkeypatch.setattr(comment_auto_reply.guard, "record_circuit_success", lambda: calls.append("success"))
    monkeypatch.setattr(
        comment_auto_reply, "reply_privately_to_comment",
        lambda cid, msg: calls.append(cid) or True,
    )

    comment_auto_reply.handle_comment("c1", "buyer1", "가격 얼마예요", "media-campaign")

    assert calls == ["c1", "success"]
    assert marked == ["buyer1"]


def test_cooldown_blocks_repeat_reply(monkeypatch):
    calls = []
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
    monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: False)
    monkeypatch.setattr(comment_auto_reply.guard, "is_user_in_cooldown", lambda u: True)
    monkeypatch.setattr(
        comment_auto_reply, "reply_privately_to_comment",
        lambda cid, msg: calls.append(cid) or True,
    )

    comment_auto_reply.handle_comment("c1", "buyer1", "가격 얼마예요", "media-campaign")

    assert calls == []


def test_daily_budget_exhausted_blocks_reply(monkeypatch):
    calls = []
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
    monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: False)
    monkeypatch.setattr(comment_auto_reply.guard, "is_user_in_cooldown", lambda u: False)
    monkeypatch.setattr(comment_auto_reply.guard, "consume_daily_budget", lambda: False)
    monkeypatch.setattr(
        comment_auto_reply, "reply_privately_to_comment",
        lambda cid, msg: calls.append(cid) or True,
    )

    comment_auto_reply.handle_comment("c1", "buyer1", "가격 얼마예요", "media-campaign")

    assert calls == []


def test_circuit_open_blocks_reply(monkeypatch):
    calls = []
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
    monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: True)
    monkeypatch.setattr(
        comment_auto_reply, "reply_privately_to_comment",
        lambda cid, msg: calls.append(cid) or True,
    )

    comment_auto_reply.handle_comment("c1", "buyer1", "가격 얼마예요", "media-campaign")

    assert calls == []


def test_send_failure_records_circuit_failure_not_cooldown(monkeypatch):
    marked = []
    failed = []
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
    monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: False)
    monkeypatch.setattr(comment_auto_reply.guard, "is_user_in_cooldown", lambda u: False)
    monkeypatch.setattr(comment_auto_reply.guard, "consume_daily_budget", lambda: True)
    monkeypatch.setattr(comment_auto_reply.guard, "mark_user_replied", lambda u: marked.append(u))
    monkeypatch.setattr(comment_auto_reply.guard, "record_circuit_failure", lambda: failed.append(1))
    monkeypatch.setattr(comment_auto_reply, "reply_privately_to_comment", lambda cid, msg: False)

    comment_auto_reply.handle_comment("c1", "buyer1", "가격 얼마예요", "media-campaign")

    assert marked == []
    assert failed == [1]


def test_auto_reply_disabled_skips_guard_entirely(monkeypatch):
    monkeypatch.setattr(comment_auto_reply, "_AUTO_REPLY_ENABLED", False)
    called = []
    monkeypatch.setattr(
        comment_auto_reply.guard, "is_campaign_post", lambda m: called.append(1) or True
    )

    comment_auto_reply.handle_comment("c1", "buyer1", "가격 얼마예요", "media-campaign")

    assert called == []


def test_non_price_comment_never_triggers_guard(monkeypatch):
    called = []
    monkeypatch.setattr(
        comment_auto_reply.guard, "is_campaign_post", lambda m: called.append(1) or True
    )

    comment_auto_reply.handle_comment("c1", "buyer1", "예쁘네요!", "media-campaign")

    assert called == []


def test_cooldown_key_prefers_commenter_id_over_username(monkeypatch):
    """username은 사용자가 바꾸면 쿨다운이 우회되므로, from.id(commenter_id)가 있으면 그걸 키로 써야 함."""
    seen_keys = []
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
    monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: False)
    monkeypatch.setattr(
        comment_auto_reply.guard, "is_user_in_cooldown",
        lambda key: seen_keys.append(key) or False,
    )
    monkeypatch.setattr(comment_auto_reply.guard, "consume_daily_budget", lambda: True)
    monkeypatch.setattr(comment_auto_reply.guard, "mark_user_replied", lambda key: seen_keys.append(key))
    monkeypatch.setattr(comment_auto_reply.guard, "record_circuit_success", lambda: None)
    monkeypatch.setattr(comment_auto_reply, "reply_privately_to_comment", lambda cid, msg: True)

    comment_auto_reply.handle_comment(
        "c1", "buyer1", "가격 얼마예요", "media-campaign", commenter_id="1792783944739953"
    )

    assert seen_keys == ["1792783944739953", "1792783944739953"]


def test_cooldown_key_falls_back_to_username_when_no_commenter_id(monkeypatch):
    seen_keys = []
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
    monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: False)
    monkeypatch.setattr(
        comment_auto_reply.guard, "is_user_in_cooldown",
        lambda key: seen_keys.append(key) or False,
    )
    monkeypatch.setattr(comment_auto_reply.guard, "consume_daily_budget", lambda: True)
    monkeypatch.setattr(comment_auto_reply.guard, "mark_user_replied", lambda key: seen_keys.append(key))
    monkeypatch.setattr(comment_auto_reply.guard, "record_circuit_success", lambda: None)
    monkeypatch.setattr(comment_auto_reply, "reply_privately_to_comment", lambda cid, msg: True)

    comment_auto_reply.handle_comment("c1", "buyer1", "가격 얼마예요", "media-campaign")

    assert seen_keys == ["buyer1", "buyer1"]


def test_reply_lock_serializes_concurrent_calls_prevents_double_send(monkeypatch, tmp_path):
    """웹훅 스레드 + 폴러 스레드가 동시에 같은 사용자에게 발송 시도해도 REPLY_LOCK 덕에 1회만 발송돼야 함
    (Codex 3차 리뷰 P1: os.replace만으론 동시성 미해결 지적에 대한 실제 검증)."""
    monkeypatch.setattr(comment_auto_reply.guard, "_CAMPAIGN_CONFIG_PATH", tmp_path / "campaign.json")
    monkeypatch.setattr(comment_auto_reply.guard, "_COOLDOWN_STATE_PATH", tmp_path / "cooldown.json")
    monkeypatch.setattr(comment_auto_reply.guard, "_BUDGET_STATE_PATH", tmp_path / "budget.json")
    comment_auto_reply.guard._CAMPAIGN_CONFIG_PATH.write_text(
        json.dumps({"media_ids": ["media-campaign"]}), encoding="utf-8"
    )
    comment_auto_reply.guard._circuit_failure_count = 0
    comment_auto_reply.guard._circuit_open_until = 0.0

    sent = []

    def _slow_send(cid, msg):
        _time.sleep(0.05)
        sent.append(cid)
        return True

    monkeypatch.setattr(comment_auto_reply, "reply_privately_to_comment", _slow_send)

    threads = [
        threading.Thread(
            target=comment_auto_reply.handle_comment,
            args=(f"c{i}", "buyer1", "가격 얼마예요", "media-campaign"),
            kwargs={"commenter_id": "stable-id-1"},
        )
        for i in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(sent) == 1, f"쿨다운을 우회해 {len(sent)}번 발송됨 — REPLY_LOCK이 동작 안 함"


def test_negative_comment_skips_reply_path_entirely(monkeypatch):
    called = []
    monkeypatch.setattr(
        comment_auto_reply.guard, "is_campaign_post", lambda m: called.append(1) or True
    )

    comment_auto_reply.handle_comment("c1", "buyer1", "사기 아니에요?", "media-campaign")

    assert called == []
