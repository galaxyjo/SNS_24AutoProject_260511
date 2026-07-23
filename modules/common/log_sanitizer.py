"""
modules/common/log_sanitizer.py — 예외/URL 문자열에서 민감정보 제거

Graph API 등 외부 호출 실패 시 requests/urllib3가 만드는 예외 문자열에는
요청 URL 전체(쿼리스트링 포함)가 그대로 들어있어, access_token 등이
평문으로 로그에 남는 문제를 막기 위한 최소 유틸리티.

로그에 넘기기 전에 반드시 이 함수를 통과시킨다:
    logger.warning(f"... | {redact_sensitive(str(e))}")
"""

import re

_SENSITIVE_KEYS = r"(access[_-]?token|api[_-]?key|authorization|token)"

# 쿼리스트링 형태: key=value / key%3Dvalue (URL-encoded '=')
# value는 다음 구분자 전까지: & / %26(encoded '&') / 공백 / 따옴표 / 닫는 괄호 / 문자열 끝
_QUERY_STYLE = re.compile(
    _SENSITIVE_KEYS + r"(=|%3[Dd])" + r"(.+?)(?=&|%26|[\s'\")]|$)",
    re.IGNORECASE,
)

# 헤더 형태: Authorization: Bearer <token>
_HEADER_STYLE = re.compile(
    r"(authorization)(:\s*)(bearer\s+)?" + r"(.+?)(?=[\s'\")]|$)",
    re.IGNORECASE,
)


def redact_sensitive(text: str) -> str:
    """문자열 내 access_token/token/api_key/authorization 값을 [REDACTED]로 치환.

    키·값 형태(쿼리스트링, URL-encoded, Authorization 헤더)를 대소문자 무관하게
    처리하며, 다른 파라미터·오류 메시지·상태코드는 그대로 유지한다.
    """
    if not text:
        return text

    text = _QUERY_STYLE.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
    text = _HEADER_STYLE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3) or ''}[REDACTED]",
        text,
    )
    return text
