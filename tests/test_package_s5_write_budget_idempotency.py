"""8단계 Safety Package S5 — Write Budget·Idempotency 테스트."""

from pathlib import Path

import pytest

from modules.common.canary_execution_guard import (
    CanaryExecutionError,
    CanaryExecutionGuard,
    CanaryWriteBudget,
    CanaryWriteOperation,
)


def _enable_context(monkeypatch, run_id):
    monkeypatch.setenv("CANARY_SAFE_MODE", "true")
    monkeypatch.setenv("CANARY_RUN_ID", run_id)
    monkeypatch.setenv("CANARY_EXPIRES_AT", "2099-07-28T05:00:00Z")


def _facebook_guard(monkeypatch, tmp_path, run_id="canary-facebook-1"):
    _enable_context(monkeypatch, run_id)
    return CanaryExecutionGuard(
        run_id,
        "https://facebook.example/permalink/123",
        CanaryWriteBudget.for_facebook(),
        db_path=tmp_path / "canary.db",
    )


def _dome_guard(monkeypatch, tmp_path, run_id="canary-dome-1"):
    _enable_context(monkeypatch, run_id)
    return CanaryExecutionGuard(
        run_id,
        "rec-source-approved",
        CanaryWriteBudget.for_dome("rec-source-approved"),
        db_path=tmp_path / "canary.db",
    )


class TestIdempotency:
    def test_constructor_does_not_create_runtime_db(self, monkeypatch, tmp_path):
        guard = _facebook_guard(monkeypatch, tmp_path)
        assert guard.db_path.exists() is False
        assert guard.read_evidence() is None
        assert guard.db_path.exists() is False

    def test_begin_persists_running_evidence(self, monkeypatch, tmp_path):
        guard = _facebook_guard(monkeypatch, tmp_path)
        guard.begin()

        evidence = guard.read_evidence()
        assert evidence["status"] == "RUNNING"
        assert evidence["route"] == "facebook"
        assert evidence["exact_source_identifier"].endswith("/123")

    @pytest.mark.parametrize("terminal", ["running", "completed", "failed"])
    def test_run_id_is_never_reusable(
        self, monkeypatch, tmp_path, terminal
    ):
        first = _facebook_guard(monkeypatch, tmp_path)
        first.begin()
        if terminal == "completed":
            first.complete()
        elif terminal == "failed":
            first.fail("EXPECTED_FAILURE")

        second = _facebook_guard(monkeypatch, tmp_path)
        with pytest.raises(CanaryExecutionError, match="재사용"):
            second.begin()

    def test_wrong_approved_run_id_fails_before_db_creation(
        self, monkeypatch, tmp_path
    ):
        _enable_context(monkeypatch, "approved-run")
        guard = CanaryExecutionGuard(
            "different-run",
            "https://facebook.example/permalink/123",
            CanaryWriteBudget.for_facebook(),
            db_path=tmp_path / "canary.db",
        )

        with pytest.raises(CanaryExecutionError, match="불일치"):
            guard.begin()
        assert guard.db_path.exists() is False

    def test_write_before_begin_is_rejected(self, monkeypatch, tmp_path):
        guard = _facebook_guard(monkeypatch, tmp_path)
        with pytest.raises(CanaryExecutionError, match=r"begin\(\) 전"):
            guard.authorize_write(CanaryWriteOperation.INSTAGRAM_POST_CREATE)

    def test_terminal_run_cannot_write(self, monkeypatch, tmp_path):
        guard = _facebook_guard(monkeypatch, tmp_path)
        guard.begin()
        guard.complete()
        with pytest.raises(CanaryExecutionError, match="종료된"):
            guard.authorize_write(CanaryWriteOperation.INSTAGRAM_POST_CREATE)

    def test_new_process_object_cannot_resume_running_run(
        self, monkeypatch, tmp_path
    ):
        first = _facebook_guard(monkeypatch, tmp_path)
        first.begin()

        replacement = _facebook_guard(monkeypatch, tmp_path)
        with pytest.raises(CanaryExecutionError, match=r"begin\(\) 전"):
            replacement.authorize_write(
                CanaryWriteOperation.INSTAGRAM_POST_CREATE
            )

    def test_expired_context_stops_next_write_without_consuming_budget(
        self, monkeypatch, tmp_path
    ):
        guard = _facebook_guard(monkeypatch, tmp_path)
        guard.begin()
        monkeypatch.setenv("CANARY_EXPIRES_AT", "2000-01-01T00:00:00Z")

        with pytest.raises(CanaryExecutionError, match="만료"):
            guard.authorize_write(
                CanaryWriteOperation.INSTAGRAM_POST_CREATE
            )
        assert guard.read_evidence()["write_counts"]["instagram_post_create"] == 0


class TestFacebookBudget:
    def test_exactly_one_instagram_post_create_is_allowed(
        self, monkeypatch, tmp_path
    ):
        guard = _facebook_guard(monkeypatch, tmp_path)
        guard.begin()

        assert guard.authorize_write(
            CanaryWriteOperation.INSTAGRAM_POST_CREATE
        ) == 1
        with pytest.raises(CanaryExecutionError, match="Budget 초과"):
            guard.authorize_write(
                CanaryWriteOperation.INSTAGRAM_POST_CREATE
            )

    @pytest.mark.parametrize(
        "operation",
        [
            CanaryWriteOperation.SOURCE_ITEM_CREATE,
            CanaryWriteOperation.SOURCE_ITEM_PATCH,
            CanaryWriteOperation.OTHER_AIRTABLE_CREATE,
            CanaryWriteOperation.OTHER_AIRTABLE_UPDATE,
            CanaryWriteOperation.AIRTABLE_DELETE,
            CanaryWriteOperation.IMGBB_UPLOAD,
            CanaryWriteOperation.INSTAGRAM_PUBLISH,
            CanaryWriteOperation.DM_OR_COMMENT,
        ],
    )
    def test_all_other_facebook_writes_have_zero_budget(
        self, monkeypatch, tmp_path, operation
    ):
        guard = _facebook_guard(monkeypatch, tmp_path)
        guard.begin()
        kwargs = (
            {"record_id": "rec-source-approved"}
            if operation == CanaryWriteOperation.SOURCE_ITEM_PATCH
            else {}
        )
        with pytest.raises(CanaryExecutionError):
            guard.authorize_write(operation, **kwargs)


class TestDomeBudget:
    def test_only_approved_source_record_can_be_patched(
        self, monkeypatch, tmp_path
    ):
        guard = _dome_guard(monkeypatch, tmp_path)
        guard.begin()

        with pytest.raises(CanaryExecutionError, match="승인된 Source"):
            guard.authorize_write(
                CanaryWriteOperation.SOURCE_ITEM_PATCH,
                record_id="rec-other",
            )
        assert guard.read_evidence()["write_counts"]["source_item_patch"] == 0

    def test_two_source_patches_and_one_post_create_are_allowed(
        self, monkeypatch, tmp_path
    ):
        guard = _dome_guard(monkeypatch, tmp_path)
        guard.begin()

        assert guard.authorize_write(
            CanaryWriteOperation.SOURCE_ITEM_PATCH,
            record_id="rec-source-approved",
        ) == 1
        assert guard.authorize_write(
            CanaryWriteOperation.SOURCE_ITEM_PATCH,
            record_id="rec-source-approved",
        ) == 2
        assert guard.authorize_write(
            CanaryWriteOperation.INSTAGRAM_POST_CREATE
        ) == 1

        with pytest.raises(CanaryExecutionError, match="Budget 초과"):
            guard.authorize_write(
                CanaryWriteOperation.SOURCE_ITEM_PATCH,
                record_id="rec-source-approved",
            )
        with pytest.raises(CanaryExecutionError, match="Budget 초과"):
            guard.authorize_write(
                CanaryWriteOperation.INSTAGRAM_POST_CREATE
            )

    @pytest.mark.parametrize(
        "operation",
        [
            CanaryWriteOperation.SOURCE_ITEM_CREATE,
            CanaryWriteOperation.OTHER_AIRTABLE_CREATE,
            CanaryWriteOperation.OTHER_AIRTABLE_UPDATE,
            CanaryWriteOperation.AIRTABLE_DELETE,
            CanaryWriteOperation.IMGBB_UPLOAD,
            CanaryWriteOperation.INSTAGRAM_PUBLISH,
            CanaryWriteOperation.DM_OR_COMMENT,
        ],
    )
    def test_unapproved_dome_writes_have_zero_budget(
        self, monkeypatch, tmp_path, operation
    ):
        guard = _dome_guard(monkeypatch, tmp_path)
        guard.begin()
        with pytest.raises(CanaryExecutionError, match="Budget 초과"):
            guard.authorize_write(operation)

    def test_budget_is_consumed_before_external_result_is_known(
        self, monkeypatch, tmp_path
    ):
        guard = _dome_guard(monkeypatch, tmp_path)
        guard.begin()

        guard.authorize_write(CanaryWriteOperation.INSTAGRAM_POST_CREATE)
        guard.fail("EXTERNAL_REQUEST_FAILED")

        evidence = guard.read_evidence()
        assert evidence["status"] == "FAILED"
        assert evidence["write_counts"]["instagram_post_create"] == 1

        replacement = _dome_guard(monkeypatch, tmp_path)
        with pytest.raises(CanaryExecutionError, match="재사용"):
            replacement.begin()
