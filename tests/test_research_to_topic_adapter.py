"""tests/test_research_to_topic_adapter.py — 260804 Track B 6G Research-to-Topic
Adapter 단위 테스트. 실제 Gemini API 호출 없음 — adapter._get_client()를
mock으로 교체한다(test_generate_hook_caption.py와 동일 패턴).

이 모듈은 aijomoojin 전용 Gemini Client(`AIJOMOOJIN_GEMINI_API_KEY`)를 쓴다 —
`caption_generator.py`의 전역 `GEMINI_API_KEY`(다른 계정과 공유)와 완전히
분리돼 있음을 `TestGetClientAccountIsolation`에서 직접 확인한다.
"""

import json

import pytest
from google.genai import types as genai_types

import modules.sns.caption_generator as caption_generator
import modules.sns.content_package_builder as cpb
import modules.sns.research_to_topic_adapter as adapter
from modules.sns.research_to_topic_adapter import (
    _make_topic_key,
    research_next_topic,
    select_unused_registry_source,
)

SOURCEBOOK_TEXT = """# Sourcebook (test fixture)

### 3.1 Existing Reference Topic
상태: VERIFIED FACT
URL: https://example.com/3-1

SNS 콘텐츠 핵심 메시지:
기존 3.x 항목은 core_message가 이미 채워져 있다.

### 4.1 Reddit Community A
상태: VERIFIED FACT
URL: https://reddit.com/r/testcommunity-a

일부 커뮤니티 설명, core_message 없음(4.x 실제 패턴과 동일).

### 4.2 Reddit Community B
상태: VERIFIED FACT
URL: https://reddit.com/r/testcommunity-b

두 번째 후보.

### 5.1 Facebook Group
상태: USE_WITH_CAUTION
URL: https://facebook.com/groups/test-group
"""


@pytest.fixture
def sourcebook_path(tmp_path):
    path = tmp_path / "sourcebook.md"
    path.write_text(SOURCEBOOK_TEXT, encoding="utf-8")
    return str(path)


@pytest.fixture
def vault_root(tmp_path):
    root = tmp_path / "vault"
    return root


class _FakeUrlMeta:
    def __init__(self, retrieved_url, status):
        self.retrieved_url = retrieved_url
        self.url_retrieval_status = status


class _FakeUrlContextMetadata:
    def __init__(self, entries):
        self.url_metadata = entries


class _FakeCandidate:
    def __init__(self, url_context_metadata):
        self.url_context_metadata = url_context_metadata


class _FakeResponse:
    def __init__(self, payload: dict, url_status, retrieved_url):
        self.text = json.dumps(payload)
        self.candidates = [
            _FakeCandidate(_FakeUrlContextMetadata([_FakeUrlMeta(retrieved_url, url_status)]))
        ]


class _FakeModels:
    def __init__(self, response=None, raise_exc=None):
        self._response = response
        self._raise_exc = raise_exc
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._raise_exc:
            raise self._raise_exc
        return self._response


class _FakeClient:
    def __init__(self, models):
        self.models = models


def _patch_gemini(monkeypatch, models):
    # research_to_topic_adapter.py는 이제 자신만의 _get_client()/_throttle()을
    # 갖는다(caption_generator와 완전 분리) — 그 모듈 자신의 이름공간을 patch한다.
    # 실제 _get_client()의 캐싱 동작(동일 인스턴스 재사용)까지 재현해, "동일
    # Client가 여러 호출부에 그대로 전달되는지" 같은 identity 비교 테스트가
    # 가능하게 한다.
    fake_client = _FakeClient(models)
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)
    monkeypatch.setattr(adapter, "_throttle", lambda: None)


def _patch_scan_used_source_urls(monkeypatch, used: set):
    monkeypatch.setattr(adapter, "scan_used_source_urls", lambda root=None: used)


SUCCESS_URL_STATUS = genai_types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS
ERROR_URL_STATUS = genai_types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_ERROR

VALID_PAYLOAD = {
    "source_title": "Reddit Community A",
    "core_message": "이 커뮤니티는 1인 AI 창업 사례를 공유한다.",
    "target_audience": "AI 자동화에 관심있는 솔로프리너",
    "content_angle": "실제 수익 인증 사례 중심",
    "evidence_summary": "여러 회원이 월 수익을 공개했다.",
    "additional_evidence_urls": ["https://reddit.com/r/testcommunity-a/comments/xyz"],
}


class TestSelectUnusedRegistrySource:
    def test_picks_first_unused_4x_5x_url(self, sourcebook_path, vault_root):
        topic = select_unused_registry_source(sourcebook_path, vault_root)
        assert topic is not None
        assert topic.topic_id == "4.1"
        assert topic.source_url == "https://reddit.com/r/testcommunity-a"

    def test_skips_urls_already_used_in_vault(self, sourcebook_path, vault_root, monkeypatch):
        _patch_scan_used_source_urls(monkeypatch, {"https://reddit.com/r/testcommunity-a"})
        topic = select_unused_registry_source(sourcebook_path, vault_root)
        assert topic.topic_id == "4.2"

    def test_returns_none_when_all_registry_urls_used(self, sourcebook_path, vault_root, monkeypatch):
        _patch_scan_used_source_urls(monkeypatch, {
            "https://reddit.com/r/testcommunity-a",
            "https://reddit.com/r/testcommunity-b",
            "https://facebook.com/groups/test-group",
        })
        assert select_unused_registry_source(sourcebook_path, vault_root) is None

    def test_ignores_3x_topics_even_if_unused(self, sourcebook_path, vault_root):
        """3.x는 이 Adapter의 대상이 아니다(기존 source_selector 경로 전용) —
        3.1이 미사용이어도 이 함수는 절대 반환하지 않는다."""
        topic = select_unused_registry_source(sourcebook_path, vault_root)
        assert topic.topic_id != "3.1"


class TestMakeTopicKey:
    def test_deterministic_for_same_input(self):
        a = _make_topic_key("https://x.example/a", "Same message")
        b = _make_topic_key("https://x.example/a", "Same message")
        assert a == b

    def test_different_for_different_core_message(self):
        a = _make_topic_key("https://x.example/a", "Message A")
        b = _make_topic_key("https://x.example/a", "Message B")
        assert a != b

    def test_normalizes_whitespace_case(self):
        a = _make_topic_key("https://x.example/a", "Hello   World")
        b = _make_topic_key("https://x.example/a", "hello world")
        assert a == b


class TestResearchNextTopic:
    def test_no_registry_candidate_returns_none_without_gemini_call(
        self, sourcebook_path, vault_root, monkeypatch
    ):
        _patch_scan_used_source_urls(monkeypatch, {
            "https://reddit.com/r/testcommunity-a",
            "https://reddit.com/r/testcommunity-b",
            "https://facebook.com/groups/test-group",
        })
        models = _FakeModels()
        _patch_gemini(monkeypatch, models)

        result = research_next_topic(sourcebook_path, vault_root)

        assert result is None
        assert models.calls == []

    def test_success_returns_source_topic_with_grounded_core_message(
        self, sourcebook_path, vault_root, monkeypatch
    ):
        response = _FakeResponse(
            VALID_PAYLOAD, SUCCESS_URL_STATUS, "https://reddit.com/r/testcommunity-a"
        )
        models = _FakeModels(response=response)
        _patch_gemini(monkeypatch, models)
        monkeypatch.setattr(
            adapter, "check_caption_safety", lambda text, **kwargs: ("SAFE", "STOP")
        )

        topic = research_next_topic(sourcebook_path, vault_root)

        assert topic is not None
        assert topic.source_url == "https://reddit.com/r/testcommunity-a"
        assert topic.core_message == VALID_PAYLOAD["core_message"]
        assert topic.title == VALID_PAYLOAD["source_title"]
        assert topic.status == "VERIFIED FACT"
        assert topic.topic_id.startswith("auto-")
        assert len(models.calls) == 1
        # Search Grounding + URL Context 둘 다 tools에 포함됐는지 확인
        tools = models.calls[0]["config"].tools
        assert any(getattr(t, "url_context", None) is not None for t in tools)
        assert any(getattr(t, "google_search", None) is not None for t in tools)
        # 260805 회장 지시 — aijomoojin 전용 고정 모델("*-latest" 아님) 사용 확인
        assert models.calls[0]["model"] == adapter.RESEARCH_MODEL == "gemini-3.5-flash-lite"

    def test_safety_check_invoked_with_isolated_client_and_throttle(
        self, sourcebook_path, vault_root, monkeypatch
    ):
        """260804 Codex 리뷰(P0) — Safety 확인이 실제로 aijomoojin 전용
        Client/Throttle을 넘겨받는지(전역 caption_generator 것이 아니라) 직접
        증명한다 — 이전 라운드는 check_caption_safety()가 REUSE된다고만
        했지, 실제로 어떤 Client가 들어가는지 검증하지 않았다."""
        response = _FakeResponse(
            VALID_PAYLOAD, SUCCESS_URL_STATUS, "https://reddit.com/r/testcommunity-a"
        )
        models = _FakeModels(response=response)
        _patch_gemini(monkeypatch, models)

        safety_calls = []

        def _spy_safety(text, *, client=None, throttle_fn=None, model=None):
            safety_calls.append({"client": client, "throttle_fn": throttle_fn, "model": model})
            return "SAFE", "STOP"

        monkeypatch.setattr(adapter, "check_caption_safety", _spy_safety)

        research_next_topic(sourcebook_path, vault_root)

        assert len(safety_calls) == 1
        assert safety_calls[0]["client"] is adapter._get_client()  # 격리된 Client 그대로 전달
        assert safety_calls[0]["throttle_fn"] is adapter._throttle  # 격리된 Throttle 그대로 전달
        assert safety_calls[0]["model"] == adapter.RESEARCH_MODEL  # 260805 — 고정모델 그대로 전달

    def test_url_retrieval_failure_returns_none_no_retry_with_different_url(
        self, sourcebook_path, vault_root, monkeypatch
    ):
        response = _FakeResponse(
            VALID_PAYLOAD, ERROR_URL_STATUS, "https://reddit.com/r/testcommunity-a"
        )
        models = _FakeModels(response=response)
        _patch_gemini(monkeypatch, models)

        result = research_next_topic(sourcebook_path, vault_root)

        assert result is None
        assert len(models.calls) == 1  # 다른 URL로 재시도 안 함(Fail-closed, 1회만)

    def test_empty_core_message_returns_none(self, sourcebook_path, vault_root, monkeypatch):
        payload = dict(VALID_PAYLOAD, core_message="")
        response = _FakeResponse(payload, SUCCESS_URL_STATUS, "https://reddit.com/r/testcommunity-a")
        models = _FakeModels(response=response)
        _patch_gemini(monkeypatch, models)

        assert research_next_topic(sourcebook_path, vault_root) is None

    def test_safety_check_failure_returns_none(self, sourcebook_path, vault_root, monkeypatch):
        response = _FakeResponse(
            VALID_PAYLOAD, SUCCESS_URL_STATUS, "https://reddit.com/r/testcommunity-a"
        )
        models = _FakeModels(response=response)
        _patch_gemini(monkeypatch, models)
        monkeypatch.setattr(
            adapter, "check_caption_safety", lambda text, **kwargs: ("UNSAFE", "SAFETY")
        )

        assert research_next_topic(sourcebook_path, vault_root) is None

    def test_gemini_call_exception_returns_none(self, sourcebook_path, vault_root, monkeypatch):
        models = _FakeModels(raise_exc=RuntimeError("permanent failure"))
        _patch_gemini(monkeypatch, models)

        assert research_next_topic(sourcebook_path, vault_root) is None

    def test_evidence_urls_always_includes_primary_source_url(
        self, sourcebook_path, vault_root, monkeypatch
    ):
        payload = dict(VALID_PAYLOAD, additional_evidence_urls=[])
        response = _FakeResponse(payload, SUCCESS_URL_STATUS, "https://reddit.com/r/testcommunity-a")
        models = _FakeModels(response=response)
        _patch_gemini(monkeypatch, models)
        monkeypatch.setattr(
            adapter, "check_caption_safety", lambda text, **kwargs: ("SAFE", "STOP")
        )

        topic = research_next_topic(sourcebook_path, vault_root)
        assert topic is not None  # evidence_urls 최소 1개(원천 URL 자체) 보장으로 자동승인 통과


class TestGetClientAccountIsolation:
    """260804 — aijomoojin 전용 Gemini Client가 전역 GEMINI_API_KEY와 완전히
    분리돼 있는지 직접 확인한다(다른 계정 영향 0건의 근거)."""

    def test_missing_key_raises_clear_error(self, monkeypatch):
        monkeypatch.setattr(adapter, "_client", None)
        monkeypatch.delenv("AIJOMOOJIN_GEMINI_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="AIJOMOOJIN_GEMINI_API_KEY"):
            adapter._get_client()

    def test_uses_aijomoojin_specific_key_not_global_gemini_key(self, monkeypatch):
        monkeypatch.setattr(adapter, "_client", None)
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "aijomoojin-only-key")
        monkeypatch.setenv("GEMINI_API_KEY", "some-other-account-shared-key")

        captured = {}

        class _FakeGenaiClient:
            def __init__(self, api_key):
                captured["api_key"] = api_key

        monkeypatch.setattr(adapter.genai, "Client", _FakeGenaiClient)

        adapter._get_client()

        assert captured["api_key"] == "aijomoojin-only-key"  # 전역 GEMINI_API_KEY는 무시됨

    def test_client_is_cached_across_calls(self, monkeypatch):
        monkeypatch.setattr(adapter, "_client", None)
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "aijomoojin-only-key")
        init_calls = []

        class _FakeGenaiClient:
            def __init__(self, api_key):
                init_calls.append(api_key)

        monkeypatch.setattr(adapter.genai, "Client", _FakeGenaiClient)

        first = adapter._get_client()
        second = adapter._get_client()

        assert first is second
        assert len(init_calls) == 1

    def test_never_constructs_global_caption_generator_client(self, monkeypatch):
        """260804 Codex 리뷰 — "전역 GEMINI_API_KEY Client 생성 0회" 직접 증명.
        caption_generator._client가 None으로 유지되는지 확인한다(그 모듈의
        genai.Client 생성자가 이 Adapter 동작 중 한 번도 안 불렸다는 뜻)."""
        monkeypatch.setattr(adapter, "_client", None)
        monkeypatch.setattr(caption_generator, "_client", None)
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "aijomoojin-only-key")

        class _FakeGenaiClient:
            def __init__(self, api_key):
                pass

        monkeypatch.setattr(adapter.genai, "Client", _FakeGenaiClient)

        adapter._get_client()

        assert caption_generator._client is None  # 전역 Client는 생성된 적 없음

    def test_own_throttle_does_not_touch_global_last_call_ts(self, monkeypatch):
        """260804 Codex 리뷰(P1) — 이 모듈의 _throttle()이 caption_generator의
        전역 _last_call_ts를 전혀 건드리지 않는지 직접 증명(다른 계정 Gemini
        호출 지연 0건의 근거)."""
        monkeypatch.setattr(caption_generator, "_last_call_ts", 12345.0)
        monkeypatch.setattr(adapter, "_last_call_ts", 0.0)

        adapter._throttle()

        assert caption_generator._last_call_ts == 12345.0  # 전역 상태 무변화

    def test_missing_key_fail_closed_without_retry_loop(self, sourcebook_path, vault_root, monkeypatch):
        """260804 Codex 리뷰 — "전용 Key 누락 시 Caption/Image/Airtable Write 0회"
        의 최초 단계 — Key가 없으면 research_next_topic() 자체가 즉시 None을
        반환해(재시도 루프 없이) 이후 Caption/Image/Airtable 단계에 절대
        도달하지 않는다."""
        monkeypatch.setattr(adapter, "_client", None)
        monkeypatch.delenv("AIJOMOOJIN_GEMINI_API_KEY", raising=False)
        monkeypatch.setattr(adapter, "_throttle", lambda: None)

        result = research_next_topic(sourcebook_path, vault_root)

        assert result is None


class TestMaskEmail:
    """260804/260805 Codex 리뷰(P2) — 로그에 이메일 전체가 남지 않는지 확인.
    실제 운영 이메일 원문은 테스트 fixture에도 남기지 않는다(예시 주소만 사용).
    별표 개수를 직접 세어 하드코딩하지 않고 len(local)로부터 계산해 비교한다
    (feedback_count_verification 메모리 — 수기 집계 실수 방지)."""

    def test_masks_local_part_keeps_domain(self):
        email = "researchbot99@example.com"
        local = email.split("@")[0]
        masked = adapter._mask_email(email)

        assert masked.endswith("@example.com")
        visible = masked.split("@")[0]
        assert visible[:2] == local[:2]
        assert visible[2:] == "*" * (len(local) - 2)
        assert local not in masked

    def test_unparseable_input_returns_unknown(self):
        assert adapter._mask_email("not-an-email") == "UNKNOWN"

    def test_one_char_local_part_is_fully_masked(self):
        """260805 Codex 리뷰(P2 재검토) — 로컬파트가 1자면 원문 노출 0글자여야 한다."""
        masked = adapter._mask_email("a@example.com")
        assert masked == "*@example.com"
        assert "a@example.com" != masked

    def test_two_char_local_part_masks_at_least_one_char(self):
        """260805 Codex 리뷰(P2 재검토) — 로컬파트가 2자여도 최소 1글자는 마스킹된다
        (기존 구현은 visible=local[:2]로 2자 전체가 그대로 노출됐음)."""
        masked = adapter._mask_email("ab@example.com")
        assert masked == "a*@example.com"
