"""Track B-6 — content_package_builder.py 단위 테스트.

Track B-1~4 순수 함수는 전부 mock 처리한다(실제 Gemini/Cloudflare 호출 없음).
검증 대상은 조립 로직 + Fail-closed 경계 + Atomic Write뿐이다.
"""

import json
from datetime import datetime, timedelta

import pytest

import modules.sns.content_package_builder as builder
from modules.sns.image_provider_cloudflare import ProviderResult
from modules.sns.source_selector import SourceTopic
from modules.sns.visual_brief import ImagePrompt


def _fake_topic(source_url="https://example.com/topic-1"):
    return SourceTopic(
        topic_id="3.1",
        title="Example Topic",
        status="VERIFIED FACT",
        source_url=source_url,
        core_message="핵심 메시지",
        prohibited_expression="",
    )


def _fake_image_prompt():
    return ImagePrompt(
        prompt_text="a symbolic illustration",
        negative_prompt="text, logo",
        aspect_ratio="1:1",
        prompt_version="v2",
    )


@pytest.fixture(autouse=True)
def _mock_pure_pipeline(monkeypatch):
    """기본값: 전체 성공 경로. 개별 테스트가 필요한 함수만 덮어쓴다."""
    monkeypatch.setattr(builder, "select_next_topic", lambda used, topics=None: _fake_topic())
    monkeypatch.setattr(
        builder, "generate_hook_caption", lambda *a, **k: ("hooking caption", "#ai #startup")
    )
    monkeypatch.setattr(builder, "build_visual_brief", lambda *a, **k: object())
    monkeypatch.setattr(builder, "build_image_prompt", lambda brief: _fake_image_prompt())
    monkeypatch.setattr(
        builder,
        "generate_image",
        lambda *a, **k: ProviderResult(success=True, image_bytes=b"fake-png-bytes"),
    )


def _content_files(vault_root):
    return sorted((vault_root / "content").glob("*"))


def _image_files(vault_root):
    return sorted((vault_root / "images").glob("*"))


def test_full_success_writes_md_and_png(tmp_path):
    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is True
    assert result.status == "complete"

    md_files = _content_files(tmp_path)
    img_files = _image_files(tmp_path)
    assert len(md_files) == 1
    assert len(img_files) == 1
    assert md_files[0].name == f"{result.content_id}.md"
    assert img_files[0].name == f"{result.content_id}.png"

    text = md_files[0].read_text(encoding="utf-8")
    fields = builder._parse_frontmatter(text)
    assert fields["status"] == "complete"
    assert fields["source_url"] == "https://example.com/topic-1"
    assert fields["image_path"] == f"images/{result.content_id}.png"
    assert img_files[0].read_bytes() == b"fake-png-bytes"


def test_no_selectable_topic_writes_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "select_next_topic", lambda used, topics=None: None)

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is False
    assert result.error_code == "NO_SELECTABLE_TOPIC"
    assert _content_files(tmp_path) == []
    assert _image_files(tmp_path) == []


def test_duplicate_content_id_blocks_and_leaves_existing_file_unchanged(tmp_path):
    first = builder.create_content_package(vault_root=tmp_path)
    assert first.success is True

    original_text = (tmp_path / "content" / f"{first.content_id}.md").read_text(encoding="utf-8")

    # 같은 topic(같은 source_url)이 다시 선택되도록 강제 — 회장 승인 규칙대로
    # content_id는 topic_id+날짜+source_url 해시로 결정적이라 동일 id가 나온다.
    second = builder.create_content_package(vault_root=tmp_path)

    assert second.success is False
    assert second.error_code == "DUPLICATE_CONTENT_ID"
    assert second.content_id == first.content_id
    assert len(_content_files(tmp_path)) == 1
    assert len(_image_files(tmp_path)) == 1
    assert (tmp_path / "content" / f"{first.content_id}.md").read_text(encoding="utf-8") == original_text


def test_empty_caption_writes_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "generate_hook_caption", lambda *a, **k: ("", ""))

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is False
    assert result.error_code == "CAPTION_GENERATION_FAILED"
    assert _content_files(tmp_path) == []
    assert _image_files(tmp_path) == []


def test_image_generation_failure_writes_no_files_and_leaves_source_retryable(tmp_path, monkeypatch):
    monkeypatch.setattr(
        builder, "generate_image",
        lambda *a, **k: ProviderResult(success=False, error_code="DAILY_IMAGE_CAP_EXCEEDED"),
    )

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is False
    assert result.error_code == "IMAGE_GENERATION_FAILED"
    assert _content_files(tmp_path) == []
    assert _image_files(tmp_path) == []
    # draft_text_only 저장 금지 확인 -> 다음 스캔에서도 이 source_url이 '사용완료'로 안 남는다
    assert builder.scan_used_source_urls(tmp_path) == set()


def test_atomic_write_failure_leaves_zero_temp_or_partial_files(tmp_path, monkeypatch):
    real_replace = builder.os.replace
    call_count = {"n": 0}

    def _flaky_replace(src, dst):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("simulated failure on second replace")
        return real_replace(src, dst)

    monkeypatch.setattr(builder.os, "replace", _flaky_replace)

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is False
    assert result.error_code == "ATOMIC_WRITE_FAILED"
    assert _content_files(tmp_path) == []
    assert _image_files(tmp_path) == []


def test_vault_scan_error_on_unparseable_frontmatter_blocks_before_generation(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    (content_dir / "broken.md").write_text("---\nnot: valid: yaml: line\n---\nbody\n", encoding="utf-8")

    called = {"select_next_topic": False}

    def _spy(used):
        called["select_next_topic"] = True
        return _fake_topic()

    monkeypatch.setattr(builder, "select_next_topic", _spy)

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is False
    assert result.error_code == "VAULT_SCAN_ERROR"
    assert called["select_next_topic"] is False
    assert _image_files(tmp_path) == []


def test_scan_used_source_urls_only_counts_complete_status(tmp_path):
    today_iso = datetime.now().isoformat(timespec="seconds")
    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    complete_fields = {
        "content_id": "3-1-260731-aaaaaaaa",
        "source_url": "https://example.com/complete",
        "status": "complete",
        "created_at": today_iso,
    }
    incomplete_fields = {
        "content_id": "3-2-260731-bbbbbbbb",
        "source_url": "https://example.com/incomplete",
        "status": "some_other_status",
        "created_at": today_iso,
    }
    (content_dir / "a.md").write_text(builder._render_frontmatter(complete_fields), encoding="utf-8")
    (content_dir / "b.md").write_text(builder._render_frontmatter(incomplete_fields), encoding="utf-8")

    used = builder.scan_used_source_urls(tmp_path)

    assert used == {"https://example.com/complete"}


def test_scan_used_source_urls_ignores_previous_days_allows_reselection(tmp_path):
    """260805 Sourcebook SSOT 복구 — "URL당 평생 1회"가 아니라 "URL당 하루
    1회"다. 어제 complete된 원천은 오늘 다시 선택 가능해야 한다."""
    yesterday_iso = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    old_fields = {
        "content_id": "3-1-260804-aaaaaaaa",
        "source_url": "https://example.com/used-yesterday",
        "status": "complete",
        "created_at": yesterday_iso,
    }
    (content_dir / "a.md").write_text(builder._render_frontmatter(old_fields), encoding="utf-8")

    used = builder.scan_used_source_urls(tmp_path)

    assert used == set()  # 어제 것은 "오늘 사용"에 포함되지 않음 — 오늘 재선택 가능


def test_scan_used_source_urls_same_day_still_excluded(tmp_path):
    """같은 날 안에서는 여전히 제외된다(같은 슬롯 회차 내 중복 선택 방지)."""
    today_iso = datetime.now().isoformat(timespec="seconds")
    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    today_fields = {
        "content_id": "3-1-260805-aaaaaaaa",
        "source_url": "https://example.com/used-today",
        "status": "complete",
        "created_at": today_iso,
    }
    (content_dir / "a.md").write_text(builder._render_frontmatter(today_fields), encoding="utf-8")

    used = builder.scan_used_source_urls(tmp_path)

    assert used == {"https://example.com/used-today"}


def test_scan_used_source_urls_missing_created_at_not_counted_as_used(tmp_path):
    """created_at이 없는(구버전) frontmatter는 크래시하지 않고 안전하게
    '오늘 사용 아님'으로 처리한다(재선택 허용 쪽으로 안전하게 기움)."""
    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    fields_no_created_at = {
        "content_id": "3-1-260101-aaaaaaaa",
        "source_url": "https://example.com/legacy",
        "status": "complete",
    }
    (content_dir / "a.md").write_text(
        builder._render_frontmatter(fields_no_created_at), encoding="utf-8"
    )

    used = builder.scan_used_source_urls(tmp_path)

    assert used == set()


def test_scan_source_url_last_used_tracks_most_recent_per_url(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    older = (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds")
    newer = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    (content_dir / "a.md").write_text(
        builder._render_frontmatter({
            "content_id": "a", "source_url": "https://example.com/x",
            "status": "complete", "created_at": older,
        }), encoding="utf-8",
    )
    (content_dir / "b.md").write_text(
        builder._render_frontmatter({
            "content_id": "b", "source_url": "https://example.com/x",
            "status": "complete", "created_at": newer,
        }), encoding="utf-8",
    )
    (content_dir / "c.md").write_text(
        builder._render_frontmatter({
            "content_id": "c", "source_url": "https://example.com/y",
            "status": "some_other_status", "created_at": newer,
        }), encoding="utf-8",
    )

    history = builder.scan_source_url_last_used(tmp_path)

    assert history == {"https://example.com/x": newer}  # 더 최근 값만 남고, 미완료 상태는 제외


def test_no_injected_topic_rotates_least_recently_used_source_first(tmp_path, monkeypatch):
    """260805 회장 지시(Sourcebook 전체 항목 순환 보완) — 파일 순서가 아니라
    '가장 오래전에 썼거나 안 쓴' 순으로 다음 후보를 고른다. 파일 순서상
    topic_a가 먼저지만 더 최근에 썼다면, 더 오래전에 쓴 topic_b가 선택돼야
    한다(그래야 Sourcebook 전체가 실제로 돌아간다)."""
    from modules.sns.source_selector import select_next_topic as real_select_next_topic

    monkeypatch.setattr(builder, "select_next_topic", real_select_next_topic)

    topic_a = _fake_topic(source_url="https://example.com/a")
    topic_b = SourceTopic(
        topic_id="3.2", title="B", status="VERIFIED FACT",
        source_url="https://example.com/b", core_message="msg b", prohibited_expression="",
    )
    monkeypatch.setattr(builder, "parse_sourcebook", lambda: [topic_a, topic_b])

    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    yesterday = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    three_days_ago = (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds")
    (content_dir / "old-a.md").write_text(
        builder._render_frontmatter({
            "content_id": "old-a", "source_url": topic_a.source_url,
            "status": "complete", "created_at": yesterday,
        }), encoding="utf-8",
    )
    (content_dir / "old-b.md").write_text(
        builder._render_frontmatter({
            "content_id": "old-b", "source_url": topic_b.source_url,
            "status": "complete", "created_at": three_days_ago,
        }), encoding="utf-8",
    )

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is True
    md_path, _ = builder._content_paths(result.content_id, tmp_path)
    fields = builder._parse_frontmatter(md_path.read_text(encoding="utf-8"))
    assert fields["source_url"] == topic_b.source_url  # 더 오래전에 쓴 쪽이 선택됨


def test_duplicate_caption_text_for_same_source_blocks_save(tmp_path, monkeypatch):
    """260805 회장 지시(콘텐츠 지문 기반 중복방지 보완) — 원천 재사용을 허용한
    만큼, 같은 원천에서 이전과 완전히 동일한 caption 문장이 다시 생성되면
    저장을 막는다."""
    topic = _fake_topic()
    monkeypatch.setattr(builder, "select_next_topic", lambda used, topics=None: topic)
    monkeypatch.setattr(
        builder, "generate_hook_caption", lambda *a, **k: ("hooking caption", "#ai #startup")
    )

    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    (content_dir / "prior.md").write_text(
        builder._render_frontmatter({
            "content_id": "prior-1", "source_url": topic.source_url,
            "status": "complete", "caption": "hooking caption",
            "created_at": (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds"),
        }), encoding="utf-8",
    )

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is False
    assert result.error_code == "DUPLICATE_CAPTION_TEXT"
    assert _content_files(tmp_path) == [content_dir / "prior.md"]
    assert _image_files(tmp_path) == []


def test_different_caption_text_for_same_source_is_allowed(tmp_path, monkeypatch):
    """새로 생성된 caption이 이전과 다르면 정상 저장된다(원천 재사용 자체는
    막지 않음 — 중복방지는 문장이 실제로 같을 때만 발동)."""
    topic = _fake_topic()
    monkeypatch.setattr(builder, "select_next_topic", lambda used, topics=None: topic)
    monkeypatch.setattr(
        builder, "generate_hook_caption", lambda *a, **k: ("a fresh new caption", "#ai #startup")
    )

    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    (content_dir / "prior.md").write_text(
        builder._render_frontmatter({
            "content_id": "prior-1", "source_url": topic.source_url,
            "status": "complete", "caption": "an old different caption",
            "created_at": (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds"),
        }), encoding="utf-8",
    )

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is True


def test_yaml_scalar_round_trips_colons_quotes_and_newlines():
    tricky = 'title: "Netflix" says\nline two'
    rendered = builder._yaml_scalar(tricky)
    assert json.loads(rendered) == tricky


# ── 260804 Track B 6G — injected_topic(Research-to-Topic Adapter 연동) ────

def test_injected_topic_bypasses_select_next_topic_and_scan(tmp_path, monkeypatch):
    """injected_topic이 주어지면 select_next_topic()/scan_used_source_urls()를
    전혀 호출하지 않는다(Adapter가 이미 검증까지 끝낸 Topic이므로 재선택 불필요)."""
    monkeypatch.setattr(builder, "select_next_topic", lambda used, topics=None: pytest.fail("호출되면 안 됨"))
    monkeypatch.setattr(builder, "scan_used_source_urls", lambda root=None: pytest.fail("호출되면 안 됨"))

    injected = _fake_topic(source_url="https://reddit.com/r/injected-topic")
    result = builder.create_content_package(vault_root=tmp_path, injected_topic=injected)

    assert result.success is True
    md_path, img_path = builder._content_paths(result.content_id, tmp_path)
    fields = builder._parse_frontmatter(md_path.read_text(encoding="utf-8"))
    assert fields["source_url"] == "https://reddit.com/r/injected-topic"


def test_no_injected_topic_uses_existing_select_next_topic_path_unchanged(tmp_path):
    """injected_topic을 생략한 기존 호출부는 100% 이전과 동일하게 동작한다
    (회귀 없음 재확인 — _mock_pure_pipeline autouse fixture의 select_next_topic
    mock이 그대로 쓰인다)."""
    result = builder.create_content_package(vault_root=tmp_path)
    assert result.success is True
    md_path, _ = builder._content_paths(result.content_id, tmp_path)
    fields = builder._parse_frontmatter(md_path.read_text(encoding="utf-8"))
    assert fields["source_url"] == "https://example.com/topic-1"  # _fake_topic() 기본값


def test_gemini_client_and_throttle_forwarded_to_generate_hook_caption(tmp_path, monkeypatch):
    """260804 Codex 리뷰(P0) — gemini_client/gemini_throttle을 넘기면
    generate_hook_caption()에 그대로 전달돼야 한다(Research-to-Topic Adapter가
    aijomoojin 전용 Credential로 Caption까지 생성하게 하는 계약의 근거)."""
    captured = {}

    def _spy_generate_hook_caption(title, core_message, prohibited_expression="",
                                    tone_style="", target_language="EN", *, client=None,
                                    throttle_fn=None, model=None):
        captured["client"] = client
        captured["throttle_fn"] = throttle_fn
        return "caption text", "#tag"

    monkeypatch.setattr(builder, "generate_hook_caption", _spy_generate_hook_caption)

    sentinel_client = object()
    sentinel_throttle = lambda: None  # noqa: E731

    result = builder.create_content_package(
        vault_root=tmp_path, gemini_client=sentinel_client, gemini_throttle=sentinel_throttle,
    )

    assert result.success is True
    assert captured["client"] is sentinel_client
    assert captured["throttle_fn"] is sentinel_throttle


def test_caption_and_carousel_receive_identical_gemini_client(tmp_path, monkeypatch):
    """260805 Track B 7B-5 — Caption과 Carousel이 동일한 계정 credential(Client
    인스턴스)을 사용해야 한다는 계약을 직접 증명한다."""
    captured = {}

    def _spy_generate_hook_caption(title, core_message, prohibited_expression="",
                                    tone_style="", target_language="EN", *, client=None,
                                    throttle_fn=None, model=None):
        captured["caption_client"] = client
        return "caption text", "#tag"

    def _spy_generate_carousel_content(topic, slot_role, template_type, *,
                                        client=None, throttle_fn=None, model=None,
                                        existing_fingerprints=None):
        captured["carousel_client"] = client
        return _FakeCarouselResult(success=True, content=_FakeCarouselContent())

    monkeypatch.setattr(builder, "generate_hook_caption", _spy_generate_hook_caption)
    monkeypatch.setattr(builder, "generate_carousel_content", _spy_generate_carousel_content)

    sentinel_client = object()

    result = builder.create_content_package(
        vault_root=tmp_path, gemini_client=sentinel_client,
        slot_role="REACH", template_type="HOOK_IMPACT",
    )

    assert result.success is True
    assert captured["caption_client"] is sentinel_client
    assert captured["carousel_client"] is sentinel_client
    assert captured["caption_client"] is captured["carousel_client"]


def test_no_gemini_override_keeps_default_none(tmp_path, monkeypatch):
    """gemini_client/gemini_throttle을 생략하면(기존 모든 호출부) None이 그대로
    전달돼 generate_hook_caption() 내부에서 전역 Client/Throttle을 쓰게 된다."""
    captured = {}

    def _spy_generate_hook_caption(title, core_message, prohibited_expression="",
                                    tone_style="", target_language="EN", *, client=None,
                                    throttle_fn=None, model=None):
        captured["client"] = client
        captured["throttle_fn"] = throttle_fn
        return "caption text", "#tag"

    monkeypatch.setattr(builder, "generate_hook_caption", _spy_generate_hook_caption)

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is True
    assert captured["client"] is None
    assert captured["throttle_fn"] is None


def test_gemini_model_forwarded_to_generate_hook_caption(tmp_path, monkeypatch):
    """260805 회장 지시 — gemini_model을 넘기면 generate_hook_caption()에 그대로
    전달돼야 한다(aijomoojin 전용 모델 고정 계약)."""
    captured = {}

    def _spy_generate_hook_caption(title, core_message, prohibited_expression="",
                                    tone_style="", target_language="EN", *, client=None,
                                    throttle_fn=None, model=None):
        captured["model"] = model
        return "caption text", "#tag"

    monkeypatch.setattr(builder, "generate_hook_caption", _spy_generate_hook_caption)

    result = builder.create_content_package(vault_root=tmp_path, gemini_model="gemini-3.5-flash-lite")

    assert result.success is True
    assert captured["model"] == "gemini-3.5-flash-lite"


def test_no_gemini_model_override_keeps_default_none(tmp_path, monkeypatch):
    """gemini_model 생략(기존 호출부)은 None이 그대로 전달돼 generate_hook_caption()
    내부에서 기본 모델을 쓰게 된다 — 하위호환."""
    captured = {}

    def _spy_generate_hook_caption(title, core_message, prohibited_expression="",
                                    tone_style="", target_language="EN", *, client=None,
                                    throttle_fn=None, model=None):
        captured["model"] = model
        return "caption text", "#tag"

    monkeypatch.setattr(builder, "generate_hook_caption", _spy_generate_hook_caption)

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is True
    assert captured["model"] is None


# ── 260805 Track B 7B-3 2차 검수 — Carousel Canary를 create_content_package()에
# 선택적 출력으로 최소 연결(승인 범위: Runtime 미연결, 기존 파이프라인 불변) ──

class _FakeCarouselContent:
    def __init__(self, fingerprint="fp-abc123", slot_role="REACH", template_type="HOOK_IMPACT"):
        self.content_fingerprint = fingerprint
        self.slot_role = slot_role
        self.template_type = template_type


class _FakeCarouselResult:
    def __init__(self, success, content=None, error_code=""):
        self.success = success
        self.content = content
        self.error_code = error_code


def test_slot_role_and_template_type_omitted_skips_carousel_generation(tmp_path, monkeypatch):
    """FACT — 기존 호출부(둘 다 생략)는 carousel 생성 자체를 시도하지 않는다.
    Gemini 추가 호출 0회, PackageResult.carousel은 None."""
    calls = []
    monkeypatch.setattr(
        builder, "generate_carousel_content",
        lambda *a, **k: calls.append((a, k)) or _FakeCarouselResult(success=True),
    )

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is True
    assert result.carousel is None
    assert calls == []


def test_slot_role_and_template_type_given_attaches_carousel_and_fingerprint(tmp_path, monkeypatch):
    """FACT — slot_role/template_type을 둘 다 넘기면 carousel이 채워지고,
    frontmatter에 content_fingerprint/slot_role/template_type이 기록된다."""
    fake_content = _FakeCarouselContent()
    captured = {}

    def _fake_generate_carousel(topic, slot_role, template_type, **kwargs):
        captured["slot_role"] = slot_role
        captured["template_type"] = template_type
        captured["existing_fingerprints"] = kwargs.get("existing_fingerprints")
        return _FakeCarouselResult(success=True, content=fake_content)

    monkeypatch.setattr(builder, "generate_carousel_content", _fake_generate_carousel)

    result = builder.create_content_package(
        vault_root=tmp_path, slot_role="REACH", template_type="HOOK_IMPACT",
    )

    assert result.success is True
    assert result.carousel is fake_content
    assert captured["slot_role"] == "REACH"
    assert captured["template_type"] == "HOOK_IMPACT"
    assert captured["existing_fingerprints"] == set()  # 빈 Vault

    md_path, _ = builder._content_paths(result.content_id, tmp_path)
    fields = builder._parse_frontmatter(md_path.read_text(encoding="utf-8"))
    assert fields["content_fingerprint"] == "fp-abc123"
    assert fields["slot_role"] == "REACH"
    assert fields["template_type"] == "HOOK_IMPACT"


def test_carousel_generation_failure_does_not_block_existing_pipeline(tmp_path, monkeypatch):
    """RISK 대응 — Carousel 실패(예: Fail-closed)해도 기존 단일 caption+이미지
    파이프라인은 그대로 성공한다(부가 출력일 뿐, 필수 아님)."""
    monkeypatch.setattr(
        builder, "generate_carousel_content",
        lambda *a, **k: _FakeCarouselResult(success=False, error_code="POSSIBLE_FABRICATION"),
    )

    result = builder.create_content_package(
        vault_root=tmp_path, slot_role="REACH", template_type="HOOK_IMPACT",
    )

    assert result.success is True  # 기존 파이프라인은 영향 없음
    assert result.carousel is None
    md_path, img_path = builder._content_paths(result.content_id, tmp_path)
    assert md_path.exists() and img_path.exists()


def test_only_slot_role_given_without_template_type_skips_carousel(tmp_path, monkeypatch):
    """RISK 대응 — 두 값 중 하나만 주어지면(불완전한 조합) Carousel 생성을
    시도하지 않는다(추측으로 template_type을 채우지 않음)."""
    calls = []
    monkeypatch.setattr(
        builder, "generate_carousel_content",
        lambda *a, **k: calls.append((a, k)) or _FakeCarouselResult(success=True),
    )

    result = builder.create_content_package(vault_root=tmp_path, slot_role="REACH")

    assert result.success is True
    assert result.carousel is None
    assert calls == []
