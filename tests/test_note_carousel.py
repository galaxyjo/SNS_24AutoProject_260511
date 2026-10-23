"""261023 STEP 4-AM — 노트 손그림 캐러셀 Target Test.

장별 image_scene 계약 / Gemini 글자·로고 판독 / render_note_card / 패키지 생성(재생성 규칙,
Fail-closed) / 기존 템플릿 경로 무변경. 네트워크(Gemini·Cloudflare) 호출은 모두 가짜로 바꾼다.
"""

import json
from io import BytesIO

import pytest
from PIL import Image

import modules.sns.carousel_content_builder as ccb
import modules.sns.content_package_builder as builder
import modules.sns.image_text_checker as checker
from modules.sns.carousel_content_builder import CarouselContent, CarouselResult, Slide
from modules.sns.image_provider_cloudflare import ProviderResult
from modules.sns.image_template_renderer import NoteCardContent, render_note_card
from modules.sns.source_selector import SourceTopic


class _FakeResponse:
    def __init__(self, payload):
        self.text = json.dumps(payload, ensure_ascii=False)


class _FakeModels:
    def __init__(self, responses=None, raise_exc=None):
        self._responses = list(responses or [])
        self._raise_exc = raise_exc
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._raise_exc:
            raise self._raise_exc
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeClient:
    def __init__(self, models):
        self.models = models


def _png(color=(200, 200, 200), size=(1024, 1024)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _topic():
    return SourceTopic(
        topic_id="3.1", title="Example Topic", status="VERIFIED FACT", source_url="https://example.com/topic-1",
        core_message="이 도구는 하루 3건 자동 게시를 지원한다. 무료 등급은 검색 기능이 제한된다.",
        prohibited_expression="",
    )


# ── A. 장별 image_scene 계약(carousel_content_builder) ─────────────────────────

_SCENES = [
    "A tired worker hands a tall pile of boxes to a friendly robot arm.",
    "An envelope presses a big switch that turns a set of gears.",
    "A shop owner and an office worker relax with coffee mugs.",
]


def _scene_payload(n=3, scenes=None):
    texts = ["AI 영업 DM, 아직도 직접 처리하고 계세요?", "무료 등급은 검색 기능이 제한된다는 점을 먼저 알아야 합니다",
             "하루 3건 자동 게시로 반복 업무를 줄일 수 있습니다"][: n - 1] + ["필요할 때 다시 보도록 저장하세요"]
    scenes = scenes or _SCENES[:n - 1] + [_SCENES[-1]]
    return {
        "slides": [{"index": i + 1, "role": "r", "text": t, "image_scene": s}
                   for i, (t, s) in enumerate(zip(texts, scenes))],
        "caption": "반복 업무를 줄이는 방법입니다.\n\n무료 등급 제한도 함께 확인했습니다.\n\n저장해두세요.",
        "hashtags": ["AI자동화", "업무자동화", "AI툴", "소상공인", "생산성"],
    }


def _repair_response(scenes_by_index):
    return _FakeResponse({"scenes": [{"index": i, "image_scene": s} for i, s in scenes_by_index.items()]})


def _run_builder(monkeypatch, payload, n=3, extra_responses=(), **kw):
    models = _FakeModels([_FakeResponse(payload), *extra_responses])
    if kw.get("with_image_scenes"):
        # note 경로는 전용 client만 쓴다 — 공유 client(_get_client)가 불리면 테스트 실패.
        kw.setdefault("client", _FakeClient(models))
        monkeypatch.setattr(ccb, "_get_client", _shared_client_forbidden)
    else:
        monkeypatch.setattr(ccb, "_get_client", lambda: _FakeClient(models))
    monkeypatch.setattr(ccb, "_throttle", lambda: None)
    monkeypatch.setattr(ccb, "check_caption_safety", lambda text, **k: ("SAFE", "STOP"))
    return ccb.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=n, **kw), models


def _shared_client_forbidden():
    raise AssertionError("shared GEMINI_API_KEY client must not be used on the note path")


class TestImageSceneContract:
    def test_scenes_returned_per_slide_in_one_call(self, monkeypatch):
        result, models = _run_builder(monkeypatch, _scene_payload(), with_image_scenes=True)
        assert result.success is True, result.error_code
        assert [s.image_scene for s in result.content.slides] == _SCENES
        assert len(models.calls) == 1
        call = models.calls[0]
        assert "image_scene" in call["config"].response_json_schema["properties"]["slides"]["items"]["required"]
        assert "For EVERY slide also write image_scene" in call["contents"]

    @pytest.mark.parametrize("bad, code", [
        ("", "IMAGE_SCENE_EMPTY"),
        ("   ", "IMAGE_SCENE_EMPTY"),
        ("A man types on a laptop next to a coffee cup.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("A clean desk with no text anywhere.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("Three boxes connected by 3 arrows.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("A shop with a Starbucks logo.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("A worker writing on a sticky note.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        # 261023 STEP 4-AS — 진단 Canary에서 낙서·말풍선 글씨를 부른 단어
        ("A person checking notes at a table.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("A person holding a notepad.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("A person with an open notebook.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("A stack of paper on a chair.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("A child reading a book.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("Two people with a speech bubble above them.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        ("Two people talking at a cafe.", "IMAGE_SCENE_FORBIDDEN_WORD"),
        (" ".join(["tree"] * 46), "IMAGE_SCENE_TOO_LONG"),
    ])
    def test_invalid_scene_fails_closed(self, monkeypatch, bad, code):
        payload = _scene_payload()
        payload["slides"][1]["image_scene"] = bad
        # 금지어면 장면만 1회 재요청한다 — 재요청도 같은 장면을 돌려주면 그대로 실패해야 한다.
        repair = [_repair_response({2: bad})] if code == "IMAGE_SCENE_FORBIDDEN_WORD" else []
        result, models = _run_builder(monkeypatch, payload, extra_responses=repair, with_image_scenes=True)
        assert result.success is False and result.error_code == code
        assert len(models.calls) == (2 if repair else 1)

    def test_missing_scene_key_fails_closed(self, monkeypatch):
        payload = _scene_payload()
        del payload["slides"][2]["image_scene"]
        result, _ = _run_builder(monkeypatch, payload, with_image_scenes=True)
        assert result.error_code == "IMAGE_SCENE_EMPTY"

    def test_eight_slide_with_scenes_rejected_without_call(self, monkeypatch):
        result, models = _run_builder(monkeypatch, _scene_payload(), n=8, with_image_scenes=True)
        assert result.error_code == "IMAGE_SCENE_UNSUPPORTED" and models.calls == []

    def test_default_call_unchanged(self, monkeypatch):
        payload = _scene_payload()
        for s in payload["slides"]:
            del s["image_scene"]
        result, models = _run_builder(monkeypatch, payload)
        assert result.success is True, result.error_code
        assert all(s.image_scene == "" for s in result.content.slides)
        assert models.calls[0]["config"].response_json_schema is ccb._CAROUSEL_RESPONSE_SCHEMA
        assert "image_scene" not in models.calls[0]["contents"]

    # 261023 STEP 4-AQ — 금지어 장면 1회 재요청
    def test_forbidden_scene_repaired_once(self, monkeypatch, caplog):
        payload = _scene_payload()
        payload["slides"][1]["image_scene"] = "A man types on a laptop next to a coffee cup."
        fixed = "A man sorts small cards into three neat piles."
        with caplog.at_level("WARNING"):
            result, models = _run_builder(monkeypatch, payload, extra_responses=[_repair_response({2: fixed})],
                                          with_image_scenes=True)
        assert result.success is True, result.error_code
        assert [s.image_scene for s in result.content.slides] == [_SCENES[0], fixed, _SCENES[2]]
        assert [s.text for s in result.content.slides] == [s["text"] for s in payload["slides"]]
        assert len(models.calls) == 2
        repair_prompt = models.calls[1]["contents"]
        assert "Slide 2 text:" in repair_prompt and "Slide 1 text:" not in repair_prompt
        assert "laptop, computer" in repair_prompt and "any digit" in repair_prompt
        assert models.calls[1]["config"].response_json_schema is ccb._SCENE_REPAIR_RESPONSE_SCHEMA
        log = " ".join(r.getMessage() for r in caplog.records)
        assert "hits=[(2, 'laptop')]" in log and "coffee cup" not in log

    def test_repair_with_wrong_index_fails_closed(self, monkeypatch):
        payload = _scene_payload()
        payload["slides"][1]["image_scene"] = "A poster on a wall."
        result, models = _run_builder(monkeypatch, payload, extra_responses=[_repair_response({3: "A tree."})],
                                      with_image_scenes=True)
        assert result.error_code == "IMAGE_SCENE_REPAIR_FAILED" and len(models.calls) == 2

    def test_repair_call_error_fails_closed(self, monkeypatch):
        payload = _scene_payload()
        payload["slides"][1]["image_scene"] = "A poster on a wall."
        result, models = _run_builder(monkeypatch, payload, extra_responses=[RuntimeError("503")],
                                      with_image_scenes=True)
        assert result.error_code == "IMAGE_SCENE_REPAIR_FAILED" and len(models.calls) == 2

    def test_repaired_scene_still_validated_for_length(self, monkeypatch):
        payload = _scene_payload()
        payload["slides"][1]["image_scene"] = "A poster on a wall."
        long_scene = " ".join(["tree"] * 46)
        result, _ = _run_builder(monkeypatch, payload, extra_responses=[_repair_response({2: long_scene})],
                                 with_image_scenes=True)
        assert result.error_code == "IMAGE_SCENE_TOO_LONG"

    def test_empty_scene_not_repaired(self, monkeypatch):
        payload = _scene_payload()
        payload["slides"][1]["image_scene"] = ""
        result, models = _run_builder(monkeypatch, payload, with_image_scenes=True)
        assert result.error_code == "IMAGE_SCENE_EMPTY" and len(models.calls) == 1

    def test_scene_not_part_of_fingerprint(self, monkeypatch):
        with_scene, _ = _run_builder(monkeypatch, _scene_payload(), with_image_scenes=True)
        payload = _scene_payload()
        for s in payload["slides"]:
            del s["image_scene"]
        without_scene, _ = _run_builder(monkeypatch, payload)
        assert with_scene.content.content_fingerprint == without_scene.content.content_fingerprint


# ── B. Gemini 글자·로고 판독(image_text_checker) ───────────────────────────────

def _check_response(flags):
    return _FakeResponse({"images": [{"index": i + 1, "has_text": t, "has_logo": l} for i, (t, l) in enumerate(flags)]})


class TestImageTextChecker:
    def test_success_one_call_with_all_images(self):
        models = _FakeModels([_check_response([(False, False), (True, False), (False, True)])])
        result = checker.check_images_for_text_and_logo(
            [_png(), _png(), _png()], client=_FakeClient(models), throttle_fn=lambda: None, model="m")
        assert result.success is True
        assert [c.passed for c in result.checks] == [True, False, False]
        assert len(models.calls) == 1 and models.calls[0]["model"] == "m"
        assert len(models.calls[0]["contents"]) == 4          # 지시문 1 + 이미지 3

    def test_no_client_fails_closed_without_shared_key(self, monkeypatch):
        monkeypatch.setattr(checker, "_throttle", lambda: None)
        result = checker.check_images_for_text_and_logo([_png()])
        assert result.success is False and result.error_code == "CHECK_CLIENT_MISSING"

    @pytest.mark.parametrize("images", [[], [b""]])
    def test_empty_input(self, images):
        result = checker.check_images_for_text_and_logo(images, client=_FakeClient(_FakeModels()))
        assert result.error_code == "CHECK_INPUT_EMPTY"

    @pytest.mark.parametrize("response, code", [
        (_check_response([(False, False)]), "CHECK_RESULT_INVALID"),                       # 2장 요청, 1장 응답
        (_FakeResponse({"images": [{"index": 1, "has_text": False, "has_logo": False},
                                   {"index": 3, "has_text": False, "has_logo": False}]}), "CHECK_RESULT_INVALID"),
        (_FakeResponse({"images": [{"index": 1, "has_text": "no", "has_logo": False},
                                   {"index": 2, "has_text": False, "has_logo": False}]}), "CHECK_RESULT_INVALID"),
        (_FakeResponse({"pictures": []}), "CHECK_PARSE_FAILED"),
    ])
    def test_bad_response_fails_closed(self, response, code):
        result = checker.check_images_for_text_and_logo(
            [_png(), _png()], client=_FakeClient(_FakeModels([response])), throttle_fn=lambda: None)
        assert result.success is False and result.error_code == code

    def test_call_exception_fails_closed(self):
        models = _FakeModels(raise_exc=ValueError("boom"))
        result = checker.check_images_for_text_and_logo(
            [_png()], client=_FakeClient(models), throttle_fn=lambda: None)
        assert result.error_code == "CHECK_CALL_FAILED"


# ── C. render_note_card ────────────────────────────────────────────────────────

class TestRenderNoteCard:
    @pytest.mark.parametrize("is_cover", [True, False])
    def test_renders_canvas(self, is_cover):
        data = render_note_card(NoteCardContent(
            text="반복되는 업무 하나를 트리거, 처리, 기록 단계의 자동화 흐름으로 바꿀 수 있습니다.",
            sketch=_png(), page=1 if is_cover else 2, total=3, source_label="Example Topic", is_cover=is_cover))
        with Image.open(BytesIO(data)) as im:
            assert im.size == (1080, 1350) and im.format == "PNG"

    @pytest.mark.parametrize("kw", [
        {"text": " "}, {"source_label": ""}, {"sketch": b""}, {"page": 0}, {"page": 4},
        {"text": "아주 긴 문장입니다 " * 60},
    ])
    def test_invalid_input_raises(self, kw):
        base = dict(text="본문입니다", sketch=_png(), page=2, total=3, source_label="Example Topic")
        with pytest.raises(ValueError):
            render_note_card(NoteCardContent(**{**base, **kw}))


# ── D. 패키지 생성(content_package_builder, note style) ─────────────────────────

def _note_carousel(n=3):
    texts = ["AI 영업 DM, 아직도 직접 처리하고 계세요?", "핵심 사실 설명", "실무 활용 방법"][: n - 1] + ["필요할 때 다시 보도록 저장하세요"]
    return CarouselContent(
        slot_role="REACH", template_type="HOOK_IMPACT", source_section_id="3.1",
        source_title="Example Topic", source_url="https://example.com/topic-1",
        slides=tuple(Slide(index=i + 1, role="r", text=t, image_scene=f"scene-{i + 1}") for i, t in enumerate(texts)),
        caption="반복 업무를 줄이는 방법입니다.\n\n저장해두세요.",
        hashtags=("AI자동화", "업무자동화", "AI툴", "소상공인", "생산성"),
        content_fingerprint=f"fp-note-{n}",
    )


@pytest.fixture
def note_env(monkeypatch):
    """check_results: 판독 호출마다 돌려줄 장별 (has_text, has_logo) 목록 큐."""
    env = {"carousel_kw": [], "prompts": [], "checked_counts": [], "check_results": [], "hero": 0,
           "gen_fail_at": None, "check_error": False}

    def _fake_carousel(topic, slot_role, template_type, **kw):
        env["carousel_kw"].append(kw)
        return CarouselResult(success=True, content=_note_carousel(kw["slide_count"]))

    def _fake_generate(prompt, negative_prompt=""):
        env["prompts"].append(prompt)
        if env["gen_fail_at"] == len(env["prompts"]):
            return ProviderResult(success=False, error_code="HTTP_500")
        return ProviderResult(success=True, image_bytes=_png())

    def _fake_check(images, **kw):
        env["checked_counts"].append(len(images))
        if env["check_error"]:
            return checker.ImageCheckResult(success=False, error_code="CHECK_CALL_FAILED")
        flags = env["check_results"].pop(0) if env["check_results"] else [(False, False)] * len(images)
        return checker.ImageCheckResult(success=True, checks=tuple(
            checker.ImageCheck(index=i + 1, has_text=t, has_logo=l) for i, (t, l) in enumerate(flags)))

    def _no_hero(*a, **k):
        env["hero"] += 1
        return _png()

    monkeypatch.setattr(builder, "generate_carousel_content", _fake_carousel)
    monkeypatch.setattr(builder, "generate_image", _fake_generate)
    monkeypatch.setattr(builder, "check_images_for_text_and_logo", _fake_check)
    monkeypatch.setattr(builder, "_build_hero_card_image", _no_hero)
    monkeypatch.setattr(builder, "generate_hook_caption", lambda *a, **k: ("x", "#x"))
    return env


def _files(root):
    return sorted(p.name for p in root.rglob("*") if p.is_file())


def _make(tmp_path, n=3):
    return builder.create_content_package(
        vault_root=tmp_path, injected_topic=_topic(), carousel_slide_count=n, carousel_style="note")


class TestNotePackage:
    @pytest.mark.parametrize("n", [2, 3, 4])
    def test_success_writes_note_package(self, tmp_path, note_env, n):
        result = _make(tmp_path, n)
        assert result.success is True, result.error_code
        assert note_env["carousel_kw"][0]["with_image_scenes"] is True
        assert note_env["hero"] == 0
        assert len(note_env["prompts"]) == n and note_env["checked_counts"] == [n]
        assert all(p.startswith(f"scene-{i + 1} Simple hand-drawn black pen line illustration") for i, p in enumerate(note_env["prompts"]))
        fields = builder.read_frontmatter(result.content_id, tmp_path)
        assert fields["carousel_style"] == "note"
        assert fields["slide_image_scenes"] == [f"scene-{i + 1}" for i in range(n)]
        assert fields["idempotency_version"] == 3 and fields["slide_count"] == n
        for rel in builder.carousel_slide_image_paths(result.content_id, n):
            with Image.open(tmp_path / rel) as im:
                assert im.size == (1080, 1350)

    def test_only_flagged_slide_regenerated(self, tmp_path, note_env):
        note_env["check_results"] = [[(False, False), (True, False), (False, False)], [(False, False)]]
        result = _make(tmp_path)
        assert result.success is True, result.error_code
        assert len(note_env["prompts"]) == 4 and note_env["checked_counts"] == [3, 1]
        assert note_env["prompts"][3].startswith("scene-2 Keep it to a single simple scene")
        assert "Keep it to a single simple scene" not in "".join(note_env["prompts"][:3])

    def test_logo_also_triggers_regeneration(self, tmp_path, note_env):
        note_env["check_results"] = [[(False, True), (False, False), (False, False)], [(False, False)]]
        assert _make(tmp_path).success is True
        assert note_env["prompts"][3].startswith("scene-1 ")

    def test_regeneration_limit_fails_closed(self, tmp_path, note_env):
        note_env["check_results"] = [[(False, False), (True, False), (False, False)], [(True, False)], [(True, False)]]
        result = _make(tmp_path)
        assert result.success is False and result.error_code == "IMAGE_TEXT_CHECK_FAILED"
        assert len(note_env["prompts"]) == 3 + builder.NOTE_IMAGE_MAX_REGENERATIONS
        assert note_env["checked_counts"] == [3, 1, 1]
        assert _files(tmp_path) == []

    def test_check_error_fails_closed(self, tmp_path, note_env):
        note_env["check_error"] = True
        result = _make(tmp_path)
        assert result.error_code == "IMAGE_CHECK_ERROR" and _files(tmp_path) == []

    def test_image_generation_failure_fails_closed(self, tmp_path, note_env):
        note_env["gen_fail_at"] = 2
        result = _make(tmp_path)
        assert result.error_code == "IMAGE_GENERATION_FAILED" and _files(tmp_path) == []
        assert note_env["checked_counts"] == []

    def test_render_failure_fails_closed(self, tmp_path, note_env, monkeypatch):
        def _boom(content):
            raise ValueError("too long")
        monkeypatch.setattr(builder, "render_note_card", _boom)
        result = _make(tmp_path)
        assert result.error_code == "IMAGE_GENERATION_FAILED" and _files(tmp_path) == []

    def test_invalid_style_rejected_before_work(self, tmp_path, note_env):
        result = builder.create_content_package(
            vault_root=tmp_path, injected_topic=_topic(), carousel_slide_count=3, carousel_style="clay")
        assert result.error_code == "CAROUSEL_STYLE_INVALID"
        assert note_env["carousel_kw"] == [] and _files(tmp_path) == []

    def test_template_style_default_unchanged(self, tmp_path, note_env):
        result = builder.create_content_package(vault_root=tmp_path, injected_topic=_topic(), carousel_slide_count=3)
        assert result.success is True, result.error_code
        assert note_env["carousel_kw"][0]["with_image_scenes"] is False
        assert note_env["hero"] == 1 and note_env["prompts"] == [] and note_env["checked_counts"] == []
        fields = builder.read_frontmatter(result.content_id, tmp_path)
        assert "carousel_style" not in fields and "slide_image_scenes" not in fields


# ── 261023 STEP 4-AS — 화풍 문장·장면 금지어 보강 ─────────────────────────────────

def test_sketch_style_has_no_props_that_invite_text():
    style = builder._NOTE_SKETCH_STYLE.lower()
    assert "white background" in style and "sky blue" in style and "yellow" in style
    for word in ("notebook", "marker", "desk", "page", "study notes"):
        assert word not in style


@pytest.mark.parametrize("scene", [
    "Two people facing each other and gesturing at a table.",
    "A worried person holding a finished box.",
    "A bookshelf corner with a plant.",            # 'book' 단어 경계 — bookshelf는 허용
])
def test_safe_scenes_still_pass(scene):
    assert ccb._IMAGE_SCENE_FORBIDDEN_RE.search(scene) is None


def test_repair_prompt_lists_new_forbidden_words():
    for word in ("note", "notepad", "notebook", "paper", "book", "speech bubble", "talking"):
        assert word in ccb._IMAGE_SCENE_FORBIDDEN_WORDS_TEXT
    assert "gesturing" in ccb._IMAGE_SCENE_RULE


# ── 261023 STEP 4-AW — 손글씨 폰트 미지원 기호·하단 출처 겹침 ──────────────────────

import modules.sns.image_template_renderer as itr  # noqa: E402
from PIL import ImageDraw  # noqa: E402


class TestNoteGlyphAndFooter:
    def test_separators_substituted_to_supported_glyphs(self):
        assert itr._note_pen_text(" 확인 · 반복 • 기록 → 끝… ") == "확인 ㆍ 반복 ㆍ 기록 > 끝..."

    def test_card_with_separators_renders(self):
        data = render_note_card(NoteCardContent(
            text="매번 손으로 확인 · 같은 답변 반복 · 시작 조건 → 처리 → 기록", sketch=_png(),
            page=2, total=3, source_label="Example Topic"))
        with Image.open(BytesIO(data)) as im:
            assert im.size == (1080, 1350)

    @pytest.mark.parametrize("ch", ["★", "✓", "①"])
    def test_unsupported_glyph_fails_closed(self, ch):
        with pytest.raises(ValueError, match="손글씨 폰트에 없는 글자"):
            render_note_card(NoteCardContent(text=f"체크 {ch} 완료", sketch=_png(), page=2, total=3,
                                             source_label="Example Topic"))

    def _draw_and_font(self):
        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        return draw, itr._load_font(itr._FONT_REGULAR, 24)

    def test_source_weekday_tag_removed(self):
        draw, font = self._draw_and_font()
        text = itr._note_source_text(draw, "Meta Docs (화 — 인스타DM·고객문의)", font, 600)
        assert text == "출처: Meta Docs"

    def test_long_source_truncated_to_fit(self):
        draw, font = self._draw_and_font()
        label = "Meta Instagram Business Messaging Documentation Extra Long Title (화 — 인스타DM·고객문의)"
        text = itr._note_source_text(draw, label, font, 500)
        assert text.startswith("출처: Meta Instagram") and text.endswith("...")
        assert "(화" not in text and draw.textlength(text, font=font) <= 500

    def test_footer_source_does_not_reach_handle(self):
        draw, font = self._draw_and_font()
        brand_w = draw.textlength(itr.BRAND_HANDLE, font=font)
        max_w = 1080 - 2 * itr._NOTE_SIDE - brand_w - 40
        text = itr._note_source_text(draw, "Meta Instagram Business Messaging Documentation (화 — 인스타DM·고객문의)",
                                     font, max_w)
        assert itr._NOTE_SIDE + draw.textlength(text, font=font) < 1080 - itr._NOTE_SIDE - brand_w



# ── 261023 STEP 4-AY — Codex BLOCKER(Credential·재생성 문구·폰트 라이선스) ──────────

class TestNoteBlockers:
    def test_note_without_dedicated_client_fails_before_gemini(self, monkeypatch):
        calls = []
        monkeypatch.setattr(ccb, "_get_client", lambda: calls.append("shared") or _FakeClient(_FakeModels()))
        result = ccb.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", slide_count=3,
                                               with_image_scenes=True)
        assert (result.success, result.error_code) == (False, "NOTE_CLIENT_MISSING")
        assert calls == []

    def test_repair_uses_dedicated_client_only(self, monkeypatch):
        payload = _scene_payload()
        payload["slides"][1]["image_scene"] = "A poster on a wall."
        result, models = _run_builder(monkeypatch, payload,
                                      extra_responses=[_repair_response({2: "A person sorting small cards."})],
                                      with_image_scenes=True)
        assert result.success is True, result.error_code
        assert len(models.calls) == 2              # 본 호출 + 재요청 모두 전용 client(공유 client는 예외)

    def test_default_path_still_uses_existing_client_resolution(self, monkeypatch):
        payload = _scene_payload()
        for s in payload["slides"]:
            del s["image_scene"]
        result, models = _run_builder(monkeypatch, payload)
        assert result.success is True and len(models.calls) == 1

    def test_retry_suffix_has_no_text_inviting_props(self):
        suffix = builder._NOTE_SKETCH_RETRY_SUFFIX.lower()
        for word in ("pen", "marker", "notebook", "binding", "desk", "device", "page"):
            assert word not in suffix
        assert "white background" in suffix and "flat color" in suffix

    def test_font_license_and_copyright_shipped(self):
        from pathlib import Path
        font_dir = Path(builder.__file__).resolve().parents[2] / "assets" / "fonts" / "nanumpen"
        ofl = (font_dir / "OFL.txt").read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE Version 1.1" in ofl and "Copyright (c) 2010, NHN Corporation" in ofl
        assert "NanumPen" in ofl
        assert 'license: "OFL"' in (font_dir / "METADATA.pb").read_text(encoding="utf-8")
