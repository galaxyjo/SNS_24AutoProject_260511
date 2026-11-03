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
    state.sleeps = []
    monkeypatch.setattr(cf.time, "sleep", lambda s: state.sleeps.append(s))
    monkeypatch.setattr(cf, "_translate_429_until", 0.0)
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
def test_no_keyword_translation_429_is_hold_not_discard(translator):
    # 261104: 번역 429 는 '키워드 불일치(폐기)'가 아니라 HOLD — 2회 재시도(2s,4s) 후 예외
    raw = "오늘 날씨가 정말 좋네요"
    with pytest.raises(cf.TranslationRateLimited):
        cf.keyword_filter_text(raw)
    assert len(translator.calls) == 3
    assert translator.sleeps == [2, 4]


def test_translation_429_recovers_on_retry(translator):
    seq = iter([Exception("TooManyRequests"), "the weather is nice today"])

    def _translate(self, text):
        translator.calls.append(text)
        r = next(seq)
        if isinstance(r, Exception):
            raise r
        return r
    cf.GoogleTranslator.translate = _translate
    assert cf.keyword_filter_text("오늘 날씨가 정말 좋네요") == "the weather is nice today"
    assert len(translator.calls) == 2


def test_non_429_translate_error_keeps_old_empty_result(translator):
    def _boom(self, text):
        translator.calls.append(text)
        raise ValueError("network down")
    cf.GoogleTranslator.translate = _boom
    assert cf.keyword_filter_text("오늘 날씨가 정말 좋네요") == ""   # 기존 동작 유지(재시도·HOLD 없음)
    assert len(translator.calls) == 1


def test_429_substring_in_other_error_is_not_rate_limit(translator):
    def _boom(self, text):
        translator.calls.append(text)
        raise ValueError("bad request id 4291 at https://x/429")
    cf.GoogleTranslator.translate = _boom
    assert cf.keyword_filter_text("오늘 날씨가 정말 좋네요") == ""
    assert len(translator.calls) == 1 and translator.sleeps == []


def test_status_code_429_attribute_is_rate_limit(translator):
    class _Http(Exception):
        status_code = 429

    def _boom(self, text):
        translator.calls.append(text)
        raise _Http("blocked")
    cf.GoogleTranslator.translate = _boom
    with pytest.raises(cf.TranslationRateLimited):
        cf.keyword_filter_text("오늘 날씨가 정말 좋네요")
    assert len(translator.calls) == 3


def test_cooldown_skips_retry_wait_after_exhaustion(translator):
    with pytest.raises(cf.TranslationRateLimited):
        cf.keyword_filter_text("오늘 날씨가 정말 좋네요")          # 소진: 3회 호출, 2s+4s 대기
    translator.calls.clear()
    translator.sleeps.clear()
    with pytest.raises(cf.TranslationRateLimited):
        cf.keyword_filter_text("내일 날씨도 좋네요")                # 쿨다운: 호출·대기 없이 즉시 HOLD
    assert translator.calls == [] and translator.sleeps == []
    # 원문 키워드 통과 글은 쿨다운 중에도 영향 없음
    assert cf.keyword_filter_text("화장품 도매 세럼") == "화장품 도매 세럼"


def test_filter_reject_reason_codes():
    assert cf.filter_reject_reason("", "") == "EMPTY_TEXT"
    assert cf.filter_reject_reason("Nguồn sỉ mỹ phẩm Hàn Quốc chính hãng cosmetic, giá tốt", "") == "EXCLUDED_LANGUAGE"
    assert cf.filter_reject_reason("오늘 날씨", "") == "TRANSLATE_EMPTY"
    assert cf.filter_reject_reason("coslife 화장품", "coslife cosmetic") == "CAPTION_BLOCKLIST"
    assert cf.filter_reject_reason("대출 도매", "loan wholesale") == "PRODUCT_EXCLUDE"
    assert cf.filter_reject_reason("오늘 날씨", "the weather is nice") == "KEYWORD_MISS"


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
    # 차단어 때문에 원문 통과 못 해 번역 경로로 넘어가고, 429 면 폐기 대신 HOLD (게시 방향으로는 절대 통과 안 함)
    with pytest.raises(cf.TranslationRateLimited):
        cf.keyword_filter_text(raw)


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
