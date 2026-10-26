"""tests/test_carousel_content_builder.py — 260805 Track B 7B-3 Sourcebook
Carousel Content Contract Canary 검증. 실제 Gemini 호출 없음 — 전부 Fake.
"""

import json
from pathlib import Path

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
    def test_per_024_settings_are_in_gemini_prompt(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(
            _topic(), "REACH", "HOOK_IMPACT",
            tone_style="활기·친근·설득력 있는 쇼호스트 말투",
            target_language="KR",
            content_pillars="AI 쇼호스트 제작 과정 / 라이브 판매 화법",
            seo_keywords="AI쇼호스트, 라이브커머스",
            conversion_cta="AI 쇼호스트 라이브 의뢰는 DM",
        )

        assert result.success is True
        prompt = models.calls[0]["contents"]
        for value in (
            "활기·친근·설득력 있는 쇼호스트 말투", "KR",
            "AI 쇼호스트 제작 과정 / 라이브 판매 화법",
            "AI쇼호스트, 라이브커머스", "AI 쇼호스트 라이브 의뢰는 DM",
        ):
            assert value in prompt

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

    def test_trailing_punctuation_after_source_number_is_allowed(self, monkeypatch):
        """261026 022 Dry-run 실측 — 원문 "5.0"이 생성문에서 "5.0,"로 쓰여도 같은 숫자다(소수점·천단위는 유지)."""
        topic = _topic(core_message="IBM Granite Speech 5.0 모델은 키워드 2,000개와 WER 5.06%를 지원한다.")
        payload = _valid_payload(caption="Granite Speech 5.0, 키워드 2,000개. WER 5.06%.\n\n저장해두고 확인하세요.")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(topic, "REACH", "HOOK_IMPACT")

        assert result.success is True
        assert builder._extract_numeric_tokens("5.0, 2,000. 5.06%") == {"5.0", "2000", "5.06%"}   # 천 단위 쉼표 정규화

    def test_number_not_in_source_still_blocked_with_trailing_punctuation(self, monkeypatch):
        """끝 문장부호를 떼도 원문에 없는 숫자("6.0,")는 계속 차단한다."""
        topic = _topic(core_message="IBM Granite Speech 5.0 모델을 공개했다.")
        payload = _valid_payload(caption="Granite Speech 6.0, 공개.\n\n저장해두고 확인하세요.")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(topic, "REACH", "HOOK_IMPACT")

        assert result.success is False
        assert result.error_code == "POSSIBLE_FABRICATION"

    def test_numbers_present_in_source_are_allowed(self, monkeypatch):
        topic = _topic(core_message="이 서비스는 하루 3건, 무료 등급 기준 20건 한도를 제공한다.")
        payload = _valid_payload(caption="하루 3건 자동 게시.\n\n저장해두고 확인하세요.")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(topic, "REACH", "HOOK_IMPACT")

        assert result.success is True

    def test_number_present_only_in_title_not_flagged_as_fabrication(self, monkeypatch):
        """260817 ERR-115 — hero_card_content_builder.py와 동일한 버그가
        여기도 잠재해 있었다: _build_prompt()가 core_message와 title을 함께
        근거로 주므로(예: 'AI RMF 1.0'), title에만 있는 숫자를 검증 대상에서
        빠뜨리면 정상 응답까지 날조로 오판정한다."""
        topic = SourceTopic(
            topic_id="3.6", title="NIST AI Risk Management Framework (AI RMF 1.0)",
            status="VERIFIED FACT", source_url="https://example.com/source-nist",
            core_message="AI 위험은 성능만이 아니라 설계·데이터·배포·거버넌스 전 과정에서 식별·관리해야 한다.",
            prohibited_expression="",
        )
        payload = _valid_payload(caption="NIST AI 위험관리 프레임워크 1.0을 확인하세요.")
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


# ── 261023 STEP 4-AE — 2~4장 짧은 카드뉴스 계약 ─────────────────────────────

def _short_payload(n, cover="AI 영업 DM, 아직도 직접 처리하고 계세요?"):
    middle = [
        {"index": 2, "role": "facts", "text": "무료 등급은 검색 기능이 제한된다는 점을 먼저 알아야 합니다"},
        {"index": 3, "role": "apply", "text": "하루 3건 자동 게시로 반복 업무를 줄일 수 있습니다"},
    ]
    last = {"role": "cta", "text": "필요할 때 다시 보도록 저장하세요"}
    slides = [{"index": 1, "role": "cover", "text": cover}] + middle[: n - 2]
    slides.append({"index": n, **last})
    return {
        "slides": slides,
        "caption": "반복 업무를 줄이는 방법입니다.\n\n무료 등급 제한도 함께 확인했습니다.\n\n저장해두세요.",
        "hashtags": ["AI자동화", "업무자동화", "AI툴", "소상공인", "생산성"],
    }


class TestShortCarousel:
    @pytest.mark.parametrize("n", [2, 3, 4])
    def test_two_to_four_slides_pass(self, monkeypatch, n):
        models = _FakeModels(response=_FakeResponse(_short_payload(n)))
        _patch_gemini(monkeypatch, models)

        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=n)

        assert result.success is True, result.error_code
        assert [s.index for s in result.content.slides] == list(range(1, n + 1))
        assert result.content.slides[0].text == "AI 영업 DM, 아직도 직접 처리하고 계세요?"
        prompt = models.calls[0]["contents"]
        assert f"exactly {n} slides" in prompt and "8-slide" not in prompt

    @pytest.mark.parametrize("n", [0, 1, 5, 7, 9])
    def test_unsupported_slide_count_fails_without_gemini(self, monkeypatch, n):
        models = _FakeModels(response=_FakeResponse(_short_payload(3)))
        _patch_gemini(monkeypatch, models)
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=n)
        assert (result.success, result.error_code) == (False, "SLIDE_COUNT_UNSUPPORTED")
        assert models.calls == []

    def test_default_slide_count_is_still_eight(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_short_payload(3)))
        _patch_gemini(monkeypatch, models)
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")
        assert result.error_code == "SLIDE_COUNT_INVALID"           # 8장 계약으로 검사
        assert "8-slide" in models.calls[0]["contents"]

    def test_returned_count_must_match_requested(self, monkeypatch):
        _patch_gemini(monkeypatch, _FakeModels(response=_FakeResponse(_short_payload(4))))
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert result.error_code == "SLIDE_COUNT_INVALID"

    @pytest.mark.parametrize("cover", ["", "   ", "첫 줄\n둘째 줄", "가" * 41])
    def test_cover_title_constraint(self, monkeypatch, cover):
        _patch_gemini(monkeypatch, _FakeModels(response=_FakeResponse(_short_payload(3, cover=cover))))
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert result.error_code == "COVER_TITLE_INVALID"

    def test_cover_title_at_limit_passes(self, monkeypatch):
        _patch_gemini(monkeypatch, _FakeModels(response=_FakeResponse(_short_payload(3, cover="가" * 40))))
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert result.success is True

    def test_cta_only_on_last_slide(self, monkeypatch):
        payload = _short_payload(3)
        payload["slides"][1]["text"] = "이 내용을 저장하세요"
        _patch_gemini(monkeypatch, _FakeModels(response=_FakeResponse(payload)))
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert result.error_code == "CTA_NOT_LAST_SLIDE"

    def test_last_slide_needs_exactly_one_cta(self, monkeypatch):
        payload = _short_payload(3)
        payload["slides"][2]["text"] = "하루 3건 자동 게시가 가능합니다"
        _patch_gemini(monkeypatch, _FakeModels(response=_FakeResponse(payload)))
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert result.error_code == "LAST_SLIDE_CTA_COUNT_INVALID"

    def test_long_body_slide_rejected(self, monkeypatch):
        payload = _short_payload(3)
        payload["slides"][1]["text"] = "단어 " * 31
        _patch_gemini(monkeypatch, _FakeModels(response=_FakeResponse(payload)))
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert result.error_code == "BODY_SLIDE_TOO_LONG"

    def test_fabrication_guard_still_applies(self, monkeypatch):
        payload = _short_payload(3)
        payload["slides"][1]["text"] = "매출이 300% 늘었습니다"
        _patch_gemini(monkeypatch, _FakeModels(response=_FakeResponse(payload)))
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert result.error_code == "POSSIBLE_FABRICATION"

    def test_safety_still_applies(self, monkeypatch):
        _patch_gemini(monkeypatch, _FakeModels(response=_FakeResponse(_short_payload(3))))
        monkeypatch.setattr(builder, "check_caption_safety", lambda text, **kwargs: ("UNSAFE", "blocked"))
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert result.error_code == "SAFETY_BLOCKED:blocked"

    @pytest.mark.parametrize("n", [2, 3])
    def test_cta_on_cover_rejected(self, monkeypatch, n):
        _patch_gemini(monkeypatch, _FakeModels(response=_FakeResponse(
            _short_payload(n, cover="AI 영업 자동화, 지금 저장하세요"))))
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=n)
        assert result.error_code == "CTA_NOT_LAST_SLIDE"


# ── 261023 STEP 4-AI — 짧은 캐러셀 CTA 위치 정규화(순수 CTA만 이동·중복 제거) ──────────

import logging


def _norm_payload(slides_text, caption=None):
    slides = [{"index": i + 1, "role": "r", "text": t} for i, t in enumerate(slides_text)]
    return {
        "slides": slides,
        "caption": caption or "반복 업무를 줄이는 방법입니다.\n\n무료 등급 제한도 함께 정리했습니다.\n\n저장해두세요.",
        "hashtags": ["AI자동화", "업무자동화", "AI툴", "소상공인", "생산성"],
    }


def _run_short(monkeypatch, payload, n):
    models = _FakeModels(response=_FakeResponse(payload))
    _patch_gemini(monkeypatch, models)
    result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=n)
    return result, models


class TestShortCtaNormalization:
    def test_middle_slide_pure_cta_moves_to_last(self, monkeypatch):
        payload = _norm_payload(["AI 영업 자동화 시작", "무료 등급은 검색이 제한됩니다. 지금 저장하세요.",
                                 "하루 3건 자동 게시로 업무를 줄입니다."])
        result, models = _run_short(monkeypatch, payload, 3)
        assert result.success is True, result.error_code
        texts = [s.text for s in result.content.slides]
        assert texts[1] == "무료 등급은 검색이 제한됩니다."
        assert texts[2].endswith("지금 저장하세요.")
        assert [builder._count_cta_sentences(t) for t in texts] == [0, 0, 1]
        assert len(models.calls) == 1                                   # Gemini 재호출 없음

    def test_cover_cta_is_not_moved_and_fails(self, monkeypatch):
        payload = _norm_payload(["AI 영업 자동화, 지금 저장하세요", "핵심 사실입니다.", "필요할 때 다시 보도록 저장하세요."])
        result, _ = _run_short(monkeypatch, payload, 3)
        assert result.error_code == "CTA_NOT_LAST_SLIDE"

    def test_duplicate_cta_keeps_exactly_one_on_last(self, monkeypatch):
        payload = _norm_payload(["AI 영업 자동화 시작", "무료 등급은 검색이 제한됩니다. 공유해 주세요.",
                                 "하루 3건 자동 게시가 됩니다. 필요할 때 다시 보도록 저장하세요."])
        result, _ = _run_short(monkeypatch, payload, 3)
        assert result.success is True, result.error_code
        texts = [s.text for s in result.content.slides]
        assert [builder._count_cta_sentences(t) for t in texts] == [0, 0, 1]
        assert texts[2].endswith("필요할 때 다시 보도록 저장하세요.")

    def test_last_slide_multiple_pure_ctas_keeps_last(self, monkeypatch):
        payload = _norm_payload(["AI 영업 자동화 시작", "하루 3건 자동 게시로 업무를 줄입니다. 지금 저장하세요. 친구에게 공유해 주세요."])
        result, _ = _run_short(monkeypatch, payload, 2)
        assert result.success is True, result.error_code
        assert result.content.slides[1].text == "하루 3건 자동 게시로 업무를 줄입니다. 친구에게 공유해 주세요."

    def test_mixed_keyword_sentence_is_not_moved_and_fails(self, monkeypatch):
        payload = _norm_payload(["AI 영업 자동화 시작", "데이터를 저장해 두면 비교가 쉽습니다.",
                                 "필요할 때 다시 보도록 저장하세요."])
        result, _ = _run_short(monkeypatch, payload, 3)
        assert result.error_code == "CTA_NOT_LAST_SLIDE"

    def test_slide_that_is_only_cta_is_not_emptied(self, monkeypatch):
        payload = _norm_payload(["AI 영업 자동화 시작", "지금 저장하세요.", "하루 3건 자동 게시가 됩니다."])
        result, _ = _run_short(monkeypatch, payload, 3)
        assert result.error_code == "CTA_NOT_LAST_SLIDE"

    def test_caption_pure_cta_on_earlier_line_is_removed(self, monkeypatch):
        caption = "반복 업무를 줄이는 방법입니다. 팔로우하세요.\n\n무료 등급 제한도 정리했습니다.\n\n저장해두세요."
        payload = _norm_payload(["AI 영업 자동화 시작", "핵심 사실입니다.", "필요할 때 다시 보도록 저장하세요."], caption)
        result, _ = _run_short(monkeypatch, payload, 3)
        assert result.success is True, result.error_code
        assert result.content.caption == "반복 업무를 줄이는 방법입니다.\n\n무료 등급 제한도 정리했습니다.\n\n저장해두세요."

    def test_caption_cta_only_on_earlier_line_moves_to_end(self, monkeypatch):
        caption = "반복 업무를 줄이는 방법입니다. 지금 저장하세요.\n\n무료 등급 제한도 정리했습니다."
        payload = _norm_payload(["AI 영업 자동화 시작", "핵심 사실입니다.", "필요할 때 다시 보도록 저장하세요."], caption)
        result, _ = _run_short(monkeypatch, payload, 3)
        assert result.success is True, result.error_code
        assert result.content.caption.splitlines()[-1].endswith("지금 저장하세요.")

    def test_caption_mixed_line_still_fails(self, monkeypatch):
        caption = "데이터를 저장해 두면 비교가 쉽습니다.\n\n무료 등급 제한도 정리했습니다.\n\n저장해두세요."
        payload = _norm_payload(["AI 영업 자동화 시작", "핵심 사실입니다.", "필요할 때 다시 보도록 저장하세요."], caption)
        result, _ = _run_short(monkeypatch, payload, 3)
        assert result.error_code == "CAPTION_CTA_NOT_LAST"

    def test_safety_runs_on_normalized_text(self, monkeypatch):
        payload = _norm_payload(["AI 영업 자동화 시작", "무료 등급은 검색이 제한됩니다. 지금 저장하세요.",
                                 "하루 3건 자동 게시로 업무를 줄입니다."])
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)
        seen = []
        monkeypatch.setattr(builder, "check_caption_safety", lambda text, **k: (seen.append(text), ("UNSAFE", "x"))[1])
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert result.error_code == "SAFETY_BLOCKED:x" and "줄입니다. 지금 저장하세요." in seen[0]

    def test_fabrication_check_still_applies(self, monkeypatch):
        payload = _norm_payload(["AI 영업 자동화 시작", "매출이 300% 늘었습니다. 지금 저장하세요.", "하루 3건 자동 게시가 됩니다."])
        result, _ = _run_short(monkeypatch, payload, 3)
        assert result.error_code == "POSSIBLE_FABRICATION"

    def test_failure_log_has_positions_without_text(self, monkeypatch, caplog):
        payload = _norm_payload(["AI 영업 자동화 시작", "데이터를 저장해 두면 비교가 쉽습니다.", "필요할 때 다시 보도록 저장하세요."])
        with caplog.at_level(logging.WARNING):
            result, _ = _run_short(monkeypatch, payload, 3)
        assert result.error_code == "CTA_NOT_LAST_SLIDE"
        log = " ".join(r.getMessage() for r in caplog.records if "CarouselContent" in r.getMessage())
        assert "slide_cta=[0, 1, 1]" in log and "caption_line_cta=" in log
        assert "데이터를 저장해" not in log

    def test_eight_slide_path_is_not_normalized(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")
        assert result.success is True and len(result.content.slides) == 8
        assert [s.text for s in result.content.slides] == [s["text"] for s in _valid_slides()]


# ── 261023 STEP 4-AV — 짧은 캐러셀 클릭형 카피 규칙(훅 → 공감 → 해결 → CTA) ──────────

class TestShortHookCopyRules:
    """261023 STEP 4-BB — 정보 전달 우선(뉴스 가치 → 핵심 사실 → 실제 사용법 + CTA) 프롬프트."""

    def _prompt(self, monkeypatch, n, topic=None):
        models = _FakeModels(response=_FakeResponse(_short_payload(n)))
        _patch_gemini(monkeypatch, models)
        builder.generate_carousel_content(topic or _topic(), "REACH", "HOOK_IMPACT", slide_count=n)
        return models.calls[0]["contents"]

    @pytest.mark.parametrize("n", [2, 3, 4])
    def test_editor_role_and_news_value_in_prompt(self, monkeypatch, n):
        prompt = self._prompt(monkeypatch, n)
        assert "Slide 1 (question hook)" in prompt and "ends with '?'" in prompt     # 261024 질문형 표지
        assert "ideally 15-30 Korean characters (never more than 40)" in prompt
        assert "real AI product name, new feature, update" in prompt and "clickbait" in prompt
        assert "the headline must include that name" in prompt
        assert "AI technology editor" in prompt and "at least one thing worth saving" in prompt
        assert "never invent menus" in prompt and "narrow the scope" in prompt
        assert "혁신, 효율성 증대" in prompt
        assert "Requests or imperative lines may appear only on the last slide" in prompt
        assert "a question that names a pain" not in prompt          # 4-AV 문제 제기형 훅 지시 제거
        assert "Prefer a question hook" not in prompt
        assert f"Slide {n} (" in prompt and "+ CTA)" in prompt

    @pytest.mark.parametrize("n", [2, 3, 4])
    def test_cover_limit_counts_every_character_in_prompt(self, monkeypatch, n):
        """261026 STEP 5-B — 022 실측 41·43자 초과: 40자는 공백·영문·숫자·문장부호 포함이라고 명시한다."""
        prompt = self._prompt(monkeypatch, n)
        assert "including spaces, English letters, digits and punctuation" in prompt
        assert "count them yourself before answering" in prompt
        assert "'IBM Granite Speech 5.0' → 'Granite 음성 AI'" in prompt

    @pytest.mark.parametrize("cover,expected", [
        ("IBM Granite Speech 5.0, 오픈 음성 모델 2위의 실력은?", "COVER_TITLE_INVALID"),   # 41자(022 실측)
        ("Granite 음성 AI, 공개 음성 모델 중 실력은 어느 정도일까?", None),              # 38자, 숫자 없음
    ])
    def test_cover_title_check_still_40_chars(self, monkeypatch, cover, expected):
        assert builder._COVER_TITLE_MAX_CHARS == 40
        result, _ = _run_short(monkeypatch, _short_payload(3, cover=cover), 3)
        assert (result.error_code if not result.success else None) == expected

    def test_three_slide_plan_is_fact_then_action(self, monkeypatch):
        prompt = self._prompt(monkeypatch, 3)
        assert "Slide 2 (fact)" in prompt and "how it differs from before" in prompt
        assert "Slide 3 (action + CTA)" in prompt
        assert "tool → what to enter → how to run it → expected result" in prompt
        assert "업무 효율 향상" in prompt                              # 막연한 이점 금지 예시

    def test_two_slide_plan_combines_fact_and_action(self, monkeypatch):
        prompt = self._prompt(monkeypatch, 2)
        assert "Slide 2 (fact + action + CTA)" in prompt and "Slide 2 (fact):" not in prompt

    def test_four_slide_plan_middle_slide_has_no_cta(self, monkeypatch):
        prompt = self._prompt(monkeypatch, 4)
        assert "Slide 3 (action)" in prompt and "No request or call to action here." in prompt
        assert "Slide 4 (extra + CTA)" in prompt and "comparison, caution or checklist" in prompt

    def test_news_article_style_and_topic_cta(self, monkeypatch):
        prompt = self._prompt(monkeypatch, 3)
        assert "the headline asks, the body states verified facts" in prompt
        assert "Do not just translate the US source" in prompt
        assert "Avoid an unconditional follow request" in prompt and "실무 적용할 때 보도록 저장하세요." in prompt

    def test_guide_topic_is_not_presented_as_news(self, monkeypatch):
        prompt = self._prompt(monkeypatch, 3)
        assert "Content type: GUIDE" in prompt and "Do not call it new" in prompt

    def test_news_topic_carries_published_date(self, monkeypatch):
        topic = SourceTopic(topic_id="14.1", title="Example News", status="VERIFIED FACT",
                            source_url="https://example.com/news-1",
                            core_message="이 도구는 하루 3건 자동 게시를 지원한다.", prohibited_expression="",
                            source_published_at="2026-10-22T15:00:00+00:00")
        prompt = self._prompt(monkeypatch, 3, topic)
        assert "Content type: NEWS (source published 2026-10-22T15:00:00+00:00)" in prompt

    def test_grounding_rule_kept(self, monkeypatch):
        prompt = self._prompt(monkeypatch, 3)
        assert "Do NOT invent any fact" in prompt and "no false claims, guarantees, false urgency" in prompt

    def test_eight_slide_prompt_unchanged(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_valid_payload()))
        _patch_gemini(monkeypatch, models)
        builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")
        prompt = models.calls[0]["contents"]
        assert "8-slide" in prompt and "Slide 1 (question hook)" not in prompt and "Content type:" not in prompt


# ── 261023 STEP 4-AV — 비마지막 장 행동 요청(CTA 키워드 없는 명령형) 차단 ────────────

class TestNonLastSlideImperative:
    def _run(self, monkeypatch, payload, n):
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)
        return builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=n)

    @pytest.mark.parametrize("cover", ["AI 영업 DM, 이제 자동화하세요", "반복 업무, 지금 자동화를 시작하세요!",
                                       "반복 업무를 시스템에 맡기십시오"])
    def test_two_slide_cover_imperative_fails(self, monkeypatch, cover):
        result = self._run(monkeypatch, _short_payload(2, cover=cover), 2)
        assert (result.success, result.error_code) == (False, "IMPERATIVE_NOT_LAST_SLIDE")

    @pytest.mark.parametrize("middle", ["무료 등급 제한을 먼저 알아두세요.", "업무 흐름을 하나씩 바꿔보세요",
                                        "검색 기능이 제한됩니다. 그래도 지금 확인해 보세요."])
    def test_three_slide_middle_imperative_fails(self, monkeypatch, middle):
        payload = _short_payload(3)
        payload["slides"][1]["text"] = middle
        result = self._run(monkeypatch, payload, 3)
        assert result.success is False
        assert result.error_code in ("IMPERATIVE_NOT_LAST_SLIDE", "CTA_NOT_LAST_SLIDE")
        if "확인해 보세요" not in middle:
            assert result.error_code == "IMPERATIVE_NOT_LAST_SLIDE"

    def test_last_slide_cta_and_question_hook_pass(self, monkeypatch):
        payload = _short_payload(3)
        payload["slides"][2]["text"] = "하루 3건 자동 게시로 업무를 줄입니다. 저장해 두고 하나씩 바꿔보세요."
        result = self._run(monkeypatch, payload, 3)
        assert result.success is True, result.error_code
        assert result.content.slides[0].text.endswith("계세요?")

    @pytest.mark.parametrize("middle", [
        "무료 등급은 검색 기능이 제한됩니다",
        "고객이 '빨리 처리해 주세요'라고 다시 묻는 일이 줄어듭니다.",
        "직접 하고 계세요? 무료 등급은 검색이 제한됩니다.",
    ])
    def test_descriptive_or_quoted_sentences_pass(self, monkeypatch, middle):
        payload = _short_payload(3)
        payload["slides"][1]["text"] = middle
        result = self._run(monkeypatch, payload, 3)
        assert result.success is True, result.error_code

    def test_middle_pure_cta_still_normalized_before_check(self, monkeypatch):
        payload = _short_payload(3)
        payload["slides"][1]["text"] = "무료 등급은 검색 기능이 제한됩니다. 지금 저장하세요."
        payload["slides"][2]["text"] = "하루 3건 자동 게시로 반복 업무를 줄일 수 있습니다."
        result = self._run(monkeypatch, payload, 3)
        assert result.success is True, result.error_code
        assert result.content.slides[1].text == "무료 등급은 검색 기능이 제한됩니다."

    def test_eight_slide_path_not_checked(self, monkeypatch):
        payload = _valid_payload()
        payload["slides"][1]["text"] = "이 기능을 꼭 써보세요"
        result = self._run(monkeypatch, payload, 8)
        assert result.error_code != "IMPERATIVE_NOT_LAST_SLIDE"


# ── 261023 STEP 4-BA — 캡션 중간의 CTA 전용 줄을 마지막 줄로 이동 ─────────────────────

class TestCaptionCtaOnlyLineMove:
    _SLIDES = ["AI 영업 자동화, 아직도 직접 하고 계세요?", "핵심 사실입니다.", "필요할 때 다시 보도록 저장하세요."]

    def test_cta_only_middle_line_moves_to_end(self, monkeypatch):
        caption = "반복 업무를 줄이는 방법입니다.\n\n무료 등급 제한도 정리했습니다.\n\n지금 저장해 두세요.\n\n작은 업무부터 바꿔 볼 수 있습니다."
        result, models = _run_short(monkeypatch, _norm_payload(self._SLIDES, caption), 3)
        assert result.success is True, result.error_code
        assert result.content.caption == ("반복 업무를 줄이는 방법입니다.\n\n무료 등급 제한도 정리했습니다.\n\n"
                                          "작은 업무부터 바꿔 볼 수 있습니다.\n\n지금 저장해 두세요.")
        assert len(models.calls) == 1                                    # Gemini 재호출 없음

    def test_multiple_cta_only_lines_keep_last_one(self, monkeypatch):
        caption = "팔로우하세요.\n\n반복 업무를 줄이는 방법입니다.\n\n지금 저장해 두세요.\n\n작은 업무부터 바꿔 볼 수 있습니다."
        result, _ = _run_short(monkeypatch, _norm_payload(self._SLIDES, caption), 3)
        assert result.success is True, result.error_code
        lines = [l for l in result.content.caption.splitlines() if l.strip()]
        assert lines[-1] == "지금 저장해 두세요." and "팔로우하세요." not in result.content.caption
        assert [builder._count_cta_sentences(l) for l in lines] == [0, 0, 1]

    def test_cta_already_on_last_line_unchanged_and_fails(self, monkeypatch):
        caption = "반복 업무를 줄이는 방법입니다.\n\n팔로우하세요.\n\n저장해두세요."
        result, _ = _run_short(monkeypatch, _norm_payload(self._SLIDES, caption), 3)
        assert result.error_code == "CAPTION_CTA_NOT_LAST"

    def test_mixed_middle_line_still_fails(self, monkeypatch):
        caption = "반복 업무를 줄이는 방법입니다.\n\n데이터를 저장해 두면 비교가 쉽습니다.\n\n작은 업무부터 바꿔 볼 수 있습니다."
        result, _ = _run_short(monkeypatch, _norm_payload(self._SLIDES, caption), 3)
        assert result.success is False and result.error_code.startswith("CAPTION_CTA")

    def test_slide_cta_only_body_still_not_moved(self, monkeypatch):
        payload = _norm_payload(["AI 영업 자동화 시작", "지금 저장하세요.", "하루 3건 자동 게시가 됩니다."])
        result, _ = _run_short(monkeypatch, payload, 3)
        assert result.error_code == "CTA_NOT_LAST_SLIDE"


class TestAccountCtaContract:
    """261026 STEP 5-B — Persona conversion_cta가 있으면 그 문구도 CTA로 인정한다(022 Dry-run 실측: 계정 CTA를
    정확히 썼는데 키워드가 없어 LAST_SLIDE_CTA_COUNT_INVALID). CTA 누락 차단·036(계정 CTA 없음) 동작은 그대로."""

    CTA_022 = "AI 뉴스 요약 자동화 문의는 DM"

    def _payload(self, last_text, caption_last):
        payload = _short_payload(3)
        payload["slides"][-1]["text"] = last_text
        payload["caption"] = "음성 AI 모델 3종을 정리했습니다.\n\n언어별 지원 범위를 비교해 보세요.\n\n" + caption_last
        return payload

    def _run(self, monkeypatch, payload, conversion_cta=""):
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3,
                                                   conversion_cta=conversion_cta)
        return result, models

    def test_022_account_cta_on_last_slide_and_caption_passes(self, monkeypatch):
        payload = self._payload("모델별 지원 언어를 비교했습니다. AI 뉴스 요약 자동화 문의는 DM.",
                                "AI 뉴스 요약 자동화 문의는 DM.")
        result, models = self._run(monkeypatch, payload, self.CTA_022)
        assert result.success is True, result.error_code
        prompt = models.calls[0]["contents"]
        assert f'exactly "{self.CTA_022}"' in prompt and "replaces the CTA keyword rule" in prompt

    def test_022_missing_cta_on_last_slide_still_blocked(self, monkeypatch):
        payload = self._payload("모델별 지원 언어를 비교했습니다.", "AI 뉴스 요약 자동화 문의는 DM.")
        result, _ = self._run(monkeypatch, payload, self.CTA_022)
        assert (result.success, result.error_code) == (False, "LAST_SLIDE_CTA_COUNT_INVALID")

    def test_022_missing_cta_in_caption_still_blocked(self, monkeypatch):
        payload = self._payload("AI 뉴스 요약 자동화 문의는 DM.", "언어별 오류율을 비교해 보세요.")
        result, _ = self._run(monkeypatch, payload, self.CTA_022)
        assert (result.success, result.error_code) == (False, "CAPTION_CTA_COUNT_INVALID")

    def test_022_account_cta_on_body_slide_blocked(self, monkeypatch):
        payload = self._payload("AI 뉴스 요약 자동화 문의는 DM.", "AI 뉴스 요약 자동화 문의는 DM.")
        payload["slides"][1]["text"] = "39만 시간 학습. AI 뉴스 요약 자동화 문의는 DM"
        result, _ = self._run(monkeypatch, payload, self.CTA_022)
        assert (result.success, result.error_code) == (False, "CTA_NOT_LAST_SLIDE")

    def test_without_account_cta_dm_phrase_is_not_a_cta(self, monkeypatch):
        """036처럼 conversion_cta가 없으면 기존 키워드 검사 그대로 — 'DM' 문장은 CTA가 아니다."""
        payload = self._payload("AI 뉴스 요약 자동화 문의는 DM.", "AI 뉴스 요약 자동화 문의는 DM.")
        result, models = self._run(monkeypatch, payload)
        assert (result.success, result.error_code) == (False, "LAST_SLIDE_CTA_COUNT_INVALID")
        assert "Account CTA" not in models.calls[0]["contents"]

    def test_without_account_cta_keyword_cta_still_passes(self, monkeypatch):
        result, _ = self._run(monkeypatch, _short_payload(3))
        assert result.success is True, result.error_code

    def test_count_helper_default_unchanged(self):
        assert builder._count_cta_sentences("문의는 DM. 저장하세요.") == 1
        assert builder._count_cta_sentences("문의는 DM. 저장하세요.", "문의는 DM") == 2
        assert builder._count_cta_sentences("저장하세요", "   ") == 1

class TestWordSeparatorAnd022Captures:
    """261026 STEP 5-B — 022 Dry-run 캡처(g·h·i) 재사용. 띄어 쓴 '·'/'→'는 단어로 세지 않고(30단어 기준 유지),
    022 Sourcebook 1.1 원문 수치 기준으로 캡처 숫자는 통과·허위 숫자는 차단한다."""

    CTA_022 = "AI 뉴스 요약 자동화 문의는 DM"
    SB_022 = Path(__file__).resolve().parents[1] / "docs" / "design" / "SNS_AI_NEWS_SOURCEBOOK_IDN022_261026.md"
    CAPTURE_G = ("음성 AI Granite 5.0, 공개 모델 2위 오른 비결은? "
                 "39만 시간 학습·6개 언어 지원·Open ASR 리더보드 오류율 5.06%·Apache 2.0 라이선스 "
                 "키워드 2,000개 지정 기능·Turbo CTC 속도 1.6배 향상·장문 오류 24% 감소. AI 뉴스 요약 자동화 문의는 DM")
    CAPTURE_H_SLIDE2 = ("2B 모델은 6개 언어 받아쓰기·상호 번역·39만 시간 학습·키워드 2,000개 지정·영어 단어 오류율 5.06% · "
                        "Turbo CTC는 7개 언어·구두점 자동 처리·속도 1.6배 향상 · 4.1-2b-plus는 장문 오류율 24% 감소 · "
                        "Apache 2.0 라이선스")
    CAPTURE_I_SLIDE2 = ("영어·프랑스어·독일어·스페인어·포르투갈어·일본어 6개 언어 받아쓰기 및 영어 상호 번역 · "
                        "39만 시간 분량 공개 음성 학습 · Open ASR 리더보드 영어 평균 단어 오류율 5.06% 공개 모델 2위 · "
                        "Apache 2.0 라이선스 공개")

    def _grounding(self):
        from modules.sns.source_selector import parse_sourcebook
        topic = next(t for t in parse_sourcebook(self.SB_022) if t.topic_id == "1.1")
        return topic.core_message + " " + topic.title

    def _payload(self, slide2):
        return {
            "slides": [
                {"index": 1, "text": "음성 AI Granite Speech 5.0, 어떤 언어를 지원할까?"},
                {"index": 2, "text": slide2},
                {"index": 3, "text": "IBM Granite Speech 5.0 오픈소스 활용 · 6개 언어 음성 데이터 처리 및 번역 적용 · "
                                     + self.CTA_022},
            ],
            "caption": "IBM이 공개한 음성 AI 모델의 지원 언어와 성능 지표를 정리했습니다.\n" + self.CTA_022,
            "hashtags": ["AI뉴스", "해외이슈", "뉴스요약", "음성인식", "오픈소스AI"],
        }

    def test_capture_i_slide2_is_29_real_words_and_passes(self):
        assert len(self.CAPTURE_I_SLIDE2.split()) == 32
        assert builder._count_words(self.CAPTURE_I_SLIDE2) == 29
        assert builder._validate_short_contract(self._payload(self.CAPTURE_I_SLIDE2), 3, self.CTA_022) is None

    def test_31_real_words_still_blocked(self):
        slide2 = self.CAPTURE_I_SLIDE2 + " 그리고 확인"
        assert builder._count_words(slide2) == 31
        assert builder._validate_short_contract(self._payload(slide2), 3, self.CTA_022) == "BODY_SLIDE_TOO_LONG"

    def test_separator_only_excludes_standalone_marks(self):
        assert builder._count_words("A · B → C") == 3
        assert builder._count_words("A·B C") == 2          # 붙어 있는 '·'는 단어 일부라 그대로 센다
        assert builder._BODY_MAX_WORDS == 30

    @pytest.mark.parametrize("text", [CAPTURE_G, CAPTURE_H_SLIDE2, CAPTURE_I_SLIDE2])
    def test_capture_numbers_grounded_in_022_sourcebook(self, text):
        assert builder._detect_possible_fabrication(text, self._grounding()) is False

    @pytest.mark.parametrize("fake", ["WER 3.5%로 1위", "48만 시간 학습", "9개 언어 지원"])
    def test_fabricated_numbers_still_blocked(self, fake):
        assert builder._detect_possible_fabrication(self.CAPTURE_I_SLIDE2 + " " + fake, self._grounding()) is True

class TestFactPlacement022:
    """261026 STEP 5-B — 2장은 핵심 사실 3~4개, 나머지 검증 사실은 캡션 본문으로(삭제·변조 금지). 30단어·CTA·숫자 검사 유지."""

    CTA_022 = TestWordSeparatorAnd022Captures.CTA_022
    SB_022 = TestWordSeparatorAnd022Captures.SB_022
    _payload = TestWordSeparatorAnd022Captures._payload
    _grounding = TestWordSeparatorAnd022Captures._grounding

    # 최종 Dry-run(18:54) 2장 실측 — 사실 8개, 구분 기호 7개, 실제 31단어
    FINAL_SLIDE2 = ("3종 공개 · 2B 모델 6개 언어 받아쓰기 및 상호 번역 · 39만 시간 학습 · 2,000개 키워드 지정 · WER 5.06% · "
                    "Turbo CTC 속도 약 1.6배 향상 · 4.1-2b-plus 오류율 24% 감소 · Apache 2.0 라이선스")
    FOUR_FACT_SLIDE2 = "2B 모델 6개 언어 받아쓰기 및 상호 번역 · 39만 시간 학습 · Open ASR 영어 WER 5.06% 공개 모델 2위 · Apache 2.0 라이선스"
    CAPTION = ("IBM이 공개한 음성 AI 모델 3종을 해외 이슈 요약으로 정리했습니다.\n"
               "제품명·인명을 최대 2,000개 키워드로 지정할 수 있습니다.\n"
               "Turbo CTC는 속도가 약 1.6배 빨라졌고, 4.1-2b-plus는 장문 음성 오류율을 24% 줄였습니다.\n"
               "AI 뉴스 요약 자동화 문의는 DM")

    def _prompt(self, monkeypatch, **kw):
        models = _FakeModels(response=_FakeResponse(_short_payload(3)))
        _patch_gemini(monkeypatch, models)
        builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3, **kw)
        return models.calls[0]["contents"]

    def test_prompt_limits_slide2_to_key_facts_and_moves_rest_to_caption(self, monkeypatch):
        prompt = self._prompt(monkeypatch)
        assert "only the 3-4 most important verified facts" in prompt
        assert "remaining verified facts and numbers in the caption body instead of dropping or changing them" in prompt
        assert "at least three information lines in total" in prompt
        assert "at most 30 words" in prompt                       # 30단어 지시 유지

    def test_seo_rule_only_with_account_keywords(self, monkeypatch):
        assert "never stuff or repeat keywords" not in self._prompt(monkeypatch)
        prompt = self._prompt(monkeypatch, seo_keywords="AI뉴스, 해외이슈")
        assert "AI뉴스, 해외이슈" in prompt and "each at most once" in prompt

    def test_final_dry_run_slide2_of_31_real_words_still_blocked(self):
        assert builder._count_words(self.FINAL_SLIDE2) == 31
        assert builder._validate_short_contract(self._payload(self.FINAL_SLIDE2), 3, self.CTA_022) == "BODY_SLIDE_TOO_LONG"

    def test_four_key_facts_on_slide2_and_rest_in_caption_pass(self):
        payload = self._payload(self.FOUR_FACT_SLIDE2)
        payload["caption"] = self.CAPTION
        assert builder._count_words(self.FOUR_FACT_SLIDE2) <= 30
        assert builder._validate_short_contract(payload, 3, self.CTA_022) is None
        combined = " ".join(s["text"] for s in payload["slides"]) + " " + payload["caption"]
        assert builder._detect_possible_fabrication(combined, self._grounding()) is False
        for fact in ("2,000", "1.6", "24%"):                     # 카드에서 빠진 사실은 캡션에 그대로 남는다
            assert fact in payload["caption"]
        assert payload["caption"].splitlines()[-1] == self.CTA_022

    def test_fake_number_in_caption_still_blocked(self):
        combined = self.FOUR_FACT_SLIDE2 + " " + self.CAPTION.replace("24%", "42%")
        assert builder._detect_possible_fabrication(combined, self._grounding()) is True

class TestCaptionCtaLineAndSeo022:
    """261026 STEP 5-B — 022 최종 Dry-run 캡션이 줄바꿈 없는 한 줄(정보 + 계정 CTA)이었다. 계정 CTA를 독립 마지막
    줄로 옮기고(문구 불변), 해시태그는 글 주제어를 쓰도록 지시한다. 036(계정 CTA 없음)은 그대로."""

    CTA_022 = "AI 뉴스 요약 자동화 문의는 DM"
    ONE_LINE = ("IBM이 공개한 음성 AI 모델 3종을 정리했습니다. 회의 및 통화용 4.1-2b-plus는 장문 음성 오류율을 24% "
                "줄였으며 모든 모델은 Apache 2.0 라이선스로 제공됩니다. AI 뉴스 요약 자동화 문의는 DM")

    def test_one_line_caption_gets_separate_cta_line(self):
        out = builder._separate_account_cta_line({"caption": self.ONE_LINE}, self.CTA_022)["caption"]
        lines = out.split("\n")
        assert lines[-1] == self.CTA_022 and lines[-2] == ""
        assert lines[0].endswith("제공됩니다.") and out.replace("\n", " ").replace("  ", " ") == self.ONE_LINE

    def test_already_separate_or_missing_cta_unchanged(self):
        done = "정보 줄입니다.\n\n" + self.CTA_022
        assert builder._separate_account_cta_line({"caption": done}, self.CTA_022)["caption"] == done
        no_cta = "정보 줄입니다. 저장해두세요."
        assert builder._separate_account_cta_line({"caption": no_cta}, self.CTA_022)["caption"] == no_cta
        assert builder._separate_account_cta_line({"caption": self.ONE_LINE}, "")["caption"] == self.ONE_LINE

    def test_generated_one_line_caption_saved_with_cta_on_last_line(self, monkeypatch):
        payload = _short_payload(3)
        payload["slides"][-1]["text"] = "공개 음성 모델 확인 · " + self.CTA_022
        payload["caption"] = self.ONE_LINE
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)
        result = builder.generate_carousel_content(_topic(core_message=_topic().core_message + " 24% 2.0 4.1-2b 3종"),
                                                   "REACH", "HOOK_IMPACT", slide_count=3,
                                                   conversion_cta=self.CTA_022)
        assert result.success is True, result.error_code
        assert result.content.caption.split("\n")[-1] == self.CTA_022

    def test_seo_prompt_requires_subject_hashtags(self, monkeypatch):
        models = _FakeModels(response=_FakeResponse(_short_payload(3)))
        _patch_gemini(monkeypatch, models)
        builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3,
                                          seo_keywords="오늘의뉴스, AI뉴스")
        prompt = models.calls[0]["contents"]
        assert "At least 3 hashtags must name this post's own subject" in prompt and "#IBM, #음성인식" in prompt
        models2 = _FakeModels(response=_FakeResponse(_short_payload(3)))
        _patch_gemini(monkeypatch, models2)
        builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3)
        assert "At least 3 hashtags must name" not in models2.calls[0]["contents"]

    def test_fake_number_in_separated_caption_still_blocked(self, monkeypatch):
        payload = _short_payload(3)
        payload["slides"][-1]["text"] = "공개 음성 모델 확인 · " + self.CTA_022
        payload["caption"] = self.ONE_LINE.replace("24%", "42%")
        models = _FakeModels(response=_FakeResponse(payload))
        _patch_gemini(monkeypatch, models)
        result = builder.generate_carousel_content(_topic(core_message=_topic().core_message + " 24% 2.0 4.1-2b 3종"),
                                                   "REACH", "HOOK_IMPACT", slide_count=3,
                                                   conversion_cta=self.CTA_022)
        assert (result.success, result.error_code) == (False, "POSSIBLE_FABRICATION")

class _SeqModels:
    """응답을 호출 순서대로 돌려준다(첫 생성 → 재작성)."""

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return _FakeResponse(self._payloads[min(len(self.calls), len(self._payloads)) - 1])


class TestFactLockAndControlledRepair022:
    """261026 STEP 5-B — 022 FACT LOCK(카드 사실 지정)·LAYOUT LOCK·LAYOUT/STYLE 1회 재작성. 사실·Safety·중복은
    재작성 없이 멈추고, 카드 사실이 없는 036 경로는 그대로다."""

    CTA = "AI 뉴스 요약 자동화 문의는 DM"
    SB_022 = Path(__file__).resolve().parents[1] / "docs" / "design" / "SNS_AI_NEWS_SOURCEBOOK_IDN022_261026.md"
    GOOD_SLIDE2 = ("6개 언어 받아쓰기·영어 상호 번역 · 39만 시간 공개 음성 학습 · 영어 평균 단어 오류율(WER) 5.06% "
                   "공개 모델 중 2위 · Apache 2.0 라이선스")
    CRAMMED_SLIDE2 = ("6개 언어 받아쓰기·영어 상호 번역·39만 시간 학습·키워드 2,000개 지정·WER 5.06% 2위·Turbo CTC "
                      "속도 1.6배 향상·4.1-2b-plus 오류율 24% 감소·Apache 2.0 라이선스")
    CAPTION = ("IBM이 공개한 음성 AI 모델 3종을 정리했습니다.\n"
               "키워드는 최대 2,000개까지 지정할 수 있습니다.\n"
               "Turbo CTC는 속도가 약 1.6배 빨라졌고 4.1-2b-plus는 장문 오류율을 24% 줄였습니다.\n"
               "AI 뉴스 요약 자동화 문의는 DM")

    def _topic(self):
        from modules.sns.source_selector import parse_sourcebook
        return next(t for t in parse_sourcebook(self.SB_022) if t.topic_id == "1.1")

    def _payload(self, slide2=None, caption=None, last=None):
        return {
            "slides": [
                {"index": 1, "role": "cover", "text": "Granite 음성 AI 3종 공개, 무엇이 달라졌나?"},
                {"index": 2, "role": "fact", "text": slide2 or self.GOOD_SLIDE2},
                {"index": 3, "role": "cta", "text": last or ("공개 모델 확인 · 지원 언어 선택 · " + self.CTA)},
            ],
            "caption": caption or self.CAPTION,
            "hashtags": ["IBM", "음성인식", "음성AI", "해외이슈", "AI뉴스"],
        }

    def _run(self, monkeypatch, payloads, topic=None, safety=("SAFE", "STOP"), **kw):
        models = _SeqModels(payloads)
        _patch_gemini(monkeypatch, models)
        monkeypatch.setattr(builder, "check_caption_safety", lambda text, **k: safety)
        result = builder.generate_carousel_content(topic or self._topic(), "REACH", "HOOK_IMPACT", slide_count=3,
                                                   conversion_cta=self.CTA, **kw)
        return result, models

    def test_sourcebook_card_facts_are_grounded(self):
        topic = self._topic()
        assert len(topic.card_facts) == 4
        grounding = builder._extract_numeric_tokens(topic.core_message + " " + topic.title)
        assert all(builder._extract_numeric_tokens(f) <= grounding for f in topic.card_facts)

    def test_assigned_facts_pass_in_one_call(self, monkeypatch):
        result, models = self._run(monkeypatch, [self._payload()])
        assert result.success is True, result.error_code
        assert len(models.calls) == 1 and "Slide 2 FACT LOCK" in models.calls[0]["contents"]
        assert result.content.slides[1].text == self.GOOD_SLIDE2
        assert result.content.caption.split("\n")[-1] == self.CTA

    def test_reexpressed_number_stops_without_repair(self, monkeypatch):
        caption = self.CAPTION.replace("3종을 정리했습니다.", "3종을 정리했습니다. 영어와 5개 언어를 지원합니다.")
        result, models = self._run(monkeypatch, [self._payload(caption=caption)])
        assert (result.success, result.error_code) == (False, "POSSIBLE_FABRICATION")
        assert len(models.calls) == 1                                        # FACT 위반은 재작성 0회

    def test_crammed_slide2_is_repaired_once_then_passes(self, monkeypatch):
        result, models = self._run(monkeypatch, [self._payload(slide2=self.CRAMMED_SLIDE2), self._payload()])
        assert result.success is True, result.error_code
        assert len(models.calls) == 2
        repair_prompt = models.calls[1]["contents"]
        assert "Rewrite ONLY the field named 'body'" in repair_prompt and "CARD_FACT_EXTRA" in repair_prompt
        assert result.content.slides[1].text == self.GOOD_SLIDE2
        assert result.content.caption == self.CAPTION                        # 실패 필드만 교체

    def test_missing_card_fact_after_repair_stops(self, monkeypatch):
        partial = "6개 언어 받아쓰기·영어 상호 번역 · 39만 시간 공개 음성 학습"
        result, models = self._run(monkeypatch, [self._payload(slide2=partial), self._payload(slide2=partial)])
        assert (result.success, result.error_code) == (False, "CARD_FACT_MISSING")
        assert len(models.calls) == 2                                        # 재작성 1회 뒤 STOP

    def test_body_over_30_words_with_attached_separators_is_repaired(self, monkeypatch):
        long_slide2 = self.GOOD_SLIDE2 + " · " + "·".join(["추가설명"] * 10)
        assert builder._count_words(long_slide2) <= 30 < builder._count_words(long_slide2, strict=True)
        result, models = self._run(monkeypatch, [self._payload(slide2=long_slide2), self._payload()])
        assert result.success is True and len(models.calls) == 2
        assert "BODY_SLIDE_TOO_LONG" in models.calls[1]["contents"]

    def test_caption_cta_error_repairs_caption_only(self, monkeypatch):
        bad_caption = self.CAPTION.replace("\n" + self.CTA, "\n자세한 내용은 원문을 참고하세요.")   # CTA 없는 마지막 줄
        fixed = self._payload(slide2="바뀌면 안 되는 2장")                    # 재작성 응답의 2장은 무시돼야 한다
        result, models = self._run(monkeypatch, [self._payload(caption=bad_caption), fixed])
        assert result.success is True, result.error_code
        assert len(models.calls) == 2 and "Rewrite ONLY the field named 'caption'" in models.calls[1]["contents"]
        assert result.content.slides[1].text == self.GOOD_SLIDE2 and result.content.caption == self.CAPTION

    def test_repair_failure_again_stops(self, monkeypatch):
        crammed = self._payload(slide2=self.CRAMMED_SLIDE2)
        result, models = self._run(monkeypatch, [crammed, crammed])
        assert (result.success, result.error_code) == (False, "CARD_FACT_EXTRA") and len(models.calls) == 2

    def test_safety_block_stops_without_repair(self, monkeypatch):
        result, models = self._run(monkeypatch, [self._payload()], safety=("UNSAFE", "blocked"))
        assert (result.success, result.error_code) == (False, "SAFETY_BLOCKED:blocked") and len(models.calls) == 1

    def test_duplicate_stops_without_repair(self, monkeypatch):
        first, _ = self._run(monkeypatch, [self._payload()])
        result, models = self._run(monkeypatch, [self._payload()],
                                   existing_fingerprints={first.content.content_fingerprint})
        assert (result.success, result.error_code) == (False, "DUPLICATE_FINGERPRINT") and len(models.calls) == 1

    def test_repair_uses_same_account_client_and_model(self, monkeypatch):
        models = _SeqModels([self._payload(slide2=self.CRAMMED_SLIDE2), self._payload()])
        own_client = _FakeClient(models)
        monkeypatch.setattr(builder, "_get_client", lambda: pytest.fail("공용 Client를 쓰면 안 됨"))
        monkeypatch.setattr(builder, "check_caption_safety", lambda text, **k: ("SAFE", "STOP"))
        result = builder.generate_carousel_content(self._topic(), "REACH", "HOOK_IMPACT", slide_count=3,
                                                   conversion_cta=self.CTA, client=own_client,
                                                   throttle_fn=lambda: None, model="m-022")
        assert result.success is True
        assert [c["model"] for c in models.calls] == ["m-022", "m-022"]

    def test_036_path_without_card_facts_unchanged(self, monkeypatch):
        """카드 사실이 없는 Topic(036 공용 Sourcebook)은 FACT LOCK 문구·재작성·엄격 단어 수가 모두 꺼져 있다."""
        crammed = self._payload(slide2=self.CRAMMED_SLIDE2)
        topic = _topic(core_message=self._topic().core_message)
        assert topic.card_facts == ()
        result, models = self._run(monkeypatch, [crammed, self._payload()], topic=topic)
        assert len(models.calls) == 1 and "FACT LOCK" not in models.calls[0]["contents"]
        assert result.success is True                                       # 기존 기준(붙여 쓴 '·'는 1단어)으로 통과

class TestTopicHashtagsAndCoverSubject022:
    """261026 STEP 5-B — Sourcebook 주제 해시태그(원문 회사·제품·기술)를 앞에 두고 Gemini 해시태그와 합친다(최대 8,
    중복 제거). 주제 해시태그가 없는 036 Topic은 그대로. 배경 개념은 오른쪽(텍스트 열 밖)에 크게 배치한다."""

    SB_022 = Path(__file__).resolve().parents[1] / "docs" / "design" / "SNS_AI_NEWS_SOURCEBOOK_IDN022_261026.md"

    def _topic(self):
        from modules.sns.source_selector import parse_sourcebook
        return next(t for t in parse_sourcebook(self.SB_022) if t.topic_id == "1.1")

    def test_022_topic_hashtags_grounded_in_source(self):
        topic = self._topic()
        assert topic.topic_hashtags == ("IBM", "음성인식", "음성AI", "다국어번역")
        text = (topic.core_message + topic.title).replace(" ", "")
        assert "IBM" in text and "음성" in text and "번역" in text

    def test_merge_puts_topic_tags_first_dedupes_and_caps(self):
        merged = builder._merge_topic_hashtags(
            {"hashtags": ["해외이슈", "ibm", "AI뉴스", "뉴스요약", "시사정리", "오늘의뉴스"]},
            ("IBM", "음성인식", "음성AI", "다국어번역"))["hashtags"]
        assert merged[:4] == ["IBM", "음성인식", "음성AI", "다국어번역"]
        assert len(merged) == builder._HASHTAG_MAX and "ibm" not in merged

    def test_merge_follows_hash_prefix_and_skips_without_topic_tags(self):
        assert builder._merge_topic_hashtags({"hashtags": ["#AI뉴스"]}, ("IBM",))["hashtags"] == ["#IBM", "#AI뉴스"]
        payload = {"hashtags": ["AI", "자동화"]}
        assert builder._merge_topic_hashtags(payload, ()) is payload        # 036: 그대로

    def test_generated_package_keeps_subject_hashtags(self, monkeypatch):
        cls = TestFactLockAndControlledRepair022
        payload = cls()._payload()
        payload["hashtags"] = ["해외이슈", "AI뉴스", "뉴스요약", "시사정리", "오늘의뉴스"]
        models = _SeqModels([payload])
        _patch_gemini(monkeypatch, models)
        result = builder.generate_carousel_content(self._topic(), "REACH", "HOOK_IMPACT", slide_count=3,
                                                   conversion_cta=cls.CTA)
        assert result.success is True, result.error_code
        assert list(result.content.hashtags[:4]) == ["IBM", "음성인식", "음성AI", "다국어번역"]
        assert len(models.calls) == 1

    def test_cover_concept_prompt_places_subject_right_without_books(self):
        from modules.sns.visual_brief import build_concept_background_prompt
        topic = self._topic()
        text = build_concept_background_prompt(topic.image_concept).prompt_text
        assert "microphone" in topic.image_concept and "sound waves" in topic.image_concept
        assert "right third of the image" in text and "left half as plain dark empty space" in text
        assert "no books, no paper" in text and "IBM" not in text
        assert not any(ch.isdigit() for ch in text)

class TestThousandsSeparatorNormalization022:
    """261026 STEP 5-B — 올바른 천 단위 쉼표만 지워 비교한다(2,000 = 2000). 소수점·퍼센트·모델명 숫자는 그대로,
    애매한 쉼표는 그대로 둬 Fail-closed. 캐러셀·카드 사실·히어로카드가 같은 함수를 쓴다."""

    SOURCE = "제품명·인명을 최대 2,000개 키워드로 지정, WER 5.06%, 6개 언어, granite-speech-5.0-2b 공개."

    @pytest.mark.parametrize("generated,expected", [
        ("키워드 최대 2000개 지정", False),            # 2,000 = 2000
        ("키워드 최대 2,000개 지정", False),
        ("WER 5.6%로 개선", True),                     # 5.06 ≠ 5.6
        ("영어와 5개 언어", True),                      # 6 ≠ 5
        ("granite-speech-5.0-2b 모델", False),          # 모델명 5.0 보존
        ("키워드 3,000개 지정", True),                  # 원문 외 숫자
        ("키워드 20,00개", True),                       # 애매한 쉼표 → 그대로 비교 → 차단
    ])
    def test_number_comparison(self, generated, expected):
        assert builder._detect_possible_fabrication(generated, self.SOURCE) is expected

    def test_token_normalization_keeps_decimals_and_percent(self):
        assert builder._extract_numeric_tokens("2,000개 10,000.5원 5.06% 5.0, 1,2") == {"2000", "10000.5", "5.06%",
                                                                                     "5.0", "1,2"}

    def test_hero_card_path_uses_same_normalization(self, monkeypatch):
        import modules.sns.hero_card_content_builder as hero
        assert hero._detect_possible_fabrication is builder._detect_possible_fabrication
        assert hero._detect_possible_fabrication("최대 2000개까지 지정 가능", self.SOURCE) is False
        assert hero._detect_possible_fabrication("최대 2001개까지 지정 가능", self.SOURCE) is True
