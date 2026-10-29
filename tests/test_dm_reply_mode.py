"""tests/test_dm_reply_mode.py — 10.6-4B(계정별 reply_mode + Observability, 260730).

Account_Registry.reply_mode(template/persona/disabled)가 전역 PRICE_AUTO_REPLY_ENABLED보다
우선 적용되는지, 공란/조회실패 시 기존 전역 동작으로 정확히 fallback하는지, 그리고
본문 없이 reply_mode_used/persona_code_ref/send_status/prompt_version/persona_check_pass가
기록되는지 검증한다. 실제 네트워크·Airtable 호출 없이 전부 monkeypatch.

modules.dm.dm_auto_reply를 정상 경로로 import하면 modules/dm/__init__.py가
dm_receiver.py를 통해 runtime_boot_policy.json을 확인하려다 이 환경에서
PermissionError를 던진다(기존에 반복 문서화된 환경제약, 이 파일과 무관) —
이 파일은 그 제약이 없는 환경(CI/회장 터미널)에서 실행하기 위해 작성한다.
"""

from datetime import datetime, timezone

import pytest

import modules.dm.dm_auto_reply as dm_auto_reply


class _FakeRepo:
    def __init__(self, accounts: dict, persona=None):
        self._accounts = accounts
        self._persona = persona
        self.observability_calls = []

    def has_recent_auto_reply(self, sender_igsid, within_minutes=3):
        return False

    def get_publish_account(self, account_code_ref):
        return self._accounts.get(account_code_ref)

    def get_persona_by_account_code(self, account_code_ref):
        return self._persona

    def record_reply_observability(self, record_id, *, reply_mode_used, persona_code_ref="",
                                    send_status="", prompt_version="", persona_check_pass=False):
        self.observability_calls.append({
            "record_id": record_id,
            "reply_mode_used": reply_mode_used,
            "persona_code_ref": persona_code_ref,
            "send_status": send_status,
            "prompt_version": prompt_version,
            "persona_check_pass": persona_check_pass,
        })


@pytest.fixture(autouse=True)
def _restore_repo_and_dedup():
    original = dm_auto_reply._repo
    dm_auto_reply._AWAITING_PRODUCT_DEDUP.clear()
    dm_auto_reply._PERSONA_REPLY_DEDUP.clear()
    dm_auto_reply._TEMPLATE_EN_HOLD.clear()
    yield
    dm_auto_reply._repo = original
    dm_auto_reply._AWAITING_PRODUCT_DEDUP.clear()
    dm_auto_reply._PERSONA_REPLY_DEDUP.clear()


def test_reply_mode_disabled_skips_send_and_records_skipped(monkeypatch):
    repo = _FakeRepo({"IDN-000099": {"reply_mode": "disabled"}})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", True)  # 전역과 무관하게 계정값 우선

    sent_calls = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent_calls.append(1) or True)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_disabled", sender_igsid="ig_test",
        inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000099",
    )

    assert sent_calls == [], "reply_mode=disabled인데 발송이 시도됨"
    assert repo.observability_calls == [{
        "record_id": "rec_disabled", "reply_mode_used": "disabled", "persona_code_ref": "",
        "send_status": "skipped", "prompt_version": "", "persona_check_pass": False,
    }]


def test_reply_mode_persona_via_account_override_even_when_global_disabled(monkeypatch):
    """전역 PRICE_AUTO_REPLY_ENABLED=false여도 계정이 reply_mode=persona면 AI 응답 경로를 탄다."""
    repo = _FakeRepo(
        {"IDN-000036": {"reply_mode": "persona"}},
        persona={"persona_code": "PER-002", "tone_style": "친근함", "greeting_template": "", "followup_template": ""},
    )
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: 10000.0)
    monkeypatch.setattr(
        "modules.dm.ai_reply_generator.generate_reply",
        lambda *a, **k: "AI가 생성한 답변",
    )
    sent_messages = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent_messages.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "update_lead_replied", lambda *a, **k: None)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_autoreply", lambda *a, **k: None)

    from modules.dm import dm_followup_scheduler
    monkeypatch.setattr(dm_followup_scheduler, "set_followup_schedule", lambda *a, **k: None)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_persona", sender_igsid="ig_test",
        inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000036",
    )

    assert sent_messages == ["AI가 생성한 답변"]
    assert repo.observability_calls[0]["reply_mode_used"] == "persona"
    assert repo.observability_calls[0]["persona_code_ref"] == "PER-002"
    assert repo.observability_calls[0]["persona_check_pass"] is True
    assert repo.observability_calls[0]["send_status"] == "sent"


def test_persona_mode_dedups_rapid_successive_calls_from_same_sender(monkeypatch):
    """10.6-4D 실측 발견 — persona 경로는 generate_reply()(수십 초 소요)가 끝나기 전
    _has_recent_auto_replied()(Airtable 쿼리)만으로는 후속 문의를 못 막아 중복 발송됨.
    즉시 선점하는 _PERSONA_REPLY_DEDUP이 두 번째 호출을 막는지 검증한다."""
    repo = _FakeRepo(
        {"IDN-000036": {"reply_mode": "persona"}},
        persona={"persona_code": "PER-002", "tone_style": "친근함", "greeting_template": "", "followup_template": ""},
    )
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: 10000.0)
    monkeypatch.setattr("modules.dm.ai_reply_generator.generate_reply", lambda *a, **k: "AI가 생성한 답변")
    sent_messages = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent_messages.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "update_lead_replied", lambda *a, **k: None)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_autoreply", lambda *a, **k: None)

    from modules.dm import dm_followup_scheduler
    monkeypatch.setattr(dm_followup_scheduler, "set_followup_schedule", lambda *a, **k: None)

    # _has_recent_auto_replied가 아직 반영 전(False)인 상황을 그대로 재현 — 첫 호출이
    # 아직 완료 전이라고 가정하고 두 번째 호출을 곧바로 실행한다.
    dm_auto_reply.handle_price_inquiry(
        record_id="rec1", sender_igsid="ig_race_test",
        inquiry_text="가격 얼마예요", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000036",
    )
    dm_auto_reply.handle_price_inquiry(
        record_id="rec2", sender_igsid="ig_race_test",
        inquiry_text="가격 얼마예요", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000036",
    )

    assert sent_messages == ["AI가 생성한 답변"], "두 번째 호출이 중복 skip 안 되고 또 발송됨"
    assert len(repo.observability_calls) == 1


def test_persona_reply_slot_released_when_base_price_missing(monkeypatch):
    """가격 조회 실패로 자동응답을 생략할 때도 선점이 풀려야 정당한 재시도가 막히지 않는다."""
    repo = _FakeRepo({"IDN-000036": {"reply_mode": "persona"}})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: None)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec1", sender_igsid="ig_price_missing",
        inquiry_text="가격 얼마예요", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000036",
    )

    assert "ig_price_missing" not in dm_auto_reply._PERSONA_REPLY_DEDUP, "가격조회 실패 후 선점이 안 풀림"


def test_reply_mode_template_via_account_override_even_when_global_enabled(monkeypatch):
    """전역 PRICE_AUTO_REPLY_ENABLED=true여도 계정이 reply_mode=template이면 고정템플릿을 쓴다."""
    repo = _FakeRepo({"IDN-000041": {"reply_mode": "template"}})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", True)

    price_called = []
    monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: price_called.append(1) or None)
    sent_messages = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent_messages.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_template", sender_igsid="ig_test",
        inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000041",
    )

    assert price_called == [], "reply_mode=template인데 get_base_price가 호출됨"
    assert sent_messages == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE]
    assert repo.observability_calls[0]["reply_mode_used"] == "template"
    assert repo.observability_calls[0]["send_status"] == "sent"


class _RaisingRepo(_FakeRepo):
    def get_publish_account(self, account_code_ref):
        raise Exception("Airtable 조회 실패")


def test_account_lookup_failure_skips_reply_for_non_global_account(monkeypatch):
    """261029 A-3c(a) Fail-closed — 전역 fallback 계정이 아닌 계정은 조회 예외 시 응답을 생략한다."""
    repo = _RaisingRepo({})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    sent_messages = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent_messages.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_fallback", sender_igsid="ig_test",
        inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000036",
    )

    assert sent_messages == [], "조회 실패 계정에 응답이 발송됨(Fail-closed 위반)"


def test_account_lookup_failure_keeps_global_flag_for_global_fallback_account(monkeypatch):
    """전역 fallback 계정(IDN-000041)은 조회 예외 시 기존 전역 PRICE_AUTO_REPLY_ENABLED 동작을 유지한다."""
    repo = _RaisingRepo({})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    sent_messages = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent_messages.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_global", sender_igsid="ig_test",
        inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
        account_code_ref=dm_auto_reply.GLOBAL_FALLBACK_ACCOUNT_CODE_REF,
    )

    assert sent_messages == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE]


def test_global_fallback_account_with_blank_reply_mode_keeps_global_template(monkeypatch):
    """전역 fallback 계정(IDN-000041)은 reply_mode가 공란이어도 의도된 예외로 기존 전역 동작을 유지한다."""
    repo = _FakeRepo({"IDN-000041": {"reply_mode": ""}})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    sent_messages = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent_messages.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_041_blank", sender_igsid="ig_test",
        inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000041",
    )

    assert sent_messages == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE]


def test_account_with_blank_reply_mode_skips_reply_unless_global_fallback_account(monkeypatch):
    """계정은 식별됐지만 reply_mode가 공란이면 응답을 생략한다(Fail-closed)."""
    repo = _FakeRepo({"IDN-000051": {"reply_mode": ""}})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    sent_messages = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent_messages.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_blank", sender_igsid="ig_test",
        inquiry_text="How much is the wholesale price?", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000051",
    )

    assert sent_messages == []


def test_empty_account_code_ref_skips_account_lookup_and_reply(monkeypatch):
    """account_code_ref가 공란이면 get_publish_account를 호출하지 않고 응답도 생략한다(Fail-closed)."""
    class _AssertNoCallRepo(_FakeRepo):
        def get_publish_account(self, account_code_ref):
            raise AssertionError("account_code_ref 공란인데 get_publish_account가 호출됨")

    repo = _AssertNoCallRepo({})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    sent_messages = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent_messages.append(1) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_empty", sender_igsid="ig_test",
        inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
    )

    assert sent_messages == []


def test_observability_recorded_as_failed_when_send_fails(monkeypatch):
    from modules.common import retry_queue as retry_queue_mod

    repo = _FakeRepo({"IDN-000099": {"reply_mode": "template"}})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: False)

    class _FakeRQ:
        def register(self, *a, **k): pass
        def start(self): pass
        def enqueue(self, *a, **k): pass

    monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: _FakeRQ())

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_failed", sender_igsid="ig_test",
        inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
        account_code_ref="IDN-000099",
    )

    assert repo.observability_calls == [{
        "record_id": "rec_failed", "reply_mode_used": "template", "persona_code_ref": "",
        "send_status": "failed", "prompt_version": "", "persona_check_pass": False,
    }]


# ── 261029 STEP 2: reply_mode=template_en (영어 B2B 도매 자동응답, 051 전용) ─────────────

def _run_inquiry(monkeypatch, accounts, account_code_ref, text, sender="ig_test", global_enabled=False):
    repo = _FakeRepo(accounts)
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", global_enabled)
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    followups = []
    from modules.dm import dm_followup_scheduler
    monkeypatch.setattr(dm_followup_scheduler, "set_followup_schedule", lambda *a, **k: followups.append(1))
    dm_auto_reply.handle_price_inquiry(
        record_id="rec_en", sender_igsid=sender, inquiry_text=text,
        received_at=datetime.now(timezone.utc), account_code_ref=account_code_ref,
    )
    return sent, repo, followups


_EN_ACCOUNTS = {"IDN-000051": {"reply_mode": "template_en"}}


def test_template_en_replies_english_template_to_wholesale_price(monkeypatch):
    sent, repo, followups = _run_inquiry(monkeypatch, _EN_ACCOUNTS, "IDN-000051", "Hi, what is your wholesale price?")
    assert sent == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]
    assert followups == []
    assert repo.observability_calls[0]["reply_mode_used"] == "template"  # Airtable 선택지에 template_en 없음
    assert repo.observability_calls[0]["send_status"] == "sent"


def test_template_en_replies_to_any_message_regardless_of_keywords(monkeypatch):
    """261029 정정: template_en 계정은 키워드와 무관하게 모든 DM에 계정 정책(영어 템플릿)을 적용한다."""
    for i, text in enumerate(("Hello, I am interested in your products", "Can we talk?", "안녕하세요", "hi")):
        dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
        sent, _, _ = _run_inquiry(monkeypatch, _EN_ACCOUNTS, "IDN-000051", text, sender=f"ig_{i}")
        assert sent == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN], text


def test_blank_reply_mode_global_account_ignores_non_price_message(monkeypatch):
    """041(공란, 전역 fallback 계정)은 가격 문의가 아닌 일반 메시지에 기존처럼 응답하지 않는다."""
    sent, repo, _ = _run_inquiry(monkeypatch, {"IDN-000041": {"reply_mode": ""}}, "IDN-000041", "Hello, nice to meet you")
    assert sent == [] and repo.observability_calls == []


def test_persona_account_ignores_non_price_message(monkeypatch):
    sent, repo, _ = _run_inquiry(monkeypatch, {"IDN-000036": {"reply_mode": "persona"}}, "IDN-000036", "Hello, nice to meet you")
    assert sent == [] and repo.observability_calls == []


def test_global_account_korean_price_inquiry_still_gets_korean_template(monkeypatch):
    sent, _, _ = _run_inquiry(monkeypatch, {"IDN-000041": {"reply_mode": ""}}, "IDN-000041", "가격 문의드립니다")
    assert sent == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE]


def test_blank_account_code_ref_sends_nothing_for_wholesale(monkeypatch):
    sent, repo, _ = _run_inquiry(monkeypatch, _EN_ACCOUNTS, "", "Wholesale price please")
    assert sent == [] and repo.observability_calls == []


def test_disabled_account_sends_nothing_for_wholesale(monkeypatch):
    sent, repo, _ = _run_inquiry(monkeypatch, {"IDN-000051": {"reply_mode": "disabled"}}, "IDN-000051", "Wholesale price please")
    assert sent == []
    assert repo.observability_calls == [{
        "record_id": "rec_en", "reply_mode_used": "disabled", "persona_code_ref": "",
        "send_status": "skipped", "prompt_version": "", "persona_check_pass": False,
    }]


def test_template_en_new_and_returning_senders_get_same_reply(monkeypatch):
    first, _, _ = _run_inquiry(monkeypatch, _EN_ACCOUNTS, "IDN-000051", "Wholesale price?", sender="ig_new_buyer")
    second, _, _ = _run_inquiry(monkeypatch, _EN_ACCOUNTS, "IDN-000051", "Wholesale price?", sender="ig_returning_buyer")
    assert first == second == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]


def test_template_en_cooldown_is_per_account_and_sender_60_minutes(monkeypatch):
    """261029 SLA 정정(회장 확정): 계정+발신자 60초 burst guard — 1분 안에 연속된 메시지는 1회만."""
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    accounts = {"IDN-000051": {"reply_mode": "template_en"}, "IDN-000052": {"reply_mode": "template_en"}}
    first, _, _ = _run_inquiry(monkeypatch, accounts, "IDN-000051", "Hello", sender="buyerA")
    second, _, _ = _run_inquiry(monkeypatch, accounts, "IDN-000051", "A completely different sentence", sender="buyerA")
    other_sender, _, _ = _run_inquiry(monkeypatch, accounts, "IDN-000051", "Hello", sender="buyerB")
    other_account, _, _ = _run_inquiry(monkeypatch, accounts, "IDN-000052", "Hello", sender="buyerA")
    assert first == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]
    assert second == []
    assert other_sender == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]
    assert other_account == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]

    # 60초(burst) 경과 후에는 다시 응답한다
    from datetime import timedelta
    dm_auto_reply._TEMPLATE_EN_DEDUP[("IDN-000051", "buyerA")] -= timedelta(seconds=61)
    again, _, _ = _run_inquiry(monkeypatch, accounts, "IDN-000051", "Hello again", sender="buyerA")
    assert again == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]


def test_template_en_cooldown_released_when_send_fails(monkeypatch):
    from modules.common import retry_queue as retry_queue_mod
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    repo = _FakeRepo(_EN_ACCOUNTS)
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: False)

    class _FakeRQ:
        def register(self, *a, **k): pass
        def start(self): pass
        def enqueue(self, *a, **k): pass

    monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: _FakeRQ())
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    dm_auto_reply.handle_price_inquiry(
        record_id="rec_fail", sender_igsid="buyerF", inquiry_text="Hello",
        received_at=datetime.now(timezone.utc), account_code_ref="IDN-000051",
    )
    assert ("IDN-000051", "buyerF") not in dm_auto_reply._TEMPLATE_EN_DEDUP, "발송 실패 후 선점이 안 풀림"


def test_banned_word_filter_kept_for_existing_accounts_but_not_applied_to_template_en(monkeypatch):
    """Spam 필터링 DEFER — template_en은 금지어 필터 미적용, 041 등 기존 계정은 기존 필터 유지."""
    text = "광고 how much"   # 가격 키워드(how much) 있음 + 허용어 없음 + 금지어(광고)
    blocked, _, _ = _run_inquiry(monkeypatch, {"IDN-000041": {"reply_mode": ""}}, "IDN-000041", text)
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    replied, _, _ = _run_inquiry(monkeypatch, _EN_ACCOUNTS, "IDN-000051", text)
    assert blocked == []
    assert replied == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]


def test_unresolved_account_holds_reply_and_retry_for_any_message(monkeypatch):
    """미식별 계정(공란): 어떤 메시지든 자동응답 발송·retry 등록 0건."""
    from modules.common import retry_queue as retry_queue_mod
    enqueued = []

    class _FakeRQ:
        def register(self, *a, **k): pass
        def start(self): pass
        def enqueue(self, *a, **k): enqueued.append(a)

    monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: _FakeRQ())
    for text in ("Hello", "가격 문의드립니다", "How much is it?"):
        sent, _, _ = _run_inquiry(monkeypatch, _EN_ACCOUNTS, "", text)
        assert sent == [], text
    assert enqueued == []


class _CountingRepo(_FakeRepo):
    def __init__(self, accounts, recent=False):
        super().__init__(accounts)
        self.recent = recent
        self.recent_calls = 0

    def has_recent_auto_reply(self, sender_igsid, within_minutes=3):
        self.recent_calls += 1
        return self.recent


def _run_with_repo(monkeypatch, repo, account_code_ref, text, sender="ig_test"):
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    dm_auto_reply.handle_price_inquiry(
        record_id="rec_x", sender_igsid=sender, inquiry_text=text,
        received_at=datetime.now(timezone.utc), account_code_ref=account_code_ref,
    )
    return sent


def test_template_en_ignores_cross_account_recent_auto_reply_lookup(monkeypatch):
    """Codex 4차: 발신자 전용 3분 중복 조회가 계정별 60분 cooldown을 덮으면 안 된다.
    다른 계정에서 최근 auto_replied가 있어도(조회 True) template_en은 자기 cooldown만 따른다."""
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    repo = _CountingRepo(_EN_ACCOUNTS, recent=True)
    sent = _run_with_repo(monkeypatch, repo, "IDN-000051", "Hello")
    assert sent == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]
    assert repo.recent_calls == 0


def test_existing_account_recent_auto_reply_still_blocks_price_inquiry(monkeypatch):
    """041 등 기존 계정의 3분 중복 방지는 그대로 유지된다(회귀 방지)."""
    repo = _CountingRepo({"IDN-000041": {"reply_mode": ""}}, recent=True)
    assert _run_with_repo(monkeypatch, repo, "IDN-000041", "가격 문의드립니다") == []
    assert repo.recent_calls == 1


def test_non_price_dm_for_existing_account_does_no_duplicate_lookup(monkeypatch):
    """모든 DM 위임으로 늘어난 Airtable 읽기를 줄인다 — 비가격 DM은 중복 조회 없이 반환."""
    repo = _CountingRepo({"IDN-000041": {"reply_mode": ""}}, recent=False)
    assert _run_with_repo(monkeypatch, repo, "IDN-000041", "Hello there") == []
    assert repo.recent_calls == 0


def test_order_dm_gets_english_reply_only_for_template_en_accounts(monkeypatch):
    """261029 회장 확정: 주문 의사 DM도 template_en 계정은 영어 자동응답. 기존 계정은 주문 처리 우선(응답 없음)."""
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    repo_en = _FakeRepo(_EN_ACCOUNTS)
    dm_auto_reply._repo = repo_en
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    now = datetime.now(timezone.utc)
    dm_auto_reply.handle_price_inquiry("rec_o1", "buyerO", "I want to order 200 pcs", now,
                                       account_code_ref="IDN-000051", is_order=True)
    assert sent == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]

    for code, mode in (("IDN-000041", ""), ("IDN-000036", "persona")):
        sent.clear()
        dm_auto_reply._repo = _FakeRepo({code: {"reply_mode": mode}})
        dm_auto_reply.handle_price_inquiry("rec_o2", "buyerP", "주문할게요 가격 알려주세요", now,
                                           account_code_ref=code, is_order=True)
        assert sent == [], code


def test_order_dm_from_unresolved_account_sends_nothing(monkeypatch):
    sent = _run_inquiry(monkeypatch, _EN_ACCOUNTS, "", "I want to order")[0]
    assert sent == []
