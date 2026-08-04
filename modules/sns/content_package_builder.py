"""content_package_builder.py — Track B-6 조사 -> 글 -> 이미지 -> Vault 저장 MVP.

기존 Track B-1~4 순수 함수(select_next_topic/generate_hook_caption/
build_visual_brief+build_image_prompt/generate_image)를 조립해 Vault에
콘텐츠 패키지(.md+.png) 1건을 저장한다. Runtime 게시 경로에는 연결하지 않는다
(Track B-7 이후 별도 승인 대상).

Fail-closed 원칙(260731 회장 승인 조건, 원 설계에서 수정된 부분):
  - 이미지 생성 실패 시 .md/.png 어느 쪽도 저장하지 않는다(draft_text_only 없음).
    해당 source_url이 "사용완료"로 오인되어 이후 재시도가 영구 차단되는 것을 막기
    위함 — 다음 호출에서 같은 topic이 다시 선택 가능해야 한다.
  - .md/.png는 임시파일에 먼저 쓰고, 둘 다 성공했을 때만 최종 경로로 교체한다
    (Atomic Write). 중간 실패 시 임시파일과 이미 교체된 파일까지 모두 제거해
    부분 상태가 남지 않게 한다.
  - content_id는 topic_id+날짜+source_url 해시(stdlib hashlib, 외부 의존성 없음)로
    결정적으로 생성한다 — 같은 topic을 같은 날 재시도해도 동일 content_id가 나와
    실패 후 재시도가 자연스럽게 이어진다.
  - Frontmatter 문자열 값은 json.dumps()로 인코딩한다 — JSON 문자열은 YAML의 유효한
    double-quoted scalar이므로, 콜론/줄바꿈/따옴표가 섞여도 PyYAML 없이 stdlib만으로
    안전하게 쓰고 읽을 수 있다.
  - Vault 중복 스캔은 status: complete인 파일만 "사용완료"로 인정하고, frontmatter
    파싱이 안 되는 파일을 만나면 조용히 건너뛰지 않고 즉시 VaultScanError로 중단한다.
"""

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from modules.sns.caption_generator import generate_hook_caption
from modules.sns.image_provider_cloudflare import generate_image
from modules.sns.source_selector import select_next_topic
from modules.sns.visual_brief import build_image_prompt, build_visual_brief

DEFAULT_VAULT_ROOT = Path(__file__).resolve().parents[2] / "vault"

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_FIELD_RE = re.compile(r"^(\w+):\s*(.*)$", re.MULTILINE)


class VaultScanError(Exception):
    """Vault content/*.md frontmatter 파싱 실패 — 호출자는 즉시 중단해야 한다."""


@dataclass(frozen=True)
class PackageResult:
    success: bool
    content_id: str = ""
    status: str = ""
    error_code: str = ""


def _make_content_id(topic_id: str, source_url: str, today: str) -> str:
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:8]
    safe_topic = topic_id.replace(".", "-")
    return f"{safe_topic}-{today}-{digest}"


def _content_paths(content_id: str, vault_root: Path) -> "tuple[Path, Path]":
    md_path = vault_root / "content" / f"{content_id}.md"
    img_path = vault_root / "images" / f"{content_id}.png"
    return md_path, img_path


def _yaml_scalar(value) -> str:
    """json.dumps()로 안전 인코딩한다 — JSON 문자열은 유효한 YAML double-quoted
    scalar라서, 콜론/줄바꿈/따옴표가 포함된 값도 별도 이스케이프 없이 안전하다."""
    return json.dumps(value, ensure_ascii=False)


def _render_frontmatter(fields: dict) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _parse_frontmatter(text: str) -> "dict | None":
    """.md 파일 앞부분 --- ... --- 블록을 파싱한다. 형식이 어긋나면 None을 반환한다
    (호출자가 Fail-closed 처리하도록 예외로 승격하는 것은 scan_used_source_urls의 책임)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    fields: dict = {}
    for line_m in _FIELD_RE.finditer(m.group(1)):
        key, raw_value = line_m.group(1), line_m.group(2).strip()
        try:
            fields[key] = json.loads(raw_value)
        except (json.JSONDecodeError, ValueError):
            return None
    return fields


def scan_used_source_urls(vault_root: "Path | None" = None) -> set:
    """Vault content/*.md 중 status: complete인 항목의 source_url만 '사용완료'로 인정한다.

    frontmatter 파싱이 안 되는 파일을 만나면 조용히 건너뛰지 않고 VaultScanError를
    발생시킨다 — 반쯤 깨진 Vault 상태에서 중복 콘텐츠가 조용히 생성되는 것을 막는다.
    """
    root = vault_root or DEFAULT_VAULT_ROOT
    content_dir = root / "content"
    used: set = set()
    if not content_dir.exists():
        return used

    for md_file in sorted(content_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fields = _parse_frontmatter(text)
        if fields is None:
            raise VaultScanError(f"unparseable frontmatter: {md_file.name}")
        if fields.get("status") == "complete" and fields.get("source_url"):
            used.add(fields["source_url"])
    return used


def read_frontmatter(content_id: str, vault_root: "Path | None" = None) -> "dict | None":
    """260804 Track B 6G Producer — 지정 content_id의 .md frontmatter를 읽어
    dict로 반환한다(파일 없음/파싱 실패 시 None). `create_content_package()`는
    무수정 — 이 함수는 호출자(Producer)가 이미 만들어진 패키지의 caption/
    source_url/channel_status 등을 다시 읽기 위한 순수 조회 전용이다."""
    root = vault_root or DEFAULT_VAULT_ROOT
    md_path, _ = _content_paths(content_id, root)
    if not md_path.exists():
        return None
    return _parse_frontmatter(md_path.read_text(encoding="utf-8"))


def find_pending_channel_packages(vault_root: "Path | None" = None) -> "list[str]":
    """260804 Track B 6G Producer — Vault content/*.md 중 channel_status가
    "pending"인 전체 항목의 content_id를 파일명 정렬 순서로 반환한다(없으면
    빈 리스트). Airtable 저장이 끝까지 확정되지 않은 채 남은 패키지를 찾기
    위한 조회 전용 — 이 함수는 Airtable을 조회하지 않으므로, 반환된
    content_id들이 실제로 아직 Airtable에 없는지는 호출자가 Repository로
    별도 확인해야 한다(기존 6건처럼 Airtable 저장은 성공했지만 이 필드
    자체가 그때는 갱신 로직이 없어 "pending"으로 남아있는 오탐 사례가 실제로
    존재함 — 260804 Codex 리뷰 근거).

    260804 Codex 2차 리뷰(P0) 수정 — 이전엔 첫 1건만 반환했는데, 그 1건이
    stale(이미 Airtable에 존재)로 판정돼도 뒤에 있는 진짜 미완료 패키지를
    영영 못 찾는 문제가 있었다. 전체 목록을 반환해 호출자가 stale을
    건너뛰며 순회할 수 있게 한다."""
    root = vault_root or DEFAULT_VAULT_ROOT
    content_dir = root / "content"
    if not content_dir.exists():
        return []
    pending: list[str] = []
    for md_file in sorted(content_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fields = _parse_frontmatter(text)
        if fields is None:
            raise VaultScanError(f"unparseable frontmatter: {md_file.name}")
        if fields.get("channel_status") == "pending":
            pending.append(fields.get("content_id", ""))
    return pending


def mark_channel_status(content_id: str, new_status: str, vault_root: "Path | None" = None) -> bool:
    """260804 Track B 6G Producer — 지정 content_id의 .md frontmatter 중
    channel_status 필드만 갱신한다(다른 필드·본문 caption은 그대로 보존).
    Airtable 저장이 확정된 뒤에만 호출자가 이 함수를 호출해야 한다("pending
    → queued" 전이는 Producer의 책임, 이 함수는 파일 쓰기만 담당). 원본
    구성(create_content_package의 frontmatter+본문 렌더링)과 동일한 Atomic
    Write 패턴(tmp 파일 → os.replace)을 사용한다. 파일이 없거나 파싱 실패
    시 False를 반환하고 아무것도 쓰지 않는다."""
    root = vault_root or DEFAULT_VAULT_ROOT
    md_path, _ = _content_paths(content_id, root)
    if not md_path.exists():
        return False
    fields = _parse_frontmatter(md_path.read_text(encoding="utf-8"))
    if fields is None:
        return False

    caption = fields.get("caption", "")
    fields["channel_status"] = new_status
    new_text = _render_frontmatter(fields) + f"\n{caption}\n"

    tmp_suffix = uuid.uuid4().hex[:8]
    tmp_md = md_path.parent / f"{content_id}.md.tmp-{tmp_suffix}"
    try:
        tmp_md.write_text(new_text, encoding="utf-8")
        os.replace(tmp_md, md_path)
    except Exception:
        _cleanup(tmp_md)
        return False
    return True


def _cleanup(*paths: Path) -> None:
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


def create_content_package(
    tone_style: str = "",
    target_language: str = "EN",
    vault_root: "Path | None" = None,
    injected_topic: "object | None" = None,
    *,
    gemini_client=None,
    gemini_throttle=None,
    gemini_model=None,
) -> PackageResult:
    """260804 Track B 6G — `injected_topic`(선택, 기본 None)은 Research-to-Topic
    Adapter(`modules/sns/research_to_topic_adapter.py`)가 이미 선정·검증한
    `source_selector.SourceTopic`을 그대로 사용하고 싶을 때만 전달한다.
    생략하면(기존 모든 호출부 그대로) 이전과 100% 동일하게 내부에서
    `select_next_topic()`을 호출한다 — 이 분기 1개를 빼면 함수 나머지는
    무수정이다(기존 REUSE 원칙, Codex/GPT 감사 대상 Diff 최소화).

    260804 Codex 리뷰(P0, 계정별 Gemini Credential 격리) — `gemini_client`/
    `gemini_throttle`도 선택 인자다. 생략하면 `generate_hook_caption()`이
    전역 GEMINI_API_KEY를 그대로 쓴다(기존 동작 100% 유지). Producer가
    `injected_topic`과 함께 aijomoojin 전용 Client/Throttle을 넘기면, 이
    패키지의 Caption 생성도 그 전용 Credential로 이뤄져 전역 Key·다른 계정
    호출 간격에 전혀 영향을 주지 않는다. 이 함수는 `research_to_topic_adapter`
    를 import하지 않는다(순환 참조 방지) — 무엇을 넘길지는 호출자(launcher/
    main.py)가 결정한다.

    260805 회장 지시 — `gemini_model`도 같은 이유로 선택 인자다. 생략하면
    `generate_hook_caption()`이 기본 모델(`"gemini-2.5-flash-lite"`)을 그대로
    쓴다(기존 동작 100% 유지). aijomoojin 전용 호출부만
    `research_to_topic_adapter.RESEARCH_MODEL`을 명시 전달한다."""
    root = vault_root or DEFAULT_VAULT_ROOT
    (root / "content").mkdir(parents=True, exist_ok=True)
    (root / "images").mkdir(parents=True, exist_ok=True)

    if injected_topic is not None:
        topic = injected_topic
    else:
        try:
            used_source_urls = scan_used_source_urls(root)
        except VaultScanError:
            return PackageResult(success=False, error_code="VAULT_SCAN_ERROR")

        topic = select_next_topic(used_source_urls)
        if topic is None:
            return PackageResult(success=False, error_code="NO_SELECTABLE_TOPIC")

    today = datetime.now().strftime("%y%m%d")
    content_id = _make_content_id(topic.topic_id, topic.source_url, today)
    md_path, img_path = _content_paths(content_id, root)
    if md_path.exists() or img_path.exists():
        return PackageResult(success=False, error_code="DUPLICATE_CONTENT_ID", content_id=content_id)

    caption, hashtags = generate_hook_caption(
        topic.title, topic.core_message, topic.prohibited_expression, tone_style, target_language,
        client=gemini_client, throttle_fn=gemini_throttle, model=gemini_model,
    )
    if not caption:
        return PackageResult(success=False, error_code="CAPTION_GENERATION_FAILED")

    brief = build_visual_brief(
        topic.topic_id, topic.core_message, topic.title, topic.prohibited_expression, tone_style
    )
    image_prompt = build_image_prompt(brief)
    if image_prompt is None:
        return PackageResult(success=False, error_code="IMAGE_PROMPT_UNAVAILABLE")

    image_result = generate_image(image_prompt.prompt_text, image_prompt.negative_prompt)
    if not image_result.success:
        return PackageResult(success=False, error_code="IMAGE_GENERATION_FAILED", content_id=content_id)

    frontmatter = {
        "content_id": content_id,
        "topic_id": topic.topic_id,
        "title": topic.title,
        "source_url": topic.source_url,
        "claims": topic.core_message,
        "status": "complete",
        "caption": caption,
        "hashtags": hashtags,
        "image_path": f"images/{content_id}.png",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "channel_status": "pending",
    }
    md_text = _render_frontmatter(frontmatter) + f"\n{caption}\n"

    tmp_suffix = uuid.uuid4().hex[:8]
    tmp_md = md_path.parent / f"{content_id}.md.tmp-{tmp_suffix}"
    tmp_img = img_path.parent / f"{content_id}.png.tmp-{tmp_suffix}"

    try:
        tmp_md.write_text(md_text, encoding="utf-8")
        tmp_img.write_bytes(image_result.image_bytes)
        os.replace(tmp_md, md_path)
        os.replace(tmp_img, img_path)
    except Exception:
        _cleanup(tmp_md, tmp_img)
        # md_path가 먼저 교체된 뒤 img_path 교체가 실패한 경우까지 대비해
        # 완성되지 않은 짝은 항상 함께 제거한다(부분 파일 금지).
        if md_path.exists() and not img_path.exists():
            _cleanup(md_path)
        elif img_path.exists() and not md_path.exists():
            _cleanup(img_path)
        return PackageResult(success=False, error_code="ATOMIC_WRITE_FAILED", content_id=content_id)

    return PackageResult(success=True, content_id=content_id, status="complete")
