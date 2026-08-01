"""modules/common/aijomoojin_binding_adapter.py — 260801 Step5 T1 aijomoojin 전용
Binding Adapter.

승인범위: IDN-000036(aijomoojin) 게시 직전, active Persona(PER-002)가 정확히
1건일 때만 통과시킨다. Persona 0건·중복·inactive·조회오류는 전부 차단(게시
호출 0회). Feature Flag 기본값 false, 이 계정에만 적용 — 다른 계정·기존
Legacy 경로는 무영향(account_code_ref가 aijomoojin이 아니면 즉시 통과).

외부 부품 원칙: 이 계정 전용 Binding 확인은 프로젝트 고유 Domain Logic이라
기존 Repository 메서드(get_active_persona_by_account_code_v2, 260801 T1 Gate
승인)를 그대로 REUSE한다. 외부 OSS는 이 1:1 계정-Persona 대조에 직접 맞지
않는다 — N/A—project-specific glue.
"""

import os

from modules.common.logger import get_logger

logger = get_logger(__name__)

AIJOMOOJIN_ACCOUNT_CODE = "IDN-000036"
AIJOMOOJIN_REQUIRED_PERSONA_CODE = "PER-002"


def aijomoojin_binding_adapter_enabled() -> bool:
    return os.getenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "false").strip().lower() == "true"


def verify_aijomoojin_binding(account_code_ref: str, repo) -> bool:
    """account_code_ref가 aijomoojin이 아니면 이 Adapter가 관여할 대상이 아니므로
    True(통과, 다른 계정 Legacy 경로 무변경). aijomoojin이면 active PER-002가
    정확히 1건일 때만 True, 그 외(0건/중복/inactive/조회오류/persona_code 불일치)는
    False(게시 호출 0회로 차단해야 함 — 호출부 책임)."""
    if account_code_ref != AIJOMOOJIN_ACCOUNT_CODE:
        return True

    try:
        persona = repo.get_active_persona_by_account_code_v2(account_code_ref)
    except Exception as exc:
        logger.warning(
            "[AijomoojinBinding] Persona 조회 실패(오류/중복 포함) — 게시 차단 | "
            "account_code_ref=%s | %s", account_code_ref, exc,
        )
        return False

    if persona is None:
        logger.warning(
            "[AijomoojinBinding] active Persona 0건 — 게시 차단 | account_code_ref=%s",
            account_code_ref,
        )
        return False

    if persona.get("persona_code", "") != AIJOMOOJIN_REQUIRED_PERSONA_CODE:
        logger.warning(
            "[AijomoojinBinding] persona_code 불일치 — 게시 차단 | expected=%s | actual=%s",
            AIJOMOOJIN_REQUIRED_PERSONA_CODE, persona.get("persona_code", ""),
        )
        return False

    return True
