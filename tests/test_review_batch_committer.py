"""tests/test_review_batch_committer.py — modules/infra/review_batch_committer.py 단위 테스트.

FakeVerifiableRepo만 사용 (실제 Airtable 연결 없음) — Codex 3A 요구사항:
저장 성공/중간 실패/GET 불일치 각각의 동작, 한 건이라도 실패하면 배치 유지,
전부 저장+GET 일치해야 커밋 허용, 실행취소도 성공 검증 전엔 완료 처리 금지.

260712 실제 운영 사고(GET 재검증 예외가 전부 "값 불일치"로 뭉뚱그려져 실제로는 성공한
저장이 실패로 오탐 표시됨) 이후 추가된 검증: verification_errors와 mismatched_ids 분리,
429/5xx/타임아웃만 제한적 재시도, 403/404는 즉시 오류 처리(재시도 없음).
"""

from modules.infra.review_batch_committer import (
    VerificationError,
    commit_batch_with_verification,
    undo_batch_with_verification,
    verify_only,
)


class FakeVerifiableRepo:
    """저장 성공/실패, GET 일치/불일치를 자유롭게 시뮬레이션하는 가짜 repo.

    force_none_for: 실제 AirtableRepository.get_review_status()의 404 계약(예외 아님, None
    반환)을 그대로 재현 — 저장은 성공했지만 조회하면 레코드가 없다고 나오는 상황.
    """

    def __init__(self, fail_on_save_for=(), mismatch_for=(), force_none_for=()):
        self.statuses: dict[str, str] = {}
        self.save_calls: list[tuple[str, str]] = []
        self.get_calls: list[str] = []
        self.fail_on_save_for = set(fail_on_save_for)
        self.mismatch_for = set(mismatch_for)
        self.force_none_for = set(force_none_for)

    def save_review_decision(self, record_id, decision, note=""):
        self.save_calls.append((record_id, decision))
        if record_id in self.fail_on_save_for:
            raise RuntimeError(f"simulated save failure for {record_id}")
        self.statuses[record_id] = decision

    def get_review_status(self, record_id):
        self.get_calls.append(record_id)
        if record_id in self.force_none_for:
            return None  # 실제 AirtableRepository의 404 계약(예외 아님, None)
        if record_id in self.mismatch_for:
            return "STALE"  # PATCH는 200을 줬지만 실제로는 반영 안 된 상황 시뮬레이션
        return self.statuses.get(record_id)


BATCH = ["r1", "r2", "r3", "r4", "r5"]


class TestCommitAllSucceed:
    def test_all_saved_and_verified_committed_true(self):
        repo = FakeVerifiableRepo()
        result = commit_batch_with_verification(repo, BATCH, block_ids=["r2", "r4"])
        assert result.committed is True
        assert result.verified is True
        assert sorted(result.saved_ids) == sorted(BATCH)
        assert result.mismatched_ids == []
        assert result.failed_id is None

    def test_zero_selected_all_pass_and_committed(self):
        repo = FakeVerifiableRepo()
        result = commit_batch_with_verification(repo, BATCH, block_ids=[])
        assert result.committed is True
        assert repo.statuses == {rid: "PASS" for rid in BATCH}

    def test_select_all_all_block_and_committed(self):
        repo = FakeVerifiableRepo()
        result = commit_batch_with_verification(repo, BATCH, block_ids=BATCH)
        assert result.committed is True
        assert repo.statuses == {rid: "BLOCK" for rid in BATCH}


class TestCommitMidBatchSaveFailure:
    def test_failure_on_third_record_stops_immediately(self):
        repo = FakeVerifiableRepo(fail_on_save_for=["r3"])
        result = commit_batch_with_verification(repo, BATCH, block_ids=[])
        assert result.committed is False
        assert result.failed_id == "r3"
        assert result.saved_ids == ["r1", "r2"]  # r3 이후는 시도조차 안 함
        assert len(repo.save_calls) == 3  # r1, r2, r3(실패) — r4, r5는 호출 안 됨

    def test_batch_not_marked_complete_on_partial_failure(self):
        """부분 실패 시 성공으로 표시되면 안 된다 — committed False가 그 신호."""
        repo = FakeVerifiableRepo(fail_on_save_for=["r1"])
        result = commit_batch_with_verification(repo, BATCH, block_ids=BATCH)
        assert result.committed is False
        assert result.saved_ids == []  # 첫 건부터 실패
        assert "simulated save failure" in result.failed_error

    def test_last_record_failure_still_reports_correctly(self):
        repo = FakeVerifiableRepo(fail_on_save_for=["r5"])
        result = commit_batch_with_verification(repo, BATCH, block_ids=[])
        assert result.committed is False
        assert result.failed_id == "r5"
        assert result.saved_ids == ["r1", "r2", "r3", "r4"]


class TestCommitGetMismatch:
    def test_mismatch_after_successful_saves_marks_not_committed(self):
        repo = FakeVerifiableRepo(mismatch_for=["r3"])
        result = commit_batch_with_verification(repo, BATCH, block_ids=["r3"])
        assert result.committed is False
        assert result.verified is False
        assert result.mismatched_ids == ["r3"]
        # 저장 자체(PATCH)는 전부 시도됐음 — 문제는 GET 재검증에서 발견됨
        assert sorted(result.saved_ids) == sorted(BATCH)

    def test_multiple_mismatches_all_reported(self):
        repo = FakeVerifiableRepo(mismatch_for=["r1", "r5"])
        result = commit_batch_with_verification(repo, BATCH, block_ids=[])
        assert result.committed is False
        assert sorted(result.mismatched_ids) == ["r1", "r5"]

    def test_get_called_for_every_batch_id_after_all_saves_succeed(self):
        repo = FakeVerifiableRepo()
        commit_batch_with_verification(repo, BATCH, block_ids=["r1"])
        assert sorted(repo.get_calls) == sorted(BATCH)


class TestUndoAllSucceed:
    def test_undo_all_reverted_and_verified(self):
        repo = FakeVerifiableRepo()
        for rid in BATCH:
            repo.statuses[rid] = "BLOCK"
        result = undo_batch_with_verification(repo, BATCH)
        assert result.committed is True
        assert result.verified is True
        assert sorted(result.reverted_ids) == sorted(BATCH)
        assert repo.statuses == {rid: "PENDING" for rid in BATCH}


class TestUndoFailure:
    def test_undo_failure_stops_immediately_not_marked_complete(self):
        repo = FakeVerifiableRepo(fail_on_save_for=["r2"])
        result = undo_batch_with_verification(repo, BATCH)
        assert result.committed is False
        assert result.failed_id == "r2"
        assert result.reverted_ids == ["r1"]

    def test_undo_get_mismatch_not_marked_complete(self):
        repo = FakeVerifiableRepo(mismatch_for=["r4"])
        result = undo_batch_with_verification(repo, BATCH)
        assert result.committed is False
        assert result.verified is False
        assert result.mismatched_ids == ["r4"]
        # 되돌리기(PATCH) 자체는 전부 시도됨 — GET 재검증에서만 실패
        assert sorted(result.reverted_ids) == sorted(BATCH)


# ── 260712 사고 이후: 검증 오류 분리 + 재시도 정책 ─────────────────────────────

class _HttpError(Exception):
    """status_code/retry_after_seconds를 노출하는 가짜 HTTP 오류."""

    def __init__(self, message, status_code=None, retry_after_seconds=None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class SimulatedTimeoutError(Exception):
    """이름에 'Timeout'이 포함 — status_code 없이도 재시도 대상으로 분류돼야 한다."""


class FakeRepoWithGetErrors:
    """get_review_status가 record_id별로 미리 정해둔 예외를 순서대로 던지다가 소진되면 정상 반환."""

    def __init__(self, get_error_plan=None, force_mismatch_for=()):
        self.statuses: dict[str, str] = {}
        self.save_calls: list[tuple[str, str]] = []
        self.get_calls: list[str] = []
        self.get_error_plan = {k: list(v) for k, v in (get_error_plan or {}).items()}
        self.force_mismatch_for = set(force_mismatch_for)

    def save_review_decision(self, record_id, decision, note=""):
        self.save_calls.append((record_id, decision))
        self.statuses[record_id] = decision

    def get_review_status(self, record_id):
        self.get_calls.append(record_id)
        errs = self.get_error_plan.get(record_id)
        if errs:
            raise errs.pop(0)
        if record_id in self.force_mismatch_for:
            return "STALE"  # 저장은 성공했다고 응답했지만 실제 값은 다른 상황(진짜 불일치) 시뮬레이션
        return self.statuses.get(record_id)


def _sleep_recorder():
    calls: list[float] = []

    def _sleep(seconds):
        calls.append(seconds)

    return calls, _sleep


class TestVerificationErrorClassification:
    def test_429_retries_with_retry_after_and_eventually_succeeds(self):
        repo = FakeRepoWithGetErrors(get_error_plan={
            "r1": [_HttpError("rate limited", status_code=429, retry_after_seconds=3.0)],
        })
        sleep_calls, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, BATCH, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is True
        assert result.verification_errors == []
        assert sleep_calls == [3.0]  # Retry-After 값 그대로 사용

    def test_429_exhausts_retries_reported_as_verification_error_not_mismatch(self):
        repo = FakeRepoWithGetErrors(get_error_plan={
            "r1": [_HttpError("rate limited", status_code=429, retry_after_seconds=1.0) for _ in range(10)],
        })
        _, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, BATCH, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is False
        assert result.mismatched_ids == []  # 값이 다른 게 아니라 확인을 못 한 것
        assert len(result.verification_errors) == 1
        err = result.verification_errors[0]
        assert isinstance(err, VerificationError)
        assert err.record_id == "r1"
        assert err.status_code == 429

    def test_5xx_retries_with_backoff_and_succeeds(self):
        repo = FakeRepoWithGetErrors(get_error_plan={
            "r2": [_HttpError("server error", status_code=503), _HttpError("server error", status_code=503)],
        })
        sleep_calls, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, BATCH, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is True
        assert sleep_calls == [1.0, 2.0]  # 지수 백오프: 1초, 2초

    def test_timeout_without_status_code_is_retried(self):
        repo = FakeRepoWithGetErrors(get_error_plan={
            "r3": [SimulatedTimeoutError("connection timed out")],
        })
        sleep_calls, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, BATCH, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is True
        assert len(sleep_calls) == 1

    def test_403_is_not_retried_reported_immediately(self):
        repo = FakeRepoWithGetErrors(get_error_plan={
            "r1": [_HttpError("forbidden", status_code=403)],
        })
        _, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, BATCH, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is False
        assert len(result.verification_errors) == 1
        assert result.verification_errors[0].status_code == 403
        # r1에 대한 get_review_status 호출이 딱 1번뿐이어야 함(재시도 없음)
        assert repo.get_calls.count("r1") == 1

    def test_404_is_not_retried_reported_immediately(self):
        repo = FakeRepoWithGetErrors(get_error_plan={
            "r1": [_HttpError("not found", status_code=404)],
        })
        _, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, BATCH, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is False
        assert result.verification_errors[0].status_code == 404
        assert repo.get_calls.count("r1") == 1

    def test_unknown_error_without_status_code_not_retried(self):
        """상태코드도 없고 Timeout도 아니면 안전하게(재시도 없이) 즉시 오류 처리."""
        repo = FakeRepoWithGetErrors(get_error_plan={"r1": [RuntimeError("mystery failure")]})
        _, sleep_fn = _sleep_recorder()
        result = commit_batch_with_verification(repo, BATCH, block_ids=[], sleep_fn=sleep_fn)
        assert result.committed is False
        assert repo.get_calls.count("r1") == 1
        assert result.verification_errors[0].status_code is None
        assert result.verification_errors[0].error_type == "RuntimeError"

    def test_mismatch_and_verification_error_can_coexist(self):
        repo = FakeRepoWithGetErrors(
            get_error_plan={"r5": [_HttpError("forbidden", status_code=403)]},
            force_mismatch_for=["r1"],  # r1은 저장은 시도됐지만 실제 값이 다름(진짜 mismatch)
        )
        result = commit_batch_with_verification(repo, BATCH, block_ids=["r1"])
        assert result.committed is False
        assert "r1" in result.mismatched_ids
        assert any(e.record_id == "r5" for e in result.verification_errors)

    def test_undo_also_separates_verification_errors(self):
        repo = FakeRepoWithGetErrors(get_error_plan={
            "r1": [_HttpError("rate limited", status_code=429, retry_after_seconds=0.01)],
        })
        for rid in BATCH:
            repo.statuses[rid] = "BLOCK"
        _, sleep_fn = _sleep_recorder()
        result = undo_batch_with_verification(repo, BATCH, sleep_fn=sleep_fn)
        assert result.committed is True  # 재시도 후 성공
        assert result.verification_errors == []


class TestVerifyOnly:
    """PATCH 없이 GET만으로 기존 expected payload를 재검증 — 260712 사고 이후 신규 함수.
    save_review_decision을 절대 호출하지 않는다(재-PATCH 금지)."""

    def test_all_match_verified_true_no_patch_calls(self):
        repo = FakeVerifiableRepo()
        for rid in BATCH:
            repo.statuses[rid] = "BLOCK"
        expected = {rid: "BLOCK" for rid in BATCH}
        result = verify_only(repo, expected)
        assert result.verified is True
        assert result.mismatched_ids == []
        assert result.verification_errors == []
        assert repo.save_calls == []  # PATCH 없음

    def test_real_mismatch_reported(self):
        repo = FakeVerifiableRepo()
        repo.statuses["r1"] = "PASS"
        expected = {"r1": "BLOCK"}
        result = verify_only(repo, expected)
        assert result.verified is False
        assert result.mismatched_ids == ["r1"]
        assert repo.save_calls == []

    def test_verification_error_does_not_trigger_patch(self):
        repo = FakeRepoWithGetErrors(get_error_plan={"r1": [_HttpError("forbidden", status_code=403)]})
        expected = {"r1": "BLOCK", "r2": "PASS"}
        repo.statuses["r2"] = "PASS"
        result = verify_only(repo, expected)
        assert result.verified is False
        assert len(result.verification_errors) == 1
        assert result.verification_errors[0].record_id == "r1"
        assert repo.save_calls == []  # verify_only는 어떤 경우에도 저장을 호출하지 않음

    def test_retries_transient_errors_before_giving_up(self):
        repo = FakeRepoWithGetErrors(get_error_plan={
            "r1": [_HttpError("server error", status_code=503)],
        })
        repo.statuses["r1"] = "BLOCK"
        sleep_calls, sleep_fn = _sleep_recorder()
        result = verify_only(repo, {"r1": "BLOCK"}, sleep_fn=sleep_fn)
        assert result.verified is True
        assert sleep_calls == [1.0]
        assert repo.save_calls == []


class TestNotFoundClassifiedAsVerificationError:
    """실제 AirtableRepository.get_review_status()는 404를 예외가 아니라 None으로 반환한다.
    이 None을 mismatched_ids(값이 다름)로 잘못 분류하면 안 되고, verification_errors
    (status_code=404, error_type='NotFound')로 분리해야 한다 — Codex 지적으로 확인된 결함."""

    def test_commit_none_status_is_verification_error_not_mismatch(self):
        repo = FakeVerifiableRepo(force_none_for=["r3"])
        result = commit_batch_with_verification(repo, BATCH, block_ids=["r3"])
        assert result.committed is False
        assert "r3" not in result.mismatched_ids
        assert any(e.record_id == "r3" and e.status_code == 404 and e.error_type == "NotFound"
                   for e in result.verification_errors)

    def test_undo_none_status_is_verification_error_not_mismatch(self):
        repo = FakeVerifiableRepo(force_none_for=["r2"])
        for rid in BATCH:
            repo.statuses[rid] = "BLOCK"
        result = undo_batch_with_verification(repo, BATCH)
        assert result.committed is False
        assert "r2" not in result.mismatched_ids
        assert any(e.record_id == "r2" and e.status_code == 404 for e in result.verification_errors)

    def test_verify_only_none_status_is_verification_error_not_mismatch(self):
        repo = FakeVerifiableRepo(force_none_for=["r1"])
        result = verify_only(repo, {"r1": "BLOCK", "r2": "PASS"})
        assert result.verified is False
        assert "r1" not in result.mismatched_ids
        assert any(e.record_id == "r1" and e.status_code == 404 and e.error_type == "NotFound"
                   for e in result.verification_errors)

    def test_none_and_real_mismatch_both_reported_separately(self):
        repo = FakeVerifiableRepo(force_none_for=["r1"], mismatch_for=["r2"])
        result = verify_only(repo, {"r1": "BLOCK", "r2": "PASS", "r3": "PASS"})
        assert result.verified is False
        assert result.mismatched_ids == ["r2"]  # 진짜 값 불일치만 여기
        assert any(e.record_id == "r1" and e.status_code == 404 for e in result.verification_errors)
