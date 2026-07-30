"""tests/test_dm_persona_kwargs.py — 260730 10.5-5단계(Persona 연결).

_get_persona_kwargs()이 account_code_ref로 연결된 Persona_Profile을 정확히
generate_reply() 인자로 변환하는지, 그리고 실패/미연결 시 기존 동작(빈 문자열,
기존 프롬프트와 100% 동일)이 그대로 유지되는지 검증한다. 실제 네트워크·Airtable
호출 없이 전부 monkeypatch.

modules.dm.dm_auto_reply를 정상 경로로 import하면 modules/dm/__init__.py가
dm_receiver.py를 통해 runtime_boot_policy.json을 확인하려다 이 환경에서
PermissionError를 던진다(기존에 반복 문서화된 환경제약, 이 파일과 무관) —
이 파일은 그 제약이 없는 환경(CI/회장 터미널)에서 실행하기 위해 작성한다.
"""

import pytest

import modules.dm.dm_auto_reply as dm_auto_reply


class _FakeRepo:
    def __init__(self, persona=None, *, raise_exc=None):
        self._persona = persona
        self._raise_exc = raise_exc

    def get_persona_by_account_code(self, account_code):
        if self._raise_exc:
            raise self._raise_exc
        return self._persona


@pytest.fixture(autouse=True)
def _restore_repo():
    original = dm_auto_reply._repo
    yield
    dm_auto_reply._repo = original


_EMPTY = {"tone_style": "", "greeting_template": "", "followup_template": ""}


def test_empty_account_code_ref_returns_empty_kwargs():
    dm_auto_reply._repo = _FakeRepo(persona=None)
    assert dm_auto_reply._get_persona_kwargs("") == _EMPTY


def test_no_linked_persona_returns_empty_kwargs():
    dm_auto_reply._repo = _FakeRepo(persona=None)
    assert dm_auto_reply._get_persona_kwargs("IDN-000041") == _EMPTY


def test_repository_exception_fails_open_to_empty_kwargs():
    dm_auto_reply._repo = _FakeRepo(raise_exc=Exception("Airtable unavailable"))
    assert dm_auto_reply._get_persona_kwargs("IDN-000041") == _EMPTY


def test_linked_persona_returns_its_fields():
    dm_auto_reply._repo = _FakeRepo(persona={
        "persona_code": "PER-001",
        "tone_style": "친근하고 캐주얼한 말투",
        "greeting_template": "안녕하세요 :)",
        "followup_template": "혹시 더 궁금하신 점 있으실까요?",
    })
    result = dm_auto_reply._get_persona_kwargs("IDN-000041")
    assert result == {
        "tone_style": "친근하고 캐주얼한 말투",
        "greeting_template": "안녕하세요 :)",
        "followup_template": "혹시 더 궁금하신 점 있으실까요?",
    }


def test_handle_price_inquiry_passes_persona_kwargs_to_generate_reply(monkeypatch):
    """실제 handle_price_inquiry() 배선까지 확인 — persona가 연결돼 있으면
    generate_reply()가 그 tone_style 등을 받아 호출돼야 한다."""
    monkeypatch.setattr(dm_auto_reply, "PRICE_AUTO_REPLY_ENABLED", True)
    monkeypatch.setattr(dm_auto_reply, "get_base_price", lambda: 50000)
    monkeypatch.setattr(dm_auto_reply, "_has_recent_auto_replied", lambda *a, **k: False)
    monkeypatch.setattr("modules.dm.rules.evaluate", lambda text: True)
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: True)
    monkeypatch.setattr(dm_auto_reply, "update_lead_replied", lambda *a, **k: None)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_autoreply", lambda *a, **k: None)
    from modules.dm import dm_followup_scheduler
    monkeypatch.setattr(dm_followup_scheduler, "set_followup_schedule", lambda *a, **k: None)

    dm_auto_reply._repo = _FakeRepo(persona={
        "persona_code": "PER-001",
        "tone_style": "친근하고 캐주얼한 말투",
        "greeting_template": "",
        "followup_template": "",
    })

    captured = {}

    def _fake_generate_reply(user_message, base_price, margin_rate, **kwargs):
        captured.update(kwargs)
        return "테스트 응답"

    import modules.dm.ai_reply_generator as ai_reply_generator
    monkeypatch.setattr(ai_reply_generator, "generate_reply", _fake_generate_reply)

    from datetime import datetime, timezone
    dm_auto_reply.handle_price_inquiry(
        "rec1", "sender1", "가격 얼마예요?", datetime.now(timezone.utc),
        account_code_ref="IDN-000041",
    )

    assert captured["tone_style"] == "친근하고 캐주얼한 말투"
