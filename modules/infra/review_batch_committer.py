"""
modules/infra/review_batch_committer.py
배치 저장 + GET 재검증 오케스트레이션.

한 건이라도 저장 실패하면 배치를 유지한다(committed=False) — 다음 배치로 넘어가지 않는다.
저장이 전부 성공해도, 저장 직후 GET으로 값이 실제로 반영됐는지 재확인해서
불일치가 있으면 역시 committed=False로 판정한다. PATCH 응답만 믿지 않는다.

검증 오류(예외)와 실제 값 불일치는 서로 다른 문제로 분리해서 다룬다 — 260712 실제 운영
50건 배치에서 GET 재검증 단계의 예외(HTTP 오류 등)를 전부 "값 불일치"로 뭉뚱그려 표시해서
실제로는 저장이 성공했는데도 실패로 오탐 표시된 사고가 있었음. 이후 재조사 결과 원인은
속도 제한이 아니라 예외 은폐(모든 예외 -> None) 자체였음이 확인됨(원인 정정: UNKNOWN이었던
"속도 제한" 가설은 실제 PATCH 간격 증거로 기각됨).
  - mismatched_ids: GET은 성공했지만 값이 기대와 다른 경우 (진짜 데이터 문제)
  - verification_errors: GET 자체가 예외를 던진 경우 — 상태 코드와 오류 종류를 보존해서 반환.
    이 경우도 안전을 위해 committed=False로 판정하지만, "데이터가 잘못됐다"는 뜻이 아니라
    "확인을 못 했다"는 뜻임을 호출자가 구분할 수 있게 한다.

429는 Retry-After(초) 기반으로, 5xx·타임아웃(상태 코드 없이 예외 타입명에 "Timeout" 포함)은
제한적 지수 백오프로 재시도한다. 403/404 등 그 외는 재시도하지 않고 즉시 오류로 기록한다.

repo가 던지는 예외에 `status_code`(int) 속성이 있으면 그걸로 429/5xx를 판별한다. 현재
AirtableRepository는 이 속성을 아직 노출하지 않으므로(속성 없으면 timeout 판별만 적용,
그 외는 전부 비재시도) 실제 연결은 별도 승인 단계에서 진행한다 — 이번 수정은 FakeRepo로만
검증한다.

Airtable/Streamlit import 금지 — repo 인자는 duck typing으로 다음 두 메서드만 있으면 된다:
  - save_review_decision(record_id: str, decision: str, note: str = "") -> None
  - get_review_status(record_id: str) -> str | None   (저장 후 재조회, 없으면 None)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from modules.infra.review_batch import build_review_payloads

_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 8.0
_DEFAULT_RETRY_AFTER_SECONDS = 1.0

SleepFn = Callable[[float], None]


@dataclass
class VerificationError:
    """GET 재검증 자체가 실패한 경우(값 불일치가 아니라 확인을 못 한 경우)."""
    record_id: str
    status_code: int | None
    error_type: str
    message: str


@dataclass
class CommitResult:
    committed: bool
    saved_ids: list[str] = field(default_factory=list)
    failed_id: str | None = None
    failed_error: str = ""
    verified: bool = False
    mismatched_ids: list[str] = field(default_factory=list)
    verification_errors: list[VerificationError] = field(default_factory=list)


@dataclass
class UndoResult:
    committed: bool
    reverted_ids: list[str] = field(default_factory=list)
    failed_id: str | None = None
    failed_error: str = ""
    verified: bool = False
    mismatched_ids: list[str] = field(default_factory=list)
    verification_errors: list[VerificationError] = field(default_factory=list)


def _is_retryable(status_code: int | None, error_type: str) -> bool:
    if status_code == 429:
        return True
    if status_code is not None and 500 <= status_code < 600:
        return True
    if status_code is None and "Timeout" in error_type:
        return True
    return False


def _get_status_with_retry(
    repo,
    record_id: str,
    sleep_fn: SleepFn = time.sleep,
) -> tuple[str | None, VerificationError | None]:
    """(status, None) 성공, 또는 (None, VerificationError) 실패 — 재시도 가능한 오류만 제한적으로 재시도."""
    attempt = 0
    while True:
        try:
            return repo.get_review_status(record_id), None
        except Exception as e:
            status_code = getattr(e, "status_code", None)
            # 네트워크 예외가 공통 예외 타입으로 래핑돼도(예: RepositoryUnavailableError),
            # original_error_type이 있으면 그걸로 판별한다 — 그래야 실제 타임아웃을
            # 403 같은 인증 오류와 같은 클래스여도 구분해서 재시도 대상으로 잡을 수 있다.
            error_type = getattr(e, "original_error_type", None) or type(e).__name__
            attempt += 1
            if not _is_retryable(status_code, error_type) or attempt > _MAX_RETRIES:
                return None, VerificationError(
                    record_id=record_id,
                    status_code=status_code,
                    error_type=error_type,
                    message=str(e),
                )
            if status_code == 429:
                wait = getattr(e, "retry_after_seconds", None) or _DEFAULT_RETRY_AFTER_SECONDS
            else:
                wait = min(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), _MAX_BACKOFF_SECONDS)
            sleep_fn(wait)


def _verify_one(
    repo,
    record_id: str,
    expected_status: str,
    sleep_fn: SleepFn,
) -> tuple[str | None, VerificationError | None]:
    """(mismatched_record_id, None) 진짜 값 불일치, (None, VerificationError) 확인 실패,
    (None, None) 정상 일치 — 셋 중 하나만 채워서 반환한다.

    get_review_status()는 계약상 레코드가 없으면(404) 예외가 아니라 None을 반환한다
    (AirtableRepository 기존 동작 유지). 260712 이후 사고 재조사에서 이 None을 그냥
    "값이 다름"으로 취급하면 실제로는 "레코드를 찾을 수 없음(404)"인 경우까지
    mismatched_ids로 잘못 분류되는 게 확인돼서, 여기서 명시적으로 verification_errors로
    분리한다.
    """
    actual, verr = _get_status_with_retry(repo, record_id, sleep_fn=sleep_fn)
    if verr is not None:
        return None, verr
    if actual is None:
        return None, VerificationError(
            record_id=record_id,
            status_code=404,
            error_type="NotFound",
            message="레코드를 찾을 수 없음(404) — get_review_status가 None 반환",
        )
    if actual != expected_status:
        return record_id, None
    return None, None


def commit_batch_with_verification(
    repo,
    batch_ids: list[str],
    block_ids: list[str],
    sleep_fn: SleepFn = time.sleep,
) -> CommitResult:
    """batch_ids 전원에 대해 저장 → 전부 성공하면 GET으로 재검증. 하나라도 저장 실패하면 즉시 중단."""
    payloads = build_review_payloads(batch_ids, block_ids)
    expected = {p["record_id"]: p["review_status"] for p in payloads}
    saved_ids: list[str] = []

    for p in payloads:
        try:
            repo.save_review_decision(p["record_id"], p["review_status"], "")
        except Exception as e:
            return CommitResult(
                committed=False,
                saved_ids=saved_ids,
                failed_id=p["record_id"],
                failed_error=str(e),
            )
        saved_ids.append(p["record_id"])

    mismatched: list[str] = []
    verification_errors: list[VerificationError] = []
    for rid, expected_status in expected.items():
        mismatch_id, verr = _verify_one(repo, rid, expected_status, sleep_fn)
        if verr is not None:
            verification_errors.append(verr)
        elif mismatch_id is not None:
            mismatched.append(mismatch_id)

    if mismatched or verification_errors:
        return CommitResult(
            committed=False,
            saved_ids=saved_ids,
            verified=False,
            mismatched_ids=mismatched,
            verification_errors=verification_errors,
        )

    return CommitResult(committed=True, saved_ids=saved_ids, verified=True)


def undo_batch_with_verification(
    repo,
    record_ids: list[str],
    sleep_fn: SleepFn = time.sleep,
) -> UndoResult:
    """record_ids 전원을 PENDING으로 되돌리고 GET으로 재검증. 하나라도 되돌리기 실패하면 즉시 중단."""
    reverted: list[str] = []

    for rid in record_ids:
        try:
            repo.save_review_decision(rid, "PENDING", "")
        except Exception as e:
            return UndoResult(
                committed=False,
                reverted_ids=reverted,
                failed_id=rid,
                failed_error=str(e),
            )
        reverted.append(rid)

    mismatched: list[str] = []
    verification_errors: list[VerificationError] = []
    for rid in record_ids:
        mismatch_id, verr = _verify_one(repo, rid, "PENDING", sleep_fn)
        if verr is not None:
            verification_errors.append(verr)
        elif mismatch_id is not None:
            mismatched.append(mismatch_id)

    if mismatched or verification_errors:
        return UndoResult(
            committed=False,
            reverted_ids=reverted,
            verified=False,
            mismatched_ids=mismatched,
            verification_errors=verification_errors,
        )

    return UndoResult(committed=True, reverted_ids=reverted, verified=True)


@dataclass
class VerifyOnlyResult:
    """PATCH 없이 GET만으로 기존 expected 값과 실제 값을 비교한 결과."""
    verified: bool
    mismatched_ids: list[str] = field(default_factory=list)
    verification_errors: list[VerificationError] = field(default_factory=list)


def verify_only(
    repo,
    expected: dict[str, str],
    sleep_fn: SleepFn = time.sleep,
) -> VerifyOnlyResult:
    """저장(PATCH)을 다시 하지 않고, expected(record_id -> 기대 review_status)와 현재 실제
    값을 GET만으로 비교한다. 260712 사고처럼 저장은 이미 끝났는데 확인만 실패했던 배치를
    재-PATCH 없이 다시 확인할 때 사용한다."""
    mismatched: list[str] = []
    verification_errors: list[VerificationError] = []

    for rid, expected_status in expected.items():
        mismatch_id, verr = _verify_one(repo, rid, expected_status, sleep_fn)
        if verr is not None:
            verification_errors.append(verr)
        elif mismatch_id is not None:
            mismatched.append(mismatch_id)

    if mismatched or verification_errors:
        return VerifyOnlyResult(
            verified=False,
            mismatched_ids=mismatched,
            verification_errors=verification_errors,
        )

    return VerifyOnlyResult(verified=True)
