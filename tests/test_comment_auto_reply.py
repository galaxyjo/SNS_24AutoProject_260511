"""comment_auto_reply.py Private Reply 파이프라인 배선 단위테스트 — 4개 안전게이트 + 성공/실패 경로."""

import json
import threading
import time as _time

import pytest

from modules.comment import comment_auto_reply

# autouse _enable_auto_reply 픽스처가 모든 테스트에서 _send_telegram_comment를 no-op으로
# 스텁하므로(아래), 실제 마스킹 동작 자체를 테스트하려면 스텁되기 전의 원본 함수 참조가
# 필요하다 — 모듈 임포트 시점(픽스처 실행 전)에 미리 잡아둔다.
_REAL_SEND_TELEGRAM_COMMENT = comment_auto_reply._send_telegram_comment
_REAL_IS_PRIVATE_REPLY_SUPPORTED = comment_auto_reply._is_private_reply_supported


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
    # 260730 10.5-6단계(댓글 Routing) — _try_private_reply()가 새로 추가된
    # _is_private_reply_supported()를 거치면서 실제 Airtable 네트워크 호출을 하지
    # 않도록 기본값을 True(기존 동작 유지)로 고정한다. 이 게이트 자체를 검증하는
    # 테스트는 아래에서 개별적으로 override한다.
    monkeypatch.setattr(comment_auto_reply, "_is_private_reply_supported", lambda media_id: True)


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


def test_negative_comment_never_triggers_guard(monkeypatch):
    """260715 회장 지시로 가격 키워드 제한을 없애고 스팸/부정 댓글만 걸러내도록 변경 —
    부정 댓글만 Private Reply 대상에서 확실히 제외되는지 확인(과거엔 '가격 키워드 없는
    댓글'을 전부 걸렀지만, 이젠 negative 댓글만 걸러야 함)."""
    called = []
    monkeypatch.setattr(
        comment_auto_reply.guard, "is_campaign_post", lambda m: called.append(1) or True
    )

    comment_auto_reply.handle_comment("c1", "buyer1", "이건 사기 아닌가요?", "media-campaign")

    assert called == []


def test_non_price_non_negative_comment_now_triggers_guard(monkeypatch):
    """260715 변경 — "예쁘네요"처럼 가격 키워드가 없어도(스팸/부정이 아니면) 이제
    Private Reply 대상이 돼야 한다(jiho2987 사례: "재고있나요"/"연락주세요" 등 키워드
    목록에 없던 실제 구매의사 표현을 놓치던 문제 해결)."""
    called = []
    monkeypatch.setattr(
        comment_auto_reply.guard, "is_campaign_post", lambda m: called.append(1) or True
    )
    monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: False)
    monkeypatch.setattr(comment_auto_reply.guard, "is_user_in_cooldown", lambda k: False)
    monkeypatch.setattr(comment_auto_reply.guard, "consume_daily_budget", lambda: False)

    comment_auto_reply.handle_comment("c1", "buyer1", "예쁘네요!", "media-campaign")

    assert called == [1]


@pytest.mark.parametrize(
    "text",
    [
        "무료체험 하려면 http://spam-link.example 클릭하세요",
        "www.follow4follow.example 방문 후 맞팔해요",
        "t.me/promo_channel 텔레그램 상담 문의",
        "선팔환영 좋아요 눌러주세요",
        "카톡 아이디 추가해서 연락주세요",
        "대출상담 무이자 카지노 도박 이벤트",
    ],
)
def test_detect_spam_comment_flags_promotional_patterns(text):
    """260716 회장 지시: "스팸"을 NEGATIVE_KEYWORDS 문자열 매칭이 아니라 실제
    광고·홍보성 신호(외부 링크/팔로우 품앗이/불법 홍보/외부 채널 유도)로 판별해야 함."""
    assert comment_auto_reply.detect_spam_comment(text) is True


def test_detect_spam_comment_does_not_flag_genuine_inquiry():
    """오탐(false positive)으로 진짜 손님 문의를 스팸 처리하면 ERR-069와 같은 리드
    유실이 재발하므로, 스팸 신호가 없는 일반 댓글은 걸러지면 안 됨."""
    assert comment_auto_reply.detect_spam_comment("재고 있나요? 연락주세요") is False
    assert comment_auto_reply.detect_spam_comment("예쁘네요!") is False


def test_spam_comment_never_triggers_guard(monkeypatch):
    """260716 변경 — 광고성 링크가 포함된 댓글은 Private Reply 대상에서 제외돼야 한다."""
    called = []
    monkeypatch.setattr(
        comment_auto_reply.guard, "is_campaign_post", lambda m: called.append(1) or True
    )

    comment_auto_reply.handle_comment(
        "c1", "buyer1", "무료체험 http://spam-link.example 클릭하세요", "media-campaign"
    )

    assert called == []


def test_promotional_keyword_spam_never_triggers_guard(monkeypatch):
    """260716 변경 — URL 없이 팔로우 품앗이/외부 채널 유도 문구만 있어도 스팸으로
    걸러져야 한다."""
    called = []
    monkeypatch.setattr(
        comment_auto_reply.guard, "is_campaign_post", lambda m: called.append(1) or True
    )

    comment_auto_reply.handle_comment(
        "c1", "buyer1", "카톡 아이디 추가해서 연락주세요", "media-campaign"
    )

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
    # 260716 발견 — guard.COOLDOWN_HOURS는 import 시점에 실제 .env(현재
    # COMMENT_REPLY_COOLDOWN_HOURS=0)에서 한 번만 읽혀 고정된다. 0으로 고정되면 쿨다운
    # 가드 자체가 무력화돼(elapsed_hours < 0은 항상 거짓이 아니라 항상 참이 되는 게
    # 아니라, "쿨다운 중"이 항상 거짓이 됨) 이 테스트가 검증하려는 "REPLY_LOCK이 중복을
    # 막는다"는 것과 무관하게 통과/실패가 갈릴 수 있어 명시적으로 고정한다.
    monkeypatch.setattr(comment_auto_reply.guard, "COOLDOWN_HOURS", 24)
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


def test_handle_comment_logs_masked_preview_not_raw_text(monkeypatch, caplog):
    """260716 회장 지시(A-1) — app.log에도 댓글 원문이 그대로 남으면 안 된다(ERR-066과
    같은 클래스). _telegram_preview() 재사용: PII 정규식 마스킹 후 20자로 잘림."""
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: False)
    long_text = "제 번호는 010-1234-5678이니 여기로 꼭 연락 부탁드립니다"

    with caplog.at_level("INFO", logger="modules.comment.comment_auto_reply"):
        comment_auto_reply.handle_comment("c1", "buyer1", long_text, "media1")

    combined = " ".join(r.message for r in caplog.records)
    assert "010-1234-5678" not in combined, "전화번호가 로그에 그대로 남으면 안 됨"
    assert long_text not in combined, "원문 전체가 로그에 그대로 남으면 안 됨(20자 미리보기여야 함)"


def test_send_telegram_comment_masks_pii_and_truncates(monkeypatch):
    """260716 회장 지시(A-1) — Telegram 본문에도 원문을 그대로 싣지 않는다. username(공개
    IG 핸들)은 마스킹 대상에서 제외(회장 260716 확인)."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    sent = {}

    class _Resp:
        ok = True
        status_code = 200
        text = ""

    def _fake_post(url, json, timeout):
        sent["json"] = json
        return _Resp()

    monkeypatch.setattr(comment_auto_reply.requests, "post", _fake_post)

    long_text = "제 번호는 010-1234-5678이니 여기로 꼭 연락 부탁드립니다"
    _REAL_SEND_TELEGRAM_COMMENT(None, "c1", "buyer1", long_text, "new")

    body = sent["json"]["text"]
    assert "010-1234-5678" not in body, "전화번호가 마스킹 없이 그대로 노출되면 안 됨"
    assert long_text not in body, "원문 전체가 그대로 실리면 안 됨(20자 미리보기여야 함)"
    assert "@buyer1" in body, "username(공개 IG 핸들)은 마스킹 대상 아님"


# ── 260730 10.5-6단계: 댓글 Routing — instagram_login 계정 Private Reply 스킵 게이트 ──

def test_is_private_reply_supported_true_when_media_untagged(monkeypatch):
    """account_code_ref 공란(레거시/다계정 이전 게시물) — 기존 동작 그대로 True."""
    monkeypatch.setattr(comment_auto_reply._repo, "get_account_code_ref_by_media_id", lambda m: "")
    assert _REAL_IS_PRIVATE_REPLY_SUPPORTED("media1") is True


def test_is_private_reply_supported_true_for_facebook_login_account(monkeypatch):
    monkeypatch.setattr(
        comment_auto_reply._repo, "get_account_code_ref_by_media_id", lambda m: "IDN-000041"
    )
    monkeypatch.setattr(
        comment_auto_reply._repo, "get_publish_account",
        lambda code: {"api_provider": "facebook_login"},
    )
    assert _REAL_IS_PRIVATE_REPLY_SUPPORTED("media1") is True


def test_is_private_reply_supported_false_for_instagram_login_account(monkeypatch):
    """aijomoojin류(instagram_login) 계정 소유 게시물 — Facebook Page가 없어 Private
    Reply가 구조적으로 불가(Meta 공식문서 확인) — 스킵되어야 한다."""
    monkeypatch.setattr(
        comment_auto_reply._repo, "get_account_code_ref_by_media_id", lambda m: "IDN-000036"
    )
    monkeypatch.setattr(
        comment_auto_reply._repo, "get_publish_account",
        lambda code: {"api_provider": "instagram_login"},
    )
    assert _REAL_IS_PRIVATE_REPLY_SUPPORTED("media1") is False


def test_is_private_reply_supported_fails_open_on_media_lookup_error(monkeypatch):
    def _raise(m):
        raise Exception("Airtable unavailable")

    monkeypatch.setattr(comment_auto_reply._repo, "get_account_code_ref_by_media_id", _raise)
    assert _REAL_IS_PRIVATE_REPLY_SUPPORTED("media1") is True


def test_is_private_reply_supported_fails_open_on_account_lookup_error(monkeypatch):
    monkeypatch.setattr(
        comment_auto_reply._repo, "get_account_code_ref_by_media_id", lambda m: "IDN-000036"
    )

    def _raise(code):
        raise Exception("Airtable unavailable")

    monkeypatch.setattr(comment_auto_reply._repo, "get_publish_account", _raise)
    assert _REAL_IS_PRIVATE_REPLY_SUPPORTED("media1") is True


def test_try_private_reply_skips_when_instagram_login_account(monkeypatch):
    """_try_private_reply()가 실제로 이 게이트를 호출해 instagram_login 계정이면
    reply_privately_to_comment() 자체를 시도하지 않아야 한다."""
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
    monkeypatch.setattr(comment_auto_reply, "_is_private_reply_supported", lambda m: False)
    called = {"sent": False}
    monkeypatch.setattr(
        comment_auto_reply, "reply_privately_to_comment",
        lambda cid, msg: called.__setitem__("sent", True) or True,
    )

    comment_auto_reply._try_private_reply(None, "c1", "buyer1", "media-aijomoojin", "buyer1")

    assert called["sent"] is False, "instagram_login 계정인데 Private Reply를 시도함"


def test_try_private_reply_proceeds_when_facebook_login_or_untagged(monkeypatch):
    """게이트가 True(레거시/yuna18253)면 기존 동작 그대로 발송을 시도해야 한다(회귀 방지)."""
    monkeypatch.setattr(comment_auto_reply.guard, "is_campaign_post", lambda m: True)
    monkeypatch.setattr(comment_auto_reply, "_is_private_reply_supported", lambda m: True)
    monkeypatch.setattr(comment_auto_reply.guard, "circuit_is_open", lambda: False)
    monkeypatch.setattr(comment_auto_reply.guard, "is_user_in_cooldown", lambda u: False)
    monkeypatch.setattr(comment_auto_reply.guard, "consume_daily_budget", lambda: True)
    monkeypatch.setattr(comment_auto_reply.guard, "mark_user_replied", lambda u: None)
    monkeypatch.setattr(comment_auto_reply.guard, "record_circuit_success", lambda: None)
    called = {"sent": False}
    monkeypatch.setattr(
        comment_auto_reply, "reply_privately_to_comment",
        lambda cid, msg: called.__setitem__("sent", True) or True,
    )

    comment_auto_reply._try_private_reply(None, "c1", "buyer1", "media-yuna", "buyer1")

    assert called["sent"] is True
