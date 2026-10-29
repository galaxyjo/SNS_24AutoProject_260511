"""tests/test_dm_handoff_en.py — reply_mode=handoff_en (261029 STEP 2-B, WhatsApp 안내).

실제 네트워크·Airtable·Slack 호출 없이 전부 monkeypatch.
"""

from datetime import datetime, timedelta, timezone

import pytest

import modules.dm.dm_auto_reply as dm_auto_reply

_ACCT = "IDN-000051"
_ENV = "DM_HANDOFF_WHATSAPP_IDN_000051"
_ACCOUNTS = {_ACCT: {"reply_mode": "handoff_en"}}


class _FakeRepo:
    def __init__(self, accounts):
        self._accounts = accounts
        self.observability_calls = []

    def has_recent_auto_reply(self, sender_igsid, within_minutes=3):
        return False

    def get_publish_account(self, account_code_ref):
        return self._accounts.get(account_code_ref)

    def record_reply_observability(self, record_id, *, reply_mode_used, persona_code_ref="",
                                    send_status="", prompt_version="", persona_check_pass=False):
        self.observability_calls.append({"reply_mode_used": reply_mode_used, "send_status": send_status})


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    original = dm_auto_reply._repo
    for d in (dm_auto_reply._TEMPLATE_EN_DEDUP, dm_auto_reply._TEMPLATE_EN_HOLD, dm_auto_reply._HANDOFF_EN_SENT):
        d.clear()
    monkeypatch.setattr(dm_auto_reply, "_alert_dm", lambda *a, **k: alerts.append(a) or True)
    alerts.clear()
    yield
    dm_auto_reply._repo = original
    for d in (dm_auto_reply._TEMPLATE_EN_DEDUP, dm_auto_reply._TEMPLATE_EN_HOLD, dm_auto_reply._HANDOFF_EN_SENT):
        d.clear()


alerts: list = []


def _run(monkeypatch, accounts=None, acct=_ACCT, sender="buyerA", text="Hello", send_ok=True):
    repo = _FakeRepo(accounts or _ACCOUNTS)
    dm_auto_reply._repo = repo
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", False)
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent.append(msg) or send_ok)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    from modules.dm import dm_followup_scheduler
    monkeypatch.setattr(dm_followup_scheduler, "set_followup_schedule", lambda *a, **k: None)
    try:
        dm_auto_reply.handle_price_inquiry(
            record_id="rec_h", sender_igsid=sender, inquiry_text=text,
            received_at=datetime.now(timezone.utc), account_code_ref=acct,
        )
    except Exception:
        pass
    return sent, repo


def test_handoff_sends_whatsapp_guidance_with_account_contact(monkeypatch):
    monkeypatch.setenv(_ENV, "+82 10-1234-5678")
    sent, repo = _run(monkeypatch)
    assert sent == ["Thanks for your interest in Korean cosmetics wholesale. "
                    "Please continue your inquiry on WhatsApp: +82 10-1234-5678"]
    assert repo.observability_calls[0]["reply_mode_used"] == "template"


def test_missing_or_malformed_contact_sends_nothing_and_alerts(monkeypatch):
    monkeypatch.delenv(_ENV, raising=False)
    sent, _ = _run(monkeypatch)
    assert sent == [] and len(alerts) == 1
    for bad in ("", "abc", "wa.me/<script>", "12"):
        monkeypatch.setenv(_ENV, bad)
        dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
        sent, _ = _run(monkeypatch)
        assert sent == [], bad


def test_contact_is_per_account_not_shared(monkeypatch):
    monkeypatch.setenv("DM_HANDOFF_WHATSAPP_IDN_000052", "+84 90 123 4567")
    monkeypatch.delenv(_ENV, raising=False)
    accounts = {_ACCT: {"reply_mode": "handoff_en"}, "IDN-000052": {"reply_mode": "handoff_en"}}
    s51, _ = _run(monkeypatch, accounts, _ACCT)
    s52, _ = _run(monkeypatch, accounts, "IDN-000052")
    assert s51 == []                                   # 051 키가 없으면 52 값을 빌려 쓰지 않는다
    assert s52 and "+84 90 123 4567" in s52[0]


def test_once_per_buyer_within_24_hours(monkeypatch):
    monkeypatch.setenv(_ENV, "+821012345678")
    first, _ = _run(monkeypatch)
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()           # 60초 burst는 지났다고 가정
    second, _ = _run(monkeypatch, text="Another message")
    other_buyer, _ = _run(monkeypatch, sender="buyerB")
    assert len(first) == 1 and second == [] and len(other_buyer) == 1

    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    dm_auto_reply._HANDOFF_EN_SENT[(_ACCT, "buyerA")] -= timedelta(hours=24, seconds=1)
    again, _ = _run(monkeypatch)
    assert len(again) == 1


def test_definite_send_failure_releases_the_24h_slot(monkeypatch):
    monkeypatch.setenv(_ENV, "+821012345678")
    sent, _ = _run(monkeypatch, send_ok=False)
    assert len(sent) == 1
    assert (_ACCT, "buyerA") not in dm_auto_reply._HANDOFF_EN_SENT


def test_existing_modes_unchanged(monkeypatch):
    monkeypatch.setenv(_ENV, "+821012345678")
    sent, _ = _run(monkeypatch, {_ACCT: {"reply_mode": "template_en"}})
    assert sent == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE_EN]
    sent, _ = _run(monkeypatch, {"IDN-000041": {"reply_mode": ""}}, "IDN-000041", text="Hello nice to meet you")
    assert sent == []
    sent, _ = _run(monkeypatch, {_ACCT: {"reply_mode": "disabled"}})
    assert sent == []
