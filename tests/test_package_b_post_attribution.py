"""8단계 Package B — 신규 Post 계정 귀속·production 분류 Fail-closed 테스트.

외부 Airtable/Meta 호출과 Runtime 상태변경 없이 Mock으로만 검증한다.
"""

import sys
import types
from unittest.mock import MagicMock

import pytest

from modules.infra.repository_interface import RepositoryValidationError


def _publish_account(code="IDN-000041"):
    return {
        "account_code": code,
        "api_provider": "facebook_login",
        "ig_user_id": "yuna-ig-user",
        "credential_key": "YUNA",
    }


def _import_source_exporter_without_optional_ai_sdk(monkeypatch):
    """Python 3.12 검증 환경에서도 3.10용 optional AI SDK를 로드하지 않는다."""
    caption_module = types.ModuleType("modules.sns.caption_generator")
    caption_module.generate_caption = lambda text: ("caption", "#tag")
    monkeypatch.setitem(sys.modules, "modules.sns.caption_generator", caption_module)
    from modules.crawlers import source_exporter
    return source_exporter


def _import_facebook_crawler_without_optional_airtable_sdk(monkeypatch):
    """이 테스트가 사용하지 않는 pyairtable/google SDK import를 Mock으로 격리한다."""
    bridge_module = types.ModuleType("modules.common.airtable_bridge")
    bridge_module.get_table = lambda name: None
    caption_module = types.ModuleType("modules.sns.caption_generator")
    caption_module.generate_caption = lambda text: ("caption", "#tag")
    monkeypatch.setitem(sys.modules, "modules.common.airtable_bridge", bridge_module)
    monkeypatch.setitem(sys.modules, "modules.sns.caption_generator", caption_module)
    from modules.sns import facebook_crawler
    return facebook_crawler


class TestRepositoryPostContract:
    def test_production_post_is_written_with_explicit_account_and_classification(
        self, monkeypatch
    ):
        from modules.infra.airtable_repository import AirtableRepository

        repo = AirtableRepository()
        monkeypatch.setattr(repo, "get_publish_account", lambda code: _publish_account(code))
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"id": "rec-post"}
        post = MagicMock(return_value=response)
        monkeypatch.setattr("modules.infra.airtable_repository.requests.post", post)
        monkeypatch.setattr(
            "modules.infra.airtable_repository.log_api_call", lambda *a, **k: None
        )

        record_id = repo.save_instagram_post({
            "image_url": "https://img.example/item.jpg",
            "account_code_ref": "IDN-000041",
            "data_classification": "production",
            "canary_run_id": "",
        })

        assert record_id == "rec-post"
        fields = post.call_args.kwargs["json"]["fields"]
        assert fields["account_code_ref"] == "IDN-000041"
        assert fields["data_classification"] == "production"
        assert "canary_run_id" not in fields

    @pytest.mark.parametrize(
        ("account_code_ref", "data_classification", "canary_run_id"),
        [
            ("", "production", ""),
            ("IDN-000041", "", ""),
            ("IDN-000041", "historical_mixed", ""),
            ("IDN-000041", "production", "unexpected-run"),
            ("IDN-000041", "test", ""),
            ("IDN-000041", "test", "unverified-run"),
        ],
    )
    def test_invalid_or_unverified_context_calls_airtable_post_zero_times(
        self,
        monkeypatch,
        account_code_ref,
        data_classification,
        canary_run_id,
    ):
        from modules.infra.airtable_repository import AirtableRepository

        repo = AirtableRepository()
        monkeypatch.setattr(repo, "get_publish_account", lambda code: _publish_account(code))
        post = MagicMock()
        monkeypatch.setattr("modules.infra.airtable_repository.requests.post", post)

        with pytest.raises(RepositoryValidationError):
            repo.save_instagram_post({
                "image_url": "https://img.example/item.jpg",
                "account_code_ref": account_code_ref,
                "data_classification": data_classification,
                "canary_run_id": canary_run_id,
            })

        post.assert_not_called()

    def test_unregistered_account_calls_airtable_post_zero_times(self, monkeypatch):
        from modules.infra.airtable_repository import AirtableRepository

        repo = AirtableRepository()
        monkeypatch.setattr(repo, "get_publish_account", lambda code: None)
        post = MagicMock()
        monkeypatch.setattr("modules.infra.airtable_repository.requests.post", post)

        with pytest.raises(RepositoryValidationError):
            repo.save_instagram_post({
                "image_url": "https://img.example/item.jpg",
                "account_code_ref": "IDN-GHOST",
                "data_classification": "production",
            })

        post.assert_not_called()

    def test_source_claim_writes_account_in_same_patch(self, monkeypatch):
        from modules.infra.airtable_repository import AirtableRepository

        response = MagicMock()
        response.raise_for_status.return_value = None
        patch = MagicMock(return_value=response)
        monkeypatch.setattr("modules.infra.airtable_repository.requests.patch", patch)
        monkeypatch.setattr(
            "modules.infra.airtable_repository.log_api_call", lambda *a, **k: None
        )

        AirtableRepository().claim_source_item_for_export(
            "rec-source",
            "2026-07-28T03:00:00.000Z",
            "IDN-000041",
        )

        assert patch.call_args.kwargs["json"]["fields"] == {
            "pipeline_status": "QUEUED",
            "export_started_at": "2026-07-28T03:00:00.000Z",
            "account_code_ref": "IDN-000041",
        }


class _ExporterRepo:
    def __init__(self, source_account=""):
        self.source_account = source_account
        self.validated = []
        self.recovered = 0
        self.claimed = []
        self.saved = []
        self.statuses = []

    def validate_instagram_post_context(self, account, classification, canary=""):
        self.validated.append((account, classification, canary))
        return _publish_account(account)

    def recover_stale_queued_source_items(self, threshold):
        self.recovered += 1
        return 0

    def fetch_source_items_for_export(self, batch_size=3, target_id=None):
        return [{
            "record_id": "rec-source",
            "source_item_id": "source-1",
            "title": "item",
            "image_url": "https://img.example/source.jpg",
            "source_url": "https://source.example/item",
            "export_retry_count": 0,
            "account_code_ref": self.source_account,
        }]

    def claim_source_item_for_export(self, record_id, started_at, account):
        self.claimed.append((record_id, account))

    def exists_post_by_image_url(self, image_url):
        return False

    def save_instagram_post(self, payload):
        self.saved.append(payload)
        return "rec-post"

    def update_source_item_status(self, record_id, status):
        self.statuses.append((record_id, status))

    def update_source_item_retry(self, *args):
        raise AssertionError("성공 경로에서 retry가 호출되면 안 됨")


class TestDomeAccountPropagation:
    def test_blank_source_is_claimed_and_posted_with_scheduler_account(self, monkeypatch):
        source_exporter = _import_source_exporter_without_optional_ai_sdk(monkeypatch)

        repo = _ExporterRepo(source_account="")
        monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: repo)
        monkeypatch.setattr(source_exporter, "generate_caption", lambda title: ("caption", "#tag"))
        monkeypatch.setattr(
            source_exporter,
            "upload_to_imgbb",
            lambda image_url: {
                "success": True,
                "public_url": "https://img.example/hosted.jpg",
                "content_hash": "hash-1",
            },
        )

        result = source_exporter.export_to_instagram_posts(
            dry_run=False,
            target_publish_account_code_ref="IDN-000041",
            data_classification="production",
        )

        assert result == {"exported": 1, "skipped": 0, "failed": 0}
        assert repo.claimed == [("rec-source", "IDN-000041")]
        assert repo.saved[0]["account_code_ref"] == "IDN-000041"
        assert repo.saved[0]["data_classification"] == "production"

    def test_scheduler_source_mismatch_creates_no_post_and_no_claim(self, monkeypatch):
        source_exporter = _import_source_exporter_without_optional_ai_sdk(monkeypatch)

        repo = _ExporterRepo(source_account="IDN-000036")
        monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: repo)

        result = source_exporter.export_to_instagram_posts(
            dry_run=False,
            target_publish_account_code_ref="IDN-000041",
            data_classification="production",
        )

        assert result == {"exported": 0, "skipped": 0, "failed": 1}
        assert repo.claimed == []
        assert repo.saved == []


class TestFacebookAccountPropagation:
    def test_save_to_airtable_passes_explicit_context(self, monkeypatch):
        facebook_crawler = _import_facebook_crawler_without_optional_airtable_sdk(monkeypatch)

        captured = {}

        class _Repo:
            def validate_instagram_post_context(self, account, classification, canary=""):
                assert (account, classification, canary) == (
                    "IDN-000041", "production", "",
                )
                return _publish_account(account)

            def exists_post_by_image_url(self, image_url):
                return False

            def save_instagram_post(self, payload):
                captured.update(payload)
                return "rec-post"

        monkeypatch.setattr(
            "modules.infra.airtable_repository.AirtableRepository", lambda: _Repo()
        )
        monkeypatch.setattr(
            facebook_crawler, "generate_caption", lambda text: ("caption", "#tag")
        )

        saved = facebook_crawler.save_to_airtable(
            "https://img.example/item.jpg",
            "https://facebook.example/post",
            text="item",
            target_publish_account_code_ref="IDN-000041",
            data_classification="production",
        )

        assert saved is True
        assert captured["account_code_ref"] == "IDN-000041"
        assert captured["data_classification"] == "production"

    def test_credential_registry_mismatch_stops_before_account_iteration(
        self, monkeypatch
    ):
        facebook_crawler = _import_facebook_crawler_without_optional_airtable_sdk(monkeypatch)

        class _Repo:
            def validate_instagram_post_context(self, account, classification, canary=""):
                return _publish_account(account)

        monkeypatch.setattr(
            "modules.infra.airtable_repository.AirtableRepository", lambda: _Repo()
        )
        monkeypatch.setenv("YUNA_INSTA_IG_USER_ID", "different-ig-user")
        monkeypatch.setenv("YUNA_INSTA_ACCESS_TOKEN", "token")
        monkeypatch.setattr(
            "modules.common.account_manager.get_active_accounts",
            lambda: pytest.fail("Credential 불일치 후 계정 순회를 시작하면 안 됨"),
        )

        with pytest.raises(RepositoryValidationError):
            facebook_crawler.run_all_accounts(
                target_publish_account_code_ref="IDN-000041",
                data_classification="production",
            )


def test_launcher_scheduler_passes_explicit_production_context():
    from launcher import main as launcher_main

    scheduler = launcher_main._build_scheduler()
    assert scheduler.get_job("fb_crawl").kwargs == {
        "target_publish_account_code_ref": "IDN-000041",
        "data_classification": "production",
    }
    assert scheduler.get_job("dome_export").kwargs == {
        "target_publish_account_code_ref": "IDN-000041",
        "data_classification": "production",
    }


class _FakeAccount:
    """run_all_accounts() 테스트용 최소 Account 대역 — Selenium/AdsPower 무관."""

    def __init__(self, name, crawl_urls):
        self.name = name
        self.crawl_urls = crawl_urls
        self.adspower_user_id = "test_user"

    def selenium_proxy_options(self):
        return {}


class TestRunAllAccountsFailureVisibility:
    """9-10-3-A Defect A — URL 단위 실패가 계정 완료로 오인되지 않는지 검증.
    (facebook_crawler.py::run_all_accounts()만 대상, run()/get_driver()/canary 경로는
    monkeypatch로 완전히 격리해 건드리지 않는다.)"""

    def test_all_urls_succeed_returns_success_status(self, monkeypatch, caplog):
        facebook_crawler = _import_facebook_crawler_without_optional_airtable_sdk(monkeypatch)
        monkeypatch.setattr(
            "modules.common.account_manager.get_active_accounts",
            lambda: [_FakeAccount("acct1", ["url1", "url2"])],
        )
        monkeypatch.setattr(facebook_crawler, "run", lambda *a, **k: [{"x": 1}])
        monkeypatch.setattr(facebook_crawler, "_validate_publish_context", lambda *a, **k: None)

        with caplog.at_level("INFO"):
            summary = facebook_crawler.run_all_accounts(
                target_publish_account_code_ref="IDN-000041",
                data_classification="production",
            )

        assert summary == {"acct1": 2}
        assert any("status=SUCCESS" in r.message for r in caplog.records)

    def test_partial_url_failure_keeps_successful_results_and_logs_partial(self, monkeypatch, caplog):
        facebook_crawler = _import_facebook_crawler_without_optional_airtable_sdk(monkeypatch)
        monkeypatch.setattr(
            "modules.common.account_manager.get_active_accounts",
            lambda: [_FakeAccount("acct1", ["good", "bad"])],
        )

        def _fake_run(url, *a, **k):
            if url == "bad":
                raise RuntimeError("boom")
            return [{"x": 1}]

        monkeypatch.setattr(facebook_crawler, "run", _fake_run)
        monkeypatch.setattr(facebook_crawler, "_validate_publish_context", lambda *a, **k: None)

        with caplog.at_level("INFO"):
            summary = facebook_crawler.run_all_accounts(
                target_publish_account_code_ref="IDN-000041",
                data_classification="production",
            )

        assert summary == {"acct1": 1}
        assert any("status=PARTIAL" in r.message for r in caplog.records)
        assert any("크롤링 실패" in r.message and "url=bad" in r.message for r in caplog.records)

    def test_all_urls_fail_raises_and_reports_no_success(self, monkeypatch, caplog):
        facebook_crawler = _import_facebook_crawler_without_optional_airtable_sdk(monkeypatch)
        monkeypatch.setattr(
            "modules.common.account_manager.get_active_accounts",
            lambda: [_FakeAccount("acct1", ["bad1", "bad2"])],
        )
        monkeypatch.setattr(
            facebook_crawler, "run",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        monkeypatch.setattr(facebook_crawler, "_validate_publish_context", lambda *a, **k: None)

        with caplog.at_level("INFO"):
            with pytest.raises(facebook_crawler.FacebookCrawlAllTargetsFailedError):
                facebook_crawler.run_all_accounts(
                    target_publish_account_code_ref="IDN-000041",
                    data_classification="production",
                )

        assert any("status=FAILED" in r.message for r in caplog.records)
        assert not any("status=SUCCESS" in r.message for r in caplog.records)

    def test_no_crawl_urls_uses_existing_skip_contract(self, monkeypatch, caplog):
        facebook_crawler = _import_facebook_crawler_without_optional_airtable_sdk(monkeypatch)
        monkeypatch.setattr(
            "modules.common.account_manager.get_active_accounts",
            lambda: [_FakeAccount("acct1", [])],
        )
        monkeypatch.setattr(facebook_crawler, "_validate_publish_context", lambda *a, **k: None)

        with caplog.at_level("WARNING"):
            summary = facebook_crawler.run_all_accounts(
                target_publish_account_code_ref="IDN-000041",
                data_classification="production",
            )

        assert summary == {}
        assert any("crawl_urls 없음" in r.message for r in caplog.records)

    def test_new_aggregate_logs_contain_no_credential_or_token_patterns(self, monkeypatch, caplog):
        facebook_crawler = _import_facebook_crawler_without_optional_airtable_sdk(monkeypatch)
        monkeypatch.setattr(
            "modules.common.account_manager.get_active_accounts",
            lambda: [_FakeAccount("acct1", ["good", "bad"])],
        )

        def _fake_run(url, *a, **k):
            if url == "bad":
                raise RuntimeError("network error")
            return [{"x": 1}]

        monkeypatch.setattr(facebook_crawler, "run", _fake_run)
        monkeypatch.setattr(facebook_crawler, "_validate_publish_context", lambda *a, **k: None)

        with caplog.at_level("INFO"):
            facebook_crawler.run_all_accounts(
                target_publish_account_code_ref="IDN-000041",
                data_classification="production",
            )

        partial_lines = [r.message for r in caplog.records if "status=PARTIAL" in r.message]
        assert partial_lines
        for line in partial_lines:
            assert "EAA" not in line and "IGAA" not in line and "access_token" not in line.lower()
