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

from modules.common.logger import get_logger
from modules.sns.caption_generator import generate_hook_caption
from modules.sns.carousel_content_builder import (
    generate_carousel_content,
    scan_existing_fingerprints,
)
from modules.sns.hero_card_content_builder import generate_hero_card_content
from modules.sns.image_provider_cloudflare import generate_image
from modules.sns.image_template_renderer import HeroBlock, HeroCardContent, render_hero_card
from modules.sns.source_selector import parse_sourcebook, select_next_topic
from modules.sns.visual_brief import build_background_only_prompt, build_image_prompt, build_visual_brief

logger = get_logger(__name__)

_HERO_ICON_SEQUENCE = ("target", "search", "gear", "graph")

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
    # 260805 Track B 7B-3 Carousel Canary — 선택적 부가 출력. `slot_role`/
    # `template_type`을 호출자가 넘길 때만 채워진다(기본 None, 기존 호출부·
    # 기존 테스트는 100% 무변화). 이 필드가 비어 있어도 위 4개 필드 기반의
    # 기존 파이프라인(단일 caption+이미지+Vault)은 그대로 동작한다 —
    # Instagram 게시·Airtable 저장 경로는 이 필드를 아직 읽지 않는다
    # (Runtime 미연결, 별도 승인 후 연결).
    carousel: "object | None" = None


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
    """Vault content/*.md 중 status: complete이고 오늘(로컬 날짜) 생성된 항목의
    source_url만 '오늘 사용완료'로 인정한다.

    260805 회장 지시(Sourcebook SSOT 복구) — 기존에는 한 번이라도 complete된
    source_url이 영구히 재선택 대상에서 빠졌다. Sourcebook 원천이 한정적이라
    "URL당 평생 1회"로는 며칠 안에 소진돼 지속 활용이 불가능해지므로, "URL당
    하루 1회"로 재정의한다 — 같은 원천을 다른 날 다시 골라 새 콘텐츠(같은
    core_message라도 매 호출 새로 생성되는 캡션)를 만들 수 있다. 같은 날 안에서는
    여전히 제외되므로 같은 슬롯 회차 안에서의 중복 선택은 막힌다. 완전한 동일
    콘텐츠 재생성 방지는 `create_content_package()`의 기존 `DUPLICATE_CONTENT_ID`
    검사(topic_id+오늘 날짜+source_url 해시로 결정적 content_id 생성)가 그대로
    담당한다 — 이 함수는 "오늘 이미 만들었는지"만 판단한다.

    frontmatter 파싱이 안 되는 파일을 만나면 조용히 건너뛰지 않고 VaultScanError를
    발생시킨다 — 반쯤 깨진 Vault 상태에서 중복 콘텐츠가 조용히 생성되는 것을 막는다.
    """
    root = vault_root or DEFAULT_VAULT_ROOT
    content_dir = root / "content"
    used: set = set()
    if not content_dir.exists():
        return used

    today = datetime.now().strftime("%Y-%m-%d")
    for md_file in sorted(content_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fields = _parse_frontmatter(text)
        if fields is None:
            raise VaultScanError(f"unparseable frontmatter: {md_file.name}")
        created_at = fields.get("created_at") or ""
        if (
            fields.get("status") == "complete"
            and fields.get("source_url")
            and created_at.startswith(today)
        ):
            used.add(fields["source_url"])
    return used


def scan_source_url_last_used(vault_root: "Path | None" = None) -> dict:
    """260805 회장 지시(Sourcebook 전체 항목 순환 보완) — Vault 전체(오늘 제한
    없음)에서 source_url별 가장 최근 `created_at`(ISO 문자열)을 반환한다. 한
    번도 안 쓰인 URL은 키 자체가 없다(호출자가 `.get(url, "")`로 처리 — 빈
    문자열은 문자열 비교상 항상 가장 먼저 정렬돼 "한 번도 안 쓴 것 우선"이
    자연히 성립한다).

    `scan_used_source_urls()`(오늘만 집계, 같은 날 중복선택 방지용)와는 목적이
    다르다 — 이 함수는 날짜 제한 없이 "가장 오래전에 썼거나 아예 안 쓴 원천"을
    찾아 Sourcebook 전체를 순환시키는 정렬 기준으로만 쓰인다(회전 우선순위,
    차단 목적 아님).
    """
    root = vault_root or DEFAULT_VAULT_ROOT
    content_dir = root / "content"
    history: dict = {}
    if not content_dir.exists():
        return history

    for md_file in sorted(content_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fields = _parse_frontmatter(text)
        if fields is None:
            raise VaultScanError(f"unparseable frontmatter: {md_file.name}")
        if fields.get("status") != "complete" or not fields.get("source_url"):
            continue
        url = fields["source_url"]
        created_at = fields.get("created_at") or ""
        if created_at > history.get(url, ""):
            history[url] = created_at
    return history


def scan_captions_for_source_url(source_url: str, vault_root: "Path | None" = None) -> set:
    """260805 회장 지시(콘텐츠 지문 기반 중복방지 보완) — 같은 `source_url`로
    이미 생성된 모든 caption 텍스트(공백만 strip, 그 외 정규화 없음)를
    반환한다. `create_content_package()`가 새로 생성한 caption이 이 집합에
    포함되면 완전히 동일한 문장이 재생성된 것으로 판정해 저장을 막는다
    (원천+콘텐츠 지문 조합의 최소 구현 — 신규 유사도 엔진 없이 정확 일치만
    본다, 근사 유사도 검사는 이번 범위 밖).
    """
    root = vault_root or DEFAULT_VAULT_ROOT
    content_dir = root / "content"
    captions: set = set()
    if not content_dir.exists():
        return captions

    for md_file in sorted(content_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fields = _parse_frontmatter(text)
        if fields is None:
            raise VaultScanError(f"unparseable frontmatter: {md_file.name}")
        if fields.get("source_url") == source_url and fields.get("caption"):
            captions.add(fields["caption"].strip())
    return captions


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


def _build_hero_card_image(topic, brief, *, client=None, throttle_fn=None, model=None) -> "bytes | None":
    """260811 Visual Type Wiring — 텍스트 생성(hero_card_content_builder)+
    텍스트없는 AI배경(visual_brief.build_background_only_prompt+generate_image)+
    Pillow 렌더링(render_hero_card)을 순서대로 실행한다. 어느 단계든 실패하면
    None을 반환한다(호출자가 IMAGE_GENERATION_FAILED로 Fail-closed, 원본 Flux
    이미지로 조용히 폴백하지 않는다)."""
    text_result = generate_hero_card_content(topic, client=client, throttle_fn=throttle_fn, model=model)
    if not text_result.success:
        logger.warning(
            f"[HeroCardImage] 텍스트 생성 단계 실패 | stage=text | error_code={text_result.error_code}"
        )
        return None

    bg_prompt = build_background_only_prompt(brief)
    if bg_prompt is None:
        logger.warning(
            "[HeroCardImage] 배경 프롬프트 생성 단계 실패 | stage=bg_prompt | "
            "error_code=EMPTY_CORE_MESSAGE"
        )
        return None
    bg_result = generate_image(bg_prompt.prompt_text, bg_prompt.negative_prompt)
    if not bg_result.success:
        logger.warning(
            f"[HeroCardImage] 배경 이미지 생성 단계 실패 | stage=bg_image | error_code={bg_result.error_code}"
        )
        return None

    text_content = text_result.content
    blocks = tuple(
        HeroBlock(icon, b.title, b.desc)
        for icon, b in zip(_HERO_ICON_SEQUENCE, text_content.blocks)
    )
    hero_content = HeroCardContent(
        headline=text_content.headline,
        subheadline=text_content.subheadline,
        blocks=blocks,
        tagline=text_content.tagline,
        source_label=topic.title,
        ai_background=bg_result.image_bytes,
    )
    try:
        return render_hero_card(hero_content)
    except (ValueError, OSError) as exc:
        # 260811 Codex 리뷰(P1) — ValueError는 render_hero_card() 자체의 필드
        # 검증 실패지만, generate_image()가 success=True를 반환해도 손상된
        # 이미지 bytes를 줄 수 있다. 그 경우 PIL.Image.open()이 손상된
        # 이미지에서 UnidentifiedImageError(OSError 하위클래스)를 낸다 — 이걸
        # 잡지 않으면 예외가 create_content_package() 밖 자동 파이프라인까지
        # 전파돼 Job 전체가 죽는다. 두 예외 모두 동일하게 Fail-closed(None
        # 반환 → 호출자가 IMAGE_GENERATION_FAILED로 안전하게 종료).
        logger.warning(
            f"[HeroCardImage] 렌더링 단계 실패 | stage=render | "
            f"error_type={type(exc).__name__} | error={exc}"
        )
        return None


def create_content_package(
    tone_style: str = "",
    target_language: str = "EN",
    vault_root: "Path | None" = None,
    injected_topic: "object | None" = None,
    *,
    gemini_client=None,
    gemini_throttle=None,
    gemini_model=None,
    slot_role: "str | None" = None,
    template_type: "str | None" = None,
    hero_card_enabled: bool = False,
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
    `research_to_topic_adapter.RESEARCH_MODEL`을 명시 전달한다.

    260805 Track B 7B-3 Carousel Canary — `slot_role`/`template_type`도
    선택 인자다(둘 다 기본 None). 생략하면(기존 모든 호출부 그대로) 8-Slide
    카드뉴스 생성은 전혀 시도되지 않고, 반환되는 `PackageResult.carousel`은
    `None`이며 나머지 동작(단일 caption+이미지+Vault 저장)은 100% 이전과
    동일하다. 둘 다 주어지면 기존 단일 caption 파이프라인은 그대로 진행하되,
    `carousel_content_builder.generate_carousel_content()`를 부가로 1회 호출해
    성공 시 `PackageResult.carousel`과 frontmatter의 `content_fingerprint`
    필드를 채운다 — 실패해도 기존 파이프라인 성공 여부에는 영향을 주지
    않는다(Best-effort 부가 출력, Instagram 게시·Airtable 저장 경로는 아직
    이 필드를 읽지 않는다 — Runtime 미연결).

    260811 Visual Type Wiring — `hero_card_enabled`도 선택 인자다(기본
    False). 생략하거나 False면(기존 모든 호출부 그대로) 이미지 생성은 기존과
    100% 동일하게 `build_image_prompt()`+`generate_image()`(원본 Flux 단일
    이미지)로 진행한다. True면 대신 `hero_card_content_builder.
    generate_hero_card_content()`(이미지 전용 구조화 텍스트)+
    `build_background_only_prompt()`+`generate_image()`(텍스트없는 AI배경)+
    `render_hero_card()`(Pillow로 실제 텍스트 렌더링)로 대체한다. 이 경로가
    실패하면(텍스트 생성 실패/배경 생성 실패/렌더 검증 실패 어느 단계든)
    원본 Flux로 조용히 폴백하지 않고 기존과 동일한 `IMAGE_GENERATION_FAILED`로
    Fail-closed한다(실패를 숨기지 않는다, CLAUDE.md 9.1)."""
    root = vault_root or DEFAULT_VAULT_ROOT
    (root / "content").mkdir(parents=True, exist_ok=True)
    (root / "images").mkdir(parents=True, exist_ok=True)

    if injected_topic is not None:
        topic = injected_topic
    else:
        try:
            used_source_urls = scan_used_source_urls(root)
            last_used = scan_source_url_last_used(root)
        except VaultScanError:
            return PackageResult(success=False, error_code="VAULT_SCAN_ERROR")

        # 260805 회장 지시(Sourcebook 전체 항목 순환 보완) — 파싱 순서 그대로면
        # "오늘 사용 안 됨" 조건을 만족하는 첫 항목(대개 3.1)이 매일 반복
        # 선택돼 뒤쪽 항목이 영영 선택되지 않는다. 후보를 "가장 오래전에
        # 썼거나 아예 안 쓴" 순으로 정렬한 뒤 select_next_topic()에 넘겨,
        # 그 함수의 기존 로직("주어진 순서에서 첫 미사용 항목 선택")은 그대로
        # 두고 순서만 바꿔 전체 Sourcebook이 돌아가게 한다.
        ordered_topics = sorted(parse_sourcebook(), key=lambda t: last_used.get(t.source_url, ""))
        topic = select_next_topic(used_source_urls, ordered_topics)
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

    # 260805 회장 지시(콘텐츠 지문 기반 중복방지 보완) — 원천 재사용을 허용한
    # 만큼, 같은 원천에서 이전과 완전히 동일한 caption 문장이 다시 나오면
    # 저장하지 않는다(정확 일치만 검사, 신규 유사도 엔진 없음).
    try:
        existing_captions = scan_captions_for_source_url(topic.source_url, root)
    except VaultScanError:
        return PackageResult(success=False, error_code="VAULT_SCAN_ERROR")
    if caption.strip() in existing_captions:
        return PackageResult(success=False, error_code="DUPLICATE_CAPTION_TEXT")

    brief = build_visual_brief(
        topic.topic_id, topic.core_message, topic.title, topic.prohibited_expression, tone_style
    )

    if hero_card_enabled:
        # 260811 Codex 리뷰(P2, 알려진 범위 밖) — hero_card_content_builder의
        # content_fingerprint는 계산만 되고 여기서는 아직 쓰이지 않는다.
        # scan_existing_fingerprints()는 carousel과 같은 frontmatter 필드
        # (`content_fingerprint`)를 읽으므로, 두 기능이 같은 호출에서 동시에
        # 켜지면(carousel용 slot_role/template_type + hero_card_enabled 동시
        # 사용) 어느 한쪽이 그 필드를 덮어써 나머지 dedup이 무력화될 수 있다
        # — 별도 필드명 설계가 필요해 이번 범위에서는 의도적으로 보류한다.
        # 지금은 수동 Canary 1건 검증이 목적이라 중복게시 위험이 낮다(운영자가
        # 직접 트리거·확인). 자동 슬롯 반영 전 별도 승인·설계 필요.
        image_bytes = _build_hero_card_image(
            topic, brief,
            client=gemini_client, throttle_fn=gemini_throttle, model=gemini_model,
        )
        if image_bytes is None:
            return PackageResult(success=False, error_code="IMAGE_GENERATION_FAILED", content_id=content_id)
    else:
        image_prompt = build_image_prompt(brief)
        if image_prompt is None:
            return PackageResult(success=False, error_code="IMAGE_PROMPT_UNAVAILABLE")

        image_result = generate_image(image_prompt.prompt_text, image_prompt.negative_prompt)
        if not image_result.success:
            return PackageResult(success=False, error_code="IMAGE_GENERATION_FAILED", content_id=content_id)
        image_bytes = image_result.image_bytes

    # 260805 Track B 7B-3 Carousel Canary — 선택적 부가 생성. slot_role/
    # template_type 둘 다 없으면 이 블록 전체를 건너뛴다(기존 호출부는
    # carousel=None 그대로, Gemini 추가 호출 0회).
    carousel = None
    if slot_role is not None and template_type is not None:
        try:
            existing_fingerprints = scan_existing_fingerprints(root)
        except VaultScanError:
            existing_fingerprints = set()
        carousel_result = generate_carousel_content(
            topic, slot_role, template_type,
            client=gemini_client, throttle_fn=gemini_throttle, model=gemini_model,
            existing_fingerprints=existing_fingerprints,
        )
        if carousel_result.success:
            carousel = carousel_result.content

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
    if carousel is not None:
        frontmatter["content_fingerprint"] = carousel.content_fingerprint
        frontmatter["slot_role"] = carousel.slot_role
        frontmatter["template_type"] = carousel.template_type
    md_text = _render_frontmatter(frontmatter) + f"\n{caption}\n"

    tmp_suffix = uuid.uuid4().hex[:8]
    tmp_md = md_path.parent / f"{content_id}.md.tmp-{tmp_suffix}"
    tmp_img = img_path.parent / f"{content_id}.png.tmp-{tmp_suffix}"

    try:
        tmp_md.write_text(md_text, encoding="utf-8")
        tmp_img.write_bytes(image_bytes)
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

    return PackageResult(success=True, content_id=content_id, status="complete", carousel=carousel)
