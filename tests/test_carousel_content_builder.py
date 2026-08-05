"""tests/test_carousel_content_builder.py — 260805 Track B 7B-3 Sourcebook
Carousel Content Contract Canary 검증. 실제 Gemini 호출 없음 — 전부 Fake.
"""

import json

import pytest

import modules.sns.carousel_content_builder as builder
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


def _topic(core_message="이 도구는 하루 3건 자동 게시를 지원한다. 무료 등급은 검색 기능이 제한된다."):
    return SourceTopic(
        topic_id="3.1", title="Example Source", status="VERIFIED FACT",
        source_url="https://example.com/source-1", core_message=core_message,
        prohibited_expression="",
    )


def _valid_slides():
    return [
        {"index": 1, "role": "hook", "text": "짧은훅문구"},
        {"index": 2, "role": "problem", "text": "무료 등급은 검색 기능이 제한된다는 문제가 있다"},
        {"index": 3, "role": "concept", "text": "핵심 개념 설명 " * 3},
        {"index": 4, "role": "concept", "text": "다른 핵심 개념 설명 " * 3},
        {"index": 5, "role": "concept", "text": "또 다른 핵심 개념 설명 " * 3},
        {"index": 6, "role": "concept", "text": "마지막 핵심 개념 설명 " * 3},
        {"index": 7, "role": "summary", "text": "요약 및 적용법"},
        {"index": 8, "role": "cta", "text": "저장하고 다음 글도 확인하세요"},
    ]


def _valid_payload(caption="짧은훅\n\n본문 문장입니다.\n\n저장해두세요."):
    return {
        "slides": _valid_slides(),
        "caption": caption,
        "hashtags": ["ai", "startup", "solopreneur", "automation", "tips"],
    }


class TestSlideContract:
    def test_generates_exactly_8_slides_from_sourcebook_fixture(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is True
        assert len(result.content.slides) == 8
        assert [s.index for s in result.content.slides] == list(range(1, 9))

    def test_hook_slide_over_15_chars_rejected(self, monkeypatch):
        payload = _valid_payload()
        payload["slides"][0]["text"] = "이것은 15자를 초과하는 매우 긴 훅 문구입니다"
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "HOOK_TOO_LONG"

    def test_wrong_slide_count_rejected(self, monkeypatch):
        payload = _valid_payload()
        payload["slides"] = payload["slides"][:7]
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "SLIDE_COUNT_INVALID"


class TestCaptionAndHashtagContract:
    def test_caption_within_400_chars_and_hashtags_5_to_8(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "ENGAGEMENT", "COMPARE")

        assert result.success is True
        assert len(result.content.caption) <= 400
        assert 5 <= len(result.content.hashtags) <= 8

    def test_caption_over_400_chars_rejected(self, monkeypatch):
        payload = _valid_payload(caption="가" * 401)
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "CAPTION_LENGTH_INVALID"

    def test_hashtag_count_out_of_range_rejected(self, monkeypatch):
        payload = _valid_payload()
        payload["hashtags"] = ["only", "four", "tags", "here"]
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "HASHTAG_COUNT_INVALID"


class TestCtaContract:
    """260805 2차 검수 보완 — Slide 8·Caption 마지막 줄 CTA 정확히 1개."""

    def test_slide_8_missing_cta_rejected(self, monkeypatch):
        payload = _valid_payload()
        payload["slides"][7]["text"] = "오늘 이야기는 여기까지입니다"  # CTA 키워드 없음
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "SLIDE_8_CTA_COUNT_INVALID"

    def test_slide_8_multiple_ctas_rejected(self, monkeypatch):
        payload = _valid_payload()
        payload["slides"][7]["text"] = "저장하세요. 댓글도 남겨주세요."
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "SLIDE_8_CTA_COUNT_INVALID"

    def test_caption_cta_not_on_last_line_rejected(self, monkeypatch):
        """마지막 줄에 CTA가 있어도, 앞줄에도 CTA가 하나 더 있으면 "마지막에
        1개만"이라는 계약 위반이다."""
        payload = _valid_payload(caption="저장해두세요.\n\n댓글도 남겨주세요.")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "CAPTION_CTA_NOT_LAST"

    def test_caption_missing_cta_rejected(self, monkeypatch):
        payload = _valid_payload(caption="짧은훅\n\n본문 문장입니다.\n\n끝입니다.")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "CAPTION_CTA_COUNT_INVALID"


class TestFabricationGuard:
    def test_superlative_claim_not_in_source_blocks_content(self, monkeypatch):
        """수치 외 축 — 원문에 없는 단정적 최상급 주장("업계 최초" 등)도 차단."""
        payload = _valid_payload()
        payload["slides"][1]["text"] = "이 도구는 업계 최초로 이 기능을 제공합니다"
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "POSSIBLE_FABRICATION"


    def test_fabricated_statistic_not_in_source_blocks_content(self, monkeypatch):
        """Sourcebook 원문에 없는 숫자(예: '327%')가 생성문에 섞이면 차단한다
        (최선노력 기계적 grounding 확인 — 비수치 날조는 이 검사로 못 잡는다,
        문서화된 한계)."""
        payload = _valid_payload(caption="매출이 327% 증가했습니다.\n\n확인하세요.")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "POSSIBLE_FABRICATION"

    def test_numbers_present_in_source_are_allowed(self, monkeypatch):
        topic = _topic(core_message="이 서비스는 하루 3건, 무료 등급 기준 20건 한도를 제공한다.")
        payload = _valid_payload(caption="하루 3건 자동 게시.\n\n저장해두고 확인하세요.")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(topic, "REACH", "HOOK_IMPACT")

        assert result.success is True


class TestFingerprintDeduplication:
    def test_identical_fingerprint_blocks_regeneration(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)
        topic = _topic()

        first = builder.generate_carousel_content(topic, "REACH", "HOOK_IMPACT")
        assert first.success is True

        existing = {first.content.content_fingerprint}
        second = builder.generate_carousel_content(
            topic, "REACH", "HOOK_IMPACT", existing_fingerprints=existing,
        )

        assert second.success is False
        assert second.error_code == "DUPLICATE_FINGERPRINT"

    def test_different_slot_role_and_template_allowed_even_same_source(self, monkeypatch):
        """FACT: 동일 Sourcebook 원천이라도 슬롯 역할·템플릿이 다르면
        fingerprint가 달라져 생성이 허용된다."""
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)
        topic = _topic()

        first = builder.generate_carousel_content(topic, "REACH", "HOOK_IMPACT")
        existing = {first.content.content_fingerprint}
        second = builder.generate_carousel_content(
            topic, "ENGAGEMENT", "COMPARE", existing_fingerprints=existing,
        )

        assert first.success is True
        assert second.success is True
        assert first.content.content_fingerprint != second.content.content_fingerprint


class TestNoSearchOrUrlContextToolUsage:
    def test_generate_content_config_carries_no_tools(self, monkeypatch):
        """Target Test 6 — Google Search/URL Context Tool이 config에 전혀
        포함되지 않는다(Research Adapter도 이 함수에서 import/호출되지 않음)."""
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert len(models.calls) == 1
        config = models.calls[0]["config"]
        assert getattr(config, "tools", None) in (None, [])

    def test_module_does_not_import_research_to_topic_adapter(self):
        import sys

        assert "modules.sns.research_to_topic_adapter" not in dir(builder)
        assert not hasattr(builder, "research_next_topic")


class TestModelFallback:
    """260805 7B-4 Live Canary에서 발견된 회귀 방지 — `model=None`을 SDK에
    그대로 넘기면 요청 URL에 "{model}"이 문자 그대로 들어가 실제 404가
    발생했다(Fake 클라이언트로는 이 결함이 드러나지 않았음, Fake는 model
    문자열 값에 신경 쓰지 않았기 때문). 이제 실제로 호출부에 전달된 model
    값을 직접 검증한다."""

    def test_no_model_override_falls_back_to_default_string_not_none(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is True
        assert models.calls[0]["model"] == "gemini-2.5-flash-lite"
        assert models.calls[0]["model"] is not None

    def test_explicit_model_override_is_used_as_is(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(
            _topic(), "REACH", "HOOK_IMPACT", model="gemini-3.5-flash-lite",
        )

        assert result.success is True
        assert models.calls[0]["model"] == "gemini-3.5-flash-lite"


class TestSlotRoleReuse:
    def test_producer_hour_mapping_matches_launcher_tuples(self):
        """회장 승인 매핑 — launcher/main.py의 기존 (5,9,16)/(6,10,17) 위치
        대응 그대로."""
        assert builder.slot_role_for_producer_hour(5) == "REACH"
        assert builder.slot_role_for_producer_hour(9) == "ENGAGEMENT"
        assert builder.slot_role_for_producer_hour(16) == "SAVE_SHARE"
        assert builder.slot_role_for_posting_hour(6) == "REACH"
        assert builder.slot_role_for_posting_hour(10) == "ENGAGEMENT"
        assert builder.slot_role_for_posting_hour(17) == "SAVE_SHARE"

    def test_unknown_hour_returns_none_not_invented(self):
        assert builder.slot_role_for_producer_hour(12) is None
        assert builder.slot_role_for_posting_hour(3) is None

    def test_unknown_slot_role_rejected(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "UNKNOWN_ROLE", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "SLOT_ROLE_UNKNOWN"
        assert models.calls == []  # Gemini 호출 전에 즉시 거부


class TestScanExistingFingerprints:
    def test_reads_fingerprint_field_from_complete_vault_entries(self, tmp_path):
        content_dir = tmp_path / "content"
        content_dir.mkdir(parents=True)
        (content_dir / "a.md").write_text(
            "---\n"
            'content_id: "a"\n'
            'status: "complete"\n'
            'content_fingerprint: "abc123"\n'
            "---\n\nbody\n",
            encoding="utf-8",
        )
        (content_dir / "b.md").write_text(
            "---\n"
            'content_id: "b"\n'
            'status: "complete"\n'
            "---\n\nbody\n",  # 구버전 항목 — content_fingerprint 필드 없음
            encoding="utf-8",
        )

        fingerprints = builder.scan_existing_fingerprints(tmp_path)

        assert fingerprints == {"abc123"}


class TestSafetyReuse:
    def test_unsafe_classification_blocks_content(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        fake_client = _FakeClient(models)
        monkeypatch.setattr(builder, "_get_client", lambda: fake_client)
        monkeypatch.setattr(builder, "_throttle", lambda: None)
        monkeypatch.setattr(
            builder, "check_caption_safety", lambda text, **kwargs: ("UNSAFE", "SAFETY")
        )

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "SAFETY_BLOCKED:SAFETY"


class TestInsufficientEvidence:
    def test_empty_core_message_fails_closed_without_gemini_call(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)
        topic = _topic(core_message="")

        result = builder.generate_carousel_content(topic, "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "INSUFFICIENT_SOURCE_EVIDENCE"
        assert models.calls == []
