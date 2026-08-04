"""tests/test_aijomoojin_content_producer.py — 260804 Track B 6G Producer
(Sourcebook Topic → 캡션/이미지 → Vault → Airtable ready, 매일 05:00/09:00/16:00
ICT) 검증. 회장 승인 10개 필수조건 + Target Test 8개 전부 포함.

Part A: `_build_scheduler()` 등록 파라미터(05/09/16, Asia/Bangkok, 안전 파라미터).
Part B: `_job_aijomoojin_content_producer()` 단일 실행 통합(ready/uploading 가드,
        성공 시 queued 전환, 실패 시 pending 유지·재시도 0회, NO_SELECTABLE_TOPIC
        안전 종료, stale pending 마커 무시, 진짜 pending 재개).
Part C: `producer_lock` 동시실행 방지(Scheduler·수동 스크립트 공유 계약의 근거).

실제 Airtable·Meta·Gemini·Cloudflare·imgbb 호출 없음 — 전부 Fake/Mock, Vault는
tmp_path로 격리.
"""

from unittest.mock import MagicMock

import pytest

import modules.infra.airtable_repository  # noqa: F401,E402
import launcher.main  # noqa: F401,E402

import modules.common.producer_lock as producer_lock
import modules.sns.content_package_builder as cpb


AIJOMOOJIN = "IDN-000036"


# ── Part A: _build_scheduler() 등록 파라미터 ──────────────────────────────

class TestSchedulerRegistration:
    def test_flag_off_registers_no_producer_jobs(self, monkeypatch):
        monkeypatch.delenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", raising=False)
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        job_ids = {j.id for j in sched.get_jobs()}
        assert not any(jid.startswith("aijomoojin_producer_") for jid in job_ids)

    def test_flag_on_registers_exactly_3_producer_jobs(self, monkeypatch):
        monkeypatch.setenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", "true")
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        producer_job_ids = {j.id for j in sched.get_jobs() if j.id.startswith("aijomoojin_producer_")}
        assert producer_job_ids == {"aijomoojin_producer_0500", "aijomoojin_producer_0900", "aijomoojin_producer_1600"}

    @pytest.mark.parametrize("producer_flag,slot_flag", [("true", "false"), ("false", "true"), ("false", "false")])
    def test_mismatched_flag_combo_registers_no_producer_jobs(self, monkeypatch, producer_flag, slot_flag):
        """260804 Codex 2차 리뷰 P0 — 두 Flag 중 하나만 켜져 있으면(둘 다 켜져야만
        정상) 등록 자체를 하지 않는다. 한 Flag만 켜진 조합에서 슬롯 밖 게시가
        가능해지는 것을 등록 단계에서부터 차단한다."""
        monkeypatch.setenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", producer_flag)
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", slot_flag)
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        producer_job_ids = {j.id for j in sched.get_jobs() if j.id.startswith("aijomoojin_producer_")}
        assert producer_job_ids == set()

    @pytest.mark.parametrize("job_id,hour", [
        ("aijomoojin_producer_0500", 5), ("aijomoojin_producer_0900", 9), ("aijomoojin_producer_1600", 16),
    ])
    def test_each_producer_job_safety_params_and_ict_hour(self, monkeypatch, job_id, hour):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        monkeypatch.setenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", "true")
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        job = next(j for j in sched.get_jobs() if j.id == job_id)

        assert job.func is launcher_main._job_aijomoojin_content_producer
        assert job.max_instances == 1
        assert job.coalesce is False
        assert job.misfire_grace_time == 60

        bangkok = ZoneInfo("Asia/Bangkok")
        just_before = datetime(2026, 8, 5, hour, 0, 0, tzinfo=bangkok) - timedelta(minutes=1)
        next_fire = job.trigger.get_next_fire_time(None, just_before)
        assert next_fire == datetime(2026, 8, 5, hour, 0, 0, tzinfo=bangkok)

    def test_canary_safe_mode_registers_no_producer_jobs(self, monkeypatch):
        monkeypatch.setenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", "true")
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler(canary_safe_mode=True)
        assert sched.get_jobs() == []

    def test_publish_slot_jobs_unaffected_by_producer_flag(self, monkeypatch):
        monkeypatch.setenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", "true")
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        slot_ids = {j.id for j in sched.get_jobs() if j.id.startswith("aijomoojin_slot_")}
        assert slot_ids == {"aijomoojin_slot_0600", "aijomoojin_slot_1000", "aijomoojin_slot_1700"}
        insta_upload_job = next(j for j in sched.get_jobs() if j.id == "insta_upload")
        assert insta_upload_job.func is launcher_main._job_insta_upload


# ── Part B: _job_aijomoojin_content_producer() 단일 실행 통합 ─────────────

def _write_fixture_package(vault_root, content_id, source_url="https://example.com/x", caption="c", channel_status="pending"):
    (vault_root / "content").mkdir(parents=True, exist_ok=True)
    (vault_root / "images").mkdir(parents=True, exist_ok=True)
    fields = {
        "content_id": content_id, "topic_id": "3.9", "title": "t", "source_url": source_url,
        "claims": "m", "status": "complete", "caption": caption, "hashtags": "#x",
        "image_path": f"images/{content_id}.png", "created_at": "2026-08-04T00:00:00",
        "channel_status": channel_status,
    }
    md_path, img_path = cpb._content_paths(content_id, vault_root)
    md_path.write_text(cpb._render_frontmatter(fields) + f"\n{caption}\n", encoding="utf-8")
    img_path.write_bytes(b"fake-png-bytes")
    return md_path, img_path


def _fake_repo(active_status="", exists_by_source_url=False, known_source_urls=frozenset(),
                exists_by_image_url=False, confirm_after_save=None, save_raises=None, save_record_id="recNEW"):
    """exists_by_source_url: 전체 source_url에 대한 기본값(True/False).
    known_source_urls: 이 집합에 있는 source_url만 True로 취급(둘 다 주어지면
    known_source_urls가 우선) — stale/genuine 파일이 섞여 있을 때 URL별로
    다른 답을 줘야 하는 테스트용.
    exists_by_image_url: 게시 직전 중복 확인(1번째 exists_post_by_image_url 호출)에
    쓰이는 값. confirm_after_save가 주어지면, 그 이후(2번째부터) 호출은
    exists_by_image_url 대신 confirm_after_save를 반환한다 — 빈 record_id
    read-after-write 확인 테스트에서 "게시 전엔 중복 아님, 저장 후엔 확인됨"을
    구분하기 위함."""
    calls = {"save": [], "active_status_checks": [], "source_url_checks": [], "image_url_checks": 0}

    class _FakeRepo:
        def get_active_post_status_for_account(self, account_code_ref):
            calls["active_status_checks"].append(account_code_ref)
            return active_status

        def find_account_post_by_source_url(self, account_code_ref, source_url):
            calls["source_url_checks"].append((account_code_ref, source_url))
            if known_source_urls:
                return source_url in known_source_urls
            return exists_by_source_url

        def exists_post_by_image_url(self, image_url):
            calls["image_url_checks"] += 1
            if calls["image_url_checks"] > 1 and confirm_after_save is not None:
                return confirm_after_save
            return exists_by_image_url

        def save_instagram_post(self, post):
            calls["save"].append(dict(post))
            if save_raises:
                raise save_raises
            return save_record_id

    return _FakeRepo(), calls


@pytest.fixture(autouse=True)
def _isolated_lock_db(tmp_path, monkeypatch):
    """모든 테스트가 격리된 Lock DB를 쓰게 한다(Runtime DB 오염 방지)."""
    monkeypatch.setattr(producer_lock, "_DB_PATH", tmp_path / "producer_lock.db")


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    monkeypatch.setattr(cpb, "DEFAULT_VAULT_ROOT", root)
    return root


@pytest.fixture
def _flag_on(monkeypatch):
    """260804 Codex 2차 리뷰 P0 — Producer가 실제로 진행하려면 두 Flag가
    모두 true여야 한다(슬롯 밖 게시 방지 계약)."""
    monkeypatch.setenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", "true")
    monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")


class TestReadyOrUploadingGuard:
    def test_ready_exists_skips_creation(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        repo, calls = _fake_repo(active_status="ready")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_aijomoojin_content_producer()

        assert calls["save"] == []
        assert calls["active_status_checks"] == [AIJOMOOJIN]

    def test_uploading_exists_holds_and_alerts_without_creation(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        repo, calls = _fake_repo(active_status="uploading")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: pytest.fail("호출되면 안 됨"))
        slack_calls = []
        monkeypatch.setattr(launcher_main, "_slack", lambda msg: slack_calls.append(msg))

        launcher_main._job_aijomoojin_content_producer()

        assert calls["save"] == []
        assert len(slack_calls) == 1
        assert "HOLD" in slack_calls[0] or "uploading" in slack_calls[0]


class TestSuccessPath:
    def test_new_package_success_creates_ready_and_marks_queued(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        def _fake_create(target_language="ko"):
            _write_fixture_package(vault_root, "new-content-1", source_url="https://new.example/a", caption="hello")
            return cpb.PackageResult(success=True, content_id="new-content-1", status="complete")

        monkeypatch.setattr(cpb, "create_content_package", _fake_create)
        monkeypatch.setattr(
            "modules.sns.image_hosting.upload_local_file_to_imgbb",
            lambda path: {"success": True, "public_url": "https://i.ibb.co/new.jpg"},
        )
        repo, calls = _fake_repo(active_status="", save_record_id="recNEW1")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer()

        assert len(calls["save"]) == 1
        saved = calls["save"][0]
        assert saved["account_code_ref"] == AIJOMOOJIN
        assert saved["post_status"] == "ready"
        assert saved["image_url"] == "https://i.ibb.co/new.jpg"
        assert saved["caption"] == "hello"
        assert saved["source_url"] == "https://new.example/a"

        fields = cpb.read_frontmatter("new-content-1", vault_root)
        assert fields["channel_status"] == "queued"

    def test_no_selectable_topic_safe_exit_zero_partial_state(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        monkeypatch.setattr(
            cpb, "create_content_package",
            lambda *a, **k: cpb.PackageResult(success=False, error_code="NO_SELECTABLE_TOPIC"),
        )
        repo, calls = _fake_repo(active_status="")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        slack_calls = []
        monkeypatch.setattr(launcher_main, "_slack", lambda msg: slack_calls.append(msg))

        launcher_main._job_aijomoojin_content_producer()

        assert calls["save"] == []
        assert (vault_root / "content").exists() is False or list((vault_root / "content").glob("*.md")) == []
        assert len(slack_calls) == 1


class TestPendingFailureNoRetry:
    def test_imgbb_failure_leaves_pending_no_retry_within_call(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        def _fake_create(target_language="ko"):
            _write_fixture_package(vault_root, "imgbb-fail-1", source_url="https://x.example/imgbb")
            return cpb.PackageResult(success=True, content_id="imgbb-fail-1", status="complete")

        monkeypatch.setattr(cpb, "create_content_package", _fake_create)
        upload_calls = []
        monkeypatch.setattr(
            "modules.sns.image_hosting.upload_local_file_to_imgbb",
            lambda path: (upload_calls.append(path) or {"success": False, "error": "boom"}),
        )
        repo, calls = _fake_repo(active_status="")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer()

        assert len(upload_calls) == 1  # 정확히 1회만 시도
        assert calls["save"] == []
        fields = cpb.read_frontmatter("imgbb-fail-1", vault_root)
        assert fields["channel_status"] == "pending"  # 전환 안 됨

    def test_airtable_failure_leaves_pending_no_retry(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        def _fake_create(target_language="ko"):
            _write_fixture_package(vault_root, "airtable-fail-1", source_url="https://x.example/at")
            return cpb.PackageResult(success=True, content_id="airtable-fail-1", status="complete")

        monkeypatch.setattr(cpb, "create_content_package", _fake_create)
        monkeypatch.setattr(
            "modules.sns.image_hosting.upload_local_file_to_imgbb",
            lambda path: {"success": True, "public_url": "https://i.ibb.co/x.jpg"},
        )
        repo, calls = _fake_repo(active_status="", save_raises=RuntimeError("airtable outcome unknown"))
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer()

        assert len(calls["save"]) == 1  # 정확히 1회만 시도(예외 발생, 재시도 없음)
        fields = cpb.read_frontmatter("airtable-fail-1", vault_root)
        assert fields["channel_status"] == "pending"


class TestPendingResumeAndStale:
    def test_stale_pending_marker_not_touched_new_package_created_instead(self, monkeypatch, _flag_on, vault_root):
        """기존 6건처럼 Airtable엔 이미 저장됐지만 channel_status가 예전 로직
        부재로 pending에 머문 항목 — 건드리지 않고, 새 topic으로 정상 진행한다."""
        from launcher import main as launcher_main

        _write_fixture_package(vault_root, "stale-1", source_url="https://already.example/posted")

        def _fake_create(target_language="ko"):
            _write_fixture_package(vault_root, "brand-new-1", source_url="https://new.example/b")
            return cpb.PackageResult(success=True, content_id="brand-new-1", status="complete")

        create_calls = []
        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: (create_calls.append(1), _fake_create())[1])
        monkeypatch.setattr(
            "modules.sns.image_hosting.upload_local_file_to_imgbb",
            lambda path: {"success": True, "public_url": "https://i.ibb.co/new2.jpg"},
        )
        repo, calls = _fake_repo(active_status="", exists_by_source_url=True)  # stale-1의 source_url이 이미 Airtable에 있음
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer()

        assert create_calls == [1]  # 새 topic 생성이 실제로 일어남(stale 때문에 막히지 않음)
        stale_fields = cpb.read_frontmatter("stale-1", vault_root)
        assert stale_fields["channel_status"] == "pending"  # 손 안 댐(회장 조건 7)
        new_fields = cpb.read_frontmatter("brand-new-1", vault_root)
        assert new_fields["channel_status"] == "queued"

    def test_genuine_pending_package_resumed_without_new_creation(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        _write_fixture_package(vault_root, "resume-1", source_url="https://orphan.example/c", caption="resumed caption")

        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: pytest.fail("새로 생성되면 안 됨(재개 대상 있음)"))
        monkeypatch.setattr(
            "modules.sns.image_hosting.upload_local_file_to_imgbb",
            lambda path: {"success": True, "public_url": "https://i.ibb.co/resumed.jpg"},
        )
        repo, calls = _fake_repo(active_status="", exists_by_source_url=False)  # 진짜로 Airtable에 없음
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer()

        assert len(calls["save"]) == 1
        assert calls["save"][0]["caption"] == "resumed caption"
        fields = cpb.read_frontmatter("resume-1", vault_root)
        assert fields["channel_status"] == "queued"

    def test_stale_then_genuine_pending_together_genuine_is_resumed(self, monkeypatch, _flag_on, vault_root):
        """260804 Codex 2차 리뷰 P0 요구 테스트 — stale 1건과 genuine pending 1건이
        동시에 Vault에 있을 때, stale에서 멈추지 않고 뒤의 genuine 항목을
        찾아 재개해야 한다(이전엔 find_pending_channel_package가 첫 1건만
        봐서 genuine 항목을 영영 못 찾는 버그가 있었다)."""
        from launcher import main as launcher_main

        # 파일명 정렬상 "aaa-stale"이 "zzz-genuine"보다 먼저 스캔되도록 이름을 고정.
        _write_fixture_package(vault_root, "aaa-stale", source_url="https://already.example/stale", caption="stale caption")
        _write_fixture_package(vault_root, "zzz-genuine", source_url="https://orphan.example/genuine", caption="genuine caption")

        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: pytest.fail("새로 생성되면 안 됨(재개 대상 있음)"))
        monkeypatch.setattr(
            "modules.sns.image_hosting.upload_local_file_to_imgbb",
            lambda path: {"success": True, "public_url": "https://i.ibb.co/genuine.jpg"},
        )
        repo, calls = _fake_repo(active_status="", known_source_urls={"https://already.example/stale"})
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer()

        assert len(calls["save"]) == 1
        assert calls["save"][0]["caption"] == "genuine caption"
        assert cpb.read_frontmatter("aaa-stale", vault_root)["channel_status"] == "pending"  # 손 안 댐
        assert cpb.read_frontmatter("zzz-genuine", vault_root)["channel_status"] == "queued"  # 재개됨


class TestEmptyRecordIdReadAfterWrite:
    """260804 Codex 3차 리뷰 P1 — save_instagram_post()가 예외 없이 빈 record_id를
    반환해도 그것만으로 queued 전환을 하지 않는다. exists_post_by_image_url()로
    "이번에 방금 올린 그 image_url"이 실제로 저장됐는지 재확인한다(source_url
    기반 확인은 과거 레코드와 혼동될 수 있어 3차 리뷰에서 교체됨)."""

    def test_empty_record_id_confirmed_by_readback_still_marks_queued(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        def _fake_create(target_language="ko"):
            _write_fixture_package(vault_root, "emptyid-confirmed", source_url="https://x.example/confirmed")
            return cpb.PackageResult(success=True, content_id="emptyid-confirmed", status="complete")

        monkeypatch.setattr(cpb, "create_content_package", _fake_create)
        monkeypatch.setattr(
            "modules.sns.image_hosting.upload_local_file_to_imgbb",
            lambda path: {"success": True, "public_url": "https://i.ibb.co/confirmed.jpg"},
        )
        # 1번째 exists_post_by_image_url 호출(게시 전 중복확인)은 False(중복 아님,
        # 정상 진행) — save_instagram_post는 빈 문자열 반환 — 2번째 호출
        # (read-after-write 확인)은 True(실제로는 저장된 상태).
        repo, calls = _fake_repo(
            active_status="", save_record_id="", exists_by_image_url=False, confirm_after_save=True,
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer()

        fields = cpb.read_frontmatter("emptyid-confirmed", vault_root)
        assert fields["channel_status"] == "queued"

    def test_empty_record_id_unconfirmed_leaves_pending_and_alerts(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        def _fake_create(target_language="ko"):
            _write_fixture_package(vault_root, "emptyid-unconfirmed", source_url="https://x.example/unconfirmed")
            return cpb.PackageResult(success=True, content_id="emptyid-unconfirmed", status="complete")

        monkeypatch.setattr(cpb, "create_content_package", _fake_create)
        monkeypatch.setattr(
            "modules.sns.image_hosting.upload_local_file_to_imgbb",
            lambda path: {"success": True, "public_url": "https://i.ibb.co/unconfirmed.jpg"},
        )
        # 1번째 호출(게시 전 중복확인)은 False, 2번째(read-after-write)도 False —
        # 즉 이번 저장이 실제로 확인되지 않는 상태.
        repo, calls = _fake_repo(
            active_status="", save_record_id="", exists_by_image_url=False, confirm_after_save=False,
        )
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        slack_calls = []
        monkeypatch.setattr(launcher_main, "_slack", lambda msg: slack_calls.append(msg))

        launcher_main._job_aijomoojin_content_producer()

        fields = cpb.read_frontmatter("emptyid-unconfirmed", vault_root)
        assert fields["channel_status"] == "pending"  # queued로 안 넘어감
        assert len(slack_calls) == 1


class TestFlagComboRuntimeGuard:
    """260804 Codex 2차 리뷰 P0 — Scheduler 등록 단계뿐 아니라 함수 실행
    시점에도 두 Flag를 함께 확인한다(등록 이후 Runtime에서 한쪽만 바뀌는
    경우까지 방어)."""

    def test_producer_flag_on_but_slot_flag_off_does_not_run(self, monkeypatch, vault_root):
        monkeypatch.setenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", "true")
        monkeypatch.delenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", raising=False)
        from launcher import main as launcher_main

        class _ExplodingRepo:
            def __init__(self):
                raise AssertionError("Flag 조합 불충족인데 Repository가 생성되면 안 됨")

        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", _ExplodingRepo)
        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_aijomoojin_content_producer()  # 예외 없이 조용히 스킵돼야 함


# ── Part C: producer_lock 동시실행 방지 ────────────────────────────────────

class TestProducerLockConcurrency:
    def test_lock_prevents_concurrent_execution_and_alerts_with_holder_info(self, monkeypatch, _flag_on, vault_root):
        """Scheduler와 수동 스크립트(tools/run_aijomoojin_producer_manual.py, 동일
        _job_aijomoojin_content_producer 호출)가 동일 Lock을 쓴다는 계약의 근거 —
        Lock이 이미 걸려 있으면 Repository조차 생성되지 않고 즉시 스킵된다.
        260804 Codex 2차 리뷰 P1/P2 — Crash로 Lock이 영구 고착돼도 조용히
        지나가지 않도록, 보유자 정보를 포함한 Slack 알림도 확인한다."""
        from launcher import main as launcher_main

        other_token = producer_lock.new_owner_token()
        assert producer_lock.acquire(other_token) is True  # 다른 실행이 이미 Lock 보유 중을 재현

        class _ExplodingRepo:
            def __init__(self):
                raise AssertionError("Lock이 걸려 있는데 Repository가 생성되면 안 됨")

        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", _ExplodingRepo)
        monkeypatch.setattr(cpb, "create_content_package", lambda *a, **k: pytest.fail("호출되면 안 됨"))
        slack_calls = []
        monkeypatch.setattr(launcher_main, "_slack", lambda msg: slack_calls.append(msg))

        launcher_main._job_aijomoojin_content_producer()  # 예외 없이 조용히 스킵돼야 함

        assert len(slack_calls) == 1
        assert other_token in slack_calls[0]  # holder 정보(owner_token) 포함 확인

        producer_lock.release(other_token)

    def test_lock_released_after_successful_run(self, monkeypatch, _flag_on, vault_root):
        from launcher import main as launcher_main

        repo, calls = _fake_repo(active_status="ready")  # 가장 빠른 경로(ready 존재)로 조기 종료
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)

        launcher_main._job_aijomoojin_content_producer()

        assert producer_lock.get_holder() is None  # finally에서 정상 해제됨

    def test_second_acquire_fails_while_first_held_unit(self):
        """producer_lock 자체의 원자성 — Scheduler Job과 수동 스크립트가 동일
        모듈을 공유하기만 하면 이 계약이 자동으로 적용된다(별도 IPC 불필요)."""
        token_a = producer_lock.new_owner_token()
        token_b = producer_lock.new_owner_token()
        assert producer_lock.acquire(token_a) is True
        assert producer_lock.acquire(token_b) is False  # 두 번째는 즉시 실패(대기 없음)
        assert producer_lock.release(token_b) is False  # 남의 Lock은 못 품
        assert producer_lock.release(token_a) is True
        assert producer_lock.get_holder() is None


class TestProducerLockGetHolderIsReadOnly:
    """260804 Codex 4차 리뷰 P1 — get_holder()가 진짜 Read-only인지(DB 파일이
    없을 때 아무것도 만들지 않는지) 직접 증명한다."""

    def test_get_holder_creates_nothing_when_db_file_absent(self, tmp_path, monkeypatch):
        db_path = tmp_path / "nonexistent" / "producer_lock.db"
        monkeypatch.setattr(producer_lock, "_DB_PATH", db_path)

        result = producer_lock.get_holder()

        assert result is None
        assert not db_path.parent.exists()  # 디렉터리조차 안 만들어짐(mkdir 호출 없음)
        assert not db_path.exists()

    def test_get_holder_reads_existing_lock_without_error(self, tmp_path):
        db_path = tmp_path / "producer_lock.db"
        token = producer_lock.new_owner_token()
        assert producer_lock.acquire(token, db_path=db_path) is True  # 정상 write 경로로 파일 준비

        result = producer_lock.get_holder(db_path=db_path)

        assert result == {"owner_token": token, "acquired_at": result["acquired_at"]}
        producer_lock.release(token, db_path=db_path)


# ── Part D: get_active_post_status_for_account() Repository 계약 검증 ─────

class TestGetActivePostStatusRepositoryContract:
    """260804 Codex 4차 리뷰 P1 — Fake Repository 기반 통합 테스트 외에, 실제
    `requests.get()` 호출 순서·파라미터·fail-closed 전파를 직접 확인한다."""

    def test_uploading_found_on_first_request_no_second_request(self, monkeypatch):
        from unittest.mock import MagicMock, patch
        from modules.infra.airtable_repository import AirtableRepository

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"records": [{"fields": {"post_status": "uploading"}}]}
        with patch("modules.infra.airtable_repository.requests.get", return_value=resp) as mock_get, \
             patch("modules.infra.airtable_repository.log_api_call"):
            repo = AirtableRepository()
            result = repo.get_active_post_status_for_account("IDN-000036")

        assert result == "uploading"
        assert mock_get.call_count == 1  # ready 요청은 하지 않음
        formula = mock_get.call_args.kwargs["params"]["filterByFormula"]
        assert "post_status}='uploading'" in formula
        assert "ready" not in formula  # 첫 요청은 uploading 전용

    def test_uploading_absent_then_ready_request_sent(self, monkeypatch):
        from unittest.mock import MagicMock, patch
        from modules.infra.airtable_repository import AirtableRepository

        empty_resp = MagicMock()
        empty_resp.raise_for_status.return_value = None
        empty_resp.json.return_value = {"records": []}
        ready_resp = MagicMock()
        ready_resp.raise_for_status.return_value = None
        ready_resp.json.return_value = {"records": [{"fields": {"post_status": "ready"}}]}

        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=[empty_resp, ready_resp],
        ) as mock_get, patch("modules.infra.airtable_repository.log_api_call"):
            repo = AirtableRepository()
            result = repo.get_active_post_status_for_account("IDN-000036")

        assert result == "ready"
        assert mock_get.call_count == 2
        first_formula = mock_get.call_args_list[0].kwargs["params"]["filterByFormula"]
        second_formula = mock_get.call_args_list[1].kwargs["params"]["filterByFormula"]
        assert "post_status}='uploading'" in first_formula
        assert "post_status}='ready'" in second_formula

    def test_neither_uploading_nor_ready_returns_empty_string(self, monkeypatch):
        from unittest.mock import MagicMock, patch
        from modules.infra.airtable_repository import AirtableRepository

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"records": []}
        with patch("modules.infra.airtable_repository.requests.get", return_value=resp) as mock_get, \
             patch("modules.infra.airtable_repository.log_api_call"):
            repo = AirtableRepository()
            result = repo.get_active_post_status_for_account("IDN-000036")

        assert result == ""
        assert mock_get.call_count == 2  # uploading 조회 후 ready 조회까지 둘 다 빈 결과

    def test_http_error_propagates_fail_closed(self, monkeypatch):
        from unittest.mock import patch
        import requests as requests_module
        from modules.infra.airtable_repository import AirtableRepository
        from modules.infra.repository_interface import RepositoryUnavailableError

        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=requests_module.ConnectionError("network down"),
        ):
            repo = AirtableRepository()
            with pytest.raises(RepositoryUnavailableError):
                repo.get_active_post_status_for_account("IDN-000036")
