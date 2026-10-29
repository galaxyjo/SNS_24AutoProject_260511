"""261029 승인 B1 — 051 전용 Persona SEO 캡션 Target Test.

외부 Airtable/Gemini/ImgBB/Meta 호출과 Runtime 상태변경 없이 Mock·Fake로만 검증한다.
PRODUCT Gate(content_filter.py) 변경과 독립이다 — 이 파일은 content_filter 판정에 의존하지 않는다.

검증 목표:
  1. 인자 없는 generate_caption 프롬프트·반환 형식 불변 (041/도매꾹 경로 보존)
  2. 플래그 OFF / 목록 밖 계정(041)은 Persona 조회 0회, 저장값 기존과 동일
  3. 051 Persona 조회 정확성·Fail-closed (inactive/중복/필드 누락/조회 오류)
  4. 한국어 원문 보존 + 영어 게시문, 비영어 문자는 저장 안 함
  5. 라이브 CTA 도매 글 삽입 차단, 승인 CTA 없으면 draft (자동게시 불가)
  6. 숫자·인증 표현 등 원문에 없는 상품정보 생성 시 draft
  7. 실패·재시도(캐시)·원복(플래그 제거) 동작
"""

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import modules.sns.caption_generator as cg
from modules.infra.repository_interface import RepositoryValidationError

ROOT = Path(__file__).resolve().parents[1]

KOREAN_SOURCE = "정품 화장품 도매 공급합니다. 선크림 48개입 박스, 재고 있습니다. 문의 주세요"
GOOD_TAGS = "#kbeauty #koreanskincare #sunscreen #koreancosmetics #wholesale"
GOOD_CAPTION = "Korean sunscreen wholesale is in stock, 48 pieces per box. Great for beauty retailers."
LIVE_CTA = "Live schedule & brand collab by DM"
SEO = "korean cosmetics wholesale, kbeauty wholesale, korean skincare supplier"


# ── 1. generate_caption 프롬프트·반환 형식 ───────────────────────────────────────

def _legacy_prompt(text: str) -> str:
    return (
        "Convert the following Facebook post into an Instagram caption and hashtags.\n\n"
        "Rules:\n"
        "- Caption: Summarize in 2-3 natural English sentences with emojis\n"
        "- Hashtags: 5-10 relevant keywords with #, separated by spaces\n"
        "- Hashtags: Korea-related tags only. Do NOT include other country names (Myanmar, Vietnam, Philippines, China, Japan, etc.)\n"
        "- Output MUST be in English only\n"
        "- Response format (use exactly this format):\n"
        "CAPTION: <caption text>\n"
        "HASHTAGS: <hashtags>\n\n"
        f"Post content:\n{text[:1000]}"
    )


@pytest.fixture
def fake_gemini(monkeypatch):
    captured = {"prompts": []}

    class _Models:
        def generate_content(self, model, contents):
            captured["prompts"].append(contents)
            return types.SimpleNamespace(text="CAPTION: Hello wholesale buyers\nHASHTAGS: #a #b")

    monkeypatch.setattr(cg, "_throttle", lambda: None)
    monkeypatch.setattr(cg, "_get_client", lambda: types.SimpleNamespace(models=_Models()))
    return captured


def test_default_call_prompt_is_byte_identical_to_legacy(fake_gemini):
    result = cg.generate_caption(KOREAN_SOURCE)
    assert fake_gemini["prompts"] == [_legacy_prompt(KOREAN_SOURCE)]
    assert result == ("Hello wholesale buyers", "#a #b")


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_blank_seo_keywords_keep_legacy_prompt(fake_gemini, blank):
    cg.generate_caption(KOREAN_SOURCE, seo_keywords=blank)
    assert fake_gemini["prompts"] == [_legacy_prompt(KOREAN_SOURCE)]


def test_seo_prompt_adds_rules_and_keeps_english_only_rule(fake_gemini):
    caption, hashtags = cg.generate_caption(KOREAN_SOURCE, seo_keywords=SEO)
    prompt = fake_gemini["prompts"][0]
    assert "Output MUST be in English only" in prompt
    assert SEO in prompt
    assert "Never invent prices, MOQ" in prompt
    assert "Do not add any call-to-action line" in prompt
    assert (caption, hashtags) == ("Hello wholesale buyers", "#a #b")


def test_generate_caption_seo_argument_is_keyword_only():
    import inspect
    params = inspect.signature(cg.generate_caption).parameters
    assert list(params) == ["text", "seo_keywords"]
    assert params["seo_keywords"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["seo_keywords"].default == ""


def test_other_callers_still_call_generate_caption_with_text_only():
    exporter = (ROOT / "modules" / "crawlers" / "source_exporter.py").read_text(encoding="utf-8")
    assert 'generate_caption(item.get("title", ""))' in exporter


# ── 2. validate_seo_caption ─────────────────────────────────────────────────────

def test_validate_ok_when_numbers_come_from_source():
    assert cg.validate_seo_caption(GOOD_CAPTION, GOOD_TAGS, KOREAN_SOURCE, SEO) == ("ok", "")


@pytest.mark.parametrize("caption,tags", [
    ("도매 문의 환영합니다", GOOD_TAGS),
    (GOOD_CAPTION, GOOD_TAGS + " #화장품"),
    ("Wholesale Gesundheit für Händler", GOOD_TAGS),
])
def test_validate_rejects_non_english_letters(caption, tags):
    assert cg.validate_seo_caption(caption, tags, KOREAN_SOURCE, SEO) == ("reject", "CAPTION_LANGUAGE_INVALID")


def test_validate_emoji_and_symbols_are_not_language_errors():
    assert cg.validate_seo_caption("Wholesale ✨ 48 per box 🇰🇷", GOOD_TAGS, KOREAN_SOURCE, SEO)[0] == "ok"


@pytest.mark.parametrize("tags", ["#a #b", "#1 #2 #3 #4 #5 #6 #7 #8 #9 #10 #11"])
def test_validate_hashtag_count_out_of_range_is_draft(tags):
    assert cg.validate_seo_caption(GOOD_CAPTION, tags, KOREAN_SOURCE, SEO) == ("draft", "CAPTION_HASHTAG_COUNT")


def test_validate_number_not_in_source_is_draft_not_reject():
    status, code = cg.validate_seo_caption("MOQ 100 boxes at 3,000 won", GOOD_TAGS, KOREAN_SOURCE, SEO)
    assert (status, code) == ("draft", "CAPTION_FACT_UNVERIFIED")


def test_validate_number_format_difference_is_accepted():
    source = "가격 2,780원 박스당 48매"
    assert cg.validate_seo_caption("Priced at 2780 won, 48 sheets per box", GOOD_TAGS, source, SEO)[0] == "ok"


def test_validate_unverified_claim_word_is_draft_but_source_claim_is_ok():
    status, code = cg.validate_seo_caption("FDA certified sunscreen wholesale", GOOD_TAGS, KOREAN_SOURCE, SEO)
    assert (status, code) == ("draft", "CAPTION_CLAIM_UNVERIFIED")
    assert cg.validate_seo_caption("FDA listed sunscreen wholesale", GOOD_TAGS, "FDA 등록 선크림 도매", SEO)[0] == "ok"


def test_validate_healthy_is_not_flagged_as_heal():
    assert cg.validate_seo_caption("Healthy skin sunscreen wholesale", GOOD_TAGS, KOREAN_SOURCE, SEO)[0] == "ok"


def test_validate_keyword_stuffing_is_draft():
    caption = "kbeauty wholesale kbeauty wholesale kbeauty wholesale for buyers"
    assert cg.validate_seo_caption(caption, GOOD_TAGS, KOREAN_SOURCE, SEO) == ("draft", "CAPTION_KEYWORD_STUFFING")


def test_validate_empty_seo_keywords_skips_stuffing_check():
    caption = "kbeauty wholesale kbeauty wholesale kbeauty wholesale for buyers"
    assert cg.validate_seo_caption(caption, GOOD_TAGS, KOREAN_SOURCE, "")[0] == "ok"


# ── 3. save_to_airtable (051 전용 경로) ─────────────────────────────────────────

def _import_facebook_crawler(monkeypatch):
    bridge_module = types.ModuleType("modules.common.airtable_bridge")
    bridge_module.get_table = lambda name: None
    monkeypatch.setitem(sys.modules, "modules.common.airtable_bridge", bridge_module)
    from modules.sns import facebook_crawler
    return facebook_crawler


class _Repo:
    def __init__(self, persona=None, persona_error=None):
        self.persona = persona
        self.persona_error = persona_error
        self.persona_calls = 0
        self.saved = []

    def validate_instagram_post_context(self, account, classification, canary=""):
        return {"account_code": account}

    def exists_post_by_image_url(self, image_url):
        return False

    def get_active_persona_by_account_code_v2(self, account_code):
        self.persona_calls += 1
        if self.persona_error:
            raise self.persona_error
        return self.persona

    def save_instagram_post(self, payload):
        self.saved.append(payload)
        return "rec-post"


PERSONA_050 = {
    "persona_code": "PER-050", "seo_keywords": SEO, "conversion_cta": LIVE_CTA,
    "language": "en", "tone_style": "x",
}


@pytest.fixture
def crawler(monkeypatch, tmp_path):
    fc = _import_facebook_crawler(monkeypatch)
    fc._CAPTION_SEO_CACHE.clear()
    monkeypatch.delenv("CAPTION_PERSONA_SEO_ACCOUNTS", raising=False)
    cta_file = tmp_path / "approved_caption_cta.json"
    cta_file.write_text(json.dumps({"PER-050": None}), encoding="utf-8")
    monkeypatch.setattr(fc, "_APPROVED_CTA_PATH", cta_file)
    monkeypatch.setattr(fc, "upload_to_imgbb", lambda url: {"success": True, "public_url": "https://i.ibb.co/x/y.jpg"})
    fc._test_cta_file = cta_file
    yield fc
    fc._CAPTION_SEO_CACHE.clear()


def _install(monkeypatch, fc, repo, *, caption=GOOD_CAPTION, tags=GOOD_TAGS):
    calls = []

    def _gen(*args, **kwargs):
        calls.append((args, kwargs))
        return caption, tags

    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
    monkeypatch.setattr(fc, "generate_caption", _gen)
    return calls


def _save(fc, account, *, text=KOREAN_SOURCE, original=None):
    return fc.save_to_airtable(
        "https://scontent.xx.fbcdn.net/v/t39/item.jpg",
        "https://facebook.example/groups/1",
        text=text,
        original_text=original,
        target_publish_account_code_ref=account,
        data_classification="production",
    )


def test_flag_unset_uses_legacy_call_and_ready_status(monkeypatch, crawler):
    repo = _Repo(persona=PERSONA_050)
    calls = _install(monkeypatch, crawler, repo)
    assert _save(crawler, "IDN-000041") is True
    assert calls == [((KOREAN_SOURCE,), {})]
    assert repo.persona_calls == 0
    payload = repo.saved[0]
    assert payload["post_status"] == "ready"
    assert payload["caption"] == GOOD_CAPTION and payload["hashtag"] == GOOD_TAGS


def test_041_unchanged_even_when_flag_lists_only_051(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    repo = _Repo(persona=PERSONA_050)
    calls = _install(monkeypatch, crawler, repo)
    assert _save(crawler, "IDN-000041") is True
    assert calls == [((KOREAN_SOURCE,), {})]
    assert repo.persona_calls == 0
    assert repo.saved[0]["post_status"] == "ready"


def test_051_without_approved_cta_is_draft_and_never_uses_live_cta(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    repo = _Repo(persona=PERSONA_050)
    calls = _install(monkeypatch, crawler, repo)
    assert _save(crawler, "IDN-000051") is True
    assert calls == [((KOREAN_SOURCE,), {"seo_keywords": SEO})]
    payload = repo.saved[0]
    assert payload["post_status"] == "draft"
    assert payload["post_status"] != "ready"
    assert LIVE_CTA not in payload["caption"]
    assert payload["caption"] == GOOD_CAPTION


def test_051_approved_cta_is_appended_exactly_once_and_ready(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    crawler._test_cta_file.write_text(json.dumps({"PER-050": "DM us for wholesale inquiries."}), encoding="utf-8")
    repo = _Repo(persona=PERSONA_050)
    _install(monkeypatch, crawler, repo)
    assert _save(crawler, "IDN-000051") is True
    payload = repo.saved[0]
    assert payload["post_status"] == "ready"
    assert payload["caption"] == GOOD_CAPTION + "\nDM us for wholesale inquiries."
    assert payload["caption"].count("DM us for wholesale inquiries.") == 1
    assert LIVE_CTA not in payload["caption"]


@pytest.mark.parametrize("bad_cta", [
    "도매 문의는 DM 주세요",
    "DM us for MOQ 100 boxes",
    "DM us, lowest price guaranteed",
    "Contact us at www.example.com",
    "Send us a message for wholesale inquiries.",
    "DM us " + "x" * 200,
    "",
])
def test_invalid_approved_cta_is_treated_as_unapproved(monkeypatch, crawler, bad_cta):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    crawler._test_cta_file.write_text(json.dumps({"PER-050": bad_cta}), encoding="utf-8")
    repo = _Repo(persona=PERSONA_050)
    _install(monkeypatch, crawler, repo)
    assert _save(crawler, "IDN-000051") is True
    assert repo.saved[0]["post_status"] == "draft"
    assert bad_cta.strip() == "" or bad_cta not in repo.saved[0]["caption"]


@pytest.mark.parametrize("persona,error,expected_code", [
    (None, None, "CAPTION_PERSONA_NOT_FOUND"),
    (None, RepositoryValidationError("2건 이상"), "CAPTION_PERSONA_AMBIGUOUS"),
    ({"persona_code": "PER-050", "seo_keywords": ""}, None, "CAPTION_PERSONA_FIELD_MISSING"),
    ({"persona_code": "", "seo_keywords": SEO}, None, "CAPTION_PERSONA_FIELD_MISSING"),
    (None, RuntimeError("network"), "CAPTION_PERSONA_LOOKUP_ERROR"),
])
def test_persona_problem_fails_closed_without_gemini_or_save(monkeypatch, crawler, persona, error, expected_code):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    repo = _Repo(persona=persona, persona_error=error)
    calls = _install(monkeypatch, crawler, repo)
    assert _save(crawler, "IDN-000051") is False
    assert calls == []
    assert repo.saved == []
    ctx, code = crawler._resolve_caption_seo(repo, "IDN-000051")
    assert ctx is None and code == expected_code


def test_persona_lookup_is_cached_and_failure_expires(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    repo = _Repo(persona=PERSONA_050)
    _install(monkeypatch, crawler, repo)
    _save(crawler, "IDN-000051")
    _save(crawler, "IDN-000051")
    assert repo.persona_calls == 1

    crawler._CAPTION_SEO_CACHE.clear()
    failing = _Repo(persona=None)
    _install(monkeypatch, crawler, failing)
    now = {"t": 1000.0}
    monkeypatch.setattr(crawler.time, "time", lambda: now["t"])
    assert _save(crawler, "IDN-000051") is False
    assert _save(crawler, "IDN-000051") is False
    assert failing.persona_calls == 1
    now["t"] += crawler._CAPTION_SEO_FAIL_TTL_SEC + 1
    failing.persona = PERSONA_050
    assert _save(crawler, "IDN-000051") is True
    assert failing.persona_calls == 2


def test_korean_original_is_preserved_and_caption_is_english(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    repo = _Repo(persona=PERSONA_050)
    _install(monkeypatch, crawler, repo)
    assert _save(crawler, "IDN-000051", original=KOREAN_SOURCE + " 연락처 포함") is True
    payload = repo.saved[0]
    assert payload["original_text"] == KOREAN_SOURCE + " 연락처 포함"
    assert payload["converted_text"] == KOREAN_SOURCE
    assert all(ord(ch) < 128 or not ch.isalpha() for ch in payload["caption"] + payload["hashtag"])


def test_hangul_in_generated_caption_is_not_saved(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    repo = _Repo(persona=PERSONA_050)
    _install(monkeypatch, crawler, repo, caption="도매 문의 환영")
    assert _save(crawler, "IDN-000051") is False
    assert repo.saved == []


def test_fact_not_in_source_becomes_draft_even_with_approved_cta(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    crawler._test_cta_file.write_text(json.dumps({"PER-050": "DM us for wholesale inquiries."}), encoding="utf-8")
    repo = _Repo(persona=PERSONA_050)
    _install(monkeypatch, crawler, repo, caption="Minimum order 500 boxes, wholesale sunscreen")
    assert _save(crawler, "IDN-000051") is True
    assert repo.saved[0]["post_status"] == "draft"


def test_empty_caption_keeps_existing_failed_status(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    repo = _Repo(persona=PERSONA_050)
    _install(monkeypatch, crawler, repo, caption="", tags="")
    assert _save(crawler, "IDN-000051") is True
    assert repo.saved[0]["post_status"] == "failed"


def test_removing_flag_restores_legacy_behavior(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    repo = _Repo(persona=PERSONA_050)
    calls = _install(monkeypatch, crawler, repo)
    _save(crawler, "IDN-000051")
    monkeypatch.delenv("CAPTION_PERSONA_SEO_ACCOUNTS")
    repo2 = _Repo(persona=PERSONA_050)
    calls2 = _install(monkeypatch, crawler, repo2)
    assert _save(crawler, "IDN-000051") is True
    assert calls2 == [((KOREAN_SOURCE,), {})]
    assert repo2.persona_calls == 0
    assert repo2.saved[0]["post_status"] == "ready"


def test_upload_failure_saves_nothing_so_next_crawl_retries(monkeypatch, crawler):
    monkeypatch.setenv("CAPTION_PERSONA_SEO_ACCOUNTS", "IDN-000051")
    monkeypatch.setattr(crawler, "upload_to_imgbb", lambda url: {"success": False, "error": "x"})
    repo = _Repo(persona=PERSONA_050)
    _install(monkeypatch, crawler, repo)
    assert _save(crawler, "IDN-000051") is False
    assert repo.saved == []


def test_live_cta_is_never_read_from_persona_in_source():
    source = (ROOT / "modules" / "sns" / "facebook_crawler.py").read_text(encoding="utf-8")
    start = source.index("def _resolve_caption_seo")
    end = source.index("def save_to_airtable")
    import re
    body = source[start:end]
    # 주석·docstring의 단어가 아니라 실제 키 접근(.get("conversion_cta") / ["conversion_cta"])만 금지한다.
    assert not re.search(r"""get\(\s*["']conversion_cta["']""", body)
    assert not re.search(r"""\[\s*["']conversion_cta["']\s*\]""", body)


# ── 4. 상류 필터 순서·draft 자동게시 불가 ───────────────────────────────────────

def test_run_applies_product_filter_before_saving():
    source = (ROOT / "modules" / "sns" / "facebook_crawler.py").read_text(encoding="utf-8")
    run_body = source[source.index("def run(\n"):]
    assert run_body.index("passes_keyword_filter(") < run_body.index("save_to_airtable(")


def test_pending_post_query_selects_only_ready_so_draft_is_never_published(monkeypatch):
    from modules.infra import airtable_repository as ar
    repo = ar.AirtableRepository()
    seen = {}

    def _get(url, headers=None, params=None, timeout=None):
        seen["formula"] = (params or {}).get("filterByFormula", "")
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"records": []}
        return response

    monkeypatch.setattr(ar.requests, "get", _get)
    monkeypatch.setattr(ar, "log_api_call", lambda *a, **k: None)
    assert repo.fetch_pending_posts(limit=5) == []
    assert "'ready'" in seen["formula"]
    assert "draft" not in seen["formula"]
