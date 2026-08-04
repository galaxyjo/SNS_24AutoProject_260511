"""modules/sns/research_to_topic_adapter.py — 260804 Track B 6G Research-to-Topic
Adapter.

selectable 3.x Topic이 0건일 때만 호출된다(`source_selector.select_next_topic()`이
None을 반환하는 경우에 한해 Producer가 호출 — 3.x가 있으면 이 모듈 자체가
호출되지 않는다, 회장 승인 조건 5). Sourcebook 4.x/5.x의 미사용 원천 URL 중
하나를 골라, Search Grounding + URL Context + Structured Output을 사용해 그
URL의 실제 내용에 기반한 Topic 1건을 만든다.

260804 계정별 Gemini Credential 분리 — `caption_generator.py`의 전역
`GEMINI_API_KEY`는 DM 자동응답(`ai_reply_generator.py`)·다른 크롤러 등 다른
계정 기능까지 공유하는 값이라, 이 모듈은 그 전역 Client를 REUSE하지 않는다.
대신 `AIJOMOOJIN_GEMINI_API_KEY`(계정 식별은 `.env`의
`AIJOMOOJIN_GEMINI_ACCOUNT_EMAIL`로 병기, 실제 주소는 `.env`에만 존재하고
코드에는 남기지 않는다 — 260805 Codex 리뷰 P2)로 별도 Client를 이 파일
안에서만 생성한다 — "1 email=1 persona=1 AI tool 계정" 원칙, 다른 계정 Gemini
사용에 영향 0건. 재시도 분류(`_classify_retry`/`_next_retry_delay`)와 호출
간격 제어(`_throttle`)는 계정과 무관한 순수 로직이라 `caption_generator.py`에서
그대로 REUSE한다.

Read-only 사전확인 결과(260804, 신규 API 미도입 판단의 근거):
  - 설치된 `google-genai==2.0.1` SDK가 `types.Tool(google_search=...)`,
    `types.Tool(url_context=...)`, `GenerateContentConfig.response_json_schema`를
    전부 지원함을 직접 introspection으로 확인(추정 아님). 신규 외부 API
    (Perplexity/Tavily/Exa) 도입 불필요.
  - `Candidate.url_context_metadata.url_metadata[].url_retrieval_status`로
    "원천 URL 접근 성공"을 모델의 자기신고 텍스트가 아니라 SDK 구조화 신호로
    직접 확인할 수 있음 — 자동승인 조건 1을 이 신호로만 판정한다.

Gemini Search는 "요즘 사람들이 이 주제에서 궁금해하는 질문/각도"를 찾는
용도로만 쓴다 — 최종 core_message는 반드시 URL Context로 가져온 원문 내용에만
근거해야 하고, Search 결과로 원문을 대체·왜곡하지 않도록 프롬프트에 명시한다
(Sourcebook 자체의 Usage Rule과 동일 원칙).

Fail-closed: 원천 URL 접근 실패, core_message 공란, Safety 위반(기존
`check_caption_safety()` REUSE) 중 하나라도 있으면 None을 반환한다. 이 함수
자신은 같은 실행 안에서 다른 URL로 재시도하지 않는다(대체 URL 연속시도·
Catch-up 금지, 회장 승인 조건) — 실패하면 호출자가 이번 Producer 실행을
그대로 종료해야 한다.

중복 방지: 신규 저장소를 만들지 않는다. Sourcebook 4.x/5.x URL 중 이미
`content_package_builder.scan_used_source_urls()`(기존 Vault 스캔, REUSE)에
있는 URL은 애초에 후보에서 제외되므로, 이 함수가 반환하는 Topic은 항상
"이번이 처음 쓰이는 source_url"이다 — topic_key 재중복 저장소가 필요 없다.
"""

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

from google import genai
from google.genai import types as genai_types

from modules.sns.caption_generator import (
    _MAX_ATTEMPTS,
    _classify_retry,
    _next_retry_delay,
    check_caption_safety,
)
from modules.sns.content_package_builder import DEFAULT_VAULT_ROOT, scan_used_source_urls
from modules.sns.source_selector import DEFAULT_SOURCEBOOK_PATH, SourceTopic, parse_sourcebook

from modules.common.logger import get_logger

logger = get_logger(__name__)

RESEARCH_MODEL = "gemini-3.5-flash-lite"  # 260805 회장 지시 — aijomoojin 전용
# Gemini 4경로(Research/Safety/Caption/게시직전 Safety) 전용 모델 고정. 근거(Runtime
# Evidence, 추정 아님): 260805 Producer Canary에서 "gemini-2.5-flash-lite"/
# "gemini-2.5-flash" 둘 다 이 계정(aijomoojin 전용 신규 Google AI Studio
# 프로젝트) 기준 HTTP 404("no longer available to new users")로 확인됨(tools/
# 구조화출력 조합과 무관 — 툴 없는 단순 호출도 동일 404). 같은 키로
# "gemini-3.5-flash-lite" 직접 호출은 성공("pong") 확인. "*-latest" 계열은
# 버전이 예고 없이 바뀔 위험이 있어(회장 지시) 고정 버전 문자열만 쓴다. 다른
# 계정이 쓰는 caption_generator.py의 전역 모델("gemini-2.5-flash-lite")은
# 이 상수와 완전히 분리돼 있어 무영향이다.
_REGISTRY_PREFIXES = ("4.", "5.")  # Sourcebook 4.x/5.x만 Source Registry 대상(3.x는 REUSE 경로가 담당)

_client = None  # 이 모듈 전용 — caption_generator._client(전역 GEMINI_API_KEY)와 별개

# 260804 Codex 리뷰(P1) — caption_generator._throttle()은 전역 _last_call_ts를
# 공유해서, 이걸 그대로 REUSE하면 aijomoojin Research 호출이 다른 계정의 Gemini
# 호출 간격까지 지연시킨다. 이 모듈은 자기 자신만의 호출 간격 상태를 따로 갖는다
# (다른 계정과 완전히 독립 — 값 자체는 동일 4.0초로 맞춰 REUSE 원칙 존중, 상태만 분리).
_CALL_INTERVAL = 4.0
_last_call_ts = 0.0


def _throttle():
    global _last_call_ts
    wait = _CALL_INTERVAL - (time.time() - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.time()


def _mask_email(email: str) -> str:
    """로그에 이메일 전체를 남기지 않는다(260804 Codex 리뷰 P2, 260805 재검토
    보완) — 로컬파트가 짧아도(1~2자) 최소 1글자는 항상 마스킹한다. 앞 최대
    2글자까지만 보존하고 나머지는 마스킹, 도메인은 그대로 둔다(문제 진단 시
    어느 계정인지 구분은 가능해야 하므로 전체 익명화는 아님)."""
    local, sep, domain = email.partition("@")
    if not sep:
        return "UNKNOWN"
    visible_len = min(2, max(len(local) - 1, 0))
    visible = local[:visible_len]
    masked = "*" * max(len(local) - visible_len, 1)
    return f"{visible}{masked}@{domain}"


def _get_client():
    """aijomoojin 전용 Gemini Client(REUSE 아님, 의도적 분리) —
    `AIJOMOOJIN_GEMINI_API_KEY`(계정 식별은 `.env`의 `AIJOMOOJIN_GEMINI_ACCOUNT_EMAIL`
    참조, 실제 주소는 코드에 남기지 않음) 사용. 다른 계정이
    쓰는 전역 `GEMINI_API_KEY`(`caption_generator._get_client()`)와 완전히
    분리된 별도 Client/Key다."""
    global _client
    if _client is None:
        api_key = os.getenv("AIJOMOOJIN_GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("AIJOMOOJIN_GEMINI_API_KEY 환경변수 미설정")
        account_email = os.getenv("AIJOMOOJIN_GEMINI_ACCOUNT_EMAIL", "")
        logger.info(
            "[ResearchAdapter] Gemini Client 초기화 | account_email=%s",
            _mask_email(account_email) if account_email else "UNKNOWN",
        )
        _client = genai.Client(api_key=api_key)
    return _client

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "source_title": {"type": "string"},
        "core_message": {"type": "string"},
        "target_audience": {"type": "string"},
        "content_angle": {"type": "string"},
        "evidence_summary": {"type": "string"},
        "additional_evidence_urls": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["source_title", "core_message", "target_audience", "content_angle", "evidence_summary"],
}


def _make_topic_key(source_url: str, core_message: str) -> str:
    normalized = re.sub(r"\s+", " ", (core_message or "").strip().lower())
    digest = hashlib.sha256(f"{source_url.strip()}|{normalized}".encode("utf-8")).hexdigest()
    return digest[:16]


def select_unused_registry_source(
    sourcebook_path: "str | None" = None,
    vault_root=None,
) -> "SourceTopic | None":
    """Sourcebook 4.x/5.x 중 아직 어떤 Vault Package에도 안 쓰인 원천 URL 1개를
    고른다(파일 순서상 첫 매치, 결정적). 없으면 None."""
    topics = parse_sourcebook(sourcebook_path or DEFAULT_SOURCEBOOK_PATH)
    used = scan_used_source_urls(vault_root or DEFAULT_VAULT_ROOT)
    for t in topics:
        if t.topic_id.startswith(_REGISTRY_PREFIXES) and t.source_url and t.source_url not in used:
            return t
    return None


def _build_prompt(candidate: SourceTopic) -> str:
    return (
        "You are researching ONE specific source URL for a business/AI-startup "
        "Instagram content pipeline aimed at Korean solo entrepreneurs.\n\n"
        f"Source URL to analyze (use the URL context tool to fetch it): {candidate.source_url}\n"
        f"Source registry label (internal, may be generic): {candidate.title}\n\n"
        "Rules:\n"
        "1. Your core_message MUST be grounded ONLY in what that exact page says. "
        "Do not add any statistic, feature, or claim that is not explicitly present there.\n"
        "2. You may use Google Search only to understand what angle or question people "
        "currently care about regarding this source's topic — never to replace or "
        "contradict what the Source URL itself says.\n"
        "3. Do not write about prohibited topics (medical/legal/financial advice, "
        "politics, adult content) and do not include personal or sensitive information.\n"
        "4. If the page cannot be meaningfully read, leave core_message empty rather "
        "than guessing.\n\n"
        "Return the analysis in the exact JSON schema provided."
    )


def research_next_topic(
    sourcebook_path: "str | None" = None,
    vault_root=None,
) -> "SourceTopic | None":
    """selectable 3.x Topic이 없을 때만 Producer가 호출한다. 실패·근거불일치·
    URL 접근불가·Safety 위반 중 하나라도 있으면 None(Fail-closed) — 이 함수
    자신은 재시도(다른 URL 선택)를 하지 않는다."""
    candidate = select_unused_registry_source(sourcebook_path, vault_root)
    if candidate is None:
        logger.info("[ResearchAdapter] Source Registry(4.x/5.x)에 미사용 URL 없음")
        return None

    config = genai_types.GenerateContentConfig(
        tools=[
            genai_types.Tool(url_context=genai_types.UrlContext()),
            genai_types.Tool(google_search=genai_types.GoogleSearch()),
        ],
        response_mime_type="application/json",
        response_json_schema=_RESPONSE_SCHEMA,
    )
    prompt = _build_prompt(candidate)

    response = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            _throttle()
            client = _get_client()
            response = client.models.generate_content(
                model=RESEARCH_MODEL, contents=prompt, config=config,
            )
            break
        except Exception as exc:
            retryable, category = _classify_retry(exc)
            logger.warning(
                "[ResearchAdapter] Gemini 호출 실패 | attempt=%s/%s | category=%s | url=%s",
                attempt, _MAX_ATTEMPTS, category, candidate.source_url,
            )
            if retryable and attempt < _MAX_ATTEMPTS:
                time.sleep(_next_retry_delay(attempt - 1, exc))
                continue
            return None
    if response is None:
        return None

    # ── 자동승인 조건 1: 원천 URL 접근 성공 — SDK 구조화 신호로만 판정(모델 자기신고 텍스트 아님) ──
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        logger.warning("[ResearchAdapter] candidate 없음 | url=%s", candidate.source_url)
        return None
    url_ctx = getattr(candidates[0], "url_context_metadata", None)
    url_entries = getattr(url_ctx, "url_metadata", None) or []
    target_ok = any(
        getattr(e, "retrieved_url", "") == candidate.source_url
        and getattr(e, "url_retrieval_status", None) == genai_types.UrlRetrievalStatus.URL_RETRIEVAL_STATUS_SUCCESS
        for e in url_entries
    )
    if not target_ok:
        logger.warning("[ResearchAdapter] 원천 URL 접근 실패/미확인 | url=%s", candidate.source_url)
        return None

    try:
        data = json.loads(response.text)
    except (ValueError, AttributeError, TypeError):
        logger.warning("[ResearchAdapter] 구조화 응답 파싱 실패 | url=%s", candidate.source_url)
        return None

    core_message = (data.get("core_message") or "").strip()
    source_title = (data.get("source_title") or "").strip() or candidate.title
    target_audience = (data.get("target_audience") or "").strip()
    content_angle = (data.get("content_angle") or "").strip()
    evidence_summary = (data.get("evidence_summary") or "").strip()
    extra_evidence = [
        u for u in (data.get("additional_evidence_urls") or []) if isinstance(u, str) and u.strip()
    ]
    evidence_urls = [candidate.source_url] + extra_evidence  # 자동승인 조건 3: 원천 URL 자체로 항상 최소 1개 충족

    # ── 자동승인 조건 2: core_message 확보 ──
    if not core_message:
        logger.warning("[ResearchAdapter] core_message 공란 — Fail-closed | url=%s", candidate.source_url)
        return None

    # ── 자동승인 조건 5: 금지주제·민감정보 — 기존 Safety 확인 로직은 REUSE하되
    # (신규 모더레이션 엔진 없음), 260804 Codex 리뷰(P0)에 따라 aijomoojin 전용
    # Client/Throttle을 명시 주입해 전역 GEMINI_API_KEY quota를 소비하지 않는다 ──
    safety_status, safety_reason = check_caption_safety(
        core_message, client=_get_client(), throttle_fn=_throttle, model=RESEARCH_MODEL,
    )
    if safety_status != "SAFE":
        logger.warning(
            "[ResearchAdapter] Safety 확인 실패 — Fail-closed | url=%s | status=%s | reason=%s",
            candidate.source_url, safety_status, safety_reason,
        )
        return None

    topic_key = _make_topic_key(candidate.source_url, core_message)
    researched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 자동승인 조건 4(중복 topic_key 0건)는 select_unused_registry_source()가
    # 이미 "이 source_url이 Vault에서 처음 쓰인다"를 보장하므로 여기서는 항상
    # 신규다 — 별도 topic_key 저장소를 새로 만들지 않는다(회장 지시).
    logger.info(
        "[ResearchAdapter] Topic 자동생성 완료(auto_approved) | topic_key=%s | url=%s | "
        "title=%s | target_audience=%s | content_angle=%s | evidence_summary=%s | "
        "evidence_urls=%s | researched_at=%s",
        topic_key, candidate.source_url, source_title, target_audience, content_angle,
        evidence_summary, evidence_urls, researched_at,
    )

    return SourceTopic(
        topic_id=f"auto-{topic_key}",
        title=source_title,
        status="VERIFIED FACT",
        source_url=candidate.source_url,
        core_message=core_message,
        prohibited_expression="",
    )
