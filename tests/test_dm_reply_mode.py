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
    yield
    dm_auto_reply._repo = original
    dm_auto_reply._AWAITING_PRODUCT_DEDUP.clear()


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


def test_account_lookup_failure_falls_back_to_global_flag(monkeypatch):
    """get_publish_account 예외 시 전역 PRICE_AUTO_REPLY_ENABLED로 fallback(기존 동작 보존)."""
    class _RaisingRepo(_FakeRepo):
        def get_publish_account(self, account_code_ref):
            raise Exception("Airtable 조회 실패")

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

    assert sent_messages == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE]


def test_empty_account_code_ref_skips_account_lookup_entirely(monkeypatch):
    """account_code_ref가 공란이면 get_publish_account 자체를 호출하지 않는다(기존 호출부 100% 호환)."""
    class _AssertNoCallRepo(_FakeRepo):
        def get_publish_account(self, account_code_ref):
            raise AssertionError("account_code_ref 공란인데 get_publish_account가 호출됨")

    repo = _AssertNoCallRepo({})
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)

    dm_auto_reply.handle_price_inquiry(
        record_id="rec_empty", sender_igsid="ig_test",
        inquiry_text="가격 문의드립니다", received_at=datetime.now(timezone.utc),
    )


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
