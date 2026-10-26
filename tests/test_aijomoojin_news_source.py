"""tests/test_aijomoojin_news_source.py — 261022 STEP 4-G 미국 AI 뉴스 원천(B안) 검증.

A: Flag OFF → create_content_package 인자가 기존과 같고 뉴스 경로 호출 0회.
B: 72시간·AI 키워드·최신 1건 선택.
C: Vault(날짜 무관 이력)·Airtable 중복 제외.
D: 중복 이력 확인 불가 → NEWS_DEDUP_UNAVAILABLE, Gemini 0회, Sourcebook으로 진행.
E: 429 소진(분석·Safety) → NEWS_QUOTA, create_content_package 0회, Slack 1회.
F: 500/503/timeout 소진 → NEWS_URL_FAIL(QUOTA 아님).
G: Safety UNSAFE → NEWS_SAFETY.
H: 실패 코드에서 Sourcebook Fallback / 14.x 피드는 선택 가능 Topic이 아님.
I: 실제 Producer가 뉴스 Topic을 injected_topic으로 넘기고 frontmatter에 게시시각을 남긴다.

실제 피드·Gemini·Airtable 호출 없음 — 전부 Fake.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types

import modules.infra.airtable_repository  # noqa: F401
import launcher.main  # noqa: F401

import modules.common.producer_lock as producer_lock
import modules.sns.content_package_builder as cpb
import modules.sns.research_to_topic_adapter as adapter
from modules.sns.source_selector import SourceTopic, list_selectable_topics, parse_sourcebook

AIJOMOOJIN = "IDN-000036"
NOW = datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)

_SOURCEBOOK = """# test sourcebook

### 3.1 Existing Topic
상태: VERIFIED FACT
공식 URL: https://example.com/existing

SNS 콘텐츠 핵심 메시지:

기존 메시지

### 14.1 Feed One
URL: https://feed.example/one.xml

### 14.2 Feed Two
URL: https://feed.example/two.xml
"""


@pytest.fixture(autouse=True)
def _isolated_lock_db(tmp_path, monkeypatch):
    monkeypatch.setattr(producer_lock, "_DB_PATH", tmp_path / "producer_lock.db")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(adapter, "_throttle", lambda: None)
    monkeypatch.setattr(adapter.time, "sleep", lambda s: None)


@pytest.fixture
def sourcebook(tmp_path):
    path = tmp_path / "sourcebook.md"
    path.write_text(_SOURCEBOOK, encoding="utf-8")
    return path


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "content").mkdir(parents=True)
    return root


def _item(title, link, hours_ago):
    return {"title": title, "link": link, "published": NOW - timedelta(hours=hours_ago)}


def _fetch_from(mapping):
    def _fetch(url):
        value = mapping[url]
        if isinstance(value, Exception):
            raise value
        return value
    return _fetch


class _Repo:
    def __init__(self, known=frozenset(), raises=None):
        self.known, self.raises, self.checks = known, raises, []

    def find_account_post_by_source_url(self, account_code_ref, source_url):
        self.checks.append((account_code_ref, source_url))
        if self.raises:
            raise self.raises
        return source_url in self.known


def _select(repo, sourcebook, vault, mapping):
    return adapter.select_news_candidate(
        AIJOMOOJIN, repo, sourcebook_path=sourcebook, vault_root=vault, now=NOW, fetch=_fetch_from(mapping),
    )


def _write_vault_package(vault, content_id, source_url, created_at="2026-09-01T00:00:00"):
    fields = {"content_id": content_id, "topic_id": "14.1", "title": "t", "source_url": source_url,
              "claims": "m", "status": "complete", "caption": "c", "hashtags": "#x",
              "image_path": f"images/{content_id}.png", "created_at": created_at}
    (vault / "content" / f"{content_id}.md").write_text(cpb._render_frontmatter(fields) + "\nc\n", encoding="utf-8")


def _candidate(url="https://news.example/a"):
    return SourceTopic(topic_id="14.1", title="OpenAI ships new agent tool", status="NEWS", source_url=url,
                       core_message="", prohibited_expression="",
                       source_published_at="2026-10-22T20:00:00+00:00")


# ── B: 72시간·키워드·최신 1건 ─────────────────────────────────────────────

class TestCandidateSelection:
    def test_newest_fresh_ai_item_wins(self, sourcebook, vault):
        mapping = {
            "https://feed.example/one.xml": [
                _item("OpenAI launches new GPT agent", "https://news.example/older", 10),
                _item("Old AI model news", "https://news.example/too-old", 80),
            ],
            "https://feed.example/two.xml": [
                _item("Anthropic Claude update for teams", "https://news.example/newest", 2),
                _item("Stock market closes higher", "https://news.example/not-ai", 1),
            ],
        }
        repo = _Repo()
        topic, code = _select(repo, sourcebook, vault, mapping)

        assert code == "NEWS_CANDIDATE"
        assert topic.source_url == "https://news.example/newest"
        assert topic.topic_id == "14.2"
        assert topic.status == "NEWS"
        assert topic.source_published_at == (NOW - timedelta(hours=2)).isoformat(timespec="seconds")
        assert repo.checks == [(AIJOMOOJIN, "https://news.example/newest")]

    def test_no_fresh_ai_item_returns_no_candidate(self, sourcebook, vault):
        mapping = {
            "https://feed.example/one.xml": [_item("AI news", "https://news.example/old", 73)],
            "https://feed.example/two.xml": [_item("Weather today", "https://news.example/w", 1)],
        }
        assert _select(_Repo(), sourcebook, vault, mapping) == (None, "NEWS_NO_CANDIDATE")

    def test_all_feeds_failing_returns_feed_error(self, sourcebook, vault):
        mapping = {"https://feed.example/one.xml": RuntimeError("down"),
                   "https://feed.example/two.xml": RuntimeError("down")}
        assert _select(_Repo(), sourcebook, vault, mapping) == (None, "NEWS_FEED_ERROR")

    def test_one_feed_failing_still_uses_the_other(self, sourcebook, vault):
        mapping = {"https://feed.example/one.xml": RuntimeError("down"),
                   "https://feed.example/two.xml": [_item("New AI tool", "https://news.example/ok", 3)]}
        topic, code = _select(_Repo(), sourcebook, vault, mapping)
        assert code == "NEWS_CANDIDATE" and topic.source_url == "https://news.example/ok"


# ── C: 날짜 무관 중복 제외 ──────────────────────────────────────────────

class TestDedupe:
    def test_vault_history_from_previous_days_is_excluded(self, sourcebook, vault):
        _write_vault_package(vault, "old-news", "https://news.example/newest", created_at="2026-09-01T00:00:00")
        mapping = {
            "https://feed.example/one.xml": [_item("New AI agent", "https://news.example/second", 5)],
            "https://feed.example/two.xml": [_item("AI model news", "https://news.example/newest", 1)],
        }
        repo = _Repo()
        topic, code = _select(repo, sourcebook, vault, mapping)
        assert code == "NEWS_CANDIDATE"
        assert topic.source_url == "https://news.example/second"
        assert (AIJOMOOJIN, "https://news.example/newest") not in repo.checks

    def test_airtable_existing_post_is_excluded(self, sourcebook, vault):
        mapping = {
            "https://feed.example/one.xml": [_item("New AI agent", "https://news.example/second", 5)],
            "https://feed.example/two.xml": [_item("AI model news", "https://news.example/newest", 1)],
        }
        repo = _Repo(known={"https://news.example/newest"})
        topic, code = _select(repo, sourcebook, vault, mapping)
        assert code == "NEWS_CANDIDATE"
        assert topic.source_url == "https://news.example/second"
        assert [c[1] for c in repo.checks] == ["https://news.example/newest", "https://news.example/second"]


    def test_eleventh_item_selected_when_top_ten_already_posted(self, sourcebook, vault):
        """상위 10건이 모두 Airtable에 있으면 11번째 신규 후보를 고른다(조회 개수 상한 없음)."""
        items = [_item(f"New AI tool {i}", f"https://news.example/{i}", i) for i in range(1, 12)]
        mapping = {"https://feed.example/one.xml": items, "https://feed.example/two.xml": []}
        repo = _Repo(known={f"https://news.example/{i}" for i in range(1, 11)})
        topic, code = _select(repo, sourcebook, vault, mapping)
        assert code == "NEWS_CANDIDATE"
        assert topic.source_url == "https://news.example/11"
        assert len(repo.checks) == 11


# ── D: 중복 이력 확인 불가 ──────────────────────────────────────────────

class TestDedupeUnavailable:
    _MAPPING = {"https://feed.example/one.xml": [_item("New AI tool", "https://news.example/a", 1)],
                "https://feed.example/two.xml": []}

    def test_vault_scan_exception(self, sourcebook, vault, monkeypatch):
        def _boom(root=None):
            raise cpb.VaultScanError("bad frontmatter")
        monkeypatch.setattr(cpb, "scan_source_url_last_used", _boom)
        assert _select(_Repo(), sourcebook, vault, self._MAPPING) == (None, "NEWS_DEDUP_UNAVAILABLE")

    def test_missing_vault_content_dir(self, sourcebook, tmp_path):
        missing = tmp_path / "no-vault"
        assert _select(_Repo(), sourcebook, missing, self._MAPPING) == (None, "NEWS_DEDUP_UNAVAILABLE")

    def test_airtable_lookup_exception(self, sourcebook, vault):
        repo = _Repo(raises=RuntimeError("airtable down"))
        assert _select(repo, sourcebook, vault, self._MAPPING) == (None, "NEWS_DEDUP_UNAVAILABLE")


# ── E/F/G: 분석 단계 오류 계약 ─────────────────────────────────────────

class _FakeModels:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


_FACTS = [
    {"type": "feature", "fact": "에이전트가 이메일 답장을 대신 작성한다.",
     "evidence_quote": "The agent drafts email replies for you."},
    {"type": "number", "fact": "요금은 월 20달러다.", "evidence_quote": "It costs $20 per month."},
    {"type": "condition", "fact": "미국 사용자에게 먼저 제공된다.",
     "evidence_quote": "It is available first to users in the US."},
]


def _ok_response(url, relevant=True, core="새 에이전트 도구로 업무를 자동화할 수 있다.", facts=_FACTS):
    import json
    meta = SimpleNamespace(url_metadata=[SimpleNamespace(
        retrieved_url=url, url_retrieval_status=genai_types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS)])
    return SimpleNamespace(
        candidates=[SimpleNamespace(url_context_metadata=meta)],
        text=json.dumps({"relevant": relevant, "source_title": "New agent tool", "core_message": core,
                         "key_facts": facts}),
    )


def _api_error(code):
    return genai_errors.APIError(code, {"error": {"code": code, "message": "x", "status": "X"}})


def _patch_client(monkeypatch, outcomes, safety=("SAFE", "")):
    models = _FakeModels(outcomes)
    monkeypatch.setattr(adapter, "_get_client", lambda: SimpleNamespace(models=models))
    safety_calls = []
    monkeypatch.setattr(adapter, "check_caption_safety",
                        lambda text, **k: (safety_calls.append(text), safety)[1])
    return models, safety_calls


class TestAnalyzeContract:
    def test_success_returns_verified_topic(self, monkeypatch):
        cand = _candidate()
        _patch_client(monkeypatch, [_ok_response(cand.source_url)])
        topic, code = adapter.analyze_news_url(cand)
        assert code == "NEWS_READY"
        assert topic.status == "VERIFIED FACT"
        assert topic.core_message and topic.source_url == cand.source_url
        assert topic.source_published_at == cand.source_published_at

    def test_analysis_429_exhausted_is_quota(self, monkeypatch):
        models, safety_calls = _patch_client(monkeypatch, [_api_error(429)])
        assert adapter.analyze_news_url(_candidate()) == (None, "NEWS_QUOTA")
        assert models.calls == adapter._MAX_ATTEMPTS
        assert safety_calls == []

    def test_safety_429_exhausted_is_quota(self, monkeypatch):
        cand = _candidate()
        _patch_client(monkeypatch, [_ok_response(cand.source_url)], safety=("RETRY_EXHAUSTED", "provider_http_429"))
        assert adapter.analyze_news_url(cand) == (None, "NEWS_QUOTA")

    @pytest.mark.parametrize("exc", [_api_error(500), _api_error(503), httpx.ReadTimeout("t")])
    def test_non_429_exhausted_is_url_fail(self, monkeypatch, exc):
        _patch_client(monkeypatch, [exc])
        assert adapter.analyze_news_url(_candidate()) == (None, "NEWS_URL_FAIL")

    def test_safety_non_429_exhausted_is_url_fail(self, monkeypatch):
        cand = _candidate()
        _patch_client(monkeypatch, [_ok_response(cand.source_url)], safety=("RETRY_EXHAUSTED", "provider_http_503"))
        assert adapter.analyze_news_url(cand) == (None, "NEWS_URL_FAIL")

    def test_permanent_error_is_url_fail(self, monkeypatch):
        models, _ = _patch_client(monkeypatch, [_api_error(400)])
        assert adapter.analyze_news_url(_candidate()) == (None, "NEWS_URL_FAIL")
        assert models.calls == 1

    def test_url_not_retrieved_is_url_unreadable(self, monkeypatch):
        models, safety_calls = _patch_client(monkeypatch, [_ok_response("https://other.example/x")])
        assert adapter.analyze_news_url(_candidate()) == (None, "NEWS_URL_UNREADABLE")
        assert models.calls == 1 and safety_calls == []

    def test_retrieved_url_with_trailing_slash_is_readable(self, monkeypatch):
        cand = _candidate()
        _patch_client(monkeypatch, [_ok_response(cand.source_url + "/")])
        topic, code = adapter.analyze_news_url(cand)
        assert code == "NEWS_READY" and topic.source_url == cand.source_url

    def test_retrieved_url_with_other_path_is_still_unreadable(self, monkeypatch):
        cand = _candidate()
        _patch_client(monkeypatch, [_ok_response(cand.source_url + "/other")])
        assert adapter.analyze_news_url(cand) == (None, "NEWS_URL_UNREADABLE")

    def test_irrelevant_article(self, monkeypatch):
        cand = _candidate()
        _, safety_calls = _patch_client(monkeypatch, [_ok_response(cand.source_url, relevant=False, core="")])
        assert adapter.analyze_news_url(cand) == (None, "NEWS_IRRELEVANT")
        assert safety_calls == []

    def test_unsafe_is_safety(self, monkeypatch):
        cand = _candidate()
        _patch_client(monkeypatch, [_ok_response(cand.source_url)], safety=("UNSAFE", "blocked"))
        assert adapter.analyze_news_url(cand) == (None, "NEWS_SAFETY")


class TestNewsKeyFacts:
    """261026 STEP 5-B — 원문 인용이 붙은 사실 3개 이상만 core_message에 반영, 부족하면 Fail-closed."""

    def test_three_facts_appended_to_core_message_and_safety_checked(self, monkeypatch):
        cand = _candidate()
        _, safety_calls = _patch_client(monkeypatch, [_ok_response(cand.source_url)])
        topic, code = adapter.analyze_news_url(cand)
        assert code == "NEWS_READY"
        lines = topic.core_message.split("\n")
        assert lines[0] == "새 에이전트 도구로 업무를 자동화할 수 있다."
        assert lines[1:] == [f"- {f['fact']}" for f in _FACTS]
        assert safety_calls == [topic.core_message]

    def test_two_facts_is_insufficient_without_safety_call(self, monkeypatch):
        cand = _candidate()
        _, safety_calls = _patch_client(monkeypatch, [_ok_response(cand.source_url, facts=_FACTS[:2])])
        assert adapter.analyze_news_url(cand) == (None, "NEWS_INSUFFICIENT_FACTS")
        assert safety_calls == []

    def test_missing_key_facts_is_insufficient(self, monkeypatch):
        cand = _candidate()
        _patch_client(monkeypatch, [_ok_response(cand.source_url, facts=None)])
        assert adapter.analyze_news_url(cand) == (None, "NEWS_INSUFFICIENT_FACTS")

    def test_number_not_in_quote_is_dropped(self, monkeypatch):
        cand = _candidate()
        fabricated = {"type": "number", "fact": "요금은 월 30달러다.", "evidence_quote": "It costs $20 per month."}
        facts = [_FACTS[0], fabricated, _FACTS[2]]
        _patch_client(monkeypatch, [_ok_response(cand.source_url, facts=facts)])
        assert adapter.analyze_news_url(cand) == (None, "NEWS_INSUFFICIENT_FACTS")

    @pytest.mark.parametrize("bad", [
        {"type": "opinion", "fact": "좋은 도구다.", "evidence_quote": "A great tool."},
        {"type": "feature", "fact": "근거 없는 기능.", "evidence_quote": ""},
        {"type": "usage", "fact": "", "evidence_quote": "Use it for email."},
        "문자열 항목",
    ])
    def test_invalid_fact_items_are_dropped(self, bad):
        assert adapter._validated_news_facts([bad]) == []

    def test_comma_numbers_match_and_facts_capped(self):
        fact = {"type": "number", "fact": "한도는 10,000건이다.", "evidence_quote": "Up to 10000 requests."}
        assert adapter._validated_news_facts([fact]) == ["한도는 10,000건이다."]
        assert len(adapter._validated_news_facts(_FACTS * 3)) == adapter.NEWS_MAX_FACTS

    def test_identifier_numbers_ignored_but_real_numbers_checked(self):
        # 261026 Dry-run 실측(Granite Speech 5.0) — 모델명 숫자는 식별자, 390,000·24%는 실제 수치
        assert adapter._numbers("granite-speech-5.0-2b 모델은 390,000시간 학습, 470m·4.1-2b-plus, GPT-4") == {"390000"}
        assert adapter._numbers("WER이 24% 감소, 월 20달러, 1.5배") == {"24", "20", "1.5"}
        facts = [
            {"type": "number", "fact": "granite-speech-5.0-2b는 390,000시간 분량으로 학습했다.",
             "evidence_quote": "It was trained on 390,000 hours of public audio."},
            {"type": "number", "fact": "granite-speech-4.1-2b-plus는 WER이 24% 감소했다.",
             "evidence_quote": "WER on long-form test sets drops 24%."},
            {"type": "number", "fact": "granite-speech-5.0-2b 요금은 월 30달러다.",
             "evidence_quote": "It costs $20 per month."},
        ]
        assert adapter._validated_news_facts(facts) == [facts[0]["fact"], facts[1]["fact"]]

    def test_prompt_requires_quoted_facts(self):
        prompt = adapter._build_news_prompt(_candidate())
        assert "key_facts" in prompt and "evidence_quote" in prompt
        assert "key_facts" in adapter._NEWS_RESPONSE_SCHEMA["required"]


# ── H: Sourcebook 14.x는 선택 대상이 아님 ───────────────────────────────

class TestSourcebookSeparation:
    def test_feed_sections_not_selectable(self, sourcebook):
        topics = parse_sourcebook(sourcebook)
        assert [t.topic_id for t in topics if t.topic_id.startswith("14.")] == ["14.1", "14.2"]
        assert [t.topic_id for t in list_selectable_topics(topics)] == ["3.1"]

    def test_real_sourcebook_feed_sections_not_selectable(self):
        topics = parse_sourcebook()
        feeds = [t for t in topics if t.topic_id.startswith("14.")]
        assert len(feeds) == 8 and all(t.source_url for t in feeds)  # 261026 14.8 Tom's Hardware 추가
        assert not any("hn.algolia.com" in t.source_url for t in feeds)
        assert not any(t.topic_id.startswith("14.") for t in list_selectable_topics(topics))


# ── A/E/H/I: Producer 배선 ─────────────────────────────────────────────

class _ProducerRepo:
    def __init__(self):
        self.saved = []

    def get_active_post_status_for_account(self, account_code_ref):
        return ""

    def find_account_post_by_source_url(self, account_code_ref, source_url):
        return False

    def find_account_post_by_content_id(self, account_code_ref, content_id):
        return False

    def exists_post_by_image_url(self, image_url):
        return False

    def save_instagram_post(self, post):
        self.saved.append(dict(post))
        return "recNEWS"


@pytest.fixture
def producer_env(tmp_path, monkeypatch):
    from launcher import main as launcher_main

    monkeypatch.setenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", "true")
    monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
    root = tmp_path / "vault"
    monkeypatch.setattr(cpb, "DEFAULT_VAULT_ROOT", root)
    repo = _ProducerRepo()
    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
    monkeypatch.setattr("modules.sns.image_hosting.upload_local_file_to_imgbb",
                        lambda path: {"success": True, "public_url": "https://i.ibb.co/news.jpg"})
    slack = []
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: slack.append(msg))
    create_calls = []

    def _fake_create(**kwargs):
        create_calls.append(kwargs)
        return cpb.PackageResult(success=False, error_code="NO_SELECTABLE_TOPIC")

    monkeypatch.setattr(cpb, "create_content_package", _fake_create)
    return SimpleNamespace(main=launcher_main, repo=repo, slack=slack, create_calls=create_calls, root=root)


def _run_producer(env, monkeypatch, hours, run_hour=8, news_result=None):
    monkeypatch.setenv("AIJOMOOJIN_NEWS_PRODUCER_HOURS", hours)
    monkeypatch.setattr(env.main, "_ict_now", lambda: datetime(2026, 10, 23, run_hour, 5))
    news_calls = []

    def _fake_news(repo):
        news_calls.append(repo)
        return news_result
    monkeypatch.setattr(env.main, "_try_aijomoojin_news_topic", _fake_news)
    env.main._job_aijomoojin_content_producer()
    return news_calls


class TestProducerWiring:
    _BASE_KEYS = {"target_language", "slot_role", "template_type", "gemini_client", "gemini_model",
                  "hero_card_enabled"}

    def test_flag_off_keeps_original_kwargs_and_no_news_call(self, producer_env, monkeypatch):
        news_calls = _run_producer(producer_env, monkeypatch, hours="", news_result=pytest.fail)
        assert news_calls == []
        assert len(producer_env.create_calls) == 1
        assert set(producer_env.create_calls[0]) == self._BASE_KEYS

    def test_flag_on_other_hour_skips_news(self, producer_env, monkeypatch):
        news_calls = _run_producer(producer_env, monkeypatch, hours="14", run_hour=8)
        assert news_calls == []
        assert set(producer_env.create_calls[0]) == self._BASE_KEYS

    def test_quota_stops_without_package_and_one_slack(self, producer_env, monkeypatch):
        _run_producer(producer_env, monkeypatch, hours="8", news_result=(None, "NEWS_QUOTA"))
        assert producer_env.create_calls == []
        assert len(producer_env.slack) == 1 and "NEWS_QUOTA" in producer_env.slack[0]

    @pytest.mark.parametrize("code", ["NEWS_DEDUP_UNAVAILABLE", "NEWS_NO_CANDIDATE", "NEWS_FEED_ERROR",
                                      "NEWS_URL_FAIL", "NEWS_URL_UNREADABLE", "NEWS_IRRELEVANT",
                                      "NEWS_SAFETY"])
    def test_other_failures_fall_back_to_sourcebook(self, producer_env, monkeypatch, code):
        news_calls = _run_producer(producer_env, monkeypatch, hours="8", news_result=(None, code))
        assert len(news_calls) == 1
        assert len(producer_env.create_calls) == 1
        assert "injected_topic" not in producer_env.create_calls[0]

    def test_dedup_unavailable_makes_zero_gemini_calls(self, producer_env, monkeypatch, tmp_path):
        """실제 _try_aijomoojin_news_topic 경로 — Vault content 폴더가 없으면 Gemini 호출 없이 Sourcebook으로 간다."""
        monkeypatch.setenv("AIJOMOOJIN_NEWS_PRODUCER_HOURS", "8")
        monkeypatch.setattr(producer_env.main, "_ict_now", lambda: datetime(2026, 10, 23, 8, 5))
        monkeypatch.setattr(adapter, "DEFAULT_VAULT_ROOT", tmp_path / "missing-vault")
        monkeypatch.setattr(adapter, "_get_client", lambda: pytest.fail("Gemini 호출되면 안 됨"))
        monkeypatch.setattr(adapter, "fetch_feed_items", lambda url: pytest.fail("피드 읽기 전에 중단돼야 함"))
        producer_env.main._job_aijomoojin_content_producer()
        assert len(producer_env.create_calls) == 1
        assert "injected_topic" not in producer_env.create_calls[0]

    def test_news_topic_passed_as_injected_topic(self, producer_env, monkeypatch):
        ready = SourceTopic(topic_id="14.1", title="New agent tool", status="VERIFIED FACT",
                            source_url="https://news.example/a", core_message="요약", prohibited_expression="",
                            source_published_at="2026-10-22T20:00:00+00:00")
        _run_producer(producer_env, monkeypatch, hours="8,14", news_result=(ready, "NEWS_READY"))
        assert len(producer_env.create_calls) == 1
        assert producer_env.create_calls[0]["injected_topic"] is ready
        assert set(producer_env.create_calls[0]) == self._BASE_KEYS | {"injected_topic"}


class TestUnreadableNextCandidate:
    """261023 STEP 4-M — 원문을 못 읽은 경우에만 다음 후보 1건. 실제 _try_aijomoojin_news_topic +
    producer 제어 흐름을 쓰고, 어댑터의 select/analyze만 Fake로 바꾼다."""

    def _patch(self, producer_env, monkeypatch, analyze_codes):
        monkeypatch.setenv("AIJOMOOJIN_NEWS_PRODUCER_HOURS", "8")
        monkeypatch.setattr(producer_env.main, "_ict_now", lambda: datetime(2026, 10, 23, 8, 5))
        cands = [_candidate("https://news.example/first"), _candidate("https://news.example/second"),
                 _candidate("https://news.example/third")]
        calls = {"select": [], "analyze": []}

        def _fake_select(account_code, repo, *, exclude_urls=None, **kw):
            calls["select"].append(set(exclude_urls or ()))
            for c in cands:
                if c.source_url not in (exclude_urls or ()):
                    return c, "NEWS_CANDIDATE"
            return None, "NEWS_NO_CANDIDATE"

        def _fake_analyze(candidate):
            calls["analyze"].append(candidate.source_url)
            code = analyze_codes[len(calls["analyze"]) - 1]
            if code == "NEWS_READY":
                from dataclasses import replace
                return replace(candidate, status="VERIFIED FACT", core_message="요약"), code
            return None, code

        monkeypatch.setattr(adapter, "select_news_candidate", _fake_select)
        monkeypatch.setattr(adapter, "analyze_news_url", _fake_analyze)
        return calls

    def test_a_first_unreadable_second_ready(self, producer_env, monkeypatch):
        calls = self._patch(producer_env, monkeypatch, ["NEWS_URL_UNREADABLE", "NEWS_READY"])
        producer_env.main._job_aijomoojin_content_producer()
        assert calls["select"] == [set(), {"https://news.example/first"}]
        assert calls["analyze"] == ["https://news.example/first", "https://news.example/second"]
        assert len(producer_env.create_calls) == 1
        assert producer_env.create_calls[0]["injected_topic"].source_url == "https://news.example/second"
        assert producer_env.slack == [] or all("NEWS_QUOTA" not in m for m in producer_env.slack)

    def test_b_first_unreadable_second_quota_stops_everything(self, producer_env, monkeypatch):
        calls = self._patch(producer_env, monkeypatch, ["NEWS_URL_UNREADABLE", "NEWS_QUOTA"])
        monkeypatch.setattr(cpb, "create_content_package", lambda **k: pytest.fail("Sourcebook 호출되면 안 됨"))
        producer_env.main._job_aijomoojin_content_producer()
        assert len(calls["select"]) == 2                       # 세 번째 후보 선택 없음
        assert calls["analyze"] == ["https://news.example/first", "https://news.example/second"]
        assert producer_env.repo.saved == []
        quota = [m for m in producer_env.slack if "NEWS_QUOTA" in m]
        assert len(quota) == 1 and len(producer_env.slack) == 1

    def test_b2_first_candidate_quota_stops_immediately(self, producer_env, monkeypatch):
        calls = self._patch(producer_env, monkeypatch, ["NEWS_QUOTA"])
        monkeypatch.setattr(cpb, "create_content_package", lambda **k: pytest.fail("Sourcebook 호출되면 안 됨"))
        producer_env.main._job_aijomoojin_content_producer()
        assert len(calls["select"]) == 1 and len(calls["analyze"]) == 1
        assert len(producer_env.slack) == 1 and "NEWS_QUOTA" in producer_env.slack[0]

    def test_c_both_unreadable_falls_back_to_sourcebook(self, producer_env, monkeypatch):
        calls = self._patch(producer_env, monkeypatch, ["NEWS_URL_UNREADABLE", "NEWS_URL_UNREADABLE"])
        producer_env.main._job_aijomoojin_content_producer()
        assert len(calls["select"]) == 2                       # 추가 후보는 1건만
        assert calls["analyze"] == ["https://news.example/first", "https://news.example/second"]
        assert len(producer_env.create_calls) == 1
        assert "injected_topic" not in producer_env.create_calls[0]
        assert all("NEWS_QUOTA" not in m for m in producer_env.slack)

    def test_d_first_irrelevant_second_ready(self, producer_env, monkeypatch):
        """261024 STEP 4-BC — 관련성 탈락도 다음 후보 1건을 본다."""
        calls = self._patch(producer_env, monkeypatch, ["NEWS_IRRELEVANT", "NEWS_READY"])
        producer_env.main._job_aijomoojin_content_producer()
        assert calls["select"] == [set(), {"https://news.example/first"}]
        assert calls["analyze"] == ["https://news.example/first", "https://news.example/second"]
        assert producer_env.create_calls[0]["injected_topic"].source_url == "https://news.example/second"

    def test_e_both_irrelevant_falls_back_to_sourcebook(self, producer_env, monkeypatch):
        calls = self._patch(producer_env, monkeypatch, ["NEWS_IRRELEVANT", "NEWS_IRRELEVANT"])
        producer_env.main._job_aijomoojin_content_producer()
        assert len(calls["select"]) == 2 and len(calls["analyze"]) == 2   # Gemini 최대 2회 유지
        assert len(producer_env.create_calls) == 1
        assert "injected_topic" not in producer_env.create_calls[0]

    def test_url_fail_does_not_try_next_candidate(self, producer_env, monkeypatch):
        calls = self._patch(producer_env, monkeypatch, ["NEWS_URL_FAIL"])
        producer_env.main._job_aijomoojin_content_producer()
        assert len(calls["select"]) == 1 and len(calls["analyze"]) == 1
        assert len(producer_env.create_calls) == 1 and "injected_topic" not in producer_env.create_calls[0]

    def test_select_respects_exclude_urls(self, sourcebook, vault):
        mapping = {"https://feed.example/one.xml": [_item("New AI agent", "https://news.example/a", 1),
                                                    _item("New AI model", "https://news.example/b", 2)],
                   "https://feed.example/two.xml": []}
        repo = _Repo()
        topic, code = adapter.select_news_candidate(
            AIJOMOOJIN, repo, sourcebook_path=sourcebook, vault_root=vault, now=NOW,
            fetch=_fetch_from(mapping), exclude_urls={"https://news.example/a"})
        assert code == "NEWS_CANDIDATE" and topic.source_url == "https://news.example/b"
        assert [c[1] for c in repo.checks] == ["https://news.example/b"]


TC1 = "https://techcrunch.com/2026/10/22/first-ai-agent-story/"
TC2 = "https://techcrunch.com/2026/10/22/second-ai-model-story/"
HF_OK = "https://venturebeat.com/ai/new-open-ai-model"  # 4-AA: 비우선 도메인 예시


def _now_item(title, link, hours_ago):
    return {"title": title, "link": link, "published": datetime.now(timezone.utc) - timedelta(hours=hours_ago)}


def _unreadable_response(url):
    meta = SimpleNamespace(url_metadata=[SimpleNamespace(
        retrieved_url=url, url_retrieval_status=genai_types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_ERROR)])
    return SimpleNamespace(candidates=[SimpleNamespace(url_context_metadata=meta)], text="{}")


class _ReadOnlyRepo:
    """find_account_post_by_source_url(GET)만 허용. 쓰기·게시 관련 메서드는 호출되면 실패."""

    def __init__(self, known=frozenset()):
        self.known, self.checks = known, []

    def find_account_post_by_source_url(self, account_code_ref, source_url):
        self.checks.append((account_code_ref, source_url))
        return source_url in self.known

    def __getattr__(self, name):
        pytest.fail(f"ReadOnlyRepo: {name} 호출되면 안 됨")


class TestOtherDomainCandidate:
    """261023 STEP 4-S — 실제 _try_aijomoojin_news_topic(repo) + 실제 select_news_candidate.
    피드·Gemini·Safety만 Fake. 저장·게시·Threads·Producer 전체 실행은 Sentinel로 막는다."""

    @pytest.fixture(autouse=True)
    def _guards(self, monkeypatch, sourcebook, vault):
        from launcher import main as launcher_main
        import modules.sns.threads_publisher as threads_publisher

        monkeypatch.setattr(adapter, "DEFAULT_SOURCEBOOK_PATH", sourcebook)
        monkeypatch.setattr(adapter, "DEFAULT_VAULT_ROOT", vault)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("publish_single 호출"))
        monkeypatch.setattr(threads_publisher, "publish_threads", lambda *a, **k: pytest.fail("Threads 게시 호출"))
        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: pytest.fail("Sourcebook 생성 호출"))
        self.main, self.vault = launcher_main, vault
        self.select_calls = []
        real_select = adapter.select_news_candidate

        def _spy_select(*a, **k):
            self.select_calls.append(set(k.get("exclude_domains") or ()))
            return real_select(*a, **k)

        monkeypatch.setattr(adapter, "select_news_candidate", _spy_select)

    def _feeds(self, monkeypatch, mapping):
        monkeypatch.setattr(adapter, "fetch_feed_items", lambda url: mapping[url])

    def _vault_files(self):
        return sorted(p.name for p in (self.vault / "content").glob("*"))

    def test_a_d_e_f_first_techcrunch_unreadable_then_other_domain(self, monkeypatch):
        _write_vault_package(self.vault, "old-hf", "https://venturebeat.com/ai/already-used")
        before = self._vault_files()
        self._feeds(monkeypatch, {
            "https://feed.example/one.xml": [_now_item("OpenAI ships new AI agent", TC1, 1),
                                             _now_item("New AI model release", TC2, 2)],
            "https://feed.example/two.xml": [
                _now_item("VentureBeat AI model already posted", "https://venturebeat.com/ai/already-used", 3),
                _now_item("Open AI model on VentureBeat", HF_OK, 4),
                _now_item("Gardening tips for autumn", "https://venturebeat.com/ai/garden", 2),
                _now_item("Old AI model news", "https://venturebeat.com/ai/old", 80),
                _now_item("AI tool already on Airtable", "https://venturebeat.com/ai/in-airtable", 3),
            ],
        })
        models, safety_calls = _patch_client(monkeypatch, [_unreadable_response(TC1), _ok_response(HF_OK)])
        repo = _ReadOnlyRepo(known={"https://venturebeat.com/ai/in-airtable"})

        topic, code = self.main._try_aijomoojin_news_topic(repo)

        assert code == "NEWS_READY" and topic.source_url == HF_OK
        assert self.select_calls == [set(), {"techcrunch.com"}]        # 후보 2건, 두 번째는 다른 도메인
        assert models.calls == 2 and len(safety_calls) == 1
        checked = [c[1] for c in repo.checks]
        assert TC2 not in checked                                      # 같은 도메인 건너뜀
        assert "https://venturebeat.com/ai/garden" not in checked      # 키워드 미달
        assert "https://venturebeat.com/ai/old" not in checked         # 72시간 초과
        assert "https://venturebeat.com/ai/already-used" not in checked  # Vault 중복
        assert checked.count(TC1) == 1                                 # 같은 URL 재시도 없음
        assert self._vault_files() == before                           # Vault 쓰기 0

    def test_b_no_other_domain_no_extra_gemini(self, monkeypatch):
        self._feeds(monkeypatch, {
            "https://feed.example/one.xml": [_now_item("OpenAI ships new AI agent", TC1, 1)],
            "https://feed.example/two.xml": [_now_item("New AI model release", TC2, 2)],
        })
        models, safety_calls = _patch_client(monkeypatch, [_unreadable_response(TC1)])

        topic, code = self.main._try_aijomoojin_news_topic(_ReadOnlyRepo())

        assert (topic, code) == (None, "NEWS_URL_UNREADABLE")
        assert self.select_calls == [set(), {"techcrunch.com"}]
        assert models.calls == 1 and safety_calls == []                # 추가 Gemini 0회

    def test_c_second_candidate_quota_stops_producer(self, monkeypatch, producer_env):
        """두 번째(다른 도메인) 후보 429 → Gemini 추가 0회, Sourcebook 0회, Slack Quota 1회."""
        monkeypatch.setattr(adapter, "DEFAULT_VAULT_ROOT", self.vault)
        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: pytest.fail("Sourcebook 호출"))
        monkeypatch.setenv("AIJOMOOJIN_NEWS_PRODUCER_HOURS", "8")
        monkeypatch.setattr(producer_env.main, "_ict_now", lambda: datetime(2026, 10, 23, 8, 5))
        self._feeds(monkeypatch, {
            "https://feed.example/one.xml": [_now_item("OpenAI ships new AI agent", TC1, 1)],
            "https://feed.example/two.xml": [_now_item("Open AI model on VentureBeat", HF_OK, 4)],
        })
        models, safety_calls = _patch_client(monkeypatch, [_unreadable_response(TC1), _api_error(429)])

        producer_env.main._job_aijomoojin_content_producer()

        assert self.select_calls == [set(), {"techcrunch.com"}]
        assert models.calls == 1 + adapter._MAX_ATTEMPTS and safety_calls == []
        assert producer_env.repo.saved == []
        assert len(producer_env.slack) == 1 and "NEWS_QUOTA" in producer_env.slack[0]

    def test_news_domain_normalizes_host(self):
        assert adapter.news_domain("https://www.TechCrunch.com/x") == "techcrunch.com"
        assert adapter.news_domain("https://huggingface.co/blog/a") == "huggingface.co"


GH_OK = "https://github.blog/ai-and-ml/new-copilot-agent/"
HF_PREF = "https://huggingface.co/blog/new-open-model"


class TestPreferredDomains:
    """261023 STEP 4-AA — 적격 후보 중 huggingface.co·github.blog 먼저, 같은 순위 안에서는 최신순."""

    def test_preferred_older_beats_newer_and_filters_still_apply(self, sourcebook, vault):
        _write_vault_package(vault, "hf-dup", "https://huggingface.co/blog/already-used")
        mapping = {
            "https://feed.example/one.xml": [_item("OpenAI ships new AI agent", "https://techcrunch.com/a", 1)],
            "https://feed.example/two.xml": [
                _item("Hugging Face AI model already posted", "https://huggingface.co/blog/already-used", 2),
                _item("Old AI model on Hugging Face", "https://huggingface.co/blog/old", 80),
                _item("Gardening tips for autumn", "https://huggingface.co/blog/garden", 3),
                _item("AI tool already on Airtable", "https://github.blog/ai-and-ml/in-airtable/", 4),
                _item("New open AI model", HF_PREF, 30),
            ],
        }
        repo = _Repo(known={"https://github.blog/ai-and-ml/in-airtable/"})
        topic, code = adapter.select_news_candidate(
            AIJOMOOJIN, repo, sourcebook_path=sourcebook, vault_root=vault, now=NOW, fetch=_fetch_from(mapping),
            preferred_domains=adapter.NEWS_PREFERRED_DOMAINS)
        assert code == "NEWS_CANDIDATE" and topic.source_url == HF_PREF       # 30시간 전 우선 > 1시간 전 비우선
        assert [c[1] for c in repo.checks] == ["https://github.blog/ai-and-ml/in-airtable/", HF_PREF]

    def test_no_preferred_candidate_falls_back_to_newest(self, sourcebook, vault):
        mapping = {
            "https://feed.example/one.xml": [_item("OpenAI ships new AI agent", "https://techcrunch.com/a", 5),
                                             _item("New AI model release", "https://openai.com/b", 2)],
            "https://feed.example/two.xml": [_item("Old AI model", "https://huggingface.co/blog/old", 80)],
        }
        topic, code = adapter.select_news_candidate(
            AIJOMOOJIN, _Repo(), sourcebook_path=sourcebook, vault_root=vault, now=NOW,
            fetch=_fetch_from(mapping), preferred_domains=adapter.NEWS_PREFERRED_DOMAINS)
        assert code == "NEWS_CANDIDATE" and topic.source_url == "https://openai.com/b"

    def test_without_preferred_domains_order_is_unchanged(self, sourcebook, vault):
        mapping = {
            "https://feed.example/one.xml": [_item("OpenAI ships new AI agent", "https://techcrunch.com/a", 1)],
            "https://feed.example/two.xml": [_item("New open AI model", HF_PREF, 30)],
        }
        topic, _ = adapter.select_news_candidate(
            AIJOMOOJIN, _Repo(), sourcebook_path=sourcebook, vault_root=vault, now=NOW, fetch=_fetch_from(mapping))
        assert topic.source_url == "https://techcrunch.com/a"

    def test_helper_first_preferred_unreadable_then_other_preferred(self, monkeypatch, sourcebook, vault):
        """실제 _try_aijomoojin_news_topic — HF(우선) 실패 → 더 새로운 TechCrunch가 아니라 GitHub(우선)."""
        from launcher import main as launcher_main
        import modules.sns.threads_publisher as threads_publisher

        monkeypatch.setattr(adapter, "DEFAULT_SOURCEBOOK_PATH", sourcebook)
        monkeypatch.setattr(adapter, "DEFAULT_VAULT_ROOT", vault)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("publish_single 호출"))
        monkeypatch.setattr(threads_publisher, "publish_threads", lambda *a, **k: pytest.fail("Threads 게시 호출"))
        monkeypatch.setattr(adapter, "fetch_feed_items", lambda url: {
            "https://feed.example/one.xml": [_now_item("OpenAI ships new AI agent", TC1, 1),
                                             _now_item("New Copilot AI agent", GH_OK, 20)],
            "https://feed.example/two.xml": [_now_item("New open AI model", HF_PREF, 10)],
        }[url])
        models, safety_calls = _patch_client(monkeypatch, [_unreadable_response(HF_PREF), _ok_response(GH_OK)])
        topic, code = launcher_main._try_aijomoojin_news_topic(_ReadOnlyRepo())
        assert code == "NEWS_READY" and topic.source_url == GH_OK
        assert models.calls == 2 and len(safety_calls) == 1

    def test_helper_preferred_quota_stops_at_once(self, monkeypatch, sourcebook, vault):
        from launcher import main as launcher_main

        monkeypatch.setattr(adapter, "DEFAULT_SOURCEBOOK_PATH", sourcebook)
        monkeypatch.setattr(adapter, "DEFAULT_VAULT_ROOT", vault)
        monkeypatch.setattr(adapter, "fetch_feed_items", lambda url: {
            "https://feed.example/one.xml": [_now_item("New Copilot AI agent", GH_OK, 20)],
            "https://feed.example/two.xml": [_now_item("New open AI model", HF_PREF, 10)],
        }[url])
        models, safety_calls = _patch_client(monkeypatch, [_api_error(429)])
        assert launcher_main._try_aijomoojin_news_topic(_ReadOnlyRepo()) == (None, "NEWS_QUOTA")
        assert models.calls == adapter._MAX_ATTEMPTS and safety_calls == []   # 두 번째 후보 없음


class TestFrontmatterPublishedAt:
    @pytest.fixture(autouse=True)
    def _mock_pipeline(self, monkeypatch):
        from modules.sns.image_provider_cloudflare import ProviderResult
        from modules.sns.visual_brief import ImagePrompt

        monkeypatch.setattr(cpb, "generate_hook_caption", lambda *a, **k: ("caption", "#ai"))
        monkeypatch.setattr(cpb, "build_visual_brief", lambda *a, **k: object())
        monkeypatch.setattr(cpb, "build_image_prompt", lambda brief: ImagePrompt(
            prompt_text="p", negative_prompt="n", aspect_ratio="1:1", prompt_version="v2"))
        monkeypatch.setattr(cpb, "generate_image", lambda *a, **k: ProviderResult(success=True, image_bytes=b"png"))

    def test_news_topic_writes_source_published_at(self, tmp_path):
        topic = SourceTopic(topic_id="14.1", title="t", status="VERIFIED FACT", source_url="https://news.example/a",
                            core_message="m", prohibited_expression="",
                            source_published_at="2026-10-22T20:00:00+00:00")
        result = cpb.create_content_package(vault_root=tmp_path, injected_topic=topic)
        assert result.success is True
        md_path, _ = cpb._content_paths(result.content_id, tmp_path)
        fields = cpb._parse_frontmatter(md_path.read_text(encoding="utf-8"))
        assert fields["source_published_at"] == "2026-10-22T20:00:00+00:00"

    def test_sourcebook_topic_has_no_source_published_at(self, tmp_path):
        topic = SourceTopic(topic_id="3.1", title="t", status="VERIFIED FACT", source_url="https://example.com/x",
                            core_message="m", prohibited_expression="")
        result = cpb.create_content_package(vault_root=tmp_path, injected_topic=topic)
        md_path, _ = cpb._content_paths(result.content_id, tmp_path)
        assert "source_published_at" not in cpb._parse_frontmatter(md_path.read_text(encoding="utf-8"))
