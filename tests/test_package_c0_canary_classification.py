"""8단계 Package C0 — Canary Classification 계약 테스트."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from modules.common.canary_classification import (
    CanaryClassificationError,
    validate_post_classification,
)
from modules.infra.repository_interface import RepositoryValidationError


_NOW = datetime(2026, 7, 28, 4, 30, tzinfo=timezone.utc)
_VALID_RUN_ID = "canary-260728-c0"


def _enable_valid_context(monkeypatch):
    monkeypatch.setenv("CANARY_SAFE_MODE", "true")
    monkeypatch.setenv("CANARY_RUN_ID", _VALID_RUN_ID)
    monkeypatch.setenv("CANARY_EXPIRES_AT", "2099-07-28T05:00:00Z")


def _publish_account(code="IDN-000041"):
    return {
        "account_code": code,
        "api_provider": "facebook_login",
        "ig_user_id": "yuna-ig-user",
        "credential_key": "YUNA",
    }


class TestClassificationContract:
    def test_production_allowed_in_normal_runtime(self, monkeypatch):
        monkeypatch.delenv("CANARY_SAFE_MODE", raising=False)
        validate_post_classification("production", "", "ready", now=_NOW)

    @pytest.mark.parametrize("safe_mode", ["true", "TRUE"])
    def test_valid_test_draft_allowed_only_in_safe_mode(self, monkeypatch, safe_mode):
        _enable_valid_context(monkeypatch)
        monkeypatch.setenv("CANARY_SAFE_MODE", safe_mode)

        validate_post_classification(
            "test",
            _VALID_RUN_ID,
            "draft",
            now=_NOW,
        )

    @pytest.mark.parametrize(
        ("safe_mode", "run_id", "expires_at", "status"),
        [
            ("false", _VALID_RUN_ID, "2026-07-28T05:00:00Z", "draft"),
            ("", _VALID_RUN_ID, "2026-07-28T05:00:00Z", "draft"),
            ("true", "", "2026-07-28T05:00:00Z", "draft"),
            ("true", "different-run", "2026-07-28T05:00:00Z", "draft"),
            ("true", _VALID_RUN_ID, "", "draft"),
            ("true", _VALID_RUN_ID, "2026-07-28T04:30:00Z", "draft"),
            ("true", _VALID_RUN_ID, "2026-07-28T05:00:00Z", "ready"),
        ],
    )
    def test_invalid_test_context_fails_closed(
        self,
        monkeypatch,
        safe_mode,
        run_id,
        expires_at,
        status,
    ):
        monkeypatch.setenv("CANARY_SAFE_MODE", safe_mode)
        monkeypatch.setenv("CANARY_RUN_ID", _VALID_RUN_ID)
        monkeypatch.setenv("CANARY_EXPIRES_AT", expires_at)

        with pytest.raises(CanaryClassificationError):
            validate_post_classification(
                "test",
                run_id,
                status,
                now=_NOW,
            )

    @pytest.mark.parametrize("safe_mode", ["true", "invalid"])
    def test_production_rejected_when_safe_mode_not_normal(self, monkeypatch, safe_mode):
        monkeypatch.setenv("CANARY_SAFE_MODE", safe_mode)
        with pytest.raises(CanaryClassificationError):
            validate_post_classification(
                "production",
                "",
                "ready",
                now=_NOW,
            )


class TestRepositoryIntegration:
    def test_valid_test_draft_is_written(self, monkeypatch):
        from modules.infra.airtable_repository import AirtableRepository

        _enable_valid_context(monkeypatch)
        repo = AirtableRepository()
        monkeypatch.setattr(repo, "get_publish_account", lambda code: _publish_account(code))
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"id": "rec-canary"}
        post = MagicMock(return_value=response)
        monkeypatch.setattr("modules.infra.airtable_repository.requests.post", post)
        monkeypatch.setattr(
            "modules.infra.airtable_repository.log_api_call", lambda *a, **k: None
        )

        record_id = repo.save_instagram_post({
            "image_url": "https://img.example/existing.jpg",
            "account_code_ref": "IDN-000041",
            "data_classification": "test",
            "canary_run_id": _VALID_RUN_ID,
            "post_status": "draft",
        })

        assert record_id == "rec-canary"
        fields = post.call_args.kwargs["json"]["fields"]
        assert fields["data_classification"] == "test"
        assert fields["canary_run_id"] == _VALID_RUN_ID
        assert fields["post_status"] == "draft"

    @pytest.mark.parametrize("status", ["", "ready", "uploading", "posted"])
    def test_test_record_non_draft_calls_airtable_post_zero_times(
        self, monkeypatch, status
    ):
        from modules.infra.airtable_repository import AirtableRepository

        _enable_valid_context(monkeypatch)
        repo = AirtableRepository()
        monkeypatch.setattr(repo, "get_publish_account", lambda code: _publish_account(code))
        post = MagicMock()
        monkeypatch.setattr("modules.infra.airtable_repository.requests.post", post)
        payload = {
            "image_url": "https://img.example/existing.jpg",
            "account_code_ref": "IDN-000041",
            "data_classification": "test",
            "canary_run_id": _VALID_RUN_ID,
        }
        if status:
            payload["post_status"] = status

        with pytest.raises(RepositoryValidationError):
            repo.save_instagram_post(payload)

        post.assert_not_called()

    def test_normal_runtime_test_calls_airtable_post_zero_times(self, monkeypatch):
        from modules.infra.airtable_repository import AirtableRepository

        monkeypatch.setenv("CANARY_SAFE_MODE", "false")
        monkeypatch.setenv("CANARY_RUN_ID", _VALID_RUN_ID)
        monkeypatch.setenv("CANARY_EXPIRES_AT", "2026-07-28T05:00:00Z")
        repo = AirtableRepository()
        monkeypatch.setattr(repo, "get_publish_account", lambda code: _publish_account(code))
        post = MagicMock()
        monkeypatch.setattr("modules.infra.airtable_repository.requests.post", post)

        with pytest.raises(RepositoryValidationError):
            repo.save_instagram_post({
                "image_url": "https://img.example/existing.jpg",
                "account_code_ref": "IDN-000041",
                "data_classification": "test",
                "canary_run_id": _VALID_RUN_ID,
                "post_status": "draft",
            })

        post.assert_not_called()

    def test_test_record_requires_explicit_draft_even_with_approval_default(
        self, monkeypatch
    ):
        from modules.infra.airtable_repository import AirtableRepository

        _enable_valid_context(monkeypatch)
        monkeypatch.setenv("REQUIRE_APPROVAL_BEFORE_PUBLISH", "true")
        repo = AirtableRepository()
        monkeypatch.setattr(repo, "get_publish_account", lambda code: _publish_account(code))
        post = MagicMock()
        monkeypatch.setattr("modules.infra.airtable_repository.requests.post", post)

        with pytest.raises(RepositoryValidationError):
            repo.save_instagram_post({
                "image_url": "https://img.example/existing.jpg",
                "account_code_ref": "IDN-000041",
                "data_classification": "test",
                "canary_run_id": _VALID_RUN_ID,
            })

        post.assert_not_called()
