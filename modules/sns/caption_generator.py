import os
import random
import re
import time
from pathlib import Path
from typing import Literal

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

_client = None

# 260807 Content Playbook 연결 — 구조 규칙은 이 파일에 옮겨적지 않는다. 이
# 파일(docs/design/CONTENT_PLAYBOOK_260807.md)이 유일한 SSOT이고, 아래
# load_generation_contract()가 매 호출마다 그 파일을 다시 읽는다.
_PLAYBOOK_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "design" / "CONTENT_PLAYBOOK_260807.md"
)
_CONTRACT_SECTION_RE = re.compile(
    r"^## Generation Contract\n(.*?)(?:\n## |\Z)", re.MULTILINE | re.DOTALL
)


def load_generation_contract(path: "Path | None" = None) -> str:
    """Content Playbook의 'Generation Contract' 섹션 원문을 그대로 반환한다.
    파일이 없거나 섹션을 찾지 못하면 빈 문자열(Fail-open) — 호출자는 빈 문자열이면
    이 블록 없이 기존 프롬프트만 사용해 100% 이전과 동일하게 동작한다."""
    target = Path(path) if path else _PLAYBOOK_PATH
    if not target.exists():
        return ""
    text = target.read_text(encoding="utf-8")
    m = _CONTRACT_SECTION_RE.search(text)
    return m.group(1).strip() if m else ""

# 호출 간 최소 간격 (초) — free tier 30 RPM 기준 안전 마진 확보
_CALL_INTERVAL = 4.0
_last_call_ts  = 0.0

# Transient error(429/408/500/502/503/504/Timeout/연결재설정) 재시도 정책.
# 최초 호출 포함 총 시도 4회, 재시도 사이 기본 대기 5s→20s→60s(±20% jitter).
# Provider가 Retry-After/retryDelay를 명시하면 120초 상한 내에서 그 값을 우선한다.
_MAX_ATTEMPTS = 4
_RETRY_DELAYS = [5, 20, 60]
_RETRY_JITTER_RATIO = 0.2
_MAX_RETRY_AFTER_SECONDS = 120.0
_RETRYABLE_HTTP_STATUS = {408, 429, 500, 502, 503, 504}
_RETRYABLE_WINERRORS = {10053, 10054}  # 연결 중단/재설정(Windows)

SafetyStatus = Literal["SAFE", "UNSAFE", "PERMANENT", "RETRY_EXHAUSTED"]


def _classify_retry(exc: Exception) -> "tuple[bool, str]":
    """예외를 (재시도 가능 여부, 로그용 error_category)로 분류한다.

    Retryable: HTTP 408/429/500/502/503/504(Provider 과부하·Rate Limit),
    Timeout 계열(httpx.TimeoutException), 연결 재설정 계열(WinError
    10053/10054, httpx.TransportError). Non-retryable: 그 외 전부
    (400/401/403, Safety 차단으로 인한 빈 응답, 잘못된 입력 등) — 즉시
    실패시켜 불필요한 대기를 만들지 않는다.
    """
    if isinstance(exc, genai_errors.APIError):
        code = exc.code
        if code in _RETRYABLE_HTTP_STATUS:
            return True, f"provider_http_{code}"
        return False, f"permanent_http_{code}"

    winerror = getattr(exc, "winerror", None)
    if winerror is None:
        winerror = getattr(exc.__cause__, "winerror", None)
    if winerror in _RETRYABLE_WINERRORS:
        return True, f"transport_reset_winerror_{winerror}"

    if isinstance(exc, httpx.TimeoutException):
        return True, f"transport_timeout_{type(exc).__name__}"
    if isinstance(exc, httpx.TransportError):
        return True, f"transport_error_{type(exc).__name__}"

    # 하위호환: APIError로 감싸이지 않은 429 표현(과거 테스트 더블 등)도 계속 인식한다.
    if "429" in str(exc):
        return True, "provider_http_429_legacy_match"

    return False, f"non_retryable_{type(exc).__name__}"


def _extract_retry_after_seconds(exc: Exception) -> "float | None":
    """Provider가 명시한 재시도 대기(Retry-After 헤더 또는 retryDelay)를 최선노력으로
    추출한다. 없으면 None(호출부가 기본 backoff를 사용)."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        value = headers.get("retry-after") or headers.get("Retry-After")
        if value:
            try:
                return min(float(value), _MAX_RETRY_AFTER_SECONDS)
            except (TypeError, ValueError):
                pass

    details = getattr(exc, "details", None)
    error_details = None
    if isinstance(details, dict):
        error_details = details.get("error", {}).get("details")
    if isinstance(error_details, list):
        for item in error_details:
            delay = item.get("retryDelay") if isinstance(item, dict) else None
            if delay:
                try:
                    return min(float(str(delay).rstrip("s")), _MAX_RETRY_AFTER_SECONDS)
                except (TypeError, ValueError):
                    pass
    return None


def _next_retry_delay(attempt_index: int, exc: Exception) -> float:
    """attempt_index(0-based) 번째 재시도 전 대기 시간(초). Provider가 Retry-After/
    retryDelay를 명시하면 그 값을 120초 상한 내에서 그대로 사용한다(jitter 미적용 —
    Provider 지시를 줄이거나 늘리지 않는다). 명시값이 없으면 기본 backoff
    (_RETRY_DELAYS)에 ±20% jitter를 적용한다."""
    provider_delay = _extract_retry_after_seconds(exc)
    if provider_delay is not None:
        return provider_delay
    base = _RETRY_DELAYS[min(attempt_index, len(_RETRY_DELAYS) - 1)]
    jitter = base * _RETRY_JITTER_RATIO
    return max(0.0, base + random.uniform(-jitter, jitter))


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY 환경변수 미설정")
        _client = genai.Client(api_key=api_key)
    return _client


def _throttle():
    """연속 호출 간격을 _CALL_INTERVAL 이상으로 유지한다."""
    global _last_call_ts
    wait = _CALL_INTERVAL - (time.time() - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.time()


def generate_caption(text: str) -> tuple[str, str]:
    """FB 포스트 텍스트 → (Instagram 캡션, 해시태그) 반환.

    Transient error(429/408/500/502/503/504/Timeout/연결재설정)는 최초 호출
    포함 최대 _MAX_ATTEMPTS(4)회까지 재시도(5s→20s→60s ±20% jitter, Provider
    명시 대기가 있으면 120초 상한 내 우선). 영구 오류(400/401/403 등)는 즉시
    실패. API 키 미설정이거나 텍스트가 없으면 빈 문자열 반환.
    """
    if not text or not text.strip():
        return "", ""

    prompt = (
        "Convert the following Facebook post into an Instagram caption and hashtags.\n\n"
        "Rules:\n"
        "- Caption: Summarize in 2-3 natural English sentences with emojis\n"
        "- Hashtags: 5-10 relevant keywords with #, separated by spaces\n"
        "- Hashtags: Korea-related tags only. Do NOT include other country names (Myanmar, Vietnam, Philippines, China, Japan, etc.)\n"
        "- Output MUST be in English only\n"
        "- Response format (use exactly this format):\n"
        "CAPTION: <caption text>\n"
        "HASHTAGS: <hashtags>\n\n"
        f"Post content:\n{text[:1000]}"
    )

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        _call_started = None
        try:
            _throttle()
            client = _get_client()
            _call_started = time.time()
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            print(f"[CAPTION] Gemini 호출 완료 | attempt={attempt}/{_MAX_ATTEMPTS} | {time.time() - _call_started:.1f}초")
            raw = response.text.strip()
            # 260807 GPT 검수로 generate_hook_caption()에서 확정된 동일 Root
            # Cause를 여기에도 적용 — Gemini가 "CAPTION:" 다음 줄부터 문장을
            # 나눠 응답할 수 있다(Raw Evidence 확인됨). 이전 로직은 "CAPTION:"
            # 으로 시작하는 그 줄 하나만 취하고 접두사 없는 다음 줄들을 조용히
            # 버렸다 — 이제 "CAPTION:" 다음부터 "HASHTAGS:" 전까지의 모든
            # 비어있지 않은 줄을 그대로 이어붙인다.
            caption_lines: list[str] = []
            hashtags = ""
            collecting = False
            for line in raw.splitlines():
                if line.startswith("CAPTION:"):
                    collecting = True
                    first = line[len("CAPTION:"):].strip()
                    if first:
                        caption_lines.append(first)
                    continue
                if line.startswith("HASHTAGS:"):
                    hashtags = line[len("HASHTAGS:"):].strip()
                    collecting = False
                    continue
                if collecting and line.strip():
                    caption_lines.append(line.strip())
            caption = "\n".join(caption_lines)
            return caption, hashtags

        except Exception as e:
            elapsed = f"{time.time() - _call_started:.1f}초" if _call_started is not None else "N/A"
            retryable, category = _classify_retry(e)
            print(
                f"[CAPTION] Gemini 호출 실패 | attempt={attempt}/{_MAX_ATTEMPTS} | "
                f"category={category} | {elapsed}"
            )
            if retryable and attempt < _MAX_ATTEMPTS:
                delay = _next_retry_delay(attempt - 1, e)
                print(f"[CAPTION] 재시도 대기 | next_attempt={attempt + 1}/{_MAX_ATTEMPTS} | {delay:.1f}초")
                time.sleep(delay)
                continue
            print(
                f"[CAPTION] 생성 실패(생략) | category={category} | "
                f"attempt={attempt}/{_MAX_ATTEMPTS} | final_exhausted={retryable}"
            )
            return "", ""

    return "", ""


def generate_hook_caption(
    title: str,
    core_message: str,
    prohibited_expression: str = "",
    tone_style: str = "",
    target_language: str = "EN",
    *,
    client=None,
    throttle_fn=None,
    model=None,
) -> tuple[str, str]:
    """Track B Source Topic(title/core_message) → 후킹형 Instagram 캡션+해시태그.

    core_message에 없는 수치·기능·성과는 만들지 않는다(Sourcebook Usage Rule #2/#6과
    동일 제약을 프롬프트에 명시). prohibited_expression이 있으면 그 표현을 피하도록
    지시한다. core_message가 비어 있으면 즉시 빈 문자열 반환 — 근거 없는 콘텐츠 생성 금지.

    Transient error(429/408/500/502/503/504/Timeout/연결재설정)는 최초 호출
    포함 최대 _MAX_ATTEMPTS(4)회까지 재시도(generate_caption()과 동일 정책,
    _classify_retry()/_next_retry_delay() REUSE). 영구 오류는 즉시 실패.

    260804 Codex 리뷰(계정별 Gemini Credential 격리) — `client`/`throttle_fn`은
    선택 인자다. 생략하면(기존 모든 호출부 그대로) 전역 `_get_client()`/`_throttle()`을
    그대로 쓴다 — 100% 기존 동작. `research_to_topic_adapter.py`가 발굴한
    Topic으로 이 함수를 부를 때만 그 모듈 전용 Client/Throttle을 주입해, 다른
    계정이 쓰는 전역 GEMINI_API_KEY·전역 호출 간격에 전혀 영향을 주지 않는다.

    260805 회장 지시 — `model`도 같은 이유로 선택 인자다. 생략하면(기존 호출부
    그대로) 기본값 `"gemini-2.5-flash-lite"`를 그대로 쓴다. aijomoojin 전용
    호출부만 `model="gemini-3.5-flash-lite"`(Runtime Evidence로 확인된 값,
    `research_to_topic_adapter.RESEARCH_MODEL`)를 명시 전달한다."""
    if not core_message or not core_message.strip():
        return "", ""

    # 260807 Codex 리뷰 지적 — Playbook Generation Contract는 "Evidence/계약이
    # 없으면 생성하지 말고 HOLD한다"는 그 문서 자신의 규칙 대상이기도 하다.
    # 파일 삭제·경로 오류·섹션 파싱 실패로 계약을 못 읽으면 구조 규칙 없이
    # 캡션을 만들어버리는 대신 즉시 HOLD한다(Fail-closed). 호출자
    # `content_package_builder.create_content_package()`는 caption이 빈
    # 문자열이면 이미 `CAPTION_GENERATION_FAILED`로 안전 종료하는 기존
    # 계약을 갖고 있어 이 함수만 수정하면 된다(신규 에러코드 불필요).
    contract_text = load_generation_contract()
    if not contract_text:
        print(
            f"[HookCaption] Content Playbook Generation Contract 로딩 실패 — "
            f"HOLD(캡션 생성 안 함) | path={_PLAYBOOK_PATH}"
        )
        return "", ""
    contract_block = f"Required structure (Content Playbook Generation Contract):\n{contract_text}\n\n"

    tone_line = f"- Tone: {tone_style}\n" if tone_style else ""
    prohibited_line = (
        f"- Do NOT use this expression or anything similar to it: {prohibited_expression}\n"
        if prohibited_expression else ""
    )

    prompt = (
        "Write a hooking Instagram caption based ONLY on the verified fact below. "
        "Do not add any statistic, feature, or claim that is not explicitly stated here.\n\n"
        f"Topic: {title}\n"
        f"Verified core message: {core_message}\n\n"
        f"{contract_block}"
        "Rules:\n"
        "- Start with a hook (question or bold statement), 3-5 short sentences total\n"
        "- End with a soft call-to-action inviting comments or saves\n"
        f"- Write in {target_language} only\n"
        f"{tone_line}"
        f"{prohibited_line}"
        "- Hashtags: 5-10 relevant keywords with #, separated by spaces\n"
        "- Response format (use exactly this format):\n"
        "CAPTION: <caption text>\n"
        "HASHTAGS: <hashtags>"
    )

    active_throttle = throttle_fn or _throttle
    active_model = model or "gemini-2.5-flash-lite"
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        _call_started = None
        try:
            active_throttle()
            active_client = client or _get_client()
            _call_started = time.time()
            response = active_client.models.generate_content(
                model=active_model,
                contents=prompt,
            )
            print(f"[HookCaption] Gemini 호출 완료 | attempt={attempt}/{_MAX_ATTEMPTS} | {time.time() - _call_started:.1f}초")
            raw = response.text.strip()
            # 260807 GPT 검수로 확정된 Root Cause 수정 — Playbook 8단계 구조는
            # Gemini가 "CAPTION:" 다음 줄부터 단계별로 줄바꿈해 응답하는 경우가
            # 있다(Raw Evidence 확인됨). 이전 로직은 "CAPTION:"으로 시작하는
            # 그 줄 하나만 취하고 접두사 없는 다음 줄들을 조용히 버렸다 — 이제
            # "CAPTION:" 다음부터 "HASHTAGS:" 전까지의 모든 비어있지 않은 줄을
            # 그대로(모델이 만든 개행 유지) 이어붙인다. generate_caption()도
            # 동일 결함이 확인돼 같은 방식으로 함께 수정했다(아래 참조).
            caption_lines: list[str] = []
            hashtags = ""
            collecting = False
            for line in raw.splitlines():
                if line.startswith("CAPTION:"):
                    collecting = True
                    first = line[len("CAPTION:"):].strip()
                    if first:
                        caption_lines.append(first)
                    continue
                if line.startswith("HASHTAGS:"):
                    hashtags = line[len("HASHTAGS:"):].strip()
                    collecting = False
                    continue
                if collecting and line.strip():
                    caption_lines.append(line.strip())
            caption = "\n".join(caption_lines)
            return caption, hashtags

        except Exception as e:
            elapsed = f"{time.time() - _call_started:.1f}초" if _call_started is not None else "N/A"
            retryable, category = _classify_retry(e)
            print(
                f"[HookCaption] Gemini 호출 실패 | attempt={attempt}/{_MAX_ATTEMPTS} | "
                f"category={category} | {elapsed}"
            )
            if retryable and attempt < _MAX_ATTEMPTS:
                delay = _next_retry_delay(attempt - 1, e)
                print(f"[HookCaption] 재시도 대기 | next_attempt={attempt + 1}/{_MAX_ATTEMPTS} | {delay:.1f}초")
                time.sleep(delay)
                continue
            print(
                f"[HookCaption] 생성 실패(생략) | category={category} | "
                f"attempt={attempt}/{_MAX_ATTEMPTS} | final_exhausted={retryable}"
            )
            return "", ""

    return "", ""


def check_caption_safety(
    caption: str, *, client=None, throttle_fn=None, model=None,
) -> tuple[SafetyStatus, str]:
    """260801 AI_CONTENT Gate v0 — 이미 생성된 caption 텍스트의 Gemini Safety
    상태를 확인한다(재생성 아님, 신규 caption을 만들지 않음).

    기존 generate_hook_caption()은 API 응답의 candidate.finish_reason/
    safety_ratings를 버리고 text만 반환하므로, 이미 생성된 콘텐츠에 대해서는
    이 함수로 별도 확인한다. structured Safety 신호를 response.text보다 먼저
    확인하고, Provider transient 오류는 caption 생성과 동일한 bounded retry 계약을
    재사용한다 — 점수·카테고리별 세부 정책 엔진은 만들지 않는다.

    260804 Codex 리뷰(P0, 계정별 Gemini Credential 격리) — `client`/`throttle_fn`
    생략 시 기존과 100% 동일(전역 `_get_client()`/`_throttle()`). Research-to-Topic
    Adapter가 자체 발굴 Topic의 core_message를 검사할 때만 전용 Client/Throttle을
    주입해, 이 Safety 확인이 다른 계정의 전역 GEMINI_API_KEY quota·호출 간격을
    소비하지 않게 한다.

    260805 회장 지시 — `model`도 선택 인자다. 생략하면 기본값
    `"gemini-2.5-flash-lite"`(기존 동작 100% 유지), aijomoojin 전용 호출부만
    `model="gemini-3.5-flash-lite"`를 명시 전달한다."""
    if not caption or not caption.strip():
        return "PERMANENT", "EMPTY_CAPTION"

    active_throttle = throttle_fn or _throttle
    active_model = model or "gemini-2.5-flash-lite"
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            active_throttle()
            active_client = client or _get_client()
            response = active_client.models.generate_content(
                model=active_model,
                contents=caption,
            )

            # 후보가 없어 response.text가 예외를 내는 경우에도 prompt 차단 신호를
            # 놓치지 않도록 structured prompt feedback을 항상 가장 먼저 확인한다.
            prompt_feedback = getattr(response, "prompt_feedback", None)
            block_reason = getattr(prompt_feedback, "block_reason", None)
            block_reason_name = getattr(block_reason, "name", "") if block_reason else ""
            if (
                block_reason is not None
                and block_reason_name != "BLOCKED_REASON_UNSPECIFIED"
            ):
                return "UNSAFE", block_reason_name or str(block_reason)

            candidates = getattr(response, "candidates", None) or []
            if not candidates:
                return "PERMANENT", "NO_CANDIDATE_WITHOUT_BLOCK_REASON"

            candidate = candidates[0]
            finish_reason = getattr(candidate, "finish_reason", None)
            if finish_reason == genai_types.FinishReason.SAFETY:
                return "UNSAFE", "SAFETY"

            # structured Safety 신호 확인이 끝난 뒤, candidate가 있을 때만 text 접근.
            response_text = response.text
            normalized_text = response_text.strip().upper() if response_text else ""
            if normalized_text == "SAFETY":
                return "UNSAFE", "SAFETY_TEXT"

            if finish_reason == genai_types.FinishReason.STOP and normalized_text:
                return "SAFE", "STOP"

            finish_reason_name = getattr(finish_reason, "name", "UNKNOWN")
            return "PERMANENT", f"UNHANDLED_FINISH_REASON:{finish_reason_name}"
        except Exception as exc:
            retryable, category = _classify_retry(exc)
            if retryable and attempt < _MAX_ATTEMPTS:
                delay = _next_retry_delay(attempt - 1, exc)
                time.sleep(delay)
                continue
            if retryable:
                return "RETRY_EXHAUSTED", category
            return "PERMANENT", category

    return "RETRY_EXHAUSTED", "retry_loop_unreachable"


def generate_caption_clone(text: str) -> tuple[str, str]:
    """
    Clone Mode:
    - Preserve original Facebook text.
    - Replace seller contacts with our mapped contacts.
    - Do not summarize.
    - Do not rewrite.
    - Do not truncate.
    - Only normalize spacing/line breaks.
    """
    from modules.sns.content_filter import replace_contacts, clean_fb_metadata
    import re

    if not text:
        return "", ""

    caption = clean_fb_metadata(text)
    caption = replace_contacts(caption)
    caption = caption.replace("\r\n", "\n").replace("\r", "\n")
    caption = re.sub(r"[ \t]+", " ", caption)
    caption = re.sub(r"\n{3,}", "\n\n", caption)
    caption = caption.strip()

    tags = re.findall(r"#[\w가-힣_]+", caption)
    hashtags = " ".join(dict.fromkeys(tags))

    return caption, hashtags
