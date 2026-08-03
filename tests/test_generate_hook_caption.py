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
