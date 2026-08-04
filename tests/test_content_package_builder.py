"""Track B-6 — content_package_builder.py 단위 테스트.

Track B-1~4 순수 함수는 전부 mock 처리한다(실제 Gemini/Cloudflare 호출 없음).
검증 대상은 조립 로직 + Fail-closed 경계 + Atomic Write뿐이다.
"""

import json

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
    monkeypatch.setattr(builder, "select_next_topic", lambda used: _fake_topic())
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
    monkeypatch.setattr(builder, "select_next_topic", lambda used: None)

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
    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    complete_fields = {
        "content_id": "3-1-260731-aaaaaaaa",
        "source_url": "https://example.com/complete",
        "status": "complete",
    }
    incomplete_fields = {
        "content_id": "3-2-260731-bbbbbbbb",
        "source_url": "https://example.com/incomplete",
        "status": "some_other_status",
    }
    (content_dir / "a.md").write_text(builder._render_frontmatter(complete_fields), encoding="utf-8")
    (content_dir / "b.md").write_text(builder._render_frontmatter(incomplete_fields), encoding="utf-8")

    used = builder.scan_used_source_urls(tmp_path)

    assert used == {"https://example.com/complete"}


def test_yaml_scalar_round_trips_colons_quotes_and_newlines():
    tricky = 'title: "Netflix" says\nline two'
    rendered = builder._yaml_scalar(tricky)
    assert json.loads(rendered) == tricky


# ── 260804 Track B 6G — injected_topic(Research-to-Topic Adapter 연동) ────

def test_injected_topic_bypasses_select_next_topic_and_scan(tmp_path, monkeypatch):
    """injected_topic이 주어지면 select_next_topic()/scan_used_source_urls()를
    전혀 호출하지 않는다(Adapter가 이미 검증까지 끝낸 Topic이므로 재선택 불필요)."""
    monkeypatch.setattr(builder, "select_next_topic", lambda used: pytest.fail("호출되면 안 됨"))
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
                                    tone_style="", target_language="EN", *, client=None, throttle_fn=None):
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


def test_no_gemini_override_keeps_default_none(tmp_path, monkeypatch):
    """gemini_client/gemini_throttle을 생략하면(기존 모든 호출부) None이 그대로
    전달돼 generate_hook_caption() 내부에서 전역 Client/Throttle을 쓰게 된다."""
    captured = {}

    def _spy_generate_hook_caption(title, core_message, prohibited_expression="",
                                    tone_style="", target_language="EN", *, client=None, throttle_fn=None):
        captured["client"] = client
        captured["throttle_fn"] = throttle_fn
        return "caption text", "#tag"

    monkeypatch.setattr(builder, "generate_hook_caption", _spy_generate_hook_caption)

    result = builder.create_content_package(vault_root=tmp_path)

    assert result.success is True
    assert captured["client"] is None
    assert captured["throttle_fn"] is None
