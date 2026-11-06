import json
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

from modules.common.logger import get_logger

logger = get_logger(__name__)

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


# 260808 회장 지시 — Threads 공식 게시물 글자수 제한(500자, Meta 공식 문서
# developers.facebook.com/documentation/threads/posts)에 맞춰 aijomoojin
# 캡션을 미리 압축한다. 이 숫자는 docs/design/CONTENT_PLAYBOOK_260807.md의
# "필수 규칙"에도 기록돼 있다(SSOT는 그 문서, 여기 상수는 Runtime 강제용).
# 현재 Runtime에는 Threads 게시 경로 자체가 없다(Read-only 확인 — modules/
# 전체에 Threads 연동 코드 0건, Instagram_Posts 스키마에도 Threads 필드
# 없음) — 이 제한은 향후 연결 대비 + 캡션 압축 품질 기준으로 선제 적용한다.
_MAX_FINAL_PAYLOAD_CHARS = 357  # 261028 회장 지시: 해시태그 제외 캡션 상한 — 기존 성공 계정 캡션 최대치(IDN-000022 357자) 기준
# 261028 회장 승인(B_MED 영어 게시): 357자는 한국어 캡션 기준이다. 모델 응답에 한글이 전혀 없는 영어 캡션만 이 상한을 쓴다
# (9요소 영어 캡션 실측 650~770자, 인스타 한도 2200자 이내). 한국어 캡션 상한·동작은 그대로다.
_MAX_FINAL_PAYLOAD_CHARS_EN = 800

# 260810 회장 지시로 전면 개정(docs/design/CONTENT_PLAYBOOK_260807.md 260810
# 변경 이력 참조) — 실게시 3건이 "깊이 없음·겉돎·친밀감 없음"으로 지적됨.
# 근본원인: 이전 EVIDENCE가 core_message 한 줄로만 제한되고 WORKFLOW가
# "입력→자동화→결과" 추상 틀에 강제로 채워져, Sourcebook 원문의 구체적
# 사실(세부 인사이트·실제 기업명 등)이 캡션에 전혀 반영되지 못했다. 회장이
# 직접 예시 2건을 다회 수정·승인해 확정한 신규 9필드 구조로 교체한다 —
# 공감 도입 3줄 + How 2개 + 주제별 제목·본문 + 핵심 한 줄 + 모토.
_REQUIRED_ELEMENT_LABELS = (
    "HOOK_EMPATHY", "HOOK_QUESTION", "HOOK_REVEAL",
    "HOW_POINT1", "HOW_POINT2",
    "DETAIL_TITLE", "DETAIL_BODY",
    "CORE_POINT", "MOTTO",
)

# 260810 — CTA는 더 이상 모델이 생성하지 않는다. 계정 프로필에 실제로는 링크가
# 설정돼 있지 않음을 Instagram Graph API 직접 조회로 확인했다(website 필드
# 없음) — 지금까지의 "프로필 링크 클릭" CTA는 존재하지 않는 목적지를 안내하고
# 있었다. 이 프로젝트가 이미 구축·운영 중인 실제 리드 채널(DM Webhook→자동
# 응답→CRM)로 CTA를 고정해, 게시물마다 다른 CTA 문구가 실수로 깨진 목적지를
# 가리킬 위험을 구조적으로 제거한다.
_FIXED_CTA_LINE = "더 나누고싶은건 댓글, 더 궁금하면 DM ^_~"


def _parse_structured_caption_response(raw: str) -> "tuple[dict[str, str], str]":
    """9-Element 구조화 응답(HOOK_EMPATHY/HOOK_QUESTION/HOOK_REVEAL/HOW_POINT1/
    HOW_POINT2/DETAIL_TITLE/DETAIL_BODY/CORE_POINT/MOTTO)과 HASHTAGS를 줄 단위로
    파싱한다. 각 라벨 다음, 다음 라벨이 나오기 전까지의 모든 비어있지 않은 줄을
    그 요소에 이어붙인다(260807 다중 줄 보존 원칙과 동일)."""
    known_labels = _REQUIRED_ELEMENT_LABELS + ("HASHTAGS",)
    collected: "dict[str, list[str]]" = {label: [] for label in known_labels}
    current: "str | None" = None
    for line in raw.splitlines():
        matched = next((label for label in known_labels if line.startswith(f"{label}:")), None)
        if matched:
            current = matched
            value = line[len(matched) + 1:].strip()
            if value:
                collected[matched].append(value)
            continue
        if current and line.strip():
            collected[current].append(line.strip())

    fields = {label: "\n".join(parts).strip() for label, parts in collected.items()}
    hashtags = fields.pop("HASHTAGS", "")
    return fields, hashtags


def _assemble_structured_caption(
    fields: "dict[str, str]", hashtags: str, cta_line: str = ""
) -> "tuple[str, str, str]":
    """9요소 Validator — 하나라도 실패하면 (\"\", \"\", HOLD사유)를 반환한다(Fail-closed,
    임의 절단·자동 재게시 없음). 검사 순서: 요소 누락 → 최종 길이가
    _MAX_FINAL_PAYLOAD_CHARS 초과. 전부 통과하면 회장이 승인한 고정 시각 템플릿
    (도입 3줄 / "1.How?" 불릿 2개 / "2.{주제별 제목}" / "3.핵심은?" / 모토 인용 /
    고정 CTA)으로 조립해 반환한다 — 번호·불릿·인용부호·CTA 문구는 모델 응답이
    아니라 이 함수가 항상 동일하게 붙인다."""
    missing = [label for label in _REQUIRED_ELEMENT_LABELS if not fields.get(label)]
    if missing:
        return "", "", f"MISSING_ELEMENTS:{','.join(missing)}"

    active_cta = (cta_line or "").strip() or _FIXED_CTA_LINE
    is_english = not any("가" <= ch <= "힣" for value in fields.values() for ch in value)
    core_label = "3.Key takeaway?" if is_english else "3.핵심은?"
    max_chars = _MAX_FINAL_PAYLOAD_CHARS_EN if is_english else _MAX_FINAL_PAYLOAD_CHARS
    caption = (
        f"{fields['HOOK_EMPATHY']}\n"
        f"{fields['HOOK_QUESTION']}\n"
        f"{fields['HOOK_REVEAL']}\n"
        f"\n"
        f"1.How?\n"
        f"• {fields['HOW_POINT1']}\n"
        f"• {fields['HOW_POINT2']}\n"
        f"\n"
        f"2.{fields['DETAIL_TITLE']}\n"
        f": {fields['DETAIL_BODY']}\n"
        f"\n"
        f"{core_label}\n"
        f": {fields['CORE_POINT']}\n"
        f"\n"
        f"\"{fields['MOTTO']}\"\n"
        f"\n"
        f"{active_cta}"
    )
    if len(caption) > max_chars:
        return "", "", f"PAYLOAD_TOO_LONG:{len(caption)}"

    return caption, hashtags, ""

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


class TextAIError(Exception):
    """GPT·Claude가 모두 실패했을 때 발생. 메시지에 상태코드(예: 429)를 싣지 않는다 —
    `_classify_retry`가 재시도 불가로 분류해 기존 실패 경로(Fail-closed)로 곧바로 넘어가게 한다.

    261107 — `providers`: 공급자별 시도 요약 목록(진단용). 각 항목은 provider·model·status·code·etype·finish·tin·tout·ms
    허용 필드만 담는다(키·프롬프트·응답 본문·오류 문구 원문은 담지 않는다)."""

    def __init__(self, message: str = "", providers: "list | None" = None):
        super().__init__(message)
        self.providers = list(providers or [])


_SAFE_CODE_CHARS = re.compile(r"[^A-Za-z0-9_.\-]")


def _safe_code(value, limit: int = 40) -> str:
    return _SAFE_CODE_CHARS.sub("", str(value or ""))[:limit]


def _provider_error_code(exc: Exception) -> str:
    """공급자 예외에서 진단용 짧은 코드만 뽑는다(허용 문자·40자 제한). 오류 문구 원문은 저장하지 않고,
    잔액 부족을 뜻하는 알려진 문구만 `credit_exhausted`로 정규화한다."""
    if isinstance(exc, TextAIError):
        return _safe_code(str(exc))
    if isinstance(exc, ValueError):
        return "invalid_json"
    body = getattr(exc, "body", None)
    err = body.get("error") if isinstance(body, dict) and isinstance(body.get("error"), dict) else body
    if isinstance(err, dict):
        message = str(err.get("message", "")).lower()
        if "credit balance" in message or "no credits" in message or "insufficient_quota" in message:
            return "credit_exhausted"
        for key in ("code", "type"):
            if err.get(key):
                return _safe_code(err[key])
    code = getattr(exc, "code", None)
    return _safe_code(code) if isinstance(code, str) else ""


_TEXT_AI_DEFAULT_GPT_MODEL = "gpt-5.4-mini"
_TEXT_AI_DEFAULT_CLAUDE_MODEL = "claude-haiku-5-5"


def _extract_json_text(raw: str) -> str:
    """모델 응답에서 JSON 객체 본문만 꺼낸다(코드펜스·앞뒤 설명 제거). 유효한 JSON이 아니면 ValueError."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("JSON object not found")
    body = text[start:end + 1]
    json.loads(body)  # 유효성 확인(파싱 실패는 ValueError)
    return body


class _TextResponse:
    """genai 응답 호환 최소 객체 — 호출부는 `.text`만 쓴다."""
    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text


class _TextAIModels:
    def __init__(self, owner: "TextAIFallbackClient"):
        self._owner = owner

    def generate_content(self, *, model=None, contents=None, config=None):
        # 문자열 프롬프트(순수 텍스트 생성)만 GPT/Claude가 처리한다. 이미지 포함 등 그 밖의 요청은 기존 Gemini로 그대로 위임.
        if isinstance(contents, str):
            return self._owner._generate_text(contents, config)
        return self._owner._delegate().models.generate_content(model=model, contents=contents, config=config)


class TextAIFallbackClient:
    """261106 — genai.Client 호환 텍스트 생성 client. GPT(1순위) 정상이면 GPT 결과만 쓰고(Claude 호출 0건),
    GPT가 어떤 이유로든 실패하면 Claude로 자동 전환한다. 둘 다 실패하면 TextAIError(→ 기존 Fail-closed 실패 경로).
    콘텐츠 형식·검증·중복 방지는 호출부 그대로이며 이 client는 텍스트 한 덩어리만 돌려준다."""

    def __init__(self, *, openai_key: str, anthropic_key: str = "", gemini_client=None, account: str = "",
                 gpt_model: str = "", claude_model: str = "", openai_factory=None, anthropic_factory=None):
        self._openai_key = openai_key
        self._anthropic_key = anthropic_key
        self._gemini = gemini_client
        self.account = account
        self.gpt_model = gpt_model or os.getenv("TEXT_AI_GPT_MODEL", "").strip() or _TEXT_AI_DEFAULT_GPT_MODEL
        self.claude_model = (claude_model or os.getenv("TEXT_AI_CLAUDE_MODEL", "").strip()
                             or _TEXT_AI_DEFAULT_CLAUDE_MODEL)
        self._openai_factory = openai_factory
        self._anthropic_factory = anthropic_factory
        self._openai = None
        self._anthropic = None
        self.models = _TextAIModels(self)
        self.last_provider = ""

    def _delegate(self):
        if self._gemini is None:
            raise TextAIError("TEXT_AI_NO_GEMINI_DELEGATE")
        return self._gemini

    def __getattr__(self, name):
        # 그 밖의 속성(이미지 등)은 기존 Gemini client로 위임한다.
        if name.startswith("_") or self.__dict__.get("_gemini") is None:
            raise AttributeError(name)
        return getattr(self._gemini, name)

    # ── 공급자 client(지연 생성) ─────────────────────────────────────
    def _gpt(self):
        if self._openai is None:
            if self._openai_factory:
                self._openai = self._openai_factory(self._openai_key)
            else:
                import openai
                self._openai = openai.OpenAI(api_key=self._openai_key)
        return self._openai

    def _claude(self):
        if not self._anthropic_key:
            raise TextAIError("TEXT_AI_NO_CLAUDE_KEY")
        if self._anthropic is None:
            if self._anthropic_factory:
                self._anthropic = self._anthropic_factory(self._anthropic_key)
            else:
                import anthropic
                self._anthropic = anthropic.Anthropic(api_key=self._anthropic_key)
        return self._anthropic

    # ── 공급자 호출 ───────────────────────────────────────────────────
    @staticmethod
    def _json_prompt(prompt: str, config) -> "tuple[str, bool]":
        schema = getattr(config, "response_json_schema", None) if config is not None else None
        mime = getattr(config, "response_mime_type", "") if config is not None else ""
        wants_json = schema is not None or mime == "application/json"
        if not wants_json:
            return prompt, False
        text = prompt + "\n\nRespond with a single valid JSON object only (no markdown, no commentary)."
        if schema is not None:
            text += " It must follow this JSON schema exactly:\n" + json.dumps(schema, ensure_ascii=False)
        return text, True

    def _call_gpt(self, prompt: str, wants_json: bool) -> str:
        kwargs = {"model": self.gpt_model, "messages": [{"role": "user", "content": prompt}]}
        if wants_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._gpt().chat.completions.create(**kwargs)
        choice = resp.choices[0]
        usage = getattr(resp, "usage", None)
        self._meta = {"finish": _safe_code(getattr(choice, "finish_reason", "")),
                      "tin": getattr(usage, "prompt_tokens", None), "tout": getattr(usage, "completion_tokens", None)}
        if getattr(choice, "finish_reason", "stop") != "stop":
            raise TextAIError("TEXT_AI_GPT_INCOMPLETE")
        text = (choice.message.content or "").strip()
        if not text:
            raise TextAIError("TEXT_AI_GPT_EMPTY")
        return text

    def _call_claude(self, prompt: str, wants_json: bool) -> str:
        resp = self._claude().messages.create(
            model=self.claude_model, max_tokens=4096, messages=[{"role": "user", "content": prompt}],
        )
        usage = getattr(resp, "usage", None)
        self._meta = {"finish": _safe_code(getattr(resp, "stop_reason", "")),
                      "tin": getattr(usage, "input_tokens", None), "tout": getattr(usage, "output_tokens", None)}
        text = "".join(getattr(b, "text", "") for b in (resp.content or [])).strip()
        if not text:
            raise TextAIError("TEXT_AI_CLAUDE_EMPTY")
        return text

    @staticmethod
    def _err_meta(exc: Exception) -> str:
        return f"error_type={type(exc).__name__} status={getattr(exc, 'status_code', None)}"

    def _attempt_meta(self, provider: str, model: str, exc: Exception, started: float) -> dict:
        """진단용 공급자 시도 요약(허용 필드만). 키·프롬프트·응답 본문·오류 문구 원문은 담지 않는다."""
        meta = getattr(self, "_meta", None) or {}
        status = getattr(exc, "status_code", None)
        return {
            "provider": provider, "model": _safe_code(model, 60),
            "status": status if isinstance(status, int) else None,
            "code": _provider_error_code(exc), "etype": type(exc).__name__,
            "finish": meta.get("finish", ""), "tin": meta.get("tin"), "tout": meta.get("tout"),
            "ms": int((time.time() - started) * 1000),
        }

    def _generate_text(self, prompt: str, config) -> _TextResponse:
        full_prompt, wants_json = self._json_prompt(prompt, config)
        gpt_error = None
        attempts: list = []
        self._meta = {}
        started = time.time()
        try:
            text = self._call_gpt(full_prompt, wants_json)
            if wants_json:
                text = _extract_json_text(text)
            self.last_provider = "gpt"
            logger.info("[TextAI] provider=gpt model=%s account=%s", self.gpt_model, self.account)
            return _TextResponse(text)
        except Exception as exc:  # 한도 초과·인증 오류·일시 장애·응답 형식 오류 전부 Claude 전환 사유
            gpt_error = exc
            attempts.append(self._attempt_meta("gpt", self.gpt_model, exc, started))
            logger.warning("[TextAI] GPT 실패 → Claude 전환 | account=%s | %s", self.account, self._err_meta(exc))
        self._meta = {}
        started = time.time()
        try:
            text = self._call_claude(full_prompt, wants_json)
            if wants_json:
                text = _extract_json_text(text)
            self.last_provider = "claude"
            logger.info("[TextAI] provider=claude model=%s account=%s (GPT 실패 후 전환)", self.claude_model, self.account)
            return _TextResponse(text)
        except Exception as exc:
            attempts.append(self._attempt_meta("claude", self.claude_model, exc, started))
            logger.error("[TextAI] GPT·Claude 모두 실패 — 게시 차단 | account=%s | gpt:%s | claude:%s",
                         self.account, self._err_meta(gpt_error), self._err_meta(exc))
            raise TextAIError("TEXT_AI_ALL_PROVIDERS_FAILED", providers=attempts) from exc

    # ── 게시 직전/글감 Safety (Gemini의 finish_reason 신호를 대체) ──────────
    def check_text_safety(self, text: str) -> "tuple[SafetyStatus, str]":
        """GPT는 OpenAI Moderation(무료·토큰 소모 없음), 실패 시 Claude 분류. 둘 다 실패하면 RETRY_EXHAUSTED."""
        try:
            result = self._gpt().moderations.create(model="omni-moderation-latest", input=text).results[0]
            if result.flagged:
                cats = result.categories
                names = [k for k, v in (cats.model_dump() if hasattr(cats, "model_dump") else dict(cats)).items() if v]
                logger.info("[TextAI] safety provider=gpt-moderation flagged account=%s", self.account)
                return "UNSAFE", "MODERATION:" + (names[0] if names else "FLAGGED")
            self.last_provider = "gpt"
            return "SAFE", "MODERATION_OK"
        except Exception as exc:
            logger.warning("[TextAI] Safety GPT 실패 → Claude 전환 | account=%s | %s", self.account, self._err_meta(exc))
        try:
            answer = self._call_claude(
                "Classify whether the following Instagram post text is safe to publish (no hate, harassment, "
                "sexual content, violence, self-harm, illegal activity or scams). Reply with exactly one word: "
                "SAFE or UNSAFE.\n\n" + text, False).strip().upper()
            self.last_provider = "claude"
            if answer.startswith("UNSAFE"):
                return "UNSAFE", "CLAUDE_UNSAFE"
            if answer.startswith("SAFE"):
                return "SAFE", "CLAUDE_SAFE"
            return "PERMANENT", "CLAUDE_UNPARSEABLE"
        except Exception as exc:
            logger.error("[TextAI] Safety GPT·Claude 모두 실패 — 게시 차단 | account=%s | %s",
                         self.account, self._err_meta(exc))
            return "RETRY_EXHAUSTED", "TEXT_AI_ALL_PROVIDERS_FAILED"


def _seo_prompt_rules(seo_keywords: str) -> str:
    """261029 B1 — 051 전용 Persona SEO 규칙. seo_keywords가 비면 빈 문자열을 반환해
    generate_caption() 프롬프트가 기존과 바이트 단위로 동일하게 유지된다."""
    keywords = (seo_keywords or "").strip()
    if not keywords:
        return ""
    return (
        "- Hashtags: English only and relevant to the product; no Korean or other non-English words\n"
        "- SEO: if one of these B2B keywords fits the product described in the post, use that ONE "
        "keyword naturally within the first 125 characters of the caption, at most twice in total: "
        f"{keywords}\n"
        "- Use only facts stated in the post. Never invent prices, MOQ, quantities, discounts, "
        "certifications or health claims\n"
        "- Do not add any call-to-action line\n"
    )


def generate_caption(text: str, *, seo_keywords: str = "") -> tuple[str, str]:
    """FB 포스트 텍스트 → (Instagram 캡션, 해시태그) 반환.

    seo_keywords(261029 B1, 선택): 비어 있으면 기존 프롬프트·반환 형식과 100% 동일.
    값이 있으면 상품에 맞는 B2B 키워드 1개 사용 규칙만 프롬프트에 추가한다(CTA는 코드가 붙인다).

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
        + _seo_prompt_rules(seo_keywords) +
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


_SEO_NUMBER_RE = re.compile(r"\d[\d,\.]*")
# 원문에 없는데 영어 출력에만 나오면 사람이 확인해야 하는 사실성 표현(번역 차이일 수 있어 폐기하지 않고 draft).
_SEO_UNVERIFIED_CLAIM_WORDS = (
    "fda", "certified", "certification", "guarantee", "lowest price", "best price",
    "free shipping", "clinically", "cure", "heal",
)


def _seo_numbers(text: str) -> set:
    out = set()
    for token in _SEO_NUMBER_RE.findall(text or ""):
        token = token.replace(",", "").strip(".")
        if token:
            out.add(token)
    return out


def validate_seo_caption(
    caption: str, hashtags: str, source_text: str, seo_keywords: str = "",
) -> tuple[str, str]:
    """261029 B1 — 051 전용 Persona SEO 캡션 결정적 검수. (status, code) 반환.

    status: "ok" / "draft"(사람 검수 후 승격 — 자동 게시 불가) / "reject"(저장하지 않음).
    - reject: 캡션·해시태그에 한글 등 비영어 문자(CAPTION_LANGUAGE_INVALID)
    - draft : 해시태그 5~10개 범위 밖, 캡션 숫자가 원문 숫자로 확인되지 않음, 원문에 없는
              인증·보증류 표현, 키워드 3회 이상 반복
    영어 숫자가 원문의 숫자와 같으면 통과한다(번역·단위 표기 차이는 오류로 보지 않으며,
    만·천 같은 한글 단위 환산처럼 확인할 수 없는 숫자는 draft로 보내 사람이 확인한다)."""
    caption = caption or ""
    hashtags = hashtags or ""
    for ch in caption + hashtags:
        if ord(ch) > 127 and ch.isalpha():
            return "reject", "CAPTION_LANGUAGE_INVALID"

    tags = [t for t in hashtags.split() if t.startswith("#")]
    if not 5 <= len(tags) <= 10:
        return "draft", "CAPTION_HASHTAG_COUNT"

    unknown_numbers = _seo_numbers(caption) - _seo_numbers(source_text)
    if unknown_numbers:
        return "draft", "CAPTION_FACT_UNVERIFIED"

    source_lower = (source_text or "").lower()
    caption_lower = caption.lower()
    for word in _SEO_UNVERIFIED_CLAIM_WORDS:
        pattern = rf"\b{re.escape(word)}\b"
        if re.search(pattern, caption_lower) and not re.search(pattern, source_lower):
            return "draft", "CAPTION_CLAIM_UNVERIFIED"

    for keyword in (k.strip().lower() for k in (seo_keywords or "").split(",")):
        if keyword and caption_lower.count(keyword) > 2:
            return "draft", "CAPTION_KEYWORD_STUFFING"

    return "ok", ""


def generate_hook_caption(
    title: str,
    core_message: str,
    prohibited_expression: str = "",
    tone_style: str = "",
    target_language: str = "EN",
    seo_keywords: str = "",
    conversion_cta: str = "",
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
    seo_line = (
        f"- Prefer these account SEO keywords when relevant to the verified source: {seo_keywords}\n"
        if seo_keywords else ""
    )
    prohibited_line = (
        f"- Do NOT use this expression or anything similar to it: {prohibited_expression}\n"
        if prohibited_expression else ""
    )

    prompt = (
        "Write a hooking Instagram caption based ONLY on the verified fact below, "
        "broken into required fields for a fixed visual template. "
        "Do not add any statistic, feature, or claim that is not explicitly stated "
        "here. Do not claim to have seen a screenshot, live demo, or runtime result "
        "unless the verified core message itself describes one.\n\n"
        f"Topic: {title}\n"
        f"Verified core message: {core_message}\n\n"
        f"{contract_block}"
        "Rules:\n"
        "- Fill in ALL 9 fields below — do not skip or merge any of them\n"
        "- HOOK_EMPATHY: a short sentence fragment capturing the target customer's "
        "current frustration, in their own words — may trail off without a full "
        "verb (e.g. ending in '...')\n"
        "- HOOK_QUESTION: one short question building curiosity about what "
        "successful accounts/companies actually do differently, ending in '?'\n"
        "- HOOK_REVEAL: one short sentence revealing that the answer is "
        "surprisingly simple, ending in '!'\n"
        "- HOW_POINT1 / HOW_POINT2: two separate concrete facts or steps drawn "
        "directly from the verified core message above\n"
        "- DETAIL_TITLE: a short 2-6 word title for a second supporting section, "
        "chosen to fit this specific topic (e.g. '구체적 방향', '전제 조건', "
        "'핵심 인사이트') — do not reuse the same title every time\n"
        "- DETAIL_BODY: one line listing concrete items from the verified core "
        "message, separated by ' · ' (a middle dot with spaces on both sides)\n"
        "- CORE_POINT: one line stating the single most important takeaway (may "
        "use ' · ' to contrast two halves)\n"
        "- MOTTO: one short, quotable sentence capturing the core insight as a "
        "memorable one-liner — do NOT add quotation marks yourself, they will be "
        "added automatically\n"
        "- Do NOT write a call-to-action field — a fixed one will be appended "
        "automatically after your fields\n"
        "- HARD LENGTH REQUIREMENT: keep the combined total of all 9 fields to "
        "roughly 420 characters or less, so that once the fixed template "
        "formatting, quotes, CTA line, and hashtags are added, the final post "
        "stays within 500 characters total\n"
        f"- Write in {target_language} only\n"
        f"{tone_line}"
        f"{seo_line}"
        f"{prohibited_line}"
        "- Hashtags: 5-10 relevant keywords with #, separated by spaces\n"
        "- Response format (use exactly this format, one field per line, no extra "
        "commentary before or after):\n"
        "HOOK_EMPATHY: <line>\n"
        "HOOK_QUESTION: <line>\n"
        "HOOK_REVEAL: <line>\n"
        "HOW_POINT1: <line>\n"
        "HOW_POINT2: <line>\n"
        "DETAIL_TITLE: <short title>\n"
        "DETAIL_BODY: <line>\n"
        "CORE_POINT: <line>\n"
        "MOTTO: <line>\n"
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
            # 260810 전면 개정 — 9요소(HOOK_EMPATHY/HOOK_QUESTION/HOOK_REVEAL/
            # HOW_POINT1/HOW_POINT2/DETAIL_TITLE/DETAIL_BODY/CORE_POINT/MOTTO)
            # 응답을 각 필드별로 파싱하고(260807 다중 줄 보존 원칙을 필드 단위로
            # 일반화), Validator로 요소 누락·500자 초과를 확인한다. CTA는 모델
            # 응답에 없다 — Validator가 고정 문구를 항상 붙인다. 하나라도
            # 실패하면 임의로 자르거나 재게시하지 않고 즉시 HOLD한다 — 기존
            # core_message 공란/Playbook 로딩 실패와 동일한 Fail-closed 계약.
            fields, hashtags = _parse_structured_caption_response(raw)
            caption, hashtags, hold_reason = _assemble_structured_caption(
                fields, hashtags, cta_line=conversion_cta,
            )
            if hold_reason:
                print(f"[HookCaption] 9요소 Validator HOLD | reason={hold_reason}")
                return "", ""
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
            if isinstance(active_client, TextAIFallbackClient):
                # 261106 — GPT/Claude 전환 client는 Gemini의 finish_reason 신호가 없으므로 자체 Safety 판정을 쓴다.
                return active_client.check_text_safety(caption)
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
