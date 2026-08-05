"""
modules/common/credential_resolver.py — credential_key → .env 자격증명 조회

Account_Registry.credential_key는 비밀값이 아니라 .env 변수명을 가리키는
참조 키일 뿐이다(예: "AI" → AI_INSTA_IG_USER_ID / AI_INSTA_ACCESS_TOKEN).
실제 access_token은 이 함수를 통해서만 조회하며, 반환값·로그 어디에도
access_token 원문을 노출하지 않는다.

사용법:
    from modules.common.credential_resolver import resolve_credential, CredentialResolutionError
    try:
        cred = resolve_credential("AI")
    except CredentialResolutionError:
        # claim_post_for_upload() 호출 전에 게시를 중단해야 한다(fail-closed)
        ...
"""

import os
import re

from modules.common.logger import get_logger

logger = get_logger(__name__)

# credential_key 허용 형식: 대문자·숫자·언더스코어만 (소문자/공백/특수문자는 모호성 방지 위해 거부)
_KEY_PATTERN = re.compile(r"^[A-Z0-9_]+$")


class CredentialResolutionError(Exception):
    """credential_key 형식 오류 또는 .env에 대응 값이 없을 때 발생."""


class ResolvedCredential:
    __slots__ = ("ig_user_id", "access_token")

    def __init__(self, ig_user_id: str, access_token: str):
        self.ig_user_id = ig_user_id
        self.access_token = access_token


def resolve_credential(credential_key: str) -> ResolvedCredential:
    """credential_key로 .env의 {key}_INSTA_IG_USER_ID / {key}_INSTA_ACCESS_TOKEN을 조회한다.

    형식이 잘못됐거나 대응하는 .env 값이 없으면 CredentialResolutionError를 발생시킨다.
    """
    if not credential_key or not _KEY_PATTERN.fullmatch(credential_key):
        raise CredentialResolutionError(
            f"credential_key 형식 오류(허용: 대문자/숫자/언더스코어) | key={credential_key!r}"
        )

    ig_user_id = os.getenv(f"{credential_key}_INSTA_IG_USER_ID", "").strip()
    access_token = os.getenv(f"{credential_key}_INSTA_ACCESS_TOKEN", "").strip()

    if not ig_user_id or not access_token:
        logger.warning(f"[credential_resolver] 자격증명 미설정 | credential_key={credential_key}")
        raise CredentialResolutionError(
            f"credential_key={credential_key}에 대응하는 .env 값 없음"
        )

    return ResolvedCredential(ig_user_id=ig_user_id, access_token=access_token)


# ── 260805 Track B 7B-5 — 페르소나별 Gemini Key 분리 ──────────────────────
#
# Instagram 자격증명은 `{credential_key}_INSTA_*` 규칙을 따르지만, Gemini
# `.env` 변수명(`AIJOMOOJIN_GEMINI_API_KEY`)은 이 규칙이 정립되기 전에 이미
# 별도로 명명돼 있었다(`credential_key="AI"`와 접두사가 다름). `.env` 값
# 수정·재명명은 이번 승인 범위 밖이므로, 기존 변수명은 그대로 두고
# credential_key → Gemini 전용 접두사 매핑만 추가한다. 새 계정이 생기면
# 이 표에 한 줄만 추가하면 된다(새 프로그램·Scheduler 불필요).
_GEMINI_ENV_PREFIX_BY_CREDENTIAL_KEY = {
    "AI": "AIJOMOOJIN",  # nguyenknv15@gmail.com / IDN-000036 / aijomoojin
}


class GeminiCredential:
    __slots__ = ("api_key", "account_email")

    def __init__(self, api_key: str, account_email: str):
        self.api_key = api_key
        self.account_email = account_email


def resolve_gemini_credential(credential_key: str) -> GeminiCredential:
    """credential_key로 페르소나 전용 Gemini API Key를 조회한다.

    대응하는 매핑이 없거나 `.env`에 Key 값이 없으면 CredentialResolutionError를
    발생시킨다(Fail-closed) — 호출자는 공유/전역 GEMINI_API_KEY로 자동
    fallback해서는 안 된다. 반환값·로그 어디에도 api_key 원문을 남기지 않는다."""
    if not credential_key or not _KEY_PATTERN.fullmatch(credential_key):
        raise CredentialResolutionError(
            f"credential_key 형식 오류(허용: 대문자/숫자/언더스코어) | key={credential_key!r}"
        )

    prefix = _GEMINI_ENV_PREFIX_BY_CREDENTIAL_KEY.get(credential_key)
    if not prefix:
        logger.warning(f"[credential_resolver] Gemini 매핑 없음 | credential_key={credential_key}")
        raise CredentialResolutionError(
            f"credential_key={credential_key}에 대응하는 Gemini 자격증명 매핑 없음"
        )

    api_key = os.getenv(f"{prefix}_GEMINI_API_KEY", "").strip()
    account_email = os.getenv(f"{prefix}_GEMINI_ACCOUNT_EMAIL", "").strip()

    if not api_key:
        logger.warning(f"[credential_resolver] Gemini API Key 미설정 | credential_key={credential_key}")
        raise CredentialResolutionError(
            f"credential_key={credential_key}에 대응하는 Gemini API Key 없음"
        )

    return GeminiCredential(api_key=api_key, account_email=account_email)
