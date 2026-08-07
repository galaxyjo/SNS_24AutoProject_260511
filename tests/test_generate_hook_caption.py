"""Track B-3 — caption_generator.generate_hook_caption() 단위 테스트.

실제 Gemini API 호출 없음 — _get_client()를 mock으로 교체한다.
"""

import httpx
import pytest
from google.genai import errors as genai_errors

import modules.sns.caption_generator as caption_generator
from modules.sns.caption_generator import generate_hook_caption


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, text=None, raise_on_first=None):
        self._text = text
        self._raise_on_first = raise_on_first
        self.calls = 0

    def generate_content(self, model, contents):
        self.calls += 1
        if self._raise_on_first and self.calls == 1:
            raise self._raise_on_first
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, models):
        self.models = models


def _patch_client(monkeypatch, models):
    monkeypatch.setattr(caption_generator, "_get_client", lambda: _FakeClient(models))
    monkeypatch.setattr(caption_generator, "_throttle", lambda: None)


def test_empty_core_message_returns_empty_without_calling_gemini(monkeypatch):
    models = _FakeModels(text="CAPTION: x\nHASHTAGS: #x")
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Netflix Culture Memo", "")

    assert (caption, hashtags) == ("", "")
    assert models.calls == 0


def test_generates_caption_and_hashtags_from_core_message(monkeypatch):
    fake_text = (
        "CAPTION: Netflix trusts people over process. Do you?\n"
        "HASHTAGS: #startup #culture #netflix"
    )
    models = _FakeModels(text=fake_text)
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption(
        "Netflix Culture Memo",
        "Netflix는 규칙을 늘리는 대신 뛰어난 사람에게 맥락과 책임을 준다.",
    )

    assert caption == "Netflix trusts people over process. Do you?"
    assert hashtags == "#startup #culture #netflix"
    assert models.calls == 1


def test_prompt_includes_prohibited_expression_when_provided(monkeypatch):
    captured = {}

    class _CapturingModels(_FakeModels):
        def generate_content(self, model, contents):
            captured["contents"] = contents
            return super().generate_content(model, contents)

    models = _CapturingModels(text="CAPTION: c\nHASHTAGS: #h")
    _patch_client(monkeypatch, models)

    generate_hook_caption(
        "Netflix Culture Memo",
        "core message",
        prohibited_expression='"실리콘밸리 조직문화의 절대적인 바이블"',
    )

    assert '"실리콘밸리 조직문화의 절대적인 바이블"' in captured["contents"]


def test_prompt_never_omits_core_message_constraint(monkeypatch):
    captured = {}

    class _CapturingModels(_FakeModels):
        def generate_content(self, model, contents):
            captured["contents"] = contents
            return super().generate_content(model, contents)

    models = _CapturingModels(text="CAPTION: c\nHASHTAGS: #h")
    _patch_client(monkeypatch, models)

    generate_hook_caption("Title", "only this fact is allowed")

    assert "only this fact is allowed" in captured["contents"]
    assert "Do not add any statistic" in captured["contents"]


def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(caption_generator.time, "sleep", lambda s: None)
    models = _FakeModels(
        text="CAPTION: recovered\nHASHTAGS: #ok",
        raise_on_first=Exception("429 rate limited"),
    )
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert caption == "recovered"
    assert models.calls == 2


def test_non_429_exception_fails_closed_to_empty(monkeypatch):
    class _RaisingModels(_FakeModels):
        def generate_content(self, model, contents):
            raise RuntimeError("network down")

    _patch_client(monkeypatch, _RaisingModels())

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert (caption, hashtags) == ("", "")


# --- 260803 GPT 승인 설계: 429 전용 Retry → transient-error Retry ADAPT ---
# (503/408/500/502/504/Timeout/연결재설정도 재시도, 400/401/403/Safety는 즉시 실패,
#  최초 호출 포함 총 시도 상한 _MAX_ATTEMPTS=4)


class _FlakyModels:
    """calls 순서대로 exceptions를 소비하고, 소진되면 성공 응답(text)을 반환한다.
    exceptions가 시도 횟수만큼 있으면(성공 없이) 항상 실패로 소진된다."""

    def __init__(self, exceptions, text=None):
        self._exceptions = exceptions
        self._text = text
        self.calls = 0

    def generate_content(self, model, contents):
        self.calls += 1
        idx = self.calls - 1
        if idx < len(self._exceptions):
            raise self._exceptions[idx]
        return _FakeResponse(self._text)


def _server_error(code, message="transient"):
    return genai_errors.ServerError(
        code, {"error": {"code": code, "message": message, "status": "UNAVAILABLE"}}
    )


def _client_error(code, message="permanent"):
    return genai_errors.ClientError(
        code, {"error": {"code": code, "message": message, "status": "INVALID_ARGUMENT"}}
    )


def _winerror_10054():
    err = ConnectionResetError("기존 연결이 원격 호스트에 의해 강제로 끊겼습니다")
    err.winerror = 10054
    return err


def test_retries_on_503_then_succeeds(monkeypatch):
    monkeypatch.setattr(caption_generator.time, "sleep", lambda s: None)
    models = _FlakyModels([_server_error(503)], text="CAPTION: ok\nHASHTAGS: #ok")
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert caption == "ok"
    assert models.calls == 2


def test_retries_on_winerror_10054_then_succeeds(monkeypatch):
    monkeypatch.setattr(caption_generator.time, "sleep", lambda s: None)
    models = _FlakyModels([_winerror_10054()], text="CAPTION: ok\nHASHTAGS: #ok")
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert caption == "ok"
    assert models.calls == 2


def test_retries_on_timeout_then_succeeds(monkeypatch):
    monkeypatch.setattr(caption_generator.time, "sleep", lambda s: None)
    models = _FlakyModels([httpx.ReadTimeout("timeout")], text="CAPTION: ok\nHASHTAGS: #ok")
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert caption == "ok"
    assert models.calls == 2


def test_retries_on_client_error_429_then_succeeds(monkeypatch):
    """string 기반 하위호환(test_retries_on_429_then_succeeds, 위)과 별개로,
    실제 SDK가 던지는 genai_errors.ClientError(429)도 재시도되는지 확인한다."""
    monkeypatch.setattr(caption_generator.time, "sleep", lambda s: None)
    models = _FlakyModels([_client_error(429)], text="CAPTION: ok\nHASHTAGS: #ok")
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert caption == "ok"
    assert models.calls == 2


def test_transient_errors_exhaust_at_max_attempts_then_fails_closed(monkeypatch):
    """503/10054/Timeout이 연속되면 최초 호출 포함 정확히 4회(=_MAX_ATTEMPTS)만
    시도하고 빈 캡션으로 종료한다 — 무한 재시도 금지, 부분 상태변경 없음(caption_generator
    자체는 반환값 외 상태를 갖지 않으므로 이 반환값이 곧 '부분기록 0'의 증거)."""
    monkeypatch.setattr(caption_generator.time, "sleep", lambda s: None)
    exceptions = [
        _server_error(503),
        _winerror_10054(),
        httpx.ReadTimeout("timeout"),
        _server_error(503),
    ]
    models = _FlakyModels(exceptions)
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert (caption, hashtags) == ("", "")
    assert models.calls == caption_generator._MAX_ATTEMPTS == 4


def test_own_retry_loop_caps_at_max_attempts_regardless_of_continued_failures(
    monkeypatch,
):
    """260803 12:05pm ICT GPT 지적으로 명칭·docstring 정정: 이 테스트는 `_get_client()`를
    통째로 mock으로 교체하므로 실제 google-genai SDK의 내부 재시도 계층(tenacity)을
    전혀 거치지 않는다 — 즉 "SDK 자체 재시도가 비활성화돼 있다"는 사실 자체는 이
    테스트가 증명하지 않는다(그 근거는 별도의 정적 코드 확인: `google/genai/
    _api_client.py:529-530` `retry_args(None)`→`stop_after_attempt(1)`, docs/evidence
    제출로만 뒷받침됨). 이 테스트가 실제로 검증하는 것은 **우리 쪽 자체 재시도
    루프**가 계속 실패해도(10회분 준비) 정확히 `_MAX_ATTEMPTS(4)`에서 멈추고 더 이상
    호출하지 않는다는 점뿐이다."""
    monkeypatch.setattr(caption_generator.time, "sleep", lambda s: None)
    exceptions = [_server_error(503)] * 10  # 소진 전까지 계속 실패하도록 충분히 많이 준비
    models = _FlakyModels(exceptions)
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert (caption, hashtags) == ("", "")
    assert models.calls == 4


@pytest.mark.parametrize("code", [400, 401, 403])
def test_permanent_client_errors_fail_immediately_without_retry(monkeypatch, code):
    models = _FlakyModels([_client_error(code)])
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert (caption, hashtags) == ("", "")
    assert models.calls == 1


def test_safety_blocked_empty_response_fails_immediately_without_retry(monkeypatch):
    """Gemini가 Safety 등으로 candidate/parts가 없는 응답을 반환하면 SDK의
    response.text 프로퍼티가 ValueError('Response is empty.')를 던진다(google/genai/
    types.py:8032-8167 확인) — 이는 재시도 대상 예외가 아니므로 1회 호출 후 즉시
    실패해야 한다."""

    class _SafetyBlockedResponse:
        @property
        def text(self):
            raise ValueError("Response is empty.")

    class _SafetyModels:
        def __init__(self):
            self.calls = 0

        def generate_content(self, model, contents):
            self.calls += 1
            return _SafetyBlockedResponse()

    models = _SafetyModels()
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert (caption, hashtags) == ("", "")
    assert models.calls == 1


# --- 260803 11:49am ICT GPT 3차 검수 Blocker 수정 확인용 Target Test ---


class _FakeHttpResponse:
    def __init__(self, headers):
        self.headers = headers


def _server_error_with_retry_after(code, retry_after_seconds, message="transient"):
    return genai_errors.ServerError(
        code,
        {"error": {"code": code, "message": message, "status": "UNAVAILABLE"}},
        response=_FakeHttpResponse({"retry-after": str(retry_after_seconds)}),
    )


def test_retry_after_500_is_clamped_to_exactly_120_no_jitter(monkeypatch):
    """Blocker 1(260803 11:58am 재검수): Provider가 500초를 요구하면 120초 상한으로
    자르되, 그 값에 jitter를 적용하면 안 된다(수정 전엔 ±20% jitter가 붙어 96~144초
    사이로 흔들렸음 — 96초면 Provider 지시보다 일찍 재호출하게 되는 위반). random을
    지터가 걸렸다면 값이 바뀔 만큼 강하게 몽키패치해도 결과가 정확히 120.0이어야
    jitter가 전혀 적용되지 않았음을 증명한다."""
    monkeypatch.setattr(caption_generator.random, "uniform", lambda a, b: b)
    exc = _server_error_with_retry_after(503, 500)

    delay = caption_generator._next_retry_delay(0, exc)

    assert delay == 120.0


def test_default_backoff_still_gets_jitter_when_no_provider_retry_after(monkeypatch):
    """Blocker 1 회귀 방지: Provider 값이 없는 fallback 경로(기본 5/20/60초)는
    여전히 jitter가 적용돼야 한다(이번 수정이 jitter 자체를 없앤 게 아니라
    Provider 경로에서만 뺀 것임을 확인)."""
    monkeypatch.setattr(caption_generator.random, "uniform", lambda a, b: b)  # 항상 최대(+) 방향
    exc = _server_error(503)  # response 없음 -> Provider Retry-After 없음

    delay = caption_generator._next_retry_delay(0, exc)  # attempt_index=0 -> base=5

    assert delay == 6.0  # 5 + (5*0.2) = 6.0, jitter가 여전히 적용됨


def test_permanent_error_logs_final_exhausted_false_not_true(monkeypatch, capsys):
    """Blocker 2: 400(영구 오류)은 재시도를 '소진'한 게 아니라 애초에 재시도 대상이
    아니므로 로그에 final_exhausted=False가 남아야 한다(수정 전엔 항상 True로 찍힘)."""
    models = _FlakyModels([_client_error(400)])
    _patch_client(monkeypatch, models)

    generate_hook_caption("Title", "core message")

    out = capsys.readouterr().out
    assert "final_exhausted=False" in out
    assert "final_exhausted=True" not in out


def test_generate_caption_retries_on_503_then_succeeds(monkeypatch):
    """generate_caption()(FB 포스트→IG 캡션, source_exporter.py/facebook_crawler.py가
    실제로 쓰는 함수)도 generate_hook_caption()과 동일한 transient-error retry 정책을
    쓰는지 확인 — 지금까지의 target test는 generate_hook_caption()만 검증했었다."""
    monkeypatch.setattr(caption_generator.time, "sleep", lambda s: None)
    models = _FlakyModels([_server_error(503)], text="CAPTION: ok\nHASHTAGS: #ok")
    _patch_client(monkeypatch, models)

    caption, hashtags = caption_generator.generate_caption("some FB post text")

    assert caption == "ok"
    assert models.calls == 2


def test_generate_caption_preserves_multiline_caption(monkeypatch):
    """260807 GPT 지시 — generate_hook_caption()에서 확정된 동일 Root Cause를
    generate_caption()에도 적용한 최소수정 확인. 'CAPTION:' 다음 줄부터
    'HASHTAGS:' 전까지 여러 줄로 응답해도 첫 줄만 남기고 버리지 않아야 한다."""
    fake_text = (
        "CAPTION: New arrivals are here this week!\n"
        "So many colors and sizes to choose from.\n"
        "DM us with any questions!\n"
        "HASHTAGS: #koreanfashion #newarrivals"
    )
    models = _FakeModels(text=fake_text)
    _patch_client(monkeypatch, models)

    caption, hashtags = caption_generator.generate_caption("some FB post text")

    assert caption == (
        "New arrivals are here this week!\n"
        "So many colors and sizes to choose from.\n"
        "DM us with any questions!"
    )
    assert hashtags == "#koreanfashion #newarrivals"


def test_generate_caption_single_line_caption_unchanged(monkeypatch):
    """회귀 확인 — 기존처럼 CAPTION이 한 줄로 오는 경우는 이전과 100% 동일하게 동작한다."""
    fake_text = "CAPTION: New arrivals are here! 🎉\nHASHTAGS: #koreanfashion #newarrivals"
    models = _FakeModels(text=fake_text)
    _patch_client(monkeypatch, models)

    caption, hashtags = caption_generator.generate_caption("some FB post text")

    assert caption == "New arrivals are here! 🎉"
    assert hashtags == "#koreanfashion #newarrivals"


def test_generate_hook_caption_uses_injected_client_not_global(monkeypatch):
    """260804 Track B 6G — client 인자를 넘기면 전역 _get_client()를 아예
    호출하지 않는다(다른 계정 전용 Client 격리 지원, generate_hook_caption()
    은 이 파일을 REUSE하는 research_to_topic_adapter.py가 실제로 의존하는
    계약이다)."""
    monkeypatch.setattr(
        caption_generator, "_get_client",
        lambda: pytest.fail("전역 _get_client()가 호출되면 안 됨(client 인자를 줬으므로)"),
    )
    injected_models = _FakeModels(text="CAPTION: injected\nHASHTAGS: #x")
    injected_client = _FakeClient(injected_models)

    caption, hashtags = generate_hook_caption(
        "Title", "core message", client=injected_client,
    )

    assert caption == "injected"
    assert injected_models.calls == 1


def test_generate_hook_caption_uses_injected_throttle_not_global(monkeypatch):
    throttle_calls = []
    models = _FakeModels(text="CAPTION: x\nHASHTAGS: #x")
    _patch_client(monkeypatch, models)
    monkeypatch.setattr(
        caption_generator, "_throttle",
        lambda: pytest.fail("전역 _throttle()이 호출되면 안 됨(throttle_fn 인자를 줬으므로)"),
    )

    generate_hook_caption("Title", "core message", throttle_fn=lambda: throttle_calls.append(1))

    assert throttle_calls == [1]


def test_generate_hook_caption_without_override_keeps_existing_behavior(monkeypatch):
    """client/throttle_fn을 생략한 기존 호출부는 100% 이전과 동일(회귀 없음)."""
    models = _FakeModels(text="CAPTION: default\nHASHTAGS: #x")
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert caption == "default"
    assert models.calls == 1


def test_generate_hook_caption_uses_injected_model_not_default(monkeypatch):
    """260805 회장 지시 — model 인자를 넘기면 그 모델 문자열이 그대로
    generate_content(model=...)에 전달돼야 한다(aijomoojin 전용 모델 고정의
    근거 계약)."""
    captured = {}

    class _CapturingModels(_FakeModels):
        def generate_content(self, model, contents):
            captured["model"] = model
            return super().generate_content(model, contents)

    models = _CapturingModels(text="CAPTION: x\nHASHTAGS: #x")
    _patch_client(monkeypatch, models)

    generate_hook_caption("Title", "core message", model="gemini-3.5-flash-lite")

    assert captured["model"] == "gemini-3.5-flash-lite"


# --- 260807 Content Playbook 연결 Target Test ---


_FAKE_PLAYBOOK = """# Content Playbook

## 1. Document Control

irrelevant preamble text

---

## Generation Contract

구조(8단계, 반드시 이 순서로 구성한다):
1. 고객문장 Hook
8. CTA 1개 — 게시물당 정확히 1개의 행동 유도 문구로 마무리한다.

필수 규칙:
- 출처(Evidence)에 없는 수치·성과·사례를 새로 만들지 않는다.
- CTA는 게시물당 1개만 포함한다(2개 이상 금지).

---

## 변경 이력
"""


def test_load_generation_contract_extracts_section_only(tmp_path):
    playbook = tmp_path / "playbook.md"
    playbook.write_text(_FAKE_PLAYBOOK, encoding="utf-8")

    contract = caption_generator.load_generation_contract(playbook)

    assert "고객문장 Hook" in contract
    assert "CTA는 게시물당 1개만 포함한다" in contract
    assert "irrelevant preamble text" not in contract
    assert "변경 이력" not in contract


def test_load_generation_contract_returns_empty_when_file_missing(tmp_path):
    missing = tmp_path / "does_not_exist.md"

    assert caption_generator.load_generation_contract(missing) == ""


def test_prompt_includes_playbook_contract_when_file_exists(tmp_path, monkeypatch):
    playbook = tmp_path / "playbook.md"
    playbook.write_text(_FAKE_PLAYBOOK, encoding="utf-8")
    monkeypatch.setattr(caption_generator, "_PLAYBOOK_PATH", playbook)

    captured = {}

    class _CapturingModels(_FakeModels):
        def generate_content(self, model, contents):
            captured["contents"] = contents
            return super().generate_content(model, contents)

    models = _CapturingModels(text="CAPTION: c\nHASHTAGS: #h")
    _patch_client(monkeypatch, models)

    generate_hook_caption("Title", "core message")

    prompt = captured["contents"]
    assert "Required structure (Content Playbook Generation Contract):" in prompt
    assert "고객문장 Hook" in prompt
    assert "CTA는 게시물당 1개만 포함한다" in prompt
    assert "출처(Evidence)에 없는 수치·성과·사례를 새로 만들지 않는다" in prompt


def test_generate_hook_caption_fails_closed_when_playbook_missing(tmp_path, monkeypatch):
    """260807 GPT 검수 — Playbook을 못 읽으면(파일 없음) 구조 규칙 없이 캡션을
    만드는 대신 즉시 HOLD한다(Fail-closed). Gemini 호출 자체가 발생하면 안 된다
    (core_message 공란 케이스와 동일한 안전계약)."""
    monkeypatch.setattr(caption_generator, "_PLAYBOOK_PATH", tmp_path / "missing.md")
    models = _FakeModels(text="CAPTION: x\nHASHTAGS: #x")
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert (caption, hashtags) == ("", "")
    assert models.calls == 0


def test_generate_hook_caption_fails_closed_when_contract_section_empty(tmp_path, monkeypatch):
    """Playbook 파일은 존재하지만 'Generation Contract' 섹션이 없거나 빈 경우도
    동일하게 HOLD해야 한다 — 파일 존재 여부만으로 안전을 오판하지 않는다."""
    broken_playbook = tmp_path / "playbook.md"
    broken_playbook.write_text("# Content Playbook\n\n## 1. Document Control\n\n내용만 있고 계약 섹션 없음\n", encoding="utf-8")
    monkeypatch.setattr(caption_generator, "_PLAYBOOK_PATH", broken_playbook)
    models = _FakeModels(text="CAPTION: x\nHASHTAGS: #x")
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert (caption, hashtags) == ("", "")
    assert models.calls == 0


def test_generate_hook_caption_preserves_multiline_caption(monkeypatch):
    """260807 GPT 검수로 확정된 Root Cause 수정 확인 — Gemini가 'CAPTION:' 다음부터
    단계별로 줄바꿈해 응답해도(Raw Evidence로 실제 관찰된 형태), 첫 줄만 남기고
    나머지를 버리지 않고 'HASHTAGS:' 전까지 전부 보존해야 한다."""
    fake_text = (
        "CAPTION: 매번 똑같은 일 처리하느라 하루가 다 갔네.\n"
        "반복되는 업무를 계속 직접 손으로 처리하고 있다.\n"
        "입력 → 자동화 → 기록.\n"
        "이 자동화 흐름을 적용해 보자.\n"
        "\n"
        "HASHTAGS: #업무자동화 #재퍼"
    )
    models = _FakeModels(text=fake_text)
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert caption == (
        "매번 똑같은 일 처리하느라 하루가 다 갔네.\n"
        "반복되는 업무를 계속 직접 손으로 처리하고 있다.\n"
        "입력 → 자동화 → 기록.\n"
        "이 자동화 흐름을 적용해 보자."
    )
    assert hashtags == "#업무자동화 #재퍼"


def test_generate_hook_caption_single_line_caption_unchanged(monkeypatch):
    """회귀 확인 — 기존처럼 CAPTION이 한 줄로 오는 경우는 이전과 100% 동일하게 동작한다."""
    fake_text = "CAPTION: Netflix trusts people over process. Do you?\nHASHTAGS: #startup #culture #netflix"
    models = _FakeModels(text=fake_text)
    _patch_client(monkeypatch, models)

    caption, hashtags = generate_hook_caption("Title", "core message")

    assert caption == "Netflix trusts people over process. Do you?"
    assert hashtags == "#startup #culture #netflix"


def test_real_playbook_file_loads_full_contract():
    """실제 docs/design/CONTENT_PLAYBOOK_260807.md가 존재하고 8단계·CTA 1개
    규칙을 담고 있는지 확인하는 Smoke Test(임시파일이 아닌 실제 Active 파일)."""
    contract = caption_generator.load_generation_contract()

    assert contract != ""
    assert "CTA 1개" in contract
    assert "입력 → 자동화 → 결과" in contract


def test_generate_hook_caption_without_model_override_keeps_default(monkeypatch):
    """model을 생략한 기존 호출부는 여전히 기본 모델("gemini-2.5-flash-lite")을
    쓴다 — 다른 계정 무영향 확인."""
    captured = {}

    class _CapturingModels(_FakeModels):
        def generate_content(self, model, contents):
            captured["model"] = model
            return super().generate_content(model, contents)

    models = _CapturingModels(text="CAPTION: x\nHASHTAGS: #x")
    _patch_client(monkeypatch, models)

    generate_hook_caption("Title", "core message")

    assert captured["model"] == "gemini-2.5-flash-lite"
