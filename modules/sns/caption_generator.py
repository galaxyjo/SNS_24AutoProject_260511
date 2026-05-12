import os
import time
from google import genai

_client = None

# 호출 간 최소 간격 (초) — 연속 호출 시 429 예방
_CALL_INTERVAL = 1.0
_last_call_ts  = 0.0

# 429 발생 시 재시도 대기 시간 (초)
_RETRY_DELAYS  = [5, 10, 20]


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
        "아래 페이스북 포스트 내용을 Instagram용 캡션과 해시태그로 변환해줘.\n\n"
        "규칙:\n"
        "- 캡션: 핵심 내용을 2~3문장으로 자연스럽게 요약 (이모지 포함)\n"
        "- 해시태그: 관련 키워드 5~10개, # 포함, 공백으로 구분\n"
        "- 응답 형식 (반드시 이 형식만 사용):\n"
        "CAPTION: <캡션 내용>\n"
        "HASHTAGS: <해시태그>\n\n"
        f"포스트 내용:\n{text[:1000]}"
    )

    for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
        if delay:
            print(f"[CAPTION] 429 재시도 {attempt}/{len(_RETRY_DELAYS)+1} | {delay}초 대기")
            time.sleep(delay)
        try:
            _throttle()
            client = _get_client()
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=prompt,
            )
            raw = response.text.strip()
            caption, hashtags = "", ""
            for line in raw.splitlines():
                if line.startswith("CAPTION:"):
                    caption = line[len("CAPTION:"):].strip()
                elif line.startswith("HASHTAGS:"):
                    hashtags = line[len("HASHTAGS:"):].strip()
            return caption, hashtags

        except Exception as e:
            err = str(e)
            if "429" in err and attempt <= len(_RETRY_DELAYS):
                continue
            print(f"[CAPTION] 생성 실패 (생략): {e}")
            return "", ""

    print("[CAPTION] 최대 재시도 초과 — 생략")
    return "", ""
