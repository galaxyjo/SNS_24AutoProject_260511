"""Package C0 — 신규 Post의 Canary 분류 계약.

이 모듈은 Scheduler를 멈추거나 Runtime을 재시작하지 않는다. 저장 요청이
``test``로 분류됐을 때 승인된 Safe Mode Context인지 검증하는 역할만 한다.
"""

from __future__ import annotations

import re
from datetime import datetime

from modules.common.canary_safe_mode import (
    CanarySafeModeError,
    get_canary_safe_mode_state,
)

_CANARY_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class CanaryClassificationError(ValueError):
    """Canary 분류 계약 위반."""


def validate_publication_candidate(
    data_classification: str = "",
    canary_run_id: str = "",
    post_status: str = "",
) -> None:
    """일반 Upload 경로가 Canary·비운영 Record를 공개 게시하지 못하게 한다.

    Package B 이전의 legacy Record는 분류값이 비어 있을 수 있어 호환을
    유지하되, ``test``/기타 분류와 Canary ID는 무조건 차단한다.
    """

    try:
        safe_mode_state = get_canary_safe_mode_state()
    except CanarySafeModeError as exc:
        raise CanaryClassificationError(str(exc)) from exc
    if safe_mode_state.enabled:
        raise CanaryClassificationError(
            "Canary Safe Mode에서는 Instagram 공개 게시 금지"
        )

    classification = (data_classification or "").strip()
    run_id = (canary_run_id or "").strip()
    status = (post_status or "").strip()

    if run_id:
        raise CanaryClassificationError(
            "canary_run_id가 있는 Record는 공개 게시 금지"
        )
    if classification not in ("", "production"):
        raise CanaryClassificationError(
            "production 또는 legacy Record만 공개 게시 가능"
        )
    if status and status != "ready":
        raise CanaryClassificationError(
            "post_status=ready Record만 공개 게시 가능"
        )


def validate_post_classification(
    data_classification: str,
    canary_run_id: str = "",
    post_status: str = "",
    *,
    now: datetime | None = None,
) -> None:
    """신규 Instagram Post 분류가 현재 Runtime Context와 일치하는지 검증한다.

    ``production``은 일반 Runtime에서만 허용하며 Canary ID를 가질 수 없다.
    ``test``는 명시적 Safe Mode, 승인된 Run ID, 미만료 Context, ``draft``
    상태를 모두 충족해야 한다. 다른 분류는 신규 저장에 사용할 수 없다.
    """

    classification = (data_classification or "").strip()
    run_id = (canary_run_id or "").strip()
    status = (post_status or "").strip()
    try:
        safe_mode_state = get_canary_safe_mode_state(now=now)
    except CanarySafeModeError as exc:
        raise CanaryClassificationError(str(exc)) from exc

    if classification == "production":
        if safe_mode_state.enabled:
            raise CanaryClassificationError(
                "Safe Mode에서는 production Record 저장 금지"
            )
        if run_id:
            raise CanaryClassificationError(
                "production Record에는 canary_run_id 저장 금지"
            )
        return

    if classification != "test":
        raise CanaryClassificationError(
            "신규 Record data_classification은 production 또는 test만 허용"
        )

    if not safe_mode_state.enabled:
        raise CanaryClassificationError(
            "일반 Runtime에서는 test Record 저장 금지"
        )
    if not _CANARY_RUN_ID_PATTERN.fullmatch(run_id):
        raise CanaryClassificationError("유효한 canary_run_id 필수")

    approved_run_id = safe_mode_state.run_id
    if not approved_run_id or run_id != approved_run_id:
        raise CanaryClassificationError(
            "canary_run_id가 승인된 Context와 일치하지 않음"
        )
    if status != "draft":
        raise CanaryClassificationError(
            "Canary Post는 post_status=draft만 허용"
        )
