import os
import time
from google import genai

_client = None

# 호출 간 최소 간격 (초) — free tier 30 RPM 기준 안전 마진 확보
_CALL_INTERVAL = 4.0
_last_call_ts  = 0.0

# 429 발생 시 재시도 대기 시간 (초)
_RETRY_DELAYS  = [20, 40, 60]


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

    429 응답 시 최대 3회 재시도 (5s → 10s → 20s 백오프).
    API 키 미설정이거나 텍스트가 없으면 빈 문자열 반환.
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

    for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
        if delay:
            print(f"[CAPTION] 429 재시도 {attempt}/{len(_RETRY_DELAYS)+1} | {delay}초 대기")
            time.sleep(delay)
        _call_started = None
        try:
            _throttle()
            client = _get_client()
            _call_started = time.time()
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            print(f"[CAPTION] Gemini 호출 완료 | {time.time() - _call_started:.1f}초")
            raw = response.text.strip()
            caption, hashtags = "", ""
            for line in raw.splitlines():
                if line.startswith("CAPTION:"):
                    caption = line[len("CAPTION:"):].strip()
                elif line.startswith("HASHTAGS:"):
                    hashtags = line[len("HASHTAGS:"):].strip()
            return caption, hashtags

        except Exception as e:
            if _call_started is not None:
                print(f"[CAPTION] Gemini 호출 실패 | {time.time() - _call_started:.1f}초")
            err = str(e)
            if "429" in err and attempt <= len(_RETRY_DELAYS):
                continue
            print(f"[CAPTION] 생성 실패 (생략): {e}")
            return "", ""

    print("[CAPTION] 최대 재시도 초과 — 생략")
    return "", ""


def generate_hook_caption(
    title: str,
    core_message: str,
    prohibited_expression: str = "",
    tone_style: str = "",
    target_language: str = "EN",
) -> tuple[str, str]:
    """Track B Source Topic(title/core_message) → 후킹형 Instagram 캡션+해시태그.

    core_message에 없는 수치·기능·성과는 만들지 않는다(Sourcebook Usage Rule #2/#6과
    동일 제약을 프롬프트에 명시). prohibited_expression이 있으면 그 표현을 피하도록
    지시한다. core_message가 비어 있으면 즉시 빈 문자열 반환 — 근거 없는 콘텐츠 생성 금지.

    429 응답 시 최대 3회 재시도(_RETRY_DELAYS와 동일 정책, generate_caption()과 REUSE).
    """
    if not core_message or not core_message.strip():
        return "", ""

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

    for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
        if delay:
            print(f"[HookCaption] 429 재시도 {attempt}/{len(_RETRY_DELAYS)+1} | {delay}초 대기")
            time.sleep(delay)
        _call_started = None
        try:
            _throttle()
            client = _get_client()
            _call_started = time.time()
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            print(f"[HookCaption] Gemini 호출 완료 | {time.time() - _call_started:.1f}초")
            raw = response.text.strip()
            caption, hashtags = "", ""
            for line in raw.splitlines():
                if line.startswith("CAPTION:"):
                    caption = line[len("CAPTION:"):].strip()
                elif line.startswith("HASHTAGS:"):
                    hashtags = line[len("HASHTAGS:"):].strip()
            return caption, hashtags

        except Exception as e:
            if _call_started is not None:
                print(f"[HookCaption] Gemini 호출 실패 | {time.time() - _call_started:.1f}초")
            err = str(e)
            if "429" in err and attempt <= len(_RETRY_DELAYS):
                continue
            print(f"[HookCaption] 생성 실패 (생략): {e}")
            return "", ""

    print("[HookCaption] 최대 재시도 초과 — 생략")
    return "", ""


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
