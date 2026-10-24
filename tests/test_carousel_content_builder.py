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
