"""261024 STEP 2(Codex 3차) — 공통 엔진 Canary(IDN-000025) 게시·복구 전체 경로 Target Test.

Persona Fail-closed, single·carousel 슬롯 게시, 결과 불명·기록 실패 원장, reconcile 계정 불일치 HOLD,
Hero·Template 카드 브랜드를 확인한다. 외부 호출은 전부 Fake(tests/conftest가 외부 통신도 차단)."""

import dataclasses
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import launcher.main as lm  # noqa: E402
import modules.sns.content_package_builder as cpb  # noqa: E402
from modules.sns.carousel_content_builder import CarouselContent, CarouselResult, Slide  # noqa: E402

CANARY = "IDN-000025"
CANARY_IG = "17841461833534417"
CANARY_ACCOUNT = {"account_code": CANARY, "api_provider": "facebook_login", "ig_user_id": CANARY_IG,
                  "credential_key": "IDN_000025", "automation_enabled": True}
URLS = ["https://i.ibb.co/c1.jpg", "https://i.ibb.co/c2.jpg", "https://i.ibb.co/c3.jpg"]
KO_CAPTION = "아마존 SP-API로 쇼핑몰 상품 등록을 자동화하는 방법을 정리했습니다"


def _write(vault, cid, fields):
    (vault / "content").mkdir(parents=True, exist_ok=True)
    md_path, _ = cpb._content_paths(cid, vault)
    md_path.write_text(cpb._render_frontmatter(fields) + "\nc\n", encoding="utf-8")


def _v3(cid, n=3):
    return {"content_id": cid, "caption": KO_CAPTION, "hashtags": "#AI", "idempotency_version": 3,
            "post_format": "carousel", "carousel_required": True, "slide_count": n,
            "slide_texts": [f"s{i}" for i in range(n)], "slide_image_paths": cpb.carousel_slide_image_paths(cid, n),
            "carousel_image_urls": URLS[:n]}


def _post(cid, image_url=URLS[0]):
    return {"post_id": "recC25", "image_url": image_url, "caption": KO_CAPTION, "hashtag": "#AI",
            "account_code_ref": CANARY, "ig_media_id": "", "data_classification": "production",
            "canary_run_id": "", "post_status": "ready", "content_id": cid, "source_url": "https://src.example/a"}


@pytest.fixture
def env(monkeypatch, tmp_path):
    import modules.common.canary_classification as cc
    import modules.sns.research_to_topic_adapter as adapter

    shared = tmp_path / "vault"
    canary_vault = tmp_path / "vault" / "accounts" / CANARY
    monkeypatch.setattr(cpb, "DEFAULT_VAULT_ROOT", shared)
    monkeypatch.setitem(lm.CONTENT_ACCOUNTS, CANARY,
                        dataclasses.replace(lm.CONTENT_ACCOUNTS[CANARY], vault_root=canary_vault))
    monkeypatch.setenv("IDN_000025_SLOT_SCHEDULE_ENABLED", "true")
    monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
    monkeypatch.setenv("IDN_000025_INSTA_IG_USER_ID", CANARY_IG)
    monkeypatch.setenv("IDN_000025_INSTA_ACCESS_TOKEN", "canary-ig-token")
    monkeypatch.delenv("IDN_000025_BINDING_ADAPTER_ENABLED", raising=False)
    monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "aijomoojin-key")
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    monkeypatch.setattr(cc, "validate_publication_candidate", lambda *a, **k: None)
    monkeypatch.setattr(lm, "_PUBLISH_PENDING_PATH", tmp_path / "pending.json")
    monkeypatch.setattr(adapter, "_get_client", lambda: pytest.fail("aijomoojin 전용 Client 사용 금지"))
    monkeypatch.setattr(lm, "fetch_media_summary",
                        lambda *a, **k: {"id": "M1", "media_type": "CAROUSEL_ALBUM", "children": 3})
    slack = []
    monkeypatch.setattr(lm, "_slack", lambda m: slack.append(m))

    keys, safety_clients = [], []

    class _FakeClient:
        def __init__(self, api_key=None):
            keys.append(api_key)

    monkeypatch.setattr("google.genai.Client", _FakeClient)

    def _safety(caption, client=None, **k):
        safety_clients.append(client)
        return "SAFE", ""

    monkeypatch.setattr("modules.sns.caption_generator.check_caption_safety", _safety)
    calls = {"fetch": [], "claim": [], "mark": [], "persona": []}
    state = {"persona": {"persona_code": "PER-024", "language": "ko"}, "mark_raises": False}

    class _Repo:
        def __init__(self, posts):
            self.posts = posts

        def fetch_pending_posts_for_account(self, code, limit=10):
            calls["fetch"].append(code)
            return self.posts

        def get_publish_account(self, code):
            assert code == CANARY
            return CANARY_ACCOUNT

        def get_active_persona_by_account_code_v2(self, code):
            calls["persona"].append(code)
            return state["persona"]

        def claim_post_for_upload(self, pid):
            calls["claim"].append(pid)
            return True

        def mark_post_result(self, pid, result):
            if state["mark_raises"]:
                raise RuntimeError("airtable down")
            calls["mark"].append((pid, dict(result)))

    def run(posts):
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _Repo(posts))
        lm._job_aijomoojin_scheduled_post(account_code=CANARY)

    def ledger():
        p = tmp_path / "pending.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    return SimpleNamespace(calls=calls, state=state, slack=slack, keys=keys, safety_clients=safety_clients,
                           run=run, ledger=ledger, shared=shared, canary_vault=canary_vault)


class TestPersonaFailClosed:
    def test_publish_gate_off_blocks_before_airtable(self, monkeypatch, env):
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))
        lm._job_aijomoojin_scheduled_post(account_code=CANARY)

    def test_binding_flag_on_blocks_before_airtable(self, monkeypatch, env):
        monkeypatch.setenv("IDN_000025_BINDING_ADAPTER_ENABLED", "true")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))
        lm._job_aijomoojin_scheduled_post(account_code=CANARY)

    def test_persona_mismatch_rejects_without_claim(self, monkeypatch, env):
        _write(env.canary_vault, "c25v2", {"content_id": "c25v2", "caption": KO_CAPTION, "idempotency_version": 2})
        env.state["persona"] = {"persona_code": "PER-002", "language": "ko"}
        monkeypatch.setattr(lm, "publish_single", lambda *a, **k: pytest.fail("게시 금지"))
        env.run([_post("c25v2")])
        assert env.calls["claim"] == []
        assert env.calls["mark"][0][1]["status"] == "rejected"
        assert "PERSONA_MISMATCH" in env.calls["mark"][0][1]["error_code"]

    def test_aijomoojin_gate_off_unchanged(self, monkeypatch, env):
        """036은 Gate OFF여도 기존처럼 진행한다(이번 Fail-closed는 새 계정 전용)."""
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        asked = []

        class _Repo:
            def fetch_pending_posts_for_account(self, code, limit=10):
                asked.append(code)
                return []

        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _Repo())
        lm._job_aijomoojin_scheduled_post()
        assert asked == ["IDN-000036"]


class TestSinglePath:
    def test_single_posted_with_canary_credentials(self, monkeypatch, env):
        _write(env.canary_vault, "c25v2", {"content_id": "c25v2", "caption": KO_CAPTION, "idempotency_version": 2})
        used = []
        monkeypatch.setattr(lm, "publish_single", lambda rid, url, cap, token, ig, api_host="": (
            used.append((rid, url, token, ig, api_host)) or {"ok": True, "ig_media_id": "IGM25"}))
        monkeypatch.setattr(lm, "publish_carousel", lambda *a, **k: pytest.fail("carousel 금지"))

        env.run([_post("c25v2", image_url="https://i.ibb.co/single25.jpg")])

        assert env.calls["fetch"] == [CANARY] and env.calls["persona"] == [CANARY]
        assert env.keys == ["canary-key"] and len(env.safety_clients) == 1       # 025 전용 Safety Client
        assert used == [("recC25", "https://i.ibb.co/single25.jpg", "canary-ig-token", CANARY_IG,
                         "graph.facebook.com")]
        assert env.calls["claim"] == ["recC25"] and env.calls["mark"][0][1]["status"] == "posted"

    def test_outcome_unknown_ledger_has_canary_account(self, monkeypatch, env):
        _write(env.canary_vault, "c25v2", {"content_id": "c25v2", "caption": KO_CAPTION, "idempotency_version": 2})
        monkeypatch.setattr(lm, "publish_single", lambda *a, **k: {"ok": False, "outcome_unknown": True,
                                                                  "creation_id": "CR25"})
        env.run([_post("c25v2")])
        entry = env.ledger()["recC25"]
        assert entry["kind"] == "outcome_unknown" and entry["creation_id"] == "CR25"
        assert entry["account_code_ref"] == CANARY and entry["credential_key"] == "IDN_000025"
        assert env.calls["mark"] == []

    def test_posted_unrecorded_ledger(self, monkeypatch, env):
        _write(env.canary_vault, "c25v2", {"content_id": "c25v2", "caption": KO_CAPTION, "idempotency_version": 2})
        monkeypatch.setattr(lm, "publish_single", lambda *a, **k: {"ok": True, "ig_media_id": "IGM25"})
        env.state["mark_raises"] = True
        env.run([_post("c25v2")])
        entry = env.ledger()["recC25"]
        assert entry["kind"] == "posted_unrecorded" and entry["ig_media_id"] == "IGM25"
        assert entry["account_code_ref"] == CANARY

    def test_failed_unrecorded_ledger(self, monkeypatch, env):
        _write(env.canary_vault, "c25v2", {"content_id": "c25v2", "caption": KO_CAPTION, "idempotency_version": 2})
        monkeypatch.setattr(lm, "publish_single", lambda *a, **k: {"ok": False, "error": "x"})
        env.state["mark_raises"] = True
        env.run([_post("c25v2")])
        entry = env.ledger()["recC25"]
        assert entry["kind"] == "failed_unrecorded" and entry["account_code_ref"] == CANARY


class TestCarouselPath:
    def test_carousel_posted_from_canary_vault_and_in_flight_cleared(self, monkeypatch, env):
        _write(env.canary_vault, "c25v3", _v3("c25v3"))
        seen = {}

        def _fake_carousel(rid, urls, caption, token, ig_user_id, api_host="", *, on_parent_created=None):
            assert on_parent_created("PARENT25") is True
            seen["ledger"] = env.ledger()
            seen["args"] = (rid, urls, token, ig_user_id, api_host)
            return {"ok": True, "ig_media_id": "IGM25C", "creation_id": "PARENT25"}

        monkeypatch.setattr(lm, "publish_carousel", _fake_carousel)
        monkeypatch.setattr(lm, "publish_single", lambda *a, **k: pytest.fail("single 금지"))

        env.run([_post("c25v3")])

        assert seen["args"] == ("recC25", URLS, "canary-ig-token", CANARY_IG, "graph.facebook.com")
        entry = seen["ledger"]["recC25"]
        assert entry["kind"] == "in_flight" and entry["account_code_ref"] == CANARY
        assert entry["credential_key"] == "IDN_000025"
        assert env.calls["mark"][0][1]["status"] == "posted"
        assert env.ledger() == {}                                       # 확정 후 이 rid만 정리

    def test_carousel_in_shared_vault_is_not_used(self, monkeypatch, env):
        _write(env.shared, "c25v3", _v3("c25v3"))                     # 공용(036) vault에만 있음
        monkeypatch.setattr(lm, "publish_carousel", lambda *a, **k: pytest.fail("게시 금지"))
        monkeypatch.setattr(lm, "publish_single", lambda *a, **k: pytest.fail("게시 금지"))
        env.run([_post("c25v3")])
        assert env.calls["claim"] == [] and env.slack and env.slack[-1].startswith("[HOLD]")

    def test_in_flight_clear_keeps_other_rid(self, monkeypatch, env):
        lm._record_publish_pending("recOTHER", "outcome_unknown", creation_id="X", credential_key="AI",
                                   api_host="graph.instagram.com", caption="c", account_code_ref="IDN-000036")
        _write(env.canary_vault, "c25v3", _v3("c25v3"))
        monkeypatch.setattr(lm, "publish_carousel", lambda rid, urls, cap, tok, ig, api_host="", *,
                            on_parent_created=None: on_parent_created("P") and {"ok": True, "ig_media_id": "M"})
        env.run([_post("c25v3")])
        assert list(env.ledger()) == ["recOTHER"]


class TestReconcileAccountGuard:
    def _entry(self):
        old = (datetime.now() - timedelta(minutes=lm._RECONCILE_MIN_AGE_MIN + 5)).strftime(lm._RECONCILE_TS_FMT)
        return {"kind": "posted_unrecorded", "ig_media_id": "IGM25", "account_code_ref": CANARY, "at": old,
                "alerted": False}

    def _run(self, monkeypatch, tmp_path, airtable_state):
        monkeypatch.setattr(lm, "_PUBLISH_PENDING_PATH", tmp_path / "pending.json")
        (tmp_path / "pending.json").write_text(json.dumps({"recC25": self._entry()}), encoding="utf-8")
        monkeypatch.setattr(lm, "_fetch_post_state", lambda rid: airtable_state)
        marks, slack = [], []

        class _Repo:
            def mark_post_result(self, pid, result):
                marks.append((pid, dict(result)))

        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _Repo())
        monkeypatch.setattr(lm, "_slack", lambda m: slack.append(m))
        lm._job_publish_reconcile()
        return marks, slack, json.loads((tmp_path / "pending.json").read_text(encoding="utf-8"))

    def test_account_mismatch_holds(self, monkeypatch, tmp_path):
        marks, slack, ledger = self._run(monkeypatch, tmp_path, ("uploading", "IDN-000036"))
        assert marks == [] and "recC25" in ledger and len(slack) == 1

    def test_matching_account_resolves(self, monkeypatch, tmp_path):
        marks, _, ledger = self._run(monkeypatch, tmp_path, ("uploading", CANARY))
        assert marks[0][0] == "recC25" and marks[0][1]["status"] == "posted" and ledger == {}


class TestCardBrand:
    def test_hero_card_uses_given_brand(self, monkeypatch):
        from modules.sns.hero_card_content_builder import HeroBlockText, HeroCardTextContent, HeroCardTextResult
        text = HeroCardTextContent(headline="h", subheadline="s",
                                   blocks=tuple(HeroBlockText("t", "d") for _ in range(3)), tagline="g",
                                   content_fingerprint="f")
        monkeypatch.setattr(cpb, "generate_hero_card_content", lambda *a, **k: HeroCardTextResult(True, text))
        monkeypatch.setattr(cpb, "build_background_only_prompt",
                            lambda brief: SimpleNamespace(prompt_text="p", negative_prompt=""))
        monkeypatch.setattr(cpb, "generate_image", lambda *a, **k: SimpleNamespace(success=True, image_bytes=b"bg"))
        brands = []
        monkeypatch.setattr(cpb, "render_hero_card", lambda content: brands.append(content.brand) or b"png")
        topic = SimpleNamespace(title="T")
        assert cpb._build_hero_card_image(topic, None, brand_handle="@rhrl201010") == b"png"
        cpb._build_hero_card_image(topic, None)
        assert brands == ["@rhrl201010", "@aijomoojin"]

    def test_template_carousel_cover_and_body_use_given_brand(self, monkeypatch, tmp_path):
        slides = tuple(Slide(index=i + 1, role="r", text=f"슬라이드 {i + 1}") for i in range(3))
        content = CarouselContent(slot_role="REACH", template_type="HOOK_IMPACT", source_section_id="12.4",
                                  source_title="T", source_url="https://src.example/a", slides=slides,
                                  caption="캡션", hashtags=("#AI",), content_fingerprint="fp")
        monkeypatch.setattr(cpb, "generate_carousel_content", lambda *a, **k: CarouselResult(True, content))
        hero_brands, body_brands = [], []
        monkeypatch.setattr(cpb, "_build_hero_card_image",
                            lambda *a, brand_handle="", **k: hero_brands.append(brand_handle) or b"cover")
        monkeypatch.setattr(cpb, "render_card", lambda c: body_brands.append(c.brand) or b"body")
        topic = SimpleNamespace(topic_id="12.4", title="T", source_url="https://src.example/a",
                                core_message="m", prohibited_expression="", source_published_at="")
        (tmp_path / "content").mkdir()
        (tmp_path / "images").mkdir()
        result =cpb._create_carousel_package(topic, "c25t", tmp_path, 3, "", "REACH", "HOOK_IMPACT",
                                              brand_handle="@rhrl201010")
        assert result.success is True
        assert hero_brands == ["@rhrl201010"] and body_brands == ["@rhrl201010", "@rhrl201010"]


class TestCoverLogoCheckAndSavedCaption022:
    """261026 STEP 5-B — 표지 배경 글자·로고 판독(기존 image_text_checker 재사용)과 저장 캡션 줄바꿈."""

    def _hero_env(self, monkeypatch, check_result):
        from modules.sns.hero_card_content_builder import HeroBlockText, HeroCardTextContent, HeroCardTextResult
        text = HeroCardTextContent(headline="h", subheadline="s",
                                   blocks=tuple(HeroBlockText("t", "d") for _ in range(4)), tagline="g",
                                   content_fingerprint="f")
        monkeypatch.setattr(cpb, "generate_hero_card_content", lambda *a, **k: HeroCardTextResult(True, text))
        monkeypatch.setattr(cpb, "build_background_only_prompt",
                            lambda brief: SimpleNamespace(prompt_text="p", negative_prompt=""))
        monkeypatch.setattr(cpb, "generate_image", lambda *a, **k: SimpleNamespace(success=True, image_bytes=b"bg"))
        calls, rendered = [], []
        monkeypatch.setattr(cpb, "check_images_for_text_and_logo",
                            lambda images, **k: calls.append(images) or check_result)
        monkeypatch.setattr(cpb, "render_hero_card", lambda content: rendered.append(1) or b"png")
        return calls, rendered

    @pytest.mark.parametrize("has_text,has_logo", [(False, True), (True, False)])
    def test_logo_or_text_in_background_blocks_cover(self, monkeypatch, has_text, has_logo):
        from modules.sns.image_text_checker import ImageCheck, ImageCheckResult
        calls, rendered = self._hero_env(monkeypatch, ImageCheckResult(True, (ImageCheck(1, has_text, has_logo),)))
        topic = SimpleNamespace(title="T")
        assert cpb._build_hero_card_image(topic, None, client=object(), logo_check=True) is None
        assert calls == [[b"bg"]] and rendered == []

    def test_check_failure_blocks_cover(self, monkeypatch):
        from modules.sns.image_text_checker import ImageCheckResult
        calls, rendered = self._hero_env(monkeypatch, ImageCheckResult(False, error_code="CHECK_CALL_FAILED"))
        assert cpb._build_hero_card_image(SimpleNamespace(title="T"), None, client=object(), logo_check=True) is None
        assert rendered == []

    def test_clean_background_renders_cover(self, monkeypatch):
        from modules.sns.image_text_checker import ImageCheck, ImageCheckResult
        calls, rendered = self._hero_env(monkeypatch, ImageCheckResult(True, (ImageCheck(1, False, False),)))
        assert cpb._build_hero_card_image(SimpleNamespace(title="T"), None, client=object(), logo_check=True) == b"png"
        assert len(calls) == 1

    def test_default_path_has_no_logo_check(self, monkeypatch):
        """036 등 기존 호출(logo_check 기본 False)은 판독을 부르지 않는다."""
        from modules.sns.image_text_checker import ImageCheckResult
        calls, rendered = self._hero_env(monkeypatch, ImageCheckResult(False, error_code="X"))
        assert cpb._build_hero_card_image(SimpleNamespace(title="T"), None) == b"png" and calls == []

    @pytest.mark.parametrize("persona_code,expected", [("PER-021", True), ("", False)])
    def test_carousel_turns_on_logo_check_only_for_persona_accounts(self, monkeypatch, tmp_path, persona_code, expected):
        from modules.sns.carousel_content_builder import _separate_account_cta_line
        cta = "AI 뉴스 요약 자동화 문의는 DM"
        caption = _separate_account_cta_line({"caption": "IBM 음성 AI 3종 정보입니다. " + cta}, cta)["caption"]
        slides = tuple(Slide(index=i + 1, role="r", text=f"슬라이드 {i + 1}") for i in range(3))
        content = CarouselContent(slot_role="REACH", template_type="HOOK_IMPACT", source_section_id="1.1",
                                  source_title="T", source_url="https://src.example/a", slides=slides,
                                  caption=caption, hashtags=("#IBM",), content_fingerprint="fp")
        monkeypatch.setattr(cpb, "generate_carousel_content", lambda *a, **k: CarouselResult(True, content))
        seen = []
        monkeypatch.setattr(cpb, "_build_hero_card_image",
                            lambda *a, logo_check=False, **k: seen.append(logo_check) or b"cover")
        monkeypatch.setattr(cpb, "render_card", lambda c: b"body")
        topic = SimpleNamespace(topic_id="1.1", title="T", source_url="https://src.example/a",
                                core_message="m", prohibited_expression="", source_published_at="")
        (tmp_path / "content").mkdir()
        (tmp_path / "images").mkdir()
        result = cpb._create_carousel_package(topic, "c22t", tmp_path, 3, "", "REACH", "HOOK_IMPACT",
                                              persona_code=persona_code)
        assert result.success is True and seen == [expected]
        saved = (tmp_path / "content" / "c22t.md").read_text(encoding="utf-8")
        assert saved.rstrip().endswith("IBM 음성 AI 3종 정보입니다.\n\n" + cta)    # 저장본에서 CTA가 독립 마지막 줄


class TestPersonaCoverBackgroundPrompt022:
    """261026 STEP 5-B — Persona 캐러셀 표지 배경은 Sourcebook '이미지 개념'만 쓰고(회사·제품명·숫자·말투 없음),
    036 기존 배경 프롬프트 경로는 그대로다. 판독 차단 배경은 검토 폴더에만 보존한다."""

    SB_022 = Path(__file__).resolve().parents[1] / "docs" / "design" / "SNS_AI_NEWS_SOURCEBOOK_IDN022_261026.md"
    BRAND_TERMS = ("IBM", "Granite", "granite", "Hugging", "Apache", "GitHub", "Copilot", "Gemma", "Qwen", "해외 이슈")

    def _topics(self):
        from modules.sns.source_selector import parse_sourcebook
        return parse_sourcebook(self.SB_022)

    def test_022_topics_have_unbranded_concepts(self):
        topics = self._topics()
        assert len(topics) == 3 and all(t.image_concept for t in topics)
        for t in topics:
            assert not any(ch.isdigit() for ch in t.image_concept)
            assert not any(term in t.image_concept for term in self.BRAND_TERMS)

    def test_shared_sourcebook_has_no_image_concepts(self):
        from modules.sns.source_selector import parse_sourcebook
        assert all(t.image_concept == "" for t in parse_sourcebook())

    def test_022_background_prompt_has_no_brand_number_or_tone(self):
        from modules.sns.visual_brief import build_concept_background_prompt
        topic = next(t for t in self._topics() if t.topic_id == "1.1")
        prompt = build_concept_background_prompt(topic.image_concept)
        assert "sound waves" in prompt.prompt_text and "microphone" in prompt.prompt_text
        assert not any(term in prompt.prompt_text for term in self.BRAND_TERMS)
        assert not any(ch.isdigit() for ch in prompt.prompt_text)
        assert "Do not draw any company logo" in prompt.prompt_text and prompt.negative_prompt == ""
        assert "뉴스 정리자" not in prompt.prompt_text
        assert build_concept_background_prompt("  ") is None

    def _hero_env(self, monkeypatch, check_ok=True):
        from modules.sns.hero_card_content_builder import HeroBlockText, HeroCardTextContent, HeroCardTextResult
        from modules.sns.image_text_checker import ImageCheck, ImageCheckResult
        text = HeroCardTextContent(headline="h", subheadline="s",
                                   blocks=tuple(HeroBlockText("t", "d") for _ in range(4)), tagline="g",
                                   content_fingerprint="f")
        monkeypatch.setattr(cpb, "generate_hero_card_content", lambda *a, **k: HeroCardTextResult(True, text))
        prompts = []
        monkeypatch.setattr(cpb, "generate_image",
                            lambda p, n="": prompts.append(p) or SimpleNamespace(success=True, image_bytes=b"bgbytes"))
        monkeypatch.setattr(cpb, "check_images_for_text_and_logo",
                            lambda images, **k: ImageCheckResult(True, (ImageCheck(1, not check_ok, False),)))
        monkeypatch.setattr(cpb, "render_hero_card", lambda content: b"png")
        return prompts

    def test_036_default_path_still_uses_core_message_prompt(self, monkeypatch):
        from modules.sns.visual_brief import build_visual_brief
        prompts = self._hero_env(monkeypatch)
        brief = build_visual_brief("3.1", "기존 핵심 메시지 문장", "Some Brand Title")
        assert cpb._build_hero_card_image(SimpleNamespace(title="T"), brief) == b"png"
        assert "기존 핵심 메시지 문장" in prompts[0] and "Some Brand Title" in prompts[0]

    def test_022_path_sends_only_concept(self, monkeypatch):
        from modules.sns.visual_brief import build_visual_brief
        prompts = self._hero_env(monkeypatch)
        topic = next(t for t in self._topics() if t.topic_id == "1.1")
        brief = build_visual_brief(topic.topic_id, topic.core_message, topic.title, "", "뉴스 정리자 말투")
        assert cpb._build_hero_card_image(topic, brief, client=object(), logo_check=True,
                                          background_concept=topic.image_concept) == b"png"
        assert "sound waves" in prompts[0] and "IBM" not in prompts[0] and "뉴스 정리자" not in prompts[0]

    def test_blocked_background_saved_for_review_only(self, monkeypatch, tmp_path):
        self._hero_env(monkeypatch, check_ok=False)
        path = tmp_path / "review" / "c22_cover_bg_blocked.png"
        assert cpb._build_hero_card_image(SimpleNamespace(title="T"), None, client=object(), logo_check=True,
                                          background_concept="abstract waves", blocked_bg_path=path) is None
        assert path.read_bytes() == b"bgbytes"

    @pytest.mark.parametrize("persona_code,concept,expected_concept", [
        ("PER-021", "abstract waves", "abstract waves"),
        ("PER-021", "", None),             # 개념 없는 Topic → 기본 비브랜드 개념(아래에서 확인)
        ("", "abstract waves", "NONE"),   # 036 등 Persona 없음 → 기존 경로(None)
    ])
    def test_carousel_passes_concept_only_for_persona(self, monkeypatch, tmp_path, persona_code, concept,
                                                      expected_concept):
        from modules.sns.visual_brief import DEFAULT_PERSONA_BACKGROUND_CONCEPT
        slides = tuple(Slide(index=i + 1, role="r", text=f"슬라이드 {i + 1}") for i in range(3))
        content = CarouselContent(slot_role="REACH", template_type="HOOK_IMPACT", source_section_id="1.1",
                                  source_title="T", source_url="https://src.example/a", slides=slides,
                                  caption="캡션", hashtags=("#IBM",), content_fingerprint="fp")
        monkeypatch.setattr(cpb, "generate_carousel_content", lambda *a, **k: CarouselResult(True, content))
        seen = []
        monkeypatch.setattr(cpb, "_build_hero_card_image",
                            lambda *a, background_concept=None, blocked_bg_path=None, **k:
                            seen.append((background_concept, blocked_bg_path)) or b"cover")
        monkeypatch.setattr(cpb, "render_card", lambda c: b"body")
        topic = SimpleNamespace(topic_id="1.1", title="T", source_url="https://src.example/a", core_message="m",
                                prohibited_expression="", source_published_at="", image_concept=concept)
        (tmp_path / "content").mkdir()
        (tmp_path / "images").mkdir()
        assert cpb._create_carousel_package(topic, "c22t", tmp_path, 3, "", "REACH", "HOOK_IMPACT",
                                            persona_code=persona_code).success is True
        got_concept, got_path = seen[0]
        if expected_concept == "NONE":
            assert got_concept is None and got_path is None
        else:
            assert got_concept == (expected_concept or DEFAULT_PERSONA_BACKGROUND_CONCEPT)
            assert got_path == tmp_path / "review" / "c22t_cover_bg_blocked.png"
