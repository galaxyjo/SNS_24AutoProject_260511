"""260725 — 계정별 Provider 분기(Instagram API with Instagram Login vs Facebook Login) 테스트.

Codex 2라운드 + GPT 아키텍처 감사에서 확정된 안전 규칙을 회귀로 잠근다:
  - account_code_ref 공란 → Legacy 전역 경로를 사용하지 않고 차단
  - INSTAGRAM_PROVIDER_ROUTING_ENABLED=false(기본) → account_code_ref 있어도 전역 폴백/claim/publish 전부 금지
  - Account_Registry 조회 실패(없음/2건 이상/형식오류) → claim 0회
  - 미지원 api_provider → claim 0회
  - credential_key 해석 실패 → claim 0회
  - Airtable ig_user_id != .env ig_user_id → claim 0회(어느 쪽도 조용히 우선하지 않음)
  - 전부 통과 시에만 claim → publish_single(api_host=...) 정확한 호스트로 호출
외부 게시·Airtable Write 없이 전부 Mock으로 검증한다.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import PublishAccount

# launcher/main.py는 import 시점에 load_dotenv(override=True)를 1회 실행한다.
# 이 파일을 단독 실행할 때(다른 테스트가 먼저 import해두지 않은 경우) 각 테스트의
# monkeypatch.setenv(...) 이후 최초 import가 일어나면 override=True가 그 값을 실제
# .env 내용으로 덮어써버린다. 여기서 모듈 임포트 시점을 파일 로드 시점(=모든
# monkeypatch보다 먼저)으로 고정해 이 문제를 원천 차단한다.
from launcher import main as launcher_main  # noqa: F401,E402


# ── 1. AirtableRepository.get_publish_account() ──────────────────────────

class TestGetPublishAccount:
    def test_returns_none_for_malformed_account_code(self):
        repo = AirtableRepository()
        # 공백/쉼표는 다중값처럼 보일 수 있어 형식 검증에서 즉시 차단(HTTP 호출 자체가 안 됨)
        assert repo.get_publish_account("IDN-000036, IDN-000037") is None
        assert repo.get_publish_account("") is None
        assert repo.get_publish_account(None) is None

    def test_returns_none_when_zero_records_found(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"records": []}
        with patch("modules.infra.airtable_repository.requests.get", return_value=resp), \
             patch("modules.infra.airtable_repository.log_api_call"):
            repo = AirtableRepository()
            assert repo.get_publish_account("IDN-NOTFOUND") is None

    def test_returns_none_when_duplicate_records_found(self):
        """동일 account_code가 2건 이상이면 어느 것인지 추측하지 않고 차단."""
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"records": [
            {"fields": {"account_code": "IDN-000036"}},
            {"fields": {"account_code": "IDN-000036"}},
        ]}
        with patch("modules.infra.airtable_repository.requests.get", return_value=resp), \
             patch("modules.infra.airtable_repository.log_api_call"):
            repo = AirtableRepository()
            assert repo.get_publish_account("IDN-000036") is None

    def test_returns_account_dict_without_token_on_success(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"records": [
            {"fields": {
                "account_code": "IDN-000036",
                "api_provider": {"id": "seltCoLWojPqTByll", "name": "instagram_login"},
                "ig_user_id": "17841467725643424",
                "credential_key": "AI",
            }},
        ]}
        with patch("modules.infra.airtable_repository.requests.get", return_value=resp), \
             patch("modules.infra.airtable_repository.log_api_call"):
            repo = AirtableRepository()
            account = repo.get_publish_account("IDN-000036")

        assert account == PublishAccount(
            account_code="IDN-000036",
            api_provider="instagram_login",
            ig_user_id="17841467725643424",
            credential_key="AI",
        )
        assert "access_token" not in account
        assert "token" not in str(account).lower()


# ── 2. launcher/main.py _job_insta_upload() 분기 ─────────────────────────

def _fake_repo(posts, get_publish_account=None, claim_result=True):
    calls = {"claim": [], "mark_post_result": []}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return posts

        def get_publish_account(self, account_code):
            if get_publish_account is None:
                raise AssertionError("get_publish_account가 호출되면 안 됨(신규 경로 미도달)")
            return get_publish_account(account_code)

        def claim_post_for_upload(self, post_id):
            calls["claim"].append(post_id)
            return claim_result

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

    return _FakeRepo(), calls


class TestJobInstaUploadProviderBranching:
    def test_empty_account_code_ref_blocks_legacy_global_path(self, monkeypatch):
        monkeypatch.setenv("INSTA_ACCESS_TOKEN", "legacy-token")
        monkeypatch.setenv("INSTA_IG_USER_ID", "legacy-iguser")
        monkeypatch.delenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", raising=False)

        from launcher import main as launcher_main

        repo, calls = _fake_repo(
            [{"post_id": "rec1", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": ""}]
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        publish_calls = []

        def _fake_publish_single(rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com"):
            publish_calls.append((access_token, ig_user_id, api_host))
            return {"ok": True, "ig_media_id": "m1"}

        monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)

        launcher_main._job_insta_upload()

        assert calls["claim"] == []
        assert publish_calls == []

    def test_flag_false_blocks_new_path_even_with_valid_account(self, monkeypatch):
        """킬스위치 기본값(false) — account_code_ref가 있어도 전역 폴백 없이 그냥 보류."""
        monkeypatch.setenv("INSTA_ACCESS_TOKEN", "legacy-token")
        monkeypatch.setenv("INSTA_IG_USER_ID", "legacy-iguser")
        monkeypatch.delenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", raising=False)

        from launcher import main as launcher_main

        repo, calls = _fake_repo(
            [{"post_id": "rec2", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-000036"}]
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        publish_calls = []
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda *a, **k: publish_calls.append(1) or {"ok": True, "ig_media_id": "x"},
        )

        launcher_main._job_insta_upload()

        assert calls["claim"] == []
        assert publish_calls == []

    def test_unknown_account_code_ref_blocks_before_claim(self, monkeypatch):
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.delenv("INSTA_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("INSTA_IG_USER_ID", raising=False)

        from launcher import main as launcher_main

        repo, calls = _fake_repo(
            [{"post_id": "rec3", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-GHOST"}],
            get_publish_account=lambda code: None,
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_insta_upload()

        assert calls["claim"] == []

    def test_unsupported_provider_blocks_before_claim(self, monkeypatch):
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")

        from launcher import main as launcher_main

        repo, calls = _fake_repo(
            [{"post_id": "rec4", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-X"}],
            get_publish_account=lambda code: {
                "account_code": "IDN-X", "api_provider": "tiktok_login",
                "ig_user_id": "1", "credential_key": "X",
            },
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_insta_upload()

        assert calls["claim"] == []

    def test_credential_resolution_failure_blocks_before_claim(self, monkeypatch):
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.delenv("NOKEY_INSTA_IG_USER_ID", raising=False)
        monkeypatch.delenv("NOKEY_INSTA_ACCESS_TOKEN", raising=False)

        from launcher import main as launcher_main

        repo, calls = _fake_repo(
            [{"post_id": "rec5", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-Y"}],
            get_publish_account=lambda code: {
                "account_code": "IDN-Y", "api_provider": "instagram_login",
                "ig_user_id": "1", "credential_key": "NOKEY",
            },
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_insta_upload()

        assert calls["claim"] == []

    def test_ig_user_id_mismatch_blocks_before_claim(self, monkeypatch):
        """GPT 감사 필수조건 — Airtable ig_user_id와 .env ig_user_id가 다르면 어느 쪽도 우선하지 않고 차단."""
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.setenv("MISMATCH_INSTA_IG_USER_ID", "ENV_VALUE_999")
        monkeypatch.setenv("MISMATCH_INSTA_ACCESS_TOKEN", "tok")

        from launcher import main as launcher_main

        repo, calls = _fake_repo(
            [{"post_id": "rec6", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-Z"}],
            get_publish_account=lambda code: {
                "account_code": "IDN-Z", "api_provider": "instagram_login",
                "ig_user_id": "AIRTABLE_VALUE_111",  # .env 값과 다름
                "credential_key": "MISMATCH",
            },
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_insta_upload()

        assert calls["claim"] == []

    def test_instagram_login_success_uses_graph_instagram_host_and_resolved_credential(self, monkeypatch):
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
        monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "ai-real-token")

        from launcher import main as launcher_main

        repo, calls = _fake_repo(
            [{"post_id": "rec7", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-000036"}],
            get_publish_account=lambda code: {
                "account_code": "IDN-000036", "api_provider": "instagram_login",
                "ig_user_id": "17841467725643424", "credential_key": "AI",
            },
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        publish_calls = []

        def _fake_publish_single(rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com"):
            publish_calls.append((access_token, ig_user_id, api_host))
            return {"ok": True, "ig_media_id": "m7"}

        monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)

        launcher_main._job_insta_upload()

        assert calls["claim"] == ["rec7"]
        assert publish_calls == [("ai-real-token", "17841467725643424", "graph.instagram.com")]

    def test_mixed_batch_accounts_do_not_cross_contaminate(self, monkeypatch):
        """혼합 배치 — 공란은 차단되고 계정키가 있는 레코드만 게시된다."""
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.setenv("INSTA_ACCESS_TOKEN", "legacy-token")
        monkeypatch.setenv("INSTA_IG_USER_ID", "legacy-iguser")
        monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
        monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "ai-real-token")

        from launcher import main as launcher_main

        posts = [
            {"post_id": "recA", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": ""},
            {"post_id": "recB", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-000036"},
        ]
        repo, calls = _fake_repo(
            posts,
            get_publish_account=lambda code: {
                "account_code": "IDN-000036", "api_provider": "instagram_login",
                "ig_user_id": "17841467725643424", "credential_key": "AI",
            },
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        publish_calls = []

        def _fake_publish_single(rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com"):
            publish_calls.append((rid, access_token, ig_user_id, api_host))
            return {"ok": True, "ig_media_id": f"m-{rid}"}

        monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)

        launcher_main._job_insta_upload()

        assert calls["claim"] == ["recB"]
        assert publish_calls == [
            ("recB", "ai-real-token", "17841467725643424", "graph.instagram.com")
        ]
