"""tests/test_review_batch_committer_batched.py — 260722 배치 API 속도개선 전용 테스트.

review_batch_committer.py가 repo에 batch_save_review_decisions/batch_get_review_status가
있으면(callable(getattr(...))로 감지) 청크(최대 10건) 단위 배치 호출로 전환하는 새 경로만
검증한다. 기존 단건 경로(test_review_batch_committer.py, 86 tests)는 이 변경으로 단 한 줄도
바뀌지 않았다 — FakeVerifiableRepo 등은 배치 메서드를 노출하지 않으므로 여전히 기존과
완전히 동일한 건당 호출 경로를 그대로 탄다.

260722 10:31 Codex 리뷰(1차)에서 지적된 두 가지를 반영해 초안에서 다시 작성됨:
  1. 배치 GET 응답에서 값이 None인 경우(응답에 없는 경우와 동일하게) mismatched_ids가
     아니라 VerificationError(NotFound)로 분류돼야 한다 — 단건 경로와 동일한 계약.
  2. 배치 PATCH가 예외를 던져도 "청크 전체 미반영"으로 단정하면 안 된다(Airtable 공식
     문서는 청크 원자성을 보장하지 않음, 타임아웃 등은 응답만 유실됐을 뿐일 수 있음) —
     422(입력 자체 거부)만 확정 실패, 그 외는 배치 GET으로 재확인 후 판정해야 한다.

여기서 확인하는 것:
  1. 청크 경계(10건씩)가 정확히 지켜지는지, 실제로 호출 횟수가 줄어드는지
  2. 422(입력 거부)는 재확인 없이 즉시 확정 실패로 처리(불필요한 GET 호출 없음)
  3. 422가 아닌 저장 예외는 배치 GET으로 재확인 — 실제로 반영돼 있었으면 "성공"으로
     인정하고 다음 청크로 계속 진행(투명한 복구)
  4. 재확인 결과 실제로 다른 값이 있으면(진짜 반영 안 됨) mismatched_ids로 확정 보고
  5. 재확인(GET) 자체가 안 되면(네트워크 재실패 등) verification_errors로만 보고하고
     failed_id/mismatched_ids에는 넣지 않는다 — "확정 실패"가 아니라 "확인 불가"이기 때문
  6. 청크 GET 검증(쓰기 후 정상 검증 경로)도 429/5xx/타임아웃 재시도, 403/404 즉시 처리 유지
  7. 응답에 없는 record_id와 값이 None인 record_id 둘 다 VerificationError(NotFound)로 통일
  8. verify_only는 배치 경로에서도 batch_save_review_decisions를 절대 호출하지 않는다

260722 10:51 Codex 리뷰(2차)에서 지적된 문제 반영: RepositoryInterface에 batch 메서드를
기본 구현(NotImplementedError)으로라도 남겨두면, 그 메서드 자체는 여전히 callable=True라서
_supports_batch()가 "지원함"으로 오인해 단건 폴백 대신 예외를 던지는 결함이 있었음.
batch_save_review_decisions/batch_get_review_status를 RepositoryInterface에서 완전히
제거(BatchReviewCapability Protocol에만 문서화)한 뒤, 아래 3가지 시나리오를 명시적으로
회귀 테스트한다:
  9. 단건 메서드만 가진 일반 Fake repo → 단건 경로 사용
  10. RepositoryInterface를 실제로 상속하지만 batch 메서드를 오버라이드하지 않은 구현체
      → 단건 경로 사용(예외 발생 없이 정상 폴백)
  11. 두 batch 메서드를 실제로 구현한 repo만 배치 경로 사용
"""

from modules.infra import repository_interface as _repository_interface
from modules.infra.review_batch_committer import (
    VerificationError,
    commit_batch_with_verification,
    undo_batch_with_verification,
    verify_only,
)


class FakeBatchRepo:
    """batch_save_review_decisions/batch_get_review_status만 노출하는 가짜 repo.

    fail_chunk_containing: 이 id가 포함된 청크의 batch_save_review_decisions 호출이 예외를 던진다.
    fail_status_code: 그 예외에 붙일 status_code(예: 422 = 확정 실패, None = 불확실한 오류).
    applies_despite_failure: True면 예외를 던지면서도 실제로는 값이 저장된 상태를 재현한다
    (타임아웃 등으로 응답만 유실되고 서버에는 실제로 반영된 상황).
    missing_for/mismatch_for: batch_get_review_status 응답 시뮬레이션(누락 또는 다른 값).
    get_call_errors: batch_get_review_status 호출 순서대로(청크 순서 기준) 소비되는 예외 큐 —
    소진되면 정상 응답으로 전환된다(재시도 후 성공 시나리오 재현용).
    """

    def __init__(
        self,
        fail_chunk_containing=(),
        fail_status_code=None,
        applies_despite_failure=False,
        mismatch_for=(),
        missing_for=(),
        get_call_errors=None,
    ):
        self.statuses: dict[str, str] = {}
        self.batch_save_calls: list[list[str]] = []
        self.batch_get_calls: list[list[str]] = []
        self.fail_chunk_containing = set(fail_chunk_containing)
        self.fail_status_code = fail_status_code
        self.applies_despite_failure = applies_despite_failure
        self.mismatch_for = set(mismatch_for)
        self.missing_for = set(missing_for)
        self.get_call_errors = list(get_call_errors or [])

    def batch_save_review_decisions(self, updates):
        ids = [u["record_id"] for u in updates]
        self.batch_save_calls.append(ids)
        if self.fail_chunk_containing & set(ids):
            if self.applies_despite_failure:
                for u in updates:
                    self.statuses[u["record_id"]] = u["decision"]
            exc = RuntimeError(f"simulated batch save failure for chunk {ids}")
            if self.fail_status_code is not None:
                exc.status_code = self.fail_status_code
            raise exc
        for u in updates:
            self.statuses[u["record_id"]] = u["decision"]

    def batch_get_review_status(self, record_ids):
        self.batch_get_calls.append(list(record_ids))
        if self.get_call_errors:
            raise self.get_call_errors.pop(0)
        result = {}
        for rid in record_ids:
            if rid in self.missing_for:
                continue
            if rid in self.mismatch_for:
                result[rid] = "STALE"
            else:
                result[rid] = self.statuses.get(rid)
        return result


class _HttpError(Exception):
    def __init__(self, message, status_code=None, retry_after_seconds=None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


def _sleep_recorder():
    calls = []

    def _sleep(seconds):
        calls.append(seconds)

    return calls, _sleep


BATCH25 = [f"r{i}" for i in range(25)]  # 10 + 10 + 5 청크 3개


class TestChunkingReducesCallCount:
    def test_25_records_use_exactly_3_batch_save_and_3_batch_get_calls(self):
        repo = FakeBatchRepo()
        result = commit_batch_with_verification(repo, BATCH25, block_ids=[])
        assert result.committed is True
        assert len(repo.batch_save_calls) == 3
        assert len(repo.batch_get_calls) == 3
        assert [len(c) for c in repo.batch_save_calls] == [10, 10, 5]
        assert [len(c) for c in repo.batch_get_calls] == [10, 10, 5]
        assert sorted(result.saved_ids) == sorted(BATCH25)

    def test_exactly_10_records_is_a_single_chunk(self):
        repo = FakeBatchRepo()
        ten = [f"r{i}" for i in range(10)]
        result = commit_batch_with_verification(repo, ten, block_ids=[])
        assert result.committed is True
        assert len(repo.batch_save_calls) == 1
        assert len(repo.batch_get_calls) == 1

    def test_11_records_split_into_10_and_1(self):
        repo = FakeBatchRepo()
        eleven = [f"r{i}" for i in range(11)]
        result = commit_batch_with_verification(repo, eleven, block_ids=[])
        assert result.committed is True
        assert [len(c) for c in repo.batch_save_calls] == [10, 1]


class TestChunkWrite422IsDefiniteFailure:
    """422(입력 자체 거부)는 Airtable이 쓰기를 시도하기도 전에 거부하는 것이므로,
    재확인(GET) 없이 즉시 확정 실패로 처리해야 한다 — 불필요한 GET 호출도 없어야 한다."""

    def test_422_in_second_chunk_stops_immediately_without_reconciliation_get(self):
        repo = FakeBatchRepo(fail_chunk_containing=["r15"], fail_status_code=422)
        result = commit_batch_with_verification(repo, BATCH25, block_ids=[])
        assert result.committed is False
        assert sorted(result.saved_ids) == sorted([f"r{i}" for i in range(10)])  # 1번째 청크만 저장됨
        assert result.failed_id == "r10"  # 실패한 청크의 첫 id
        assert "422" in result.failed_error
        assert "r15" in result.failed_error  # 실패한 청크 전체 id가 오류 메시지에 나열됨
        assert len(repo.batch_save_calls) == 2  # 3번째 청크는 시도조차 안 함
        assert repo.batch_get_calls == []  # 422는 재확인 GET을 아예 하지 않는다

    def test_422_in_first_chunk_saves_nothing(self):
        repo = FakeBatchRepo(fail_chunk_containing=["r3"], fail_status_code=422)
        result = commit_batch_with_verification(repo, BATCH25, block_ids=[])
        assert result.committed is False
        assert result.saved_ids == []
        assert result.failed_id == "r0"
        assert len(repo.batch_save_calls) == 1
        assert repo.batch_get_calls == []


class TestChunkWriteUncertainFailureIsReconciled:
    """422가 아닌 저장 예외(타임아웃/커넥션 오류/5xx 등)는 실제로 반영됐을 수 있으므로,
    배치 GET으로 재확인한 뒤에만 최종 판정한다."""

    def test_uncertain_failure_that_actually_applied_is_treated_as_saved(self):
        """서버에는 실제로 반영됐는데 응답만 유실된 상황 — 재확인 결과 전부 기대값과 일치하면
        저장 성공으로 인정하고 다음 청크로 계속 진행해야 한다(투명한 복구)."""
        repo = FakeBatchRepo(
            fail_chunk_containing=["r15"],
            applies_despite_failure=True,  # 예외는 던지지만 실제로는 저장됨
        )
        result = commit_batch_with_verification(repo, BATCH25, block_ids=[])
        assert result.committed is True  # 전부 실제로 반영돼 있었으므로 최종적으로 성공
        assert sorted(result.saved_ids) == sorted(BATCH25)
        assert result.failed_id is None
        assert len(repo.batch_save_calls) == 3  # 예외가 나도 계속 다음 청크 진행
        # 2번째 청크에 대해 재확인 GET 1회 + 최종 전체 검증 3회(1,2,3번째 청크) = 4회
        assert len(repo.batch_get_calls) == 4

    def test_uncertain_failure_that_genuinely_did_not_apply_is_mismatch_not_failed_id(self):
        """실제로 반영 안 된 게 재확인으로 확정되면 mismatched_ids로 보고한다 —
        failed_id(단정)가 아니라 mismatched_ids(재확인으로 확정된 진짜 불일치)."""
        chunk2 = [f"r{i}" for i in range(10, 20)]
        repo = FakeBatchRepo(fail_chunk_containing=["r15"])  # applies_despite_failure=False(기본)
        for rid in chunk2:
            repo.statuses[rid] = "OLD_VALUE"  # 재확인 시 "다른 값이 이미 있음"이 확인되도록 미리 세팅
        result = commit_batch_with_verification(repo, BATCH25, block_ids=[])
        assert result.committed is False
        assert result.failed_id is None  # 확정 실패(422)가 아니므로 failed_id를 쓰지 않는다
        assert sorted(result.mismatched_ids) == sorted(chunk2)  # 재확인으로 확정된 진짜 불일치
        assert sorted(result.saved_ids) == sorted([f"r{i}" for i in range(10)])  # 1번째 청크만 저장됨
        assert len(repo.batch_save_calls) == 2  # 3번째 청크는 시도 안 함

    def test_uncertain_failure_where_reconciliation_get_itself_fails_is_verification_error(self):
        """재확인(GET) 자체가 안 되면(네트워크 재실패 등) "확정 실패"가 아니라
        verification_errors로만 보고해야 한다 — failed_id도 mismatched_ids도 아니다."""
        repo = FakeBatchRepo(
            fail_chunk_containing=["r3"],
            get_call_errors=[_HttpError("forbidden", status_code=403)],  # 재확인 GET도 실패
        )
        ten = [f"r{i}" for i in range(10)]
        result = commit_batch_with_verification(repo, ten, block_ids=[])
        assert result.committed is False
        assert result.failed_id is None
        assert result.mismatched_ids == []
        assert len(result.verification_errors) == 10  # 청크 전체 id
        assert all(e.status_code == 403 for e in result.verification_errors)


class TestChunkVerificationMismatch:
    def test_mismatch_in_third_chunk_reported(self):
        repo = FakeBatchRepo(mismatch_for=["r22"])
        result = commit_batch_with_verification(repo, BATCH25, block_ids=["r22"])
        assert result.committed is False
        assert result.mismatched_ids == ["r22"]
        assert sorted(result.saved_ids) == sorted(BATCH25)  # 저장 자체는 전부 성공

    def test_missing_record_in_chunk_is_verification_error_not_mismatch(self):
        """batch_get_review_status 응답에 없는 id는 단건 404-None 계약과 동일하게 처리돼야 한다."""
        repo = FakeBatchRepo(missing_for=["r5"])
        result = commit_batch_with_verification(repo, BATCH25, block_ids=["r5"])
        assert result.committed is False
        assert "r5" not in result.mismatched_ids
        assert any(
            e.record_id == "r5" and e.status_code == 404 and e.error_type == "NotFound"
            for e in result.verification_errors
        )

    def test_present_but_none_value_in_chunk_is_verification_error_not_mismatch(self):
        """응답엔 있지만 값 자체가 None(필드가 비어있음)인 경우도 mismatched_ids가 아니라
        VerificationError(NotFound)여야 한다 — 260722 Codex 리뷰 1차 지적 사항.
        (FakeBatchRepo는 미저장 상태를 그대로 None으로 돌려주므로, 저장하지 않은 채로
        검증만 호출하면 이 상황이 자연히 재현된다.)"""
        repo = FakeBatchRepo()
        expected = {"r1": "BLOCK"}  # r1은 저장된 적 없음 — batch_get이 {"r1": None}을 돌려줌
        result = verify_only(repo, expected)
        assert result.verified is False
        assert result.mismatched_ids == []  # None을 값 불일치로 잘못 넣지 않음
        assert any(e.record_id == "r1" and e.status_code == 404 and e.error_type == "NotFound"
                   for e in result.verification_errors)


class TestChunkVerificationErrorClassification:
    def test_whole_chunk_403_produces_one_verification_error_per_id_in_chunk(self):
        repo = FakeBatchRepo(get_call_errors=[_HttpError("forbidden", status_code=403)])
        ten = [f"r{i}" for i in range(10)]
        result = commit_batch_with_verification(repo, ten, block_ids=[])
        assert result.committed is False
        assert len(result.verification_errors) == 10  # 청크 전체 id 각각
        assert all(e.status_code == 403 for e in result.verification_errors)
        assert {e.record_id for e in result.verification_errors} == set(ten)
        # 재시도 없음 확인 — 이 청크에 대한 GET 호출이 딱 1번뿐이어야 함
        assert len(repo.batch_get_calls) == 1

    def test_429_retries_chunk_and_eventually_succeeds(self):
        repo = FakeBatchRepo(get_call_errors=[_HttpError("rate limited", status_code=429, retry_after_seconds=2.0)])
        ten = [f"r{i}" for i in range(10)]
        sleep_calls, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, ten, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is True
        assert sleep_calls == [2.0]
        assert len(repo.batch_get_calls) == 2  # 실패 1회 + 재시도 성공 1회, 같은 청크

    def test_5xx_retries_with_backoff_across_chunk(self):
        repo = FakeBatchRepo(get_call_errors=[
            _HttpError("server error", status_code=503),
            _HttpError("server error", status_code=503),
        ])
        ten = [f"r{i}" for i in range(10)]
        sleep_calls, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, ten, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is True
        assert sleep_calls == [1.0, 2.0]

    def test_exhausted_retries_reported_as_verification_error_for_whole_chunk(self):
        repo = FakeBatchRepo(get_call_errors=[
            _HttpError("rate limited", status_code=429, retry_after_seconds=0.01) for _ in range(10)
        ])
        ten = [f"r{i}" for i in range(10)]
        _, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, ten, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is False
        assert result.mismatched_ids == []
        assert len(result.verification_errors) == 10


class TestUndoUsesBatchPath:
    def test_undo_25_records_uses_chunked_batch_calls(self):
        repo = FakeBatchRepo()
        for rid in BATCH25:
            repo.statuses[rid] = "BLOCK"
        result = undo_batch_with_verification(repo, BATCH25)
        assert result.committed is True
        assert repo.statuses == {rid: "PENDING" for rid in BATCH25}
        assert len(repo.batch_save_calls) == 3
        assert len(repo.batch_get_calls) == 3

    def test_undo_422_is_definite_failure(self):
        repo = FakeBatchRepo(fail_chunk_containing=["r3"], fail_status_code=422)
        for rid in BATCH25:
            repo.statuses[rid] = "BLOCK"
        result = undo_batch_with_verification(repo, BATCH25)
        assert result.committed is False
        assert result.failed_id == "r0"
        assert repo.batch_get_calls == []

    def test_undo_uncertain_failure_that_actually_applied_recovers(self):
        repo = FakeBatchRepo(fail_chunk_containing=["r3"], applies_despite_failure=True)
        for rid in BATCH25:
            repo.statuses[rid] = "BLOCK"
        result = undo_batch_with_verification(repo, BATCH25)
        assert result.committed is True
        assert repo.statuses == {rid: "PENDING" for rid in BATCH25}


class TestVerifyOnlyUsesBatchPathWithoutWriting:
    def test_verify_only_never_calls_batch_save(self):
        repo = FakeBatchRepo()
        for rid in BATCH25:
            repo.statuses[rid] = "BLOCK"
        expected = {rid: "BLOCK" for rid in BATCH25}
        result = verify_only(repo, expected)
        assert result.verified is True
        assert repo.batch_save_calls == []
        assert len(repo.batch_get_calls) == 3

    def test_verify_only_reports_mismatch_via_batch_path(self):
        repo = FakeBatchRepo()
        repo.statuses["r1"] = "PASS"
        result = verify_only(repo, {"r1": "BLOCK"})
        assert result.verified is False
        assert result.mismatched_ids == ["r1"]
        assert repo.batch_save_calls == []


class _PlainSingleRecordRepo:
    """RepositoryInterface를 상속하지 않는, 순수 duck-typed 단건 repo(기존 Fake들과 동일한 성격)."""

    def __init__(self):
        self.save_calls: list[tuple[str, str]] = []
        self.statuses: dict[str, str] = {}

    def save_review_decision(self, record_id, decision, other_note=""):
        self.save_calls.append((record_id, decision))
        self.statuses[record_id] = decision

    def get_review_status(self, record_id):
        return self.statuses.get(record_id)


def _make_repository_interface_subclass_without_batch_override():
    """RepositoryInterface를 실제로 상속하되 batch_save_review_decisions/
    batch_get_review_status는 오버라이드하지 않은 최소 구현체를 만든다.

    RepositoryInterface에는 abstractmethod가 40여 개 있어 전부 손으로 스텁을 쓰는 대신,
    __abstractmethods__ 목록을 그대로 순회해 자동으로 no-op 스텁을 생성한다 — 오직
    save_review_decision/get_review_status만 실제 동작하도록 오버라이드한다. 이 클래스가
    batch_save_review_decisions를 정의하지 않는다는 사실 자체가 260722 Codex 리뷰 2차의
    핵심 검증 대상이다(RepositoryInterface가 더 이상 이 메서드를 선언하지 않으므로
    상속만으로는 생기지 않아야 한다)."""
    abstract_names = _repository_interface.RepositoryInterface.__abstractmethods__
    stubs = {name: (lambda self, *a, **k: None) for name in abstract_names}

    def save_review_decision(self, record_id, decision, other_note=""):
        self.save_calls.append((record_id, decision))
        self.statuses[record_id] = decision

    def get_review_status(self, record_id):
        return self.statuses.get(record_id)

    def __init__(self):
        self.save_calls = []
        self.statuses = {}

    stubs["__init__"] = __init__
    stubs["save_review_decision"] = save_review_decision
    stubs["get_review_status"] = get_review_status

    cls = type(
        "MinimalInterfaceRepoWithoutBatchOverride",
        (_repository_interface.RepositoryInterface,),
        stubs,
    )
    return cls()


class TestCapabilityDetectionScopedToActualImplementation:
    """260722 10:51 Codex 리뷰 2차 지적 회귀 테스트 — RepositoryInterface에서
    batch_save_review_decisions/batch_get_review_status를 완전히 제거했으므로, 아래
    세 시나리오가 각각 정확히 의도한 경로를 타야 한다."""

    def test_plain_duck_typed_repo_without_batch_methods_uses_single_record_path(self):
        repo = _PlainSingleRecordRepo()
        result = commit_batch_with_verification(repo, ["r1", "r2"], block_ids=["r1"])
        assert result.committed is True
        assert len(repo.save_calls) == 2  # 건당 순차 호출(배치 없음)

    def test_repository_interface_subclass_without_batch_override_uses_single_record_path(self):
        """RepositoryInterface를 실제로 상속했지만 batch 메서드를 구현하지 않은 경우 —
        예외 없이 정상적으로 단건 경로로 폴백해야 한다(수정 전에는 기본 NotImplementedError
        메서드가 callable=True라서 배치 경로로 오인돼 이 호출에서 예외가 났었음)."""
        repo = _make_repository_interface_subclass_without_batch_override()
        assert getattr(repo, "batch_save_review_decisions", None) is None
        assert getattr(repo, "batch_get_review_status", None) is None

        result = commit_batch_with_verification(repo, ["r1", "r2"], block_ids=["r1"])

        assert result.committed is True
        assert len(repo.save_calls) == 2
        assert repo.statuses == {"r1": "BLOCK", "r2": "PASS"}

    def test_repo_implementing_both_batch_methods_uses_batch_path(self):
        """대조군 — 두 batch 메서드를 실제로 제공하면 배치 경로가 사용돼야 한다."""
        repo = FakeBatchRepo()
        result = commit_batch_with_verification(repo, ["r1", "r2"], block_ids=["r1"])
        assert result.committed is True
        assert len(repo.batch_save_calls) == 1  # 건당이 아니라 청크 1회
        assert len(repo.batch_get_calls) == 1
