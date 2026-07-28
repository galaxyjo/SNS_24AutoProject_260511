"""8단계 Safety Package S2 — Canary 공개 게시 차단 테스트."""

from unittest.mock import MagicMock

import pytest

from modules.common.canary_classification import (
    CanaryClassificationError,
    validate_publication_candidate,
)


class TestPublicationContract:
    @pytest.mark.parametrize(
        ("classification", "run_id", "status"),
        [
            ("test", "canary-1", "draft"),
            ("test", "", "ready"),
            ("production", "canary-1", "ready"),
            ("historical_mixed", "", "ready"),
            ("production", "", "draft"),
        ],
    )
    def test_canary_or_non_publishable_record_is_blocked(
        self, monkeypatch, classification, run_id, status
    ):
        monkeypatch.setenv("CANARY_SAFE_MODE", "false")
        with pytest.raises(CanaryClassificationError):
            validate_publication_candidate(classification, run_id, status)

    @pytest.mark.parametrize("classification", ["", "production"])
    def test_legacy_and_production_ready_remain_publishable(
        self, monkeypatch, classification
    ):
        monkeypatch.setenv("CANARY_SAFE_MODE", "false")
        validate_publication_candidate(classification, "", "ready")

    def test_direct_publish_is_blocked_while_safe_mode_is_active(self, monkeypatch):
        monkeypatch.setenv("CANARY_SAFE_MODE", "true")
        monkeypatch.setenv("CANARY_RUN_ID", "canary-260728-s2")
        monkeypatch.setenv("CANARY_EXPIRES_AT", "2099-07-28T05:00:00Z")
        with pytest.raises(CanaryClassificationError):
            validate_publication_candidate("production", "", "ready")


class TestRepositoryQuery:
    def test_pending_query_excludes_test_and_canary_records(self, monkeypatch):
        from modules.infra.airtable_repository import AirtableRepository

        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "records": [{
                "id": "rec-production",
                "fields": {
                    "post_status": "ready",
                    "data_classification": "production",
                    "canary_run_id": "",
                    "account_code_ref": "IDN-000041",
                    "image_url": "https://img.example/existing.jpg",
                },
            }]
        }
        get = MagicMock(return_value=response)
        monkeypatch.setattr("modules.infra.airtable_repository.requests.get", get)
        monkeypatch.setattr(
            "modules.infra.airtable_repository.log_api_call", lambda *a, **k: None
        )

        posts = AirtableRepository().fetch_pending_posts(limit=50)

        formula = get.call_args.kwargs["params"]["filterByFormula"]
        assert "{post_status}='ready'" in formula
        assert "OR({data_classification}=BLANK(),{data_classification}='production')" in formula
        assert "{canary_run_id}=BLANK()" in formula
        assert posts[0]["data_classification"] == "production"
        assert posts[0]["canary_run_id"] == ""


class TestUploadDefenseInDepth:
    @pytest.mark.parametrize(
        "post",
        [
            {
                "post_id": "rec-test",
                "post_status": "ready",
                "data_classification": "test",
                "canary_run_id": "canary-1",
                "account_code_ref": "IDN-000041",
            },
            {
                "post_id": "rec-canary-id",
                "post_status": "ready",
                "data_classification": "production",
                "canary_run_id": "canary-1",
                "account_code_ref": "IDN-000041",
            },
            {
                "post_id": "rec-draft",
                "post_status": "draft",
                "data_classification": "test",
                "canary_run_id": "canary-1",
                "account_code_ref": "IDN-000041",
            },
        ],
    )
    def test_blocked_record_never_reaches_claim_or_publish(
        self, monkeypatch, post
    ):
        from launcher import main as launcher_main

        monkeypatch.setenv("CANARY_SAFE_MODE", "false")

        class _FakeRepo:
            def fetch_pending_posts(self, limit=50):
                return [post]

            def get_publish_account(self, account_code):
                raise AssertionError("차단 Record는 계정 조회까지 가면 안 됨")

            def claim_post_for_upload(self, post_id):
                raise AssertionError("차단 Record는 claim까지 가면 안 됨")

        monkeypatch.setattr(
            "modules.infra.airtable_repository.AirtableRepository",
            lambda: _FakeRepo(),
        )
        publish = MagicMock()
        monkeypatch.setattr(launcher_main, "publish_single", publish)

        launcher_main._job_insta_upload()

        publish.assert_not_called()

    def test_direct_job_in_safe_mode_cannot_publish_production_record(
        self, monkeypatch
    ):
        from launcher import main as launcher_main

        monkeypatch.setenv("CANARY_SAFE_MODE", "true")
        monkeypatch.setenv("CANARY_RUN_ID", "canary-260728-s2")
        monkeypatch.setenv("CANARY_EXPIRES_AT", "2099-07-28T05:00:00Z")

        class _FakeRepo:
            def fetch_pending_posts(self, limit=50):
                return [{
                    "post_id": "rec-production",
                    "post_status": "ready",
                    "data_classification": "production",
                    "canary_run_id": "",
                    "account_code_ref": "IDN-000041",
                }]

            def get_publish_account(self, account_code):
                raise AssertionError("Safe Mode에서는 계정 조회까지 가면 안 됨")

            def claim_post_for_upload(self, post_id):
                raise AssertionError("Safe Mode에서는 claim까지 가면 안 됨")

        monkeypatch.setattr(
            "modules.infra.airtable_repository.AirtableRepository",
            lambda: _FakeRepo(),
        )
        publish = MagicMock()
        monkeypatch.setattr(launcher_main, "publish_single", publish)

        launcher_main._job_insta_upload()

        publish.assert_not_called()
