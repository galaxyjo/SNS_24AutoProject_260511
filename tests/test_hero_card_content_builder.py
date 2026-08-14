"""tests/test_hero_card_content_builder.py — 260811 Visual Type Wiring 검증.
실제 Gemini 호출 없음 — 전부 Fake(carousel_content_builder 테스트와 동일 패턴).
"""

import json

import pytest

import modules.sns.hero_card_content_builder as builder
from modules.sns.source_selector import SourceTopic


class _FakeResponse:
    def __init__(self, payload: dict):
        self.text = json.dumps(payload)


class _FakeModels:
    def __init__(self, response=None, raise_exc=None):
        self._response = response
        self._raise_exc = raise_exc
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._raise_exc:
            raise self._raise_exc
        return self._response


class _FakeClient:
    def __init__(self, models):
        self.models = models


def _patch_gemini(monkeypatch, models):
    fake_client = _FakeClient(models)
    monkeypatch.setattr(builder, "_get_client", lambda: fake_client)
    monkeypatch.setattr(builder, "_throttle", lambda: None)
    monkeypatch.setattr(builder, "check_caption_safety", lambda text, **kwargs: ("SAFE", "STOP"))


def _topic(core_message="유명 VC가 실제 투자 검토에 사용하는 사업계획 구조를 공개자료로 배울 수 있다."):
    return SourceTopic(
        topic_id="3.4", title="Sequoia Capital Resources", status="VERIFIED FACT",
        source_url="https://example.com/source-1", core_message=core_message,
        prohibited_expression="",
    )


def _valid_blocks():
    return [
        {"title": "검토 기준", "desc": "실제 투자 검토용"},
        {"title": "사업계획", "desc": "실제 구조 확인"},
        {"title": "공개 자료", "desc": "누구나 학습 가능"},
        {"title": "활용 방법", "desc": "내 사업에 적용"},
    ]


def _valid_payload(**overrides):
    payload = {
        "headline": "VC 투자 검토 구조",
        "subheadline": "유명 VC의 실제 투자 검토 구조를 배울 수 있다.",
        "blocks": _valid_blocks(),
        "tagline": "실제 VC의 투자 검토법을 확인하세요.",
    }
    payload.update(overrides)
    return payload


class TestFieldContract:
    def test_generates_headline_subheadline_4blocks_tagline(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is True
        assert result.content.headline == "VC 투자 검토 구조"
        assert len(result.content.blocks) == 4

    def test_headline_over_max_chars_rejected(self, monkeypatch):
        payload = _valid_payload(headline="이것은 상한 글자수를 명백히 초과하는 문단 수준으로 아주 길고 긴 헤드라인 문구를 일부러 만들어 봅니다")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "HEADLINE_INVALID"

    def test_empty_headline_rejected(self, monkeypatch):
        payload = _valid_payload(headline="")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "HEADLINE_INVALID"

    def test_subheadline_over_max_chars_rejected(self, monkeypatch):
        payload = _valid_payload(subheadline="이것은 상한 글자수를 명백히 초과하는 문단 수준의 매우 길고 긴 서브헤드라인 문구를 일부러 만들어서 상한을 확실히 넘기도록 반복해서 길게 늘려 봅니다 정말로 아주 길게")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "SUBHEADLINE_INVALID"

    def test_wrong_block_count_rejected(self, monkeypatch):
        payload = _valid_payload()
        payload["blocks"] = payload["blocks"][:3]
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "BLOCK_COUNT_INVALID"

    def test_block_title_over_max_chars_rejected(self, monkeypatch):
        payload = _valid_payload()
        payload["blocks"][0]["title"] = "이것은 상한 글자수를 명백히 초과하는 아주 길고 긴 라벨입니다"
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "BLOCK_TITLE_INVALID"

    def test_block_desc_over_max_chars_rejected(self, monkeypatch):
        payload = _valid_payload()
        payload["blocks"][0]["desc"] = "이것은 상한 글자수를 명백히 초과하는 문단 수준으로 아주 길고 긴 설명문을 일부러 만들어 봅니다"
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "BLOCK_DESC_INVALID"

    def test_empty_block_title_rejected(self, monkeypatch):
        payload = _valid_payload()
        payload["blocks"][0]["title"] = ""
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "BLOCK_TITLE_INVALID"

    def test_tagline_over_max_chars_rejected(self, monkeypatch):
        payload = _valid_payload(tagline="이것은 상한 글자수를 명백히 초과하는 문단 수준의 매우 길고 긴 태그라인 문구를 일부러 만들어서 상한을 확실히 넘기도록 반복해서 길게 늘려 봅니다 정말로")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "TAGLINE_INVALID"


class TestFabricationGuard:
    def test_fabricated_statistic_not_in_source_blocks_content(self, monkeypatch):
        payload = _valid_payload(subheadline="투자성공률 87%를 보장합니다.")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "POSSIBLE_FABRICATION"

    def test_superlative_claim_not_in_source_blocks_content(self, monkeypatch):
        payload = _valid_payload(tagline="업계 최고의 VC 자료입니다.")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "POSSIBLE_FABRICATION"


class TestFingerprintDeduplication:
    def test_identical_fingerprint_blocks_regeneration(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        first = builder.generate_hero_card_content(_topic())
        assert first.success is True

        result = builder.generate_hero_card_content(
            _topic(), existing_fingerprints={first.content.content_fingerprint},
        )

        assert result.success is False
        assert result.error_code == "DUPLICATE_FINGERPRINT"


class TestSafetyReuse:
    def test_unsafe_classification_blocks_content(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)
        monkeypatch.setattr(builder, "check_caption_safety", lambda text, **kwargs: ("UNSAFE", "SAFETY"))

        result = builder.generate_hero_card_content(_topic())

        assert result.success is False
        assert result.error_code == "SAFETY_BLOCKED:SAFETY"


class TestNoSourceEvidence:
    def test_empty_core_message_rejected_before_any_gemini_call(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_hero_card_content(_topic(core_message=""))

        assert result.success is False
        assert result.error_code == "INSUFFICIENT_SOURCE_EVIDENCE"
        assert models.calls == []


class TestModelFallback:
    def test_no_model_override_falls_back_to_default_string_not_none(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        builder.generate_hero_card_content(_topic())

        assert models.calls[0]["model"] == "gemini-2.5-flash-lite"

    def test_explicit_model_override_is_used_as_is(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        builder.generate_hero_card_content(_topic(), model="gemini-3.5-flash-lite")

        assert models.calls[0]["model"] == "gemini-3.5-flash-lite"
