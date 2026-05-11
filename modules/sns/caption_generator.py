import os
from google import genai

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY 환경변수 미설정")
        _client = genai.Client(api_key=api_key)
    return _client


def generate_caption(text: str) -> tuple[str, str]:
    """FB 포스트 텍스트 → (Instagram 캡션, 해시태그) 반환.

    API 키 미설정이거나 텍스트가 없으면 빈 문자열 반환.
    """
    if not text or not text.strip():
        return "", ""

    try:
        client = _get_client()
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
        print(f"[CAPTION] 생성 실패 (생략): {e}")
        return "", ""
