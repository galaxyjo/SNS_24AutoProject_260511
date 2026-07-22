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

── 260722 배치 API 속도개선 (260722 10:31 Codex 리뷰 반영 후 개정) ────────────
repo가 아래 두 메서드도 추가로 노출하면(선택 기능 — callable(getattr(...))로 감지,
없어도 전혀 문제없음) 위 단건 메서드를 순차 호출하는 대신 Airtable 배치 엔드포인트
(요청당 최대 10건)로 묶어서 호출한다. `BatchReviewCapability`는 타입 문서화용 Protocol일
뿐 RepositoryInterface의 필수 계약이 아니다 — 감지·폴백은 항상 duck typing으로 이뤄진다:
  - batch_save_review_decisions(updates: list[dict]) -> None
  - batch_get_review_status(record_ids: list[str]) -> dict[str, str | None]

**배치 쓰기의 원자성은 공식적으로 보장되지 않는다.** Airtable 공식 문서(API 호출 제한)는
호출당 최대 10건이라는 사실만 명시할 뿐, 청크 전체가 원자적으로 성공/실패한다는 보장은
확인되지 않았다(260722 Codex 리뷰 지적) — 특히 타임아웃/커넥션 오류/5xx는 "서버 응답만
유실됐고 실제로는 반영됐을 수 있는" 상태다. 이 코드는 그 불확실성을 다음과 같이 처리한다:
  - 422(Airtable이 쓰기 전에 입력 자체를 거부)만 "확실히 미반영"으로 간주해 즉시 실패 처리.
  - 그 외 모든 저장 예외(타임아웃/커넥션 오류/429/5xx 등)는 즉시 실패로 단정하지 않고,
    배치 GET으로 실제 값을 재확인한다 — 전부 기대값과 일치하면 저장 성공으로 인정하고
    다음 청크로 계속 진행하며, 확인 자체가 안 되면(네트워크 재실패 등) "확정 실패"가 아니라
    verification_errors(확인 불가)로 보고해 위 계층(review_grid_ui)이 batch를 영구
    실패(mark_failed) 처리하지 않고 재확인 가능한 상태로 남겨둘 수 있게 한다.

배치 GET 검증(쓰기 후 재검증, 그리고 쓰기 실패 시 재확인 둘 다)은 청크 단위로 429/5xx/
타임아웃 재시도, 403/404 즉시 오류 처리를 적용한다 — 청크 전체가 실패하면 그 청크에 속한
모든 record_id 각각에 VerificationError를 만든다(HTTP 레벨에서는 어느 레코드가 원인인지
구분할 수 없으므로). 응답에 없는 record_id와 응답은 있으나 값이 None인 record_id 둘 다
단건 경로의 404-None 계약과 동일하게 VerificationError(NotFound)로 분류한다 — 둘 다
mismatched_ids(진짜 값 불일치)로 잘못 분류하지 않는다.

repo가 배치 메서드를 노출하지 않는 기존 Fake/테스트 더블은 전과 완전히 동일하게
단건 경로로 동작한다 — 이 변경으로 기존 동작이 바뀌는 대상은 없다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

from modules.infra.review_batch import build_review_payloads

_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 8.0
_DEFAULT_RETRY_AFTER_SECONDS = 1.0
_BATCH_CHUNK_SIZE = 10

SleepFn = Callable[[float], None]


@runtime_checkable
class BatchReviewCapability(Protocol):
    """선택 기능 문서화용 Protocol — RepositoryInterface의 필수 계약이 아니다.
    isinstance 판정에는 쓰지 않는다(Protocol의 runtime_checkable은 시그니처가 아니라
    메서드 존재만 확인해 오탐 가능성이 있음) — 실제 감지는 `_supports_batch()`가
    callable(getattr(...))로 각 메서드를 개별 확인한다."""

    def batch_save_review_decisions(self, updates: list[dict]) -> None: ...
    def batch_get_review_status(self, record_ids: list[str]) -> dict: ...


def _chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _supports_batch(repo) -> bool:
    return (
        callable(getattr(repo, "batch_save_review_decisions", None))
        and callable(getattr(repo, "batch_get_review_status", None))
    )


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


def _batch_get_status_with_retry(
    repo,
    chunk_ids: list[str],
    sleep_fn: SleepFn,
) -> tuple[dict[str, str | None] | None, VerificationError | None]:
    """(status_map, None) 청크 GET 성공, 또는 (None, VerificationError-템플릿) 청크 전체 실패.
    실패 시 반환하는 VerificationError.record_id는 비워둔다 — 호출자가 청크의 모든
    record_id 각각에 대해 복제해서 채운다(HTTP 레벨에서는 어느 레코드가 원인인지 알 수 없음)."""
    attempt = 0
    while True:
        try:
            return repo.batch_get_review_status(chunk_ids), None
        except Exception as e:
            status_code = getattr(e, "status_code", None)
            error_type = getattr(e, "original_error_type", None) or type(e).__name__
            attempt += 1
            if not _is_retryable(status_code, error_type) or attempt > _MAX_RETRIES:
                return None, VerificationError(
                    record_id="", status_code=status_code, error_type=error_type, message=str(e),
                )
            if status_code == 429:
                wait = getattr(e, "retry_after_seconds", None) or _DEFAULT_RETRY_AFTER_SECONDS
            else:
                wait = min(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), _MAX_BACKOFF_SECONDS)
            sleep_fn(wait)


def _verify_chunk(
    repo,
    chunk_ids: list[str],
    expected: dict[str, str],
    sleep_fn: SleepFn,
) -> tuple[list[str], list[VerificationError]]:
    """chunk_ids(최대 10건) 전체를 배치 GET 1회로 검증. (mismatched_ids, verification_errors) 반환."""
    status_map, verr_template = _batch_get_status_with_retry(repo, chunk_ids, sleep_fn)
    if verr_template is not None:
        return [], [
            VerificationError(
                record_id=rid,
                status_code=verr_template.status_code,
                error_type=verr_template.error_type,
                message=verr_template.message,
            )
            for rid in chunk_ids
        ]
    mismatched: list[str] = []
    verification_errors: list[VerificationError] = []
    for rid in chunk_ids:
        # dict.get()은 "응답에 아예 없는 id"와 "응답엔 있지만 값이 None(필드 비어있음)인 id"를
        # 똑같이 None으로 접어준다 — 단건 경로(get_review_status의 404-None 계약)가 이 둘을
        # 구분하지 않고 전부 VerificationError(NotFound)로 분류하는 것과 반드시 동일해야 한다
        # (260722 Codex 리뷰 지적: None을 mismatched_ids로 잘못 넣으면 복구 가능한 배치를
        # 진짜 실패로 오판할 수 있음).
        actual = status_map.get(rid)
        if actual is None:
            verification_errors.append(VerificationError(
                record_id=rid,
                status_code=404,
                error_type="NotFound",
                message="레코드를 찾을 수 없거나 review_status가 비어있음 — batch_get_review_status None 반환",
            ))
        elif actual != expected[rid]:
            mismatched.append(rid)
    return mismatched, verification_errors


def _verify_all(
    repo,
    expected: dict[str, str],
    sleep_fn: SleepFn,
) -> tuple[list[str], list[VerificationError]]:
    """expected(record_id -> 기대 review_status) 전체를 검증 — repo가 배치 메서드를
    노출하면 청크(최대 10건)당 배치 GET 1회, 아니면 기존과 동일하게 건당 GET 1회."""
    mismatched: list[str] = []
    verification_errors: list[VerificationError] = []

    if _supports_batch(repo):
        for chunk_ids in _chunked(list(expected.keys()), _BATCH_CHUNK_SIZE):
            m, v = _verify_chunk(repo, chunk_ids, expected, sleep_fn)
            mismatched.extend(m)
            verification_errors.extend(v)
    else:
        for rid, expected_status in expected.items():
            mismatch_id, verr = _verify_one(repo, rid, expected_status, sleep_fn)
            if verr is not None:
                verification_errors.append(verr)
            elif mismatch_id is not None:
                mismatched.append(mismatch_id)

    return mismatched, verification_errors


@dataclass
class _SaveOutcome:
    """_save_all()의 반환값. 세 가지 결과 중 정확히 하나만 의미를 가진다:
      1. 전부 성공: failed_id/mismatched_ids/verification_errors 전부 비어있음.
      2. 확정 실패(422처럼 입력 자체가 거부됨): failed_id/failed_error에 채워짐.
      3. 청크 GET 재확인 결과 확정된 문제: mismatched_ids(진짜 값 불일치) 또는
         verification_errors(확인 자체 불가 — "확정 실패"가 아님, 호출자가 batch를
         영구 실패 처리하지 않고 재확인 가능한 상태로 남겨둘 수 있어야 한다)."""
    saved_ids: list[str] = field(default_factory=list)
    failed_id: str | None = None
    failed_error: str = ""
    mismatched_ids: list[str] = field(default_factory=list)
    verification_errors: list[VerificationError] = field(default_factory=list)


def _save_all(
    repo,
    payloads: list[dict],
    sleep_fn: SleepFn = time.sleep,
) -> _SaveOutcome:
    """payloads([{"record_id","review_status"}, ...])를 전부 저장. repo가 배치 메서드를
    노출하면 청크(최대 10건)당 배치 PATCH 1회, 아니면 기존과 동일하게 건당 PATCH 1회.

    실패 시 saved_ids는 그 이전에 이미 저장된 것만 포함 — 실패한 청크(또는 레코드)와
    그 이후는 시도하지 않는다(기존 정신 유지).

    배치 경로에서 PATCH 자체가 예외를 던져도 "청크 전체 미반영"으로 단정하지 않는다
    (260722 Codex 리뷰 지적 — Airtable 공식 문서는 청크의 원자성을 보장하지 않고,
    타임아웃/커넥션 오류는 응답만 유실됐을 뿐 실제로는 반영됐을 수 있다). 422(입력 자체
    거부)만 확실한 실패로 간주하고, 그 외 예외는 배치 GET으로 실제 값을 재확인한다."""
    saved_ids: list[str] = []

    if _supports_batch(repo):
        for chunk in _chunked(payloads, _BATCH_CHUNK_SIZE):
            chunk_ids = [p["record_id"] for p in chunk]
            expected_chunk = {p["record_id"]: p["review_status"] for p in chunk}
            updates = [
                {"record_id": p["record_id"], "decision": p["review_status"], "other_note": ""}
                for p in chunk
            ]
            try:
                repo.batch_save_review_decisions(updates)
            except Exception as e:
                status_code = getattr(e, "status_code", None)
                if status_code == 422:
                    # Airtable이 쓰기를 시도하기 전에 입력 자체를 거부 — 확실히 미반영.
                    failed_error = (
                        f"청크 저장 거부됨(422, {len(chunk_ids)}건: {', '.join(chunk_ids)}) — {e}"
                    )
                    return _SaveOutcome(saved_ids=saved_ids, failed_id=chunk_ids[0], failed_error=failed_error)

                # 그 외(타임아웃/커넥션 오류/429/5xx 등)는 실제로 반영됐을 수 있음 —
                # 확정 실패로 단정하지 않고 배치 GET으로 재확인한다.
                mismatched, verification_errors = _verify_chunk(repo, chunk_ids, expected_chunk, sleep_fn)
                if not mismatched and not verification_errors:
                    # 재확인 결과 전부 기대값과 일치 — 저장은 실제로 성공한 것으로 인정.
                    saved_ids.extend(chunk_ids)
                    continue
                return _SaveOutcome(
                    saved_ids=saved_ids,
                    mismatched_ids=mismatched,
                    verification_errors=verification_errors,
                )
            saved_ids.extend(chunk_ids)
        return _SaveOutcome(saved_ids=saved_ids)

    for p in payloads:
        try:
            repo.save_review_decision(p["record_id"], p["review_status"], "")
        except Exception as e:
            return _SaveOutcome(saved_ids=saved_ids, failed_id=p["record_id"], failed_error=str(e))
        saved_ids.append(p["record_id"])
    return _SaveOutcome(saved_ids=saved_ids)


def commit_batch_with_verification(
    repo,
    batch_ids: list[str],
    block_ids: list[str],
    sleep_fn: SleepFn = time.sleep,
) -> CommitResult:
    """batch_ids 전원에 대해 저장 → 전부 성공하면 GET으로 재검증. 하나라도 저장 실패하면 즉시 중단.

    repo가 배치 메서드(batch_save_review_decisions/batch_get_review_status)를 노출하면
    청크(최대 10건) 단위로 묶어서 호출해 왕복 횟수를 줄인다 — 노출하지 않으면 기존과
    완전히 동일한 건당 순차 호출로 동작한다."""
    payloads = build_review_payloads(batch_ids, block_ids)
    expected = {p["record_id"]: p["review_status"] for p in payloads}

    save_outcome = _save_all(repo, payloads, sleep_fn)
    if save_outcome.failed_id is not None:
        return CommitResult(
            committed=False,
            saved_ids=save_outcome.saved_ids,
            failed_id=save_outcome.failed_id,
            failed_error=save_outcome.failed_error,
        )
    if save_outcome.mismatched_ids or save_outcome.verification_errors:
        # 쓰기 예외 발생 후 GET 재확인 결과 확정된 문제(진짜 불일치) 또는 확인 자체 불가.
        # 후자는 "확정 실패"가 아니므로 호출자가 batch를 영구 실패 처리하면 안 된다.
        return CommitResult(
            committed=False,
            saved_ids=save_outcome.saved_ids,
            verified=False,
            mismatched_ids=save_outcome.mismatched_ids,
            verification_errors=save_outcome.verification_errors,
        )
    saved_ids = save_outcome.saved_ids

    mismatched, verification_errors = _verify_all(repo, expected, sleep_fn)

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
    """record_ids 전원을 PENDING으로 되돌리고 GET으로 재검증. 하나라도 되돌리기 실패하면 즉시 중단.

    repo가 배치 메서드를 노출하면 청크(최대 10건) 단위로 묶어서 호출한다."""
    payloads = [{"record_id": rid, "review_status": "PENDING"} for rid in record_ids]

    save_outcome = _save_all(repo, payloads, sleep_fn)
    if save_outcome.failed_id is not None:
        return UndoResult(
            committed=False,
            reverted_ids=save_outcome.saved_ids,
            failed_id=save_outcome.failed_id,
            failed_error=save_outcome.failed_error,
        )
    if save_outcome.mismatched_ids or save_outcome.verification_errors:
        return UndoResult(
            committed=False,
            reverted_ids=save_outcome.saved_ids,
            verified=False,
            mismatched_ids=save_outcome.mismatched_ids,
            verification_errors=save_outcome.verification_errors,
        )
    reverted = save_outcome.saved_ids

    expected = {rid: "PENDING" for rid in record_ids}
    mismatched, verification_errors = _verify_all(repo, expected, sleep_fn)

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
    재-PATCH 없이 다시 확인할 때 사용한다. repo가 배치 메서드를 노출하면 청크 단위로 묶는다."""
    mismatched, verification_errors = _verify_all(repo, expected, sleep_fn)

    if mismatched or verification_errors:
        return VerifyOnlyResult(
            verified=False,
            mismatched_ids=mismatched,
            verification_errors=verification_errors,
        )

    return VerifyOnlyResult(verified=True)
