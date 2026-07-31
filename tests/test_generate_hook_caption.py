"""Track B-3 — caption_generator.generate_hook_caption() 단위 테스트.

실제 Gemini API 호출 없음 — _get_client()를 mock으로 교체한다.
"""

import modules.sns.caption_generator as caption_generator
from modules.sns.caption_generator import generate_hook_caption


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, text=None, raise_on_first=None):
        self._text = text
        self._raise_on_first = raise_on_first
        self.calls = 0

    def generate_content(self, model, contents):
        self.calls += 1
        if self._raise_on_first and self.calls == 1:
            raise self._raise_on_first
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, models):
        self.models = models


def _patch_client(monkeypatch, models):
    monkeypatch.setattr(caption_generator, "_get_client", lambda: _FakeClient(models))
    monkeypatch.setattr(caption_generator, "_throttle", lambda: None)


def test_empty_core_message_returns_empty_without_calling_gemini(monkeypatch):
    models = _FakeModels(text="CAPTION: x\nHASHTAGS: #x")
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Netflix Culture Memo", "")

    assert (caption, hashtags) == ("", "")
    assert models.calls == 0


def test_generates_caption_and_hashtags_from_core_message(monkeypatch):
    fake_text = (
        "CAPTION: Netflix trusts people over process. Do you?\n"
        "HASHTAGS: #startup #culture #netflix"
    )
    models = _FakeModels(text=fake_text)
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption(
        "Netflix Culture Memo",
        "Netflix는 규칙을 늘리는 대신 뛰어난 사람에게 맥락과 책임을 준다.",
    )

    assert caption == "Netflix trusts people over process. Do you?"
    assert hashtags == "#startup #culture #netflix"
    assert models.calls == 1


def test_prompt_includes_prohibited_expression_when_provided(monkeypatch):
    captured = {}

    class _CapturingModels(_FakeModels):
        def generate_content(self, model, contents):
            captured["contents"] = contents
            return super().generate_content(model, contents)

    models = _CapturingModels(text="CAPTION: c\nHASHTAGS: #h")
    _patch_client(monkeypatch, models)

    generate_hook_caption(
        "Netflix Culture Memo",
        "core message",
        prohibited_expression='"실리콘밸리 조직문화의 절대적인 바이블"',
    )

    assert '"실리콘밸리 조직문화의 절대적인 바이블"' in captured["contents"]


def test_prompt_never_omits_core_message_constraint(monkeypatch):
    captured = {}

    class _CapturingModels(_FakeModels):
        def generate_content(self, model, contents):
            captured["contents"] = contents
            return super().generate_content(model, contents)

    models = _CapturingModels(text="CAPTION: c\nHASHTAGS: #h")
    _patch_client(monkeypatch, models)

    generate_hook_caption("Title", "only this fact is allowed")

    assert "only this fact is allowed" in captured["contents"]
    assert "Do not add any statistic" in captured["contents"]


def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(caption_generator.time, "sleep", lambda s: None)
    models = _FakeModels(
        text="CAPTION: recovered\nHASHTAGS: #ok",
        raise_on_first=Exception("429 rate limited"),
    )
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert caption == "recovered"
    assert models.calls == 2


def test_non_429_exception_fails_closed_to_empty(monkeypatch):
    class _RaisingModels(_FakeModels):
        def generate_content(self, model, contents):
            raise RuntimeError("network down")

    _patch_client(monkeypatch, _RaisingModels())

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert (caption, hashtags) == ("", "")
