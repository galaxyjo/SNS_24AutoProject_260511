"""tests/test_aijomoojin_binding_adapter.py — 260801 Step5 T1 aijomoojin 전용
Binding Adapter 검증.

Part A: verify_aijomoojin_binding() 순수 로직 단위테스트(Repository도 Mock).
Part B: launcher/main.py._job_insta_upload() 통합 — Feature Flag on/off, 다른 계정,
Binding 성공/실패 시 publish_single() 호출횟수를 검증한다. canary_classification의
validate_publication_candidate()는 이 세션 환경의 기존 runtime_boot_policy.json
PermissionError(T4, 이번 변경과 무관)를 우회하기 위해 monkeypatch로 no-op 처리한다
— ACL·환경변수 변경이 아니라 순수 테스트 격리다.
실제 네트워크·Airtable·Meta 호출 없이 전부 Mock/Fake로 검증한다.
"""

from unittest.mock import MagicMock

import pytest

# modules.infra.airtable_repository와 launcher.main은 import 시점에
# load_dotenv(override=True)를 실행한다(각 파일 자체 관행, test_provider_routing.py의
# 동일 주석 참조). 파일 로드 시점(모든 monkeypatch.setenv보다 먼저)에 미리 import해
# 두어, 테스트 도중 최초 import가 실 .env 값으로 monkeypatch 값을 덮어쓰는 것을 막는다.
import modules.infra.airtable_repository  # noqa: F401,E402
import launcher.main  # noqa: F401,E402

from modules.common.aijomoojin_binding_adapter import (
    AIJOMOOJIN_ACCOUNT_CODE,
    aijomoojin_binding_adapter_enabled,
    verify_aijomoojin_binding,
)


@pytest.fixture(autouse=True)
def _no_slot_schedule_leak(monkeypatch):
    """260804 Track B 6G — 실 .env의 AIJOMOOJIN_SLOT_SCHEDULE_ENABLED=true가
    이 파일의 _job_insta_upload() 통합 테스트로 새어들어와 IDN-000036 레코드가
    claim 전에 스킵되는 것을 막는다(이 파일은 그 Flag와 무관한 테스트다)."""
    monkeypatch.delenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", raising=False)


# ── Part A: 순수 로직 단위테스트 ──────────────────────────────────────────

class TestVerifyAijomoojinBindingUnit:
    def test_non_target_account_returns_true_without_repo_call(self):
        repo = MagicMock()
        assert verify_aijomoojin_binding("IDN-000041", repo) is True
        repo.get_active_persona_by_account_code_v2.assert_not_called()

    def test_target_account_persona_found_returns_true(self):
        repo = MagicMock()
        repo.get_active_persona_by_account_code_v2.return_value = {"persona_code": "PER-002"}
        assert verify_aijomoojin_binding(AIJOMOOJIN_ACCOUNT_CODE, repo) is True

    def test_target_account_persona_none_returns_false(self):
        repo = MagicMock()
        repo.get_active_persona_by_account_code_v2.return_value = None
        assert verify_aijomoojin_binding(AIJOMOOJIN_ACCOUNT_CODE, repo) is False

    def test_target_account_repo_raises_returns_false(self):
        """중복(RepositoryValidationError)·API 오류(RepositoryUnavailableError) 전부
        이 경로로 수렴 — 게시 차단."""
        repo = MagicMock()
        repo.get_active_persona_by_account_code_v2.side_effect = RuntimeError("dup or api error")
        assert verify_aijomoojin_binding(AIJOMOOJIN_ACCOUNT_CODE, repo) is False

    def test_target_account_persona_code_mismatch_returns_false(self):
        repo = MagicMock()
        repo.get_active_persona_by_account_code_v2.return_value = {"persona_code": "PER-999"}
        assert verify_aijomoojin_binding(AIJOMOOJIN_ACCOUNT_CODE, repo) is False

    def test_flag_default_is_false(self, monkeypatch):
        monkeypatch.delenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", raising=False)
        assert aijomoojin_binding_adapter_enabled() is False


# ── Part B: launcher/main.py 통합(publish_single 호출횟수 검증) ──────────

def _fake_repo_with_persona(posts, get_publish_account, persona_result):
    calls = {"claim": [], "persona_lookup": []}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return posts

        def get_publish_account(self, account_code):
            return get_publish_account(account_code)

        def claim_post_for_upload(self, post_id):
            calls["claim"].append(post_id)
            return True

        def mark_post_result(self, post_id, result):
            pass

        def get_active_persona_by_account_code_v2(self, account_code):
            calls["persona_lookup"].append(account_code)
            if isinstance(persona_result, Exception):
                raise persona_result
            return persona_result

    return _FakeRepo(), calls


@pytest.fixture
def bypass_canary_classification(monkeypatch):
    """이번 변경과 무관한 기존 runtime_boot_policy.json PermissionError(T4)를
    우회하기 위한 순수 테스트 격리 — validate_publication_candidate를 no-op으로
    치환한다(ACL·환경변수 변경 아님)."""
    import modules.common.canary_classification as canary_classification

    monkeypatch.setattr(canary_classification, "validate_publication_candidate", lambda *a, **k: None)


class TestJobInstaUploadAijomoojinBindingIntegration:
    AI_ACCOUNT = {
        "account_code": "IDN-000036", "api_provider": "instagram_login",
        "ig_user_id": "17841467725643424", "credential_key": "AI",
        "automation_enabled": True,
    }

    def _post(self, rid="rec1", account_code_ref="IDN-000036"):
        return {"post_id": rid, "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": account_code_ref}

    def test_flag_enabled_blocks_publish_when_persona_missing(self, monkeypatch, bypass_canary_classification):
        monkeypatch.setenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "true")
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
        monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
        monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "ai-real-token")

        from launcher import main as launcher_main

        repo, calls = _fake_repo_with_persona([self._post()], lambda code: self.AI_ACCOUNT, persona_result=None)
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        publish_calls = []
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: publish_calls.append(1))

        launcher_main._job_insta_upload()

        assert calls["persona_lookup"] == ["IDN-000036"]
        assert calls["claim"] == []
        assert publish_calls == []

    def test_flag_enabled_allows_publish_when_binding_ok(self, monkeypatch, bypass_canary_classification):
        monkeypatch.setenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "true")
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
        monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
        monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "ai-real-token")

        from launcher import main as launcher_main

        repo, calls = _fake_repo_with_persona(
            [self._post()], lambda code: self.AI_ACCOUNT, persona_result={"persona_code": "PER-002"}
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        publish_calls = []
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com": (
                publish_calls.append(1) or {"ok": True, "ig_media_id": "m1"}
            ),
        )

        launcher_main._job_insta_upload()

        assert calls["claim"] == ["rec1"]
        assert publish_calls == [1]

    def test_flag_disabled_legacy_path_unaffected(self, monkeypatch, bypass_canary_classification):
        monkeypatch.delenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", raising=False)
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
        monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
        monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "ai-real-token")

        from launcher import main as launcher_main

        # persona_result=Exception이어도 Flag off라 신규 경로(Persona 조회) 자체가 호출되면 안 됨
        repo, calls = _fake_repo_with_persona(
            [self._post()], lambda code: self.AI_ACCOUNT, persona_result=RuntimeError("should not be called")
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        publish_calls = []
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com": (
                publish_calls.append(1) or {"ok": True, "ig_media_id": "m1"}
            ),
        )

        launcher_main._job_insta_upload()

        assert calls["persona_lookup"] == []
        assert calls["claim"] == ["rec1"]
        assert publish_calls == [1]

    def test_other_account_unaffected_even_when_flag_enabled(self, monkeypatch, bypass_canary_classification):
        monkeypatch.setenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "true")
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
        monkeypatch.setenv("YUNA_INSTA_IG_USER_ID", "17841476202821375")
        monkeypatch.setenv("YUNA_INSTA_ACCESS_TOKEN", "yuna-real-token")

        from launcher import main as launcher_main

        other_account = {
            "account_code": "IDN-000041", "api_provider": "facebook_login",
            "ig_user_id": "17841476202821375", "credential_key": "YUNA",
            "automation_enabled": True,
        }
        repo, calls = _fake_repo_with_persona(
            [self._post(rid="rec2", account_code_ref="IDN-000041")],
            lambda code: other_account,
            persona_result=RuntimeError("should not be called for non-aijomoojin"),
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        publish_calls = []
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com": (
                publish_calls.append(1) or {"ok": True, "ig_media_id": "m2"}
            ),
        )

        launcher_main._job_insta_upload()

        assert calls["persona_lookup"] == []
        assert calls["claim"] == ["rec2"]
        assert publish_calls == [1]
