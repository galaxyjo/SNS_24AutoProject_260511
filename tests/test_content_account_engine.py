"""261024 STEP 2 — 공통 콘텐츠 엔진 계정별 설정(Canary IDN-000025) Target Test.

aijomoojin(IDN-000036)의 기존 값·호출 인자는 그대로이고, 새 계정은 자기 Flag·전용 Gemini Key·
Vault·Lock만 쓰는지 확인한다. 실제 Gemini·이미지·Airtable·Instagram 호출은 없다(전부 Fake)."""

import dataclasses
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import launcher.main as launcher_main  # noqa: E402
import modules.common.producer_lock as producer_lock  # noqa: E402
import modules.sns.content_package_builder as cpb  # noqa: E402
from modules.common.credential_resolver import CredentialResolutionError, resolve_gemini_credential  # noqa: E402
from modules.sns.content_filter import passes_ai_content_gate_v0  # noqa: E402
from tests.test_aijomoojin_content_producer import _fake_repo, _write_fixture_package  # noqa: E402

CANARY = "IDN-000025"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(producer_lock, "_DB_PATH", tmp_path / "producer_lock.db")
    shared = tmp_path / "vault"
    monkeypatch.setattr(cpb, "DEFAULT_VAULT_ROOT", shared)
    canary_vault = tmp_path / "vault" / "accounts" / CANARY
    monkeypatch.setitem(launcher_main.CONTENT_ACCOUNTS, CANARY,
                        dataclasses.replace(launcher_main.CONTENT_ACCOUNTS[CANARY], vault_root=canary_vault))
    for name in ("CONTENT_PRODUCER_ENABLED", "SLOT_SCHEDULE_ENABLED", "CAROUSEL_ENABLED", "CAROUSEL_STYLE",
                 "HERO_CARD_ENABLED", "GEMINI_API_KEY"):
        monkeypatch.delenv(f"IDN_000025_{name}", raising=False)
    return shared, canary_vault


@pytest.fixture
def canary_flags_on(monkeypatch):
    monkeypatch.setenv("IDN_000025_CONTENT_PRODUCER_ENABLED", "true")
    monkeypatch.setenv("IDN_000025_SLOT_SCHEDULE_ENABLED", "true")


class TestAccountConfig:
    def test_aijomoojin_config_keeps_existing_values(self):
        acct = launcher_main.CONTENT_ACCOUNTS["IDN-000036"]
        assert (acct.credential_key, acct.env_prefix, acct.vault_root, acct.lock_name, acct.news_enabled) == (
            "AI", "AIJOMOOJIN", None, "aijomoojin_content_producer", True)
        assert launcher_main._vault_kwargs(acct) == {}          # 기존 호출 인자 그대로

    def test_canary_config_uses_own_prefix_vault_lock_and_no_news(self):
        acct = launcher_main.CONTENT_ACCOUNTS[CANARY]
        assert (acct.credential_key, acct.env_prefix, acct.lock_name, acct.news_enabled) == (
            "IDN_000025", "IDN_000025", "content_producer_IDN-000025", False)
        assert acct.vault_root != cpb.DEFAULT_VAULT_ROOT
        assert launcher_main._vault_kwargs(acct) == {"vault_root": acct.vault_root}

    def test_runtime_canary_vault_is_under_ignored_vault_folder(self):
        # 모듈 원본 값(픽스처가 바꾸기 전) — gitignore 대상 vault/ 아래, 공용 vault/content와 분리.
        import importlib.util
        spec = importlib.util.find_spec("launcher.main")
        text = Path(spec.origin).read_text(encoding="utf-8")
        assert '_ROOT / "vault" / "accounts" / "IDN-000025"' in text


class TestCredentialFailClosed:
    def test_canary_gemini_key_missing_raises(self, monkeypatch):
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "aijomoojin-key")
        monkeypatch.setenv("GEMINI_API_KEY", "shared-key")
        with pytest.raises(CredentialResolutionError):
            resolve_gemini_credential("IDN_000025")

    def test_canary_gemini_key_reads_own_env_only(self, monkeypatch):
        monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
        assert resolve_gemini_credential("IDN_000025").api_key == "canary-key"


class TestSchedulerRegistration:
    def test_canary_flags_off_registers_no_canary_jobs(self, monkeypatch):
        sched = launcher_main._build_scheduler()
        assert not any(CANARY in j.id for j in sched.get_jobs())

    def test_canary_flags_on_registers_5_slots_and_5_producers(self, monkeypatch, canary_flags_on):
        sched = launcher_main._build_scheduler()
        jobs = [j for j in sched.get_jobs() if CANARY in j.id]
        slot = sorted(j.id for j in jobs if j.id.startswith("content_slot_"))
        prod = sorted(j.id for j in jobs if j.id.startswith("content_producer_"))
        assert slot == [f"content_slot_{CANARY}_{h:02d}00" for h in (6, 9, 12, 15, 18)]
        assert prod == [f"content_producer_{CANARY}_{h:02d}00" for h in (5, 8, 11, 14, 17)]
        assert all(j.kwargs == {"account_code": CANARY} for j in jobs)

    def test_canary_single_flag_registers_nothing(self, monkeypatch):
        monkeypatch.setenv("IDN_000025_SLOT_SCHEDULE_ENABLED", "true")
        sched = launcher_main._build_scheduler()
        assert not any(CANARY in j.id for j in sched.get_jobs())


class TestCanaryProducer:
    def test_flags_off_does_nothing(self, monkeypatch):
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))
        launcher_main._job_aijomoojin_content_producer(account_code=CANARY)

    def test_unknown_account_does_nothing(self, monkeypatch, canary_flags_on):
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))
        launcher_main._job_aijomoojin_content_producer(account_code="IDN-000022")

    def test_missing_gemini_key_fails_closed_without_other_keys(self, monkeypatch, canary_flags_on, _isolated):
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "aijomoojin-key")
        monkeypatch.setenv("GEMINI_API_KEY", "shared-key")
        monkeypatch.setattr("google.genai.Client", lambda **k: pytest.fail("Gemini Client 생성되면 안 됨"))
        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: pytest.fail("호출되면 안 됨"))
        repo, calls = _fake_repo(active_status="")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        slack = []
        monkeypatch.setattr(launcher_main, "_slack", lambda m: slack.append(m))

        launcher_main._job_aijomoojin_content_producer(account_code=CANARY)

        # Codex P1 — Key 확인이 Airtable·Vault·Lock보다 먼저다.
        assert calls["active_status_checks"] == [] and calls["save"] == []
        assert len(slack) == 1 and "IDN_000025" in slack[0]
        assert producer_lock.get_holder(lock_name="content_producer_IDN-000025") is None

    def test_missing_key_blocks_pending_resume(self, monkeypatch, canary_flags_on, _isolated):
        """Codex P1 — 025 vault에 pending 패키지가 있어도 전용 Key가 없으면 업로드·Airtable 쓰기 0건."""
        _, canary_vault = _isolated
        _write_fixture_package(canary_vault, "c25-pending", idempotency_version=2)
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "aijomoojin-key")
        monkeypatch.setattr("modules.sns.image_hosting.upload_local_file_to_imgbb",
                            lambda path: pytest.fail("업로드되면 안 됨"))
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))
        monkeypatch.setattr(launcher_main, "_slack", lambda m: None)

        launcher_main._job_aijomoojin_content_producer(account_code=CANARY)

        assert cpb.read_frontmatter("c25-pending", canary_vault)["channel_status"] == "pending"

    def test_missing_brand_handle_blocks_card_features(self, monkeypatch, canary_flags_on):
        monkeypatch.setitem(launcher_main.CONTENT_ACCOUNTS, CANARY,
                            dataclasses.replace(launcher_main.CONTENT_ACCOUNTS[CANARY], brand_handle=""))
        monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
        monkeypatch.setenv("IDN_000025_CAROUSEL_ENABLED", "true")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))
        launcher_main._job_aijomoojin_content_producer(account_code=CANARY)

    def test_canary_passes_own_brand_handle_to_builder(self, monkeypatch, canary_flags_on, _isolated):
        monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
        monkeypatch.setattr("google.genai.Client", lambda **k: object())
        create_calls = []
        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: create_calls.append(k) or
                            cpb.PackageResult(success=False, error_code="NO_SELECTABLE_TOPIC"))
        repo, _ = _fake_repo(active_status="")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(launcher_main, "_slack", lambda m: None)

        launcher_main._job_aijomoojin_content_producer(account_code=CANARY)

        assert create_calls[0]["brand_handle"] == "@rhrl201010"

    def test_canary_lock_is_separate_from_aijomoojin_lock(self, monkeypatch, canary_flags_on):
        other = producer_lock.new_owner_token()
        assert producer_lock.acquire(other) is True                  # aijomoojin Lock 보유 중
        monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
        repo, calls = _fake_repo(active_status="ready")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer(account_code=CANARY)

        assert calls["active_status_checks"] == [CANARY]             # 막히지 않고 진행됨
        assert producer_lock.get_holder()["owner_token"] == other    # aijomoojin Lock은 그대로
        producer_lock.release(other)

    def test_success_uses_own_key_vault_and_account(self, monkeypatch, canary_flags_on, _isolated):
        shared, canary_vault = _isolated
        monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "aijomoojin-key")
        keys = []

        class _FakeClient:
            def __init__(self, api_key=None):
                keys.append(api_key)

        monkeypatch.setattr("google.genai.Client", _FakeClient)
        create_calls = []

        def _fake_create(target_language="ko", **kwargs):
            create_calls.append({"target_language": target_language, **kwargs})
            _write_fixture_package(canary_vault, "c25-1", source_url="https://c25.example/a",
                                   caption="hello", idempotency_version=2)
            return cpb.PackageResult(success=True, content_id="c25-1", status="complete")

        monkeypatch.setattr(cpb, "create_content_package", _fake_create)
        uploaded = []
        monkeypatch.setattr("modules.sns.image_hosting.upload_local_file_to_imgbb",
                            lambda path: uploaded.append(path) or {"success": True, "public_url": "https://i.ibb.co/c25.jpg"})
        repo, calls = _fake_repo(active_status="", save_record_id="recC25",
                                 content_id_owner_account=CANARY)
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer(account_code=CANARY)

        assert keys == ["canary-key"]
        assert create_calls[0]["vault_root"] == canary_vault
        assert calls["persona_checks"] == [CANARY]
        assert {
            key: create_calls[0][key]
            for key in ("persona_code", "tone_style", "target_language", "content_pillars",
                        "seo_keywords", "conversion_cta")
        } == {
            "persona_code": "PER-024",
            "tone_style": "활기차고 친근한 쇼호스트 말투",
            "target_language": "KR",
            "content_pillars": "AI 쇼호스트 / 라이브 판매",
            "seo_keywords": "AI쇼호스트, 라이브커머스",
            "conversion_cta": "AI 쇼호스트 라이브 의뢰는 DM",
        }
        assert calls["save"][0]["account_code_ref"] == CANARY
        assert Path(uploaded[0]).is_relative_to(canary_vault)
        assert cpb.read_frontmatter("c25-1", canary_vault)["channel_status"] == "queued"
        assert not (shared / "content" / "c25-1.md").exists()     # 공용 vault 미사용

    def test_two_accounts_never_mix_persona_settings(self, tmp_path):
        persona_by_account = {
            "IDN-000025": {
                "persona_code": "PER-024", "tone_style": "쇼호스트", "language": "KR",
                "content_pillars": "라이브 판매", "seo_keywords": "라이브커머스", "conversion_cta": "DM 문의",
            },
            "IDN-000026": {
                "persona_code": "PER-025", "tone_style": "차분한 전문가", "language": "EN",
                "content_pillars": "skin care", "seo_keywords": "beauty", "conversion_cta": "Book now",
            },
        }

        class _Repo:
            def get_active_persona_by_account_code_v2(self, code):
                return persona_by_account[code]

        first = dataclasses.replace(launcher_main.CONTENT_ACCOUNTS[CANARY], account_code="IDN-000025")
        second = dataclasses.replace(first, account_code="IDN-000026", vault_root=tmp_path / "v26")
        first_kwargs = launcher_main._content_persona_kwargs(_Repo(), first)
        second_kwargs = launcher_main._content_persona_kwargs(_Repo(), second)

        assert first_kwargs["persona_code"] == "PER-024" and first_kwargs["tone_style"] == "쇼호스트"
        assert second_kwargs["persona_code"] == "PER-025" and second_kwargs["tone_style"] == "차분한 전문가"
        assert first_kwargs["content_pillars"] != second_kwargs["content_pillars"]

    def test_missing_persona_setting_fails_closed_before_builder(self, monkeypatch, canary_flags_on):
        monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
        incomplete = {
            "persona_code": "PER-024", "tone_style": "쇼호스트", "language": "KR",
            "content_pillars": "라이브 판매", "seo_keywords": "", "conversion_cta": "DM 문의",
        }
        repo, calls = _fake_repo(active_status="", persona=incomplete)
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr("google.genai.Client", lambda **k: object())
        monkeypatch.setattr(cpb, "create_content_package", lambda **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_aijomoojin_content_producer(account_code=CANARY)

        assert calls["persona_checks"] == [CANARY]

    def test_aijomoojin_persona_lookup_is_not_added(self):
        class _Repo:
            def get_active_persona_by_account_code_v2(self, code):
                pytest.fail("036 기존 Producer에 Persona 조회가 추가되면 안 됨")

        assert launcher_main._content_persona_kwargs(
            _Repo(), launcher_main.CONTENT_ACCOUNTS["IDN-000036"],
        ) == {}

    def test_canary_ignores_aijomoojin_pending_packages(self, monkeypatch, canary_flags_on, _isolated):
        shared, _ = _isolated
        _write_fixture_package(shared, "aijo-pending", idempotency_version=2)   # aijomoojin 미완료 패키지
        repo, calls = _fake_repo(active_status="")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(cpb, "create_content_package",
                            lambda *a, **k: cpb.PackageResult(success=False, error_code="NO_SELECTABLE_TOPIC"))
        monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
        monkeypatch.setattr("google.genai.Client", lambda **k: object())

        launcher_main._job_aijomoojin_content_producer(account_code=CANARY)

        assert calls["content_id_checks"] == []                      # 다른 계정 pending을 보지 않음
        assert cpb.read_frontmatter("aijo-pending", shared)["channel_status"] == "pending"


class TestCanarySlotPost:
    def test_flag_off_skips_before_airtable(self, monkeypatch):
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))
        launcher_main._job_aijomoojin_scheduled_post(account_code=CANARY)

    def test_unknown_account_skips(self, monkeypatch):
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))
        launcher_main._job_aijomoojin_scheduled_post(account_code="IDN-000022")

    def test_missing_key_stops_even_when_publish_gate_off(self, monkeypatch):
        """Codex P1 — 025의 Key Fail-closed는 PUBLISH_TEXT_GATE_ENABLED에 종속되지 않는다."""
        monkeypatch.setenv("IDN_000025_SLOT_SCHEDULE_ENABLED", "true")
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "aijomoojin-key")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))
        monkeypatch.setattr(launcher_main, "_slack", lambda m: None)
        launcher_main._job_aijomoojin_scheduled_post(account_code=CANARY)

    def test_queries_only_canary_account(self, monkeypatch):
        monkeypatch.setenv("IDN_000025_SLOT_SCHEDULE_ENABLED", "true")
        monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")      # 새 계정은 Gate ON일 때만 진행
        asked = []

        class _Repo:
            def fetch_pending_posts_for_account(self, code, limit=1):
                asked.append(code)
                return []

        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _Repo())
        launcher_main._job_aijomoojin_scheduled_post(account_code=CANARY)
        assert asked == [CANARY]


class TestPollerExclusion:
    """Codex P1 — 025 ready는 Flag가 꺼져 있어도 5분 폴러가 게시하지 않는다(036 기존 규칙은 그대로)."""

    class _Stop(Exception):
        pass

    def _run(self, monkeypatch, account_code_ref):
        post = {"post_id": "recX", "image_url": "https://i.ibb.co/x.jpg", "caption": "c", "hashtag": "",
                "account_code_ref": account_code_ref, "post_status": "ready", "data_classification": "production"}

        class _Repo:
            def fetch_pending_posts(self, limit=50):
                return [post]

        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _Repo())
        reached = []

        def _validate(*a, **k):
            reached.append(account_code_ref)
            raise self._Stop()

        monkeypatch.setattr("modules.common.canary_classification.validate_publication_candidate", _validate)
        try:
            launcher_main._job_insta_upload()
        except self._Stop:
            pass
        return reached

    def test_canary_ready_excluded_with_flags_off(self, monkeypatch):
        assert self._run(monkeypatch, CANARY) == []

    def test_aijomoojin_flag_off_still_reaches_poller(self, monkeypatch):
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "false")
        assert self._run(monkeypatch, "IDN-000036") == ["IDN-000036"]

    def test_aijomoojin_flag_on_excluded(self, monkeypatch):
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        assert self._run(monkeypatch, "IDN-000036") == []


class TestManualTools:
    """Codex P1 — 수동 도구가 지정한 계정만 실행한다(기본은 036)."""

    def _run_tool(self, monkeypatch, tool, func_name, argv):
        import runpy
        calls = []
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)   # 테스트 프로세스 env 오염 방지
        monkeypatch.setattr(launcher_main, func_name, lambda **k: calls.append(k))
        monkeypatch.setattr(sys, "argv", [tool] + argv)
        root = Path(__file__).resolve().parents[1]
        try:
            runpy.run_path(str(root / "tools" / tool), run_name="__main__")
        except SystemExit as exc:
            return calls, exc.code
        return calls, 0

    @pytest.mark.parametrize("tool,func", [("run_aijomoojin_producer_manual.py", "_job_aijomoojin_content_producer"),
                                           ("run_aijomoojin_publish_manual.py", "_job_aijomoojin_scheduled_post")])
    def test_default_is_aijomoojin_and_flag_selects_canary(self, monkeypatch, tool, func):
        assert self._run_tool(monkeypatch, tool, func, [])[0] == [{"account_code": "IDN-000036"}]
        assert self._run_tool(monkeypatch, tool, func, ["--account-code", CANARY])[0] == [{"account_code": CANARY}]

    @pytest.mark.parametrize("tool,func", [("run_aijomoojin_producer_manual.py", "_job_aijomoojin_content_producer"),
                                           ("run_aijomoojin_publish_manual.py", "_job_aijomoojin_scheduled_post")])
    def test_unknown_account_does_not_run(self, monkeypatch, tool, func):
        calls, code = self._run_tool(monkeypatch, tool, func, ["--account-code", "IDN-000022"])
        assert calls == [] and code not in (0, None)

    def test_lock_tool_reads_canary_lock(self, monkeypatch, capsys):
        import runpy
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
        token = producer_lock.new_owner_token()
        producer_lock.acquire(token, lock_name="content_producer_IDN-000025")
        monkeypatch.setattr(sys, "argv", ["check", "--account-code", CANARY])
        root = Path(__file__).resolve().parents[1]
        runpy.run_path(str(root / "tools" / "check_aijomoojin_producer_lock.py"), run_name="__main__")
        out = capsys.readouterr().out
        assert "lock_name=content_producer_IDN-000025" in out and "LOCK_STATE: held" in out
        # Codex 2차 P1 — 해제 안내는 이 계정 Lock 이름을 정확히 담고, 인자 없는 해제를 안내하지 않는다.
        assert "force_release(lock_name='content_producer_IDN-000025')" in out
        assert "force_release()" not in out
        producer_lock.release(token, lock_name="content_producer_IDN-000025")


class TestLockFailureSlack:
    """Codex 2차 P1 — Lock 선점 실패 Slack이 그 계정의 조회·해제 명령을 안내한다."""

    @pytest.mark.parametrize("account_code,lock_name", [(CANARY, "content_producer_IDN-000025"),
                                                         ("IDN-000036", "aijomoojin_content_producer")])
    def test_slack_names_account_lock(self, monkeypatch, account_code, lock_name):
        prefix = "IDN_000025" if account_code == CANARY else "AIJOMOOJIN"
        monkeypatch.setenv(f"{prefix}_CONTENT_PRODUCER_ENABLED", "true")
        monkeypatch.setenv(f"{prefix}_SLOT_SCHEDULE_ENABLED", "true")
        monkeypatch.setenv("IDN_000025_GEMINI_API_KEY", "canary-key")
        other = producer_lock.new_owner_token()
        producer_lock.acquire(other, lock_name=lock_name)
        sent = []
        monkeypatch.setattr(launcher_main, "_slack", lambda m: sent.append(m))
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: pytest.fail("Airtable 호출되면 안 됨"))

        launcher_main._job_aijomoojin_content_producer(account_code=account_code)

        assert len(sent) == 1
        assert f'force_release(lock_name="{lock_name}")' in sent[0]
        assert f"--account-code {account_code}" in sent[0]
        assert "force_release()" not in sent[0]
        producer_lock.release(other, lock_name=lock_name)


class TestBrandHandle:
    def test_note_cards_use_given_brand(self, monkeypatch):
        from types import SimpleNamespace
        monkeypatch.setattr(cpb, "generate_image", lambda prompt: SimpleNamespace(success=True, image_bytes=b"s"))
        monkeypatch.setattr(cpb, "check_images_for_text_and_logo", lambda images, **k: SimpleNamespace(
            success=True, checks=[SimpleNamespace(index=i + 1, passed=True) for i in range(len(images))]))
        brands = []
        monkeypatch.setattr(cpb, "render_note_card", lambda content: brands.append(content.brand) or b"png")
        carousel = SimpleNamespace(slides=[SimpleNamespace(text=f"t{i}", image_scene="scene") for i in range(3)])
        topic = SimpleNamespace(title="T")

        images, err = cpb._build_note_carousel_images(topic, carousel, brand_handle="@rhrl201010")
        assert err == "" and brands == ["@rhrl201010"] * 3
        brands.clear()
        cpb._build_note_carousel_images(topic, carousel)
        assert brands == ["@aijomoojin"] * 3                         # 기본(036) 그대로


class TestMissedSlotAlert:
    @pytest.mark.parametrize("job_id,alerted", [(f"content_slot_{CANARY}_0600", True),
                                                (f"content_producer_{CANARY}_0500", True),
                                                ("aijomoojin_slot_0600", True), ("insta_upload", False)])
    def test_listener_covers_content_jobs(self, monkeypatch, job_id, alerted):
        from types import SimpleNamespace
        sent = []
        monkeypatch.setattr(launcher_main, "_slack", lambda m: sent.append(m))
        listener = next(getattr(launcher_main, n) for n in dir(launcher_main)
                        if n.startswith("_on_") and "miss" in n.lower())
        listener(SimpleNamespace(job_id=job_id, scheduled_run_time="t"))
        assert bool(sent) is alerted


class TestAiContentGatePersona:
    def test_canary_with_own_persona_passes_identity(self, monkeypatch):
        # 외부 Gemini 호출 금지 — Safety 확인은 Fake로 대체한다.
        monkeypatch.setattr("modules.sns.caption_generator.check_caption_safety",
                            lambda caption, **k: ("SAFE", ""))
        assert passes_ai_content_gate_v0("한국어 캡션입니다 테스트", CANARY, "https://x.example", "PER-024") == (
            True, "PUBLISH_ALLOWED")

    def test_canary_with_aijomoojin_persona_rejected(self):
        assert passes_ai_content_gate_v0("캡션", CANARY, "https://x.example", "PER-002") == (
            False, "AI_CONTENT_PERSONA_MISMATCH")

    def test_unlisted_account_rejected(self):
        assert passes_ai_content_gate_v0("캡션", "IDN-000022", "https://x.example", "PER-021") == (
            False, "AI_CONTENT_ACCOUNT_MISMATCH")

    def test_aijomoojin_unchanged(self):
        assert passes_ai_content_gate_v0("캡션", "IDN-000036", "https://x.example", "PER-024") == (
            False, "AI_CONTENT_PERSONA_MISMATCH")
