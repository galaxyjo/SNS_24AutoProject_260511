"""260914 — content_filter.keyword_filter_text() 원문 키워드 선검사 검증.

배경: Google 무료 번역(deep_translator)이 TooManyRequests 로 막히면
detect_and_translate() 가 "" 를 돌려줘, 원문에 '화장품'·'도매'·'wholesale' 이
뚜렷한 게시물까지 크롤러에서 '필터 제외' 로 버려졌다(9/12~14 제외율 99.9%).

실제 번역 서버 호출 없음 — GoogleTranslator 를 전 테스트에서 Mock 으로 교체한다.

검증 목표:
  1. 원문 키워드(한국어/영어) → 번역 호출 없이 통과
  2. 배제 언어(베트남어 등) → 키워드가 섞여 있어도 제외 (기존 유지)
  3. 원문 키워드 없음 → 기존 번역 경로로 넘어감 (기존 유지)
  4. 차단어(coslife) → 번역 실패 시 제외, 번역돼도 키워드 필터에서 제외 (기존 유지)
  5. 크롤러가 실제로 이 함수를 쓴다 (배선)
"""

from types import SimpleNamespace

import pytest

import modules.sns.content_filter as cf


@pytest.fixture(autouse=True)
def translator(monkeypatch):
    """GoogleTranslator 를 호출 기록용 Mock 으로 교체. 기본은 번역 차단(예외) 상태."""
    state = SimpleNamespace(calls=[], result=None)

    class _FakeTranslator:
        def __init__(self, source="auto", target="en"):
            self.source = source

        def translate(self, text):
            state.calls.append(text)
            if state.result is None:
                raise Exception("TooManyRequests: You made too many requests to the server")
            return state.result

    monkeypatch.setattr(cf, "GoogleTranslator", _FakeTranslator)
    return state


# ── 1. 원문 키워드는 번역 없이 통과 ─────────────────────────────────────────
def test_korean_keyword_passes_without_translation(translator):
    raw = "정품 화장품 도매 공급합니다. 세럼 토너 대량 재고 있습니다"
    out = cf.keyword_filter_text(raw)
    assert out == raw
    assert cf.passes_keyword_filter(out)
    assert translator.calls == []


def test_english_keyword_passes_without_translation(translator):
    raw = "Korean cosmetics wholesale, MOQ 100, serum and toner supply"
    out = cf.keyword_filter_text(raw)
    assert out == raw
    assert cf.passes_keyword_filter(out)
    assert translator.calls == []


# ── 2. 배제 언어는 키워드가 섞여 있어도 제외 (기존 유지) ──────────────────────
def test_excluded_language_blocked_even_with_keyword(translator):
    raw = "Nguồn sỉ mỹ phẩm Hàn Quốc chính hãng cosmetic, giá tốt cho đại lý"
    assert cf._has_excluded_language(raw) is True
    assert cf.keyword_filter_text(raw) == ""
    assert translator.calls == []


# ── 3. 원문 키워드 없음 → 기존 번역 경로 (기존 유지) ─────────────────────────
def test_no_keyword_falls_back_to_translation_blocked(translator):
    raw = "오늘 날씨가 정말 좋네요"
    assert cf.keyword_filter_text(raw) == ""          # 번역 차단 → 기존과 동일하게 ""
    assert len(translator.calls) == 1


def test_no_keyword_falls_back_to_translation_success(translator):
    translator.result = "the weather is nice today"
    raw = "오늘 날씨가 정말 좋네요"
    out = cf.keyword_filter_text(raw)
    assert out == "the weather is nice today"          # 번역문 그대로 반환(기존 경로)
    assert not cf.passes_keyword_filter(out)           # 판정 결과도 기존과 동일
    assert len(translator.calls) == 1


# ── 4. 차단어는 여전히 제외 (기존 유지) ──────────────────────────────────────
def test_blocklist_word_blocked_when_translation_fails(translator):
    raw = "coslife 화장품 도매"
    out = cf.keyword_filter_text(raw)
    assert not out or not cf.passes_keyword_filter(out)


def test_blocklist_word_blocked_when_translation_succeeds(translator):
    translator.result = "coslife cosmetics wholesale"
    raw = "coslife 화장품 도매"
    out = cf.keyword_filter_text(raw)
    assert not out or not cf.passes_keyword_filter(out)


def test_empty_text(translator):
    assert cf.keyword_filter_text("") == ""
    assert cf.keyword_filter_text(None) == ""
    assert translator.calls == []


# ── 5. 크롤러 배선 ───────────────────────────────────────────────────────────
def test_crawler_uses_keyword_prefilter():
    import modules.sns.facebook_crawler as fc
    assert fc.keyword_filter_text is cf.keyword_filter_text
    assert not hasattr(fc, "detect_and_translate")     # 직접 번역 경로는 더 이상 크롤러에 없다
