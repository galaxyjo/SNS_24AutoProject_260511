"""source_selector.py — Track B Source Pipeline: Sourcebook 파싱 + Topic 선택.

docs/design/SNS_AI_STARTUP_CONTENT_SOURCEBOOK_260723.md을 파싱해 Track B 콘텐츠
생성에 사용할 Topic(출처 URL + 핵심 메시지가 고정된 단위)을 선택한다.

Airtable 조회는 하지 않는다 — 이미 사용된 source_url 집합은 호출자가 전달한다
(Track B-2A Source Contract Lock, 260731). Runtime 게시 파이프라인 연결은 Track B
순서 6(별도 승인 대상)에서 다룬다.

데이터 계약(Track B-2A 확정):
  topic_id / title / status / source_url / core_message / prohibited_expression
"""

import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SOURCEBOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs" / "design" / "SNS_AI_STARTUP_CONTENT_SOURCEBOOK_260723.md"
)

# 문서 내 URL 라벨이 항목마다 다름(260731 실측: 공식 URL / 저자 사이트 / 공식 예시 URL / URL) — 우선순위 순.
_URL_LABELS = ["공식 URL", "공식 예시 URL", "URL", "저자 사이트"]

_SECTION_SPLIT_RE = re.compile(r"^### (\d+\.\d+) (.+)$", re.MULTILINE)
_STATUS_RE = re.compile(r"^상태:\s*(.+)$", re.MULTILINE)
_LABEL_URL_RE = re.compile(
    r"^(?:" + "|".join(re.escape(l) for l in _URL_LABELS) + r"):\s*(https?://\S+)",
    re.MULTILINE,
)
_BARE_URL_RE = re.compile(r"^-?\s*(https?://\S+)", re.MULTILINE)
_CORE_MESSAGE_RE = re.compile(
    r"^SNS 콘텐츠 핵심 메시지:\s*\n+(.+?)(?:\n\s*\n|\n주의|\n사용 금지|\Z)",
    re.MULTILINE | re.DOTALL,
)
_PROHIBITED_INLINE_RE = re.compile(r"^(?:주의|사용 금지 표현):\s*(\S.*)$", re.MULTILINE)
_PROHIBITED_BLOCK_RE = re.compile(
    r"^주의:\s*\n+(.+?)(?:\n\s*\n|\Z)", re.MULTILINE | re.DOTALL
)

VALID_STATUSES = {"VERIFIED FACT", "USE_WITH_CAUTION"}
HOLD_STATUS = "HOLD"


@dataclass(frozen=True)
class SourceTopic:
    topic_id: str
    title: str
    status: str
    source_url: str
    core_message: str
    prohibited_expression: str


def _extract_url(body: str) -> str:
    m = _LABEL_URL_RE.search(body)
    if m:
        return m.group(1).strip()
    m = _BARE_URL_RE.search(body)
    if m:
        return m.group(1).strip()
    return ""


def _extract_core_message(body: str) -> str:
    m = _CORE_MESSAGE_RE.search(body)
    if not m:
        return ""
    return " ".join(line.strip() for line in m.group(1).splitlines() if line.strip())


def _extract_prohibited(body: str) -> str:
    m = _PROHIBITED_INLINE_RE.search(body)
    if m:
        return m.group(1).strip()
    m = _PROHIBITED_BLOCK_RE.search(body)
    if m:
        return " ".join(line.strip() for line in m.group(1).splitlines() if line.strip())
    return ""


def parse_sourcebook(path: "Path | None" = None) -> list[SourceTopic]:
    """Sourcebook을 섹션(### N.M 제목) 단위로 파싱한다.

    필드를 못 찾으면 빈 문자열로 남긴다 — Fail-closed 판단(선택 가능 여부)은
    list_selectable_topics()가 수행하며, 이 함수는 원문 추출만 한다.
    """
    target = Path(path) if path else DEFAULT_SOURCEBOOK_PATH
    text = target.read_text(encoding="utf-8")

    matches = list(_SECTION_SPLIT_RE.finditer(text))
    topics: list[SourceTopic] = []
    for i, m in enumerate(matches):
        topic_id = m.group(1)
        title = m.group(2).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]

        status_m = _STATUS_RE.search(body)
        status = status_m.group(1).strip() if status_m else ""

        topics.append(
            SourceTopic(
                topic_id=topic_id,
                title=title,
                status=status,
                source_url=_extract_url(body),
                core_message=_extract_core_message(body),
                prohibited_expression=_extract_prohibited(body),
            )
        )
    return topics


def list_selectable_topics(topics: "list[SourceTopic] | None" = None) -> list[SourceTopic]:
    """Track B 콘텐츠 생성에 실제로 사용 가능한 Topic만 반환한다(Fail-closed 필터).

    제외 조건: status가 VALID_STATUSES에 없음(HOLD 등 미확인 상태 포함) / source_url 공란 /
    core_message 공란(현재 Sourcebook 구조상 3.x 참고자료 항목만 core_message를 가짐 —
    4.x/5.x 커뮤니티 플랫폼 항목은 이 필터에서 자연스럽게 제외됨, 260731 실측 확인).
    """
    source = topics if topics is not None else parse_sourcebook()
    return [
        t for t in source
        if t.status in VALID_STATUSES and t.source_url and t.core_message
    ]


def select_next_topic(
    used_source_urls: "set[str] | None" = None,
    topics: "list[SourceTopic] | None" = None,
) -> "SourceTopic | None":
    """이미 사용된 source_url을 제외하고 다음 선택 가능한 Topic 1개를 반환한다.

    중복 기준은 source_url(Track B-2A 확정 — 이 Sourcebook 구조상 항목당 URL 1개:
    핵심메시지 1개가 1:1이라 topic_id/source_url이 사실상 동일 단위). Airtable 조회는
    하지 않는다 — used_source_urls는 호출자가 Runtime에서 조회해 전달한다.
    """
    used = used_source_urls or set()
    for t in list_selectable_topics(topics):
        if t.source_url not in used:
            return t
    return None
