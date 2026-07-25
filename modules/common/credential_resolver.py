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
