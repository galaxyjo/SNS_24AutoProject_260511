"""Track B-2A/2B — source_selector.py 단위 테스트.

합성 Fixture(라벨 비일관성 재현)로 파싱을, 실제 Sourcebook 파일로 통합 스모크를 검증한다.
Airtable/Runtime 호출 없음 — 순수 파일 파싱 + 선택 로직.
"""

import pytest

from modules.sns.source_selector import (
    DEFAULT_SOURCEBOOK_PATH,
    list_selectable_topics,
    parse_sourcebook,
    select_next_topic,
)

_FIXTURE_MD = """# Fixture Sourcebook

## 3. Silicon Valley Operating Resources

### 3.1 Netflix Culture Memo

상태: VERIFIED FACT

정확한 명칭: Netflix Culture Memo

공식 URL: https://jobs.netflix.com/culture

PDF: https://jobs.netflix.com/netflix-culture.pdf

검증된 설명:
- 더미 설명

SNS 콘텐츠 핵심 메시지:
Netflix는 규칙을 늘리는 대신 뛰어난 사람에게 맥락과 책임을 준다.

주의:
절대적 표현은 사용하지 않는다.

---

### 3.2 Author Site Label Variant

상태: VERIFIED FACT

저자 사이트: https://example.com/author

SNS 콘텐츠 핵심 메시지:
저자 사이트 라벨만 있는 경우도 URL을 추출해야 한다.

---

### 3.5 Bare Bullet URL Variant

상태: VERIFIED FACT

- https://www.ycombinator.com/library
- https://www.startupschool.org/

SNS 콘텐츠 핵심 메시지:
라벨 없는 불릿 목록에서도 첫 URL을 추출해야 한다.

---

### 4.1 Community Platform No Core Message

상태: VERIFIED FACT

URL: https://www.reddit.com/

주의:
- 홍보 규칙이 Subreddit마다 다르다.

---

### 5.5 Hold Status Excluded

상태: HOLD

URL: https://www.facebook.com/groups/000000/

SNS 콘텐츠 핵심 메시지:
HOLD 상태라 선택되면 안 된다.

---
"""


@pytest.fixture
def fixture_path(tmp_path):
    p = tmp_path / "fixture_sourcebook.md"
    p.write_text(_FIXTURE_MD, encoding="utf-8")
    return p


def test_parse_sourcebook_extracts_all_sections(fixture_path):
    topics = parse_sourcebook(fixture_path)
    assert [t.topic_id for t in topics] == ["3.1", "3.2", "3.5", "4.1", "5.5"]


def test_parse_sourcebook_handles_label_variants(fixture_path):
    topics = {t.topic_id: t for t in parse_sourcebook(fixture_path)}
    assert topics["3.1"].source_url == "https://jobs.netflix.com/culture"
    assert topics["3.2"].source_url == "https://example.com/author"
    assert topics["3.5"].source_url == "https://www.ycombinator.com/library"
    assert topics["4.1"].source_url == "https://www.reddit.com/"


def test_parse_sourcebook_core_message_only_when_labeled(fixture_path):
    topics = {t.topic_id: t for t in parse_sourcebook(fixture_path)}
    assert topics["3.1"].core_message
    assert "Netflix" in topics["3.1"].core_message
    assert topics["4.1"].core_message == ""  # 커뮤니티 플랫폼 항목엔 핵심메시지 라벨 없음


def test_parse_sourcebook_pdf_line_does_not_override_official_url(fixture_path):
    topics = {t.topic_id: t for t in parse_sourcebook(fixture_path)}
    assert topics["3.1"].source_url == "https://jobs.netflix.com/culture"
    assert "netflix-culture.pdf" not in topics["3.1"].source_url


def test_list_selectable_topics_excludes_no_core_message_and_hold(fixture_path):
    topics = parse_sourcebook(fixture_path)
    selectable = list_selectable_topics(topics)
    ids = [t.topic_id for t in selectable]
    assert ids == ["3.1", "3.2", "3.5"]
    assert "4.1" not in ids  # core_message 공란
    assert "5.5" not in ids  # status=HOLD


def test_select_next_topic_skips_used_source_urls(fixture_path):
    topics = parse_sourcebook(fixture_path)
    first = select_next_topic(topics=topics)
    assert first.topic_id == "3.1"

    second = select_next_topic(used_source_urls={first.source_url}, topics=topics)
    assert second.topic_id == "3.2"


def test_select_next_topic_returns_none_when_all_used(fixture_path):
    topics = parse_sourcebook(fixture_path)
    selectable = list_selectable_topics(topics)
    used = {t.source_url for t in selectable}
    assert select_next_topic(used_source_urls=used, topics=topics) is None


def test_select_next_topic_empty_used_set_defaults_to_first(fixture_path):
    topics = parse_sourcebook(fixture_path)
    assert select_next_topic(topics=topics).topic_id == "3.1"


# ── 실제 Sourcebook 파일 통합 스모크(파일 존재·형식 드리프트 감지) ──────────

def test_default_sourcebook_path_exists():
    assert DEFAULT_SOURCEBOOK_PATH.exists()


def test_real_sourcebook_parses_without_exception_and_has_selectable_topics():
    topics = parse_sourcebook()
    assert len(topics) >= 13
    selectable = list_selectable_topics(topics)
    assert len(selectable) >= 1
    for t in selectable:
        assert t.source_url.startswith("http")
        assert t.core_message
        assert t.status in {"VERIFIED FACT", "USE_WITH_CAUTION"}
