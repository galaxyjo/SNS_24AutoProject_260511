"""tests/test_aijomoojin_slot_upload_job.py — 260804 Track B 6G 정식 운영모드
(APScheduler 3슬롯 방식, 회장 결정: publish_ledger.py는 DEFER, 최소 Delta로
기존 자산만 REUSE) 검증.

260804 Codex 1차 리뷰(CHANGES REQUIRED) 반영 후 재검증:
  - P0: `_job_insta_upload()`가 Flag ON이어도 IDN-000036을 5분마다 계속
    처리하던 문제 — 계정 전용 skip 조건 추가로 수정, 여기서 회귀 테스트.
  - P1: `fetch_pending_posts(limit=50)` 뒤 클라이언트 필터 방식이 다른 계정
    레코드에 밀려 슬롯을 놓칠 수 있던 문제 — `fetch_pending_posts_for_account()`
    (신규, 서버측 계정 한정 쿼리)로 전환, 여기서 검증.
  - P2: misfire_grace_time 300→60초로 축소 + "Catch-up 0건"이 아니라 "60초
    초과만 Skip"으로 표현 정정. Feature Flag를 함수 실행 시점에도 재확인 —
    단, 이는 방어적 일관성 확인일 뿐 "재시작 없는 즉시 원복" 수단이
    아니다(아래 260804 Codex 2차 리뷰 P1 참조, 여기서 검증).
  - P1(원자성/다중 Job): Publish Ledger 도입은 회장이 명시적으로 DEFER했다
    (별도 메모: project_aijomoojin_ledger_deferred_260804.md) — 대신 P0 수정으로
    old/new Job이 애초에 같은 레코드를 두고 경쟁하지 않도록 구조적으로
    분리했다. 다중 launcher 프로세스 동시기동 시나리오는 `claim_post_for_upload()`
    의 기존 "non-atomic, single-worker only" 한계와 동일한 시스템 전체
    선행 위험이며 이번 Delta가 새로 만든 위험이 아니다(다른 계정도 동일).

260804 Codex 2차 리뷰(CHANGES REQUIRED) 반영:
  - P1: "`.env` 수정만으로 재시작 없이 즉시 원복" 서술이 부정확했음(python-dotenv
    `load_dotenv(override=True)`는 import 시점 1회만 실행, 이후 `os.getenv()`는
    프로세스에 고정된 값만 읽는다) — 서술·주석·테스트명을 정정하고, 실제
    메커니즘(재시작 필요)을 직접 증명하는 테스트를 추가(`TestDotenvDoesNotReloadAfterImport`).
  - P2: `fetch_pending_posts_for_account()`에 계정코드 정규식 검증·양수 limit
    검증·명시적 `scheduled_upload_at asc` 정렬을 추가하고, 실제 `requests.get()`
    파라미터를 직접 검증하는 Repository 계약 테스트를 추가
    (`TestFetchPendingPostsForAccountRepositoryContract`).

회장 승인 안전조건 4개 축 + Codex 요구 5개 테스트 전부 포함:
  1. 계정 격리 — `_job_insta_upload()`는 Flag ON이면 IDN-000036을 claim조차
     안 한다(P0 회귀 테스트). 신규 Job은 계정 전용 쿼리라 다른 계정 후보와
     경쟁하지 않는다.
  2. 슬롯당 1건 — 호출당 후보 1건만 시도.
  3. max_instances=1 / coalesce=False / misfire_grace_time=60(축소) — 등록
     파라미터 직접 확인.
  4. 실패·outcome_unknown·누락 시 Catch-up 0건 — 각각 별도 테스트.

Part A: `_build_scheduler()` 등록 파라미터 검증.
Part B: `_job_aijomoojin_scheduled_post()` 단일 실행 통합.
Part C: `_job_insta_upload()` ↔ 신규 Job 계정 분리(P0 회귀) + Flag 방어적 재확인(P2).
Part D: `.env` 재로드 실제 메커니즘 증명 + `fetch_pending_posts_for_account()`
        Repository 계약 검증(260804 Codex 2차 리뷰 P1/P2).
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import modules.infra.airtable_repository  # noqa: F401,E402
import launcher.main  # noqa: F401,E402


BANGKOK = ZoneInfo("Asia/Bangkok")

AI_ACCOUNT = {
    "account_code": "IDN-000036", "api_provider": "instagram_login",
    "ig_user_id": "17841467725643424", "credential_key": "AI",
    "automation_enabled": True,
}


def _post(rid="rec1", account_code_ref="IDN-000036", ig_media_id=""):
    return {
        "post_id": rid, "image_url": "http://img", "caption": "c", "hashtag": "",
        "account_code_ref": account_code_ref, "ig_media_id": ig_media_id,
        "data_classification": "", "canary_run_id": "", "post_status": "ready",
    }


@pytest.fixture
def bypass_canary_classification(monkeypatch):
    """다른 test_*.py와 동일한 순수 테스트 격리(이 세션 환경의 runtime_boot_policy.json
    PermissionError 우회, 이번 변경과 무관)."""
    import modules.common.canary_classification as canary_classification
    monkeypatch.setattr(canary_classification, "validate_publication_candidate", lambda *a, **k: None)


@pytest.fixture
def _base_env(monkeypatch):
    # 260804 Codex 리뷰 P2 수정(함수 실행 시점 Flag 재확인)으로, _job_aijomoojin_scheduled_post()
    # 를 실제로 실행시키는 모든 테스트는 이 Flag를 켜야 한다 — 꺼진 상태를
    # 검증하는 테스트는 TestRuntimeFlagOffShortCircuit에서 별도로 다룬다.
    monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
    monkeypatch.setenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "false")
    monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
    monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "ai-real-token")


# ── Part A: _build_scheduler() 등록 파라미터 ──────────────────────────────

class TestSchedulerRegistration:
    def test_flag_off_registers_no_slot_jobs(self, monkeypatch):
        monkeypatch.delenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", raising=False)
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        job_ids = {j.id for j in sched.get_jobs()}
        assert not any(jid.startswith("aijomoojin_slot_") for jid in job_ids)

    def test_flag_on_registers_exactly_3_slot_jobs(self, monkeypatch):
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        slot_job_ids = {j.id for j in sched.get_jobs() if j.id.startswith("aijomoojin_slot_")}
        assert slot_job_ids == {"aijomoojin_slot_0600", "aijomoojin_slot_1000", "aijomoojin_slot_1700"}

    @pytest.mark.parametrize("job_id,hour", [
        ("aijomoojin_slot_0600", 6), ("aijomoojin_slot_1000", 10), ("aijomoojin_slot_1700", 17),
    ])
    def test_each_slot_has_safety_params_and_fires_at_correct_ict_hour(self, monkeypatch, job_id, hour):
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        job = next(j for j in sched.get_jobs() if j.id == job_id)

        assert job.func is launcher_main._job_aijomoojin_scheduled_post
        assert job.max_instances == 1  # 겹침 실행 방지
        assert job.coalesce is False
        # 260804 Codex 리뷰 P2 — 300초는 "Catch-up 0건"이 아니라 5분 지연 허용이었다.
        # 60초로 축소(여전히 정확한 표현은 "60초 초과만 Skip", 절대 0건은 아님).
        assert job.misfire_grace_time == 60

        just_before = datetime(2026, 8, 4, hour, 0, 0, tzinfo=BANGKOK) - timedelta(minutes=1)
        next_fire = job.trigger.get_next_fire_time(None, just_before)
        assert next_fire == datetime(2026, 8, 4, hour, 0, 0, tzinfo=BANGKOK)

    def test_other_existing_jobs_unaffected_by_flag(self, monkeypatch):
        """_job_insta_upload 등 기존 Job은 이번 Delta로 등록 방식 자체가 무변화."""
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        insta_upload_job = next(j for j in sched.get_jobs() if j.id == "insta_upload")
        assert insta_upload_job.func is launcher_main._job_insta_upload
        assert insta_upload_job.trigger.interval.total_seconds() == launcher_main.UPLOAD_POLL_MIN * 60


# ── Part B: _job_aijomoojin_scheduled_post() 단일 실행 통합 ───────────────

def _fake_repo(account_posts, get_publish_account=lambda code: AI_ACCOUNT, claim_result=True):
    """fetch_pending_posts_for_account()만 노출한다 — 신규 Job이 실수로 옛
    fetch_pending_posts(전체 계정 조회)를 다시 쓰게 되면 AttributeError로
    이 테스트들이 즉시 실패한다(회귀 방지)."""
    calls = {"claim": [], "mark_post_result": [], "fetch_pending_posts_for_account": []}

    class _FakeRepo:
        def fetch_pending_posts_for_account(self, account_code_ref, limit=10):
            calls["fetch_pending_posts_for_account"].append((account_code_ref, limit))
            return account_posts

        def get_publish_account(self, account_code):
            return get_publish_account(account_code)

        def claim_post_for_upload(self, post_id):
            calls["claim"].append(post_id)
            return claim_result

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

        def get_active_persona_by_account_code_v2(self, account_code):
            raise AssertionError("PUBLISH_TEXT_GATE_ENABLED=false 기본이라 호출되면 안 됨")

    return _FakeRepo(), calls


class TestJobAijomoojinScheduledPost:
    # ── 계정 격리(신규 Job은 애초에 계정 한정 쿼리만 사용) ──
    def test_queries_only_own_account_via_scoped_method(self, monkeypatch, bypass_canary_classification, _base_env):
        from launcher import main as launcher_main

        repo, calls = _fake_repo([_post(rid="rec_ai")])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                {"ok": True, "ig_media_id": "m1"}
            ),
        )

        launcher_main._job_aijomoojin_scheduled_post()

        assert calls["fetch_pending_posts_for_account"] == [("IDN-000036", 1)]
        assert calls["claim"] == ["rec_ai"]

    def test_other_account_volume_does_not_starve_this_account(self, monkeypatch, bypass_canary_classification, _base_env):
        """260804 Codex 리뷰 P1 — 다른 계정 50건이 있어도(여기선 서버측 필터를
        Fake로 재현) aijomoojin 후보 1건은 항상 그대로 반환된다는 계약을
        직접 증명한다(클라이언트 필터로 밀려나던 옛 방식과 대비)."""
        from launcher import main as launcher_main

        # 실제로는 Airtable filterByFormula가 계정을 서버측에서 한정하므로,
        # 다른 계정 레코드 수는 이 메서드의 반환값에 전혀 영향을 주지 않는다 —
        # Fake는 그 계약(항상 자기 계정 것만 옴)만 재현한다.
        repo, calls = _fake_repo([_post(rid="rec_ai")])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                {"ok": True, "ig_media_id": "m1"}
            ),
        )

        launcher_main._job_aijomoojin_scheduled_post()

        assert calls["claim"] == ["rec_ai"]

    def test_no_ready_aijomoojin_record_is_noop(self, monkeypatch, bypass_canary_classification, _base_env):
        from launcher import main as launcher_main

        repo, calls = _fake_repo([])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_aijomoojin_scheduled_post()

        assert calls["claim"] == []

    # ── 슬롯당 1건(호출당 후보 1건만 시도) ──
    def test_only_first_ready_candidate_is_attempted_when_multiple_exist(
        self, monkeypatch, bypass_canary_classification, _base_env
    ):
        from launcher import main as launcher_main

        posts = [_post(rid="rec1"), _post(rid="rec2")]
        repo, calls = _fake_repo(posts)
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        publish_calls = []
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                publish_calls.append(rid) or {"ok": True, "ig_media_id": "m1"}
            ),
        )

        launcher_main._job_aijomoojin_scheduled_post()

        assert calls["claim"] == ["rec1"]
        assert publish_calls == ["rec1"]  # rec2는 이번 호출에서 시도조차 안 됨

    def test_successful_publish_marks_posted(self, monkeypatch, bypass_canary_classification, _base_env):
        from launcher import main as launcher_main

        repo, calls = _fake_repo([_post()])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                {"ok": True, "ig_media_id": "m1"}
            ),
        )

        launcher_main._job_aijomoojin_scheduled_post()

        assert calls["mark_post_result"] == [("rec1", {"status": "posted", "platform_post_id": "m1", "error_code": ""})]

    # ── Kill Switch(기존 안전장치 REUSE 확인) ──
    def test_automation_disabled_blocks_before_claim(self, monkeypatch, bypass_canary_classification, _base_env):
        from launcher import main as launcher_main

        off_account = dict(AI_ACCOUNT, automation_enabled=False)
        repo, calls = _fake_repo([_post()], get_publish_account=lambda code: off_account)
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_aijomoojin_scheduled_post()

        assert calls["claim"] == []

    # ── 실패 시 Catch-up 0건(같은 호출 안 재시도 없음) ──
    def test_failed_publish_marks_failed_and_does_not_retry_within_call(
        self, monkeypatch, bypass_canary_classification, _base_env
    ):
        from launcher import main as launcher_main

        repo, calls = _fake_repo([_post()])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        publish_calls = []
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                publish_calls.append(rid) or {"ok": False, "error": "boom"}
            ),
        )

        launcher_main._job_aijomoojin_scheduled_post()

        assert publish_calls == ["rec1"]  # 정확히 1회만 시도, 같은 호출 안 재시도 없음
        assert calls["mark_post_result"] == [("rec1", {"status": "failed", "platform_post_id": "", "error_code": "boom"})]

    def test_next_slot_call_does_not_see_previously_failed_record(
        self, monkeypatch, bypass_canary_classification, _base_env
    ):
        """실제 Airtable은 mark_post_result(status=failed) 이후 그 레코드를
        post_status='ready' 조회에서 제외한다(기존 계약) — Fake Repository로
        이 계약을 재현해, 다음 슬롯 호출에서 실패건이 다시 등장하지 않음을 확인한다."""
        from launcher import main as launcher_main

        state = {"posts": [_post(rid="rec1")]}

        class _StatefulRepo:
            def fetch_pending_posts_for_account(self, account_code_ref, limit=10):
                return list(state["posts"])

            def get_publish_account(self, account_code):
                return AI_ACCOUNT

            def claim_post_for_upload(self, post_id):
                return True

            def mark_post_result(self, post_id, result):
                if result["status"] != "ready":
                    state["posts"] = [p for p in state["posts"] if p["post_id"] != post_id]

        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _StatefulRepo())
        publish_calls = []
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                publish_calls.append(rid) or {"ok": False, "error": "boom"}
            ),
        )

        launcher_main._job_aijomoojin_scheduled_post()  # 1번째 슬롯: 실패
        launcher_main._job_aijomoojin_scheduled_post()  # 2번째 슬롯: 놓친 슬롯 Catch-up 없어야 함

        assert publish_calls == ["rec1"]  # 두 번째 호출에서 추가 시도 0회

    # ── outcome_unknown 시 Catch-up 0건(260804 Codex 요구 테스트) ──
    def test_outcome_unknown_does_not_mark_result_and_no_retry_within_call(
        self, monkeypatch, bypass_canary_classification, _base_env
    ):
        from launcher import main as launcher_main

        repo, calls = _fake_repo([_post()])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        publish_calls = []
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                publish_calls.append(rid) or {"ok": False, "outcome_unknown": True, "creation_id": "c1"}
            ),
        )

        launcher_main._job_aijomoojin_scheduled_post()

        assert publish_calls == ["rec1"]  # 정확히 1회만 시도
        # 결과 불명은 Airtable에 failed/posted 어느 쪽으로도 확정 기록하지 않는다
        # (uploading 상태로 격리 — claim_post_for_upload가 이미 그렇게 마킹함, 기존 계약).
        assert calls["mark_post_result"] == []


# ── Part C: _job_insta_upload() ↔ 신규 Job 계정 분리(P0 회귀) + Flag Runtime 재확인(P2) ──

class TestOldJobAijomoojinExclusion:
    """260804 Codex 1차 리뷰 P0 — Flag ON이면 기존 5분 폴링 Job이 IDN-000036을
    더 이상 처리하지 않아야 한다(안 그러면 신규 3슬롯 Job과 동시에 같은
    레코드를 노려 슬롯 제한이 무력화되고 중복게시 위험이 생긴다)."""

    def _insta_upload_fake_repo(self, posts):
        calls = {"claim": []}

        class _FakeRepo:
            def fetch_pending_posts(self, limit=50):
                return posts

            def claim_post_for_upload(self, post_id):
                calls["claim"].append(post_id)
                return True

            def mark_post_result(self, post_id, result):
                pass

        return _FakeRepo(), calls

    def test_flag_on_old_job_skips_aijomoojin_entirely(self, monkeypatch, bypass_canary_classification):
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        # routing/기타 Flag가 뭐든 상관없이 이 skip이 그보다 먼저 걸려야 한다 —
        # 일부러 라우팅을 켜서(신규 경로가 열려 있어도) 여전히 차단되는지 확인.
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")

        from launcher import main as launcher_main

        repo, calls = self._insta_upload_fake_repo([_post(rid="rec_ai", account_code_ref="IDN-000036")])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_insta_upload()

        assert calls["claim"] == []  # old Job은 이제 이 레코드를 절대 건드리지 않는다

    def test_flag_off_old_job_still_processes_aijomoojin_as_before(self, monkeypatch, bypass_canary_classification):
        """Flag가 꺼져 있으면(기본값) 기존 동작 100% 보존 — 회귀 없음 재확인."""
        monkeypatch.delenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", raising=False)
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
        monkeypatch.setenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "false")
        monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
        monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "ai-real-token")

        from launcher import main as launcher_main

        class _FakeRepo:
            def fetch_pending_posts(self, limit=50):
                return [_post(rid="rec_ai", account_code_ref="IDN-000036")]

            def get_publish_account(self, account_code):
                return AI_ACCOUNT

            def claim_post_for_upload(self, post_id):
                calls["claim"].append(post_id)
                return True

            def mark_post_result(self, post_id, result):
                pass

        calls = {"claim": []}
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo())
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                {"ok": True, "ig_media_id": "m1"}
            ),
        )

        launcher_main._job_insta_upload()

        assert calls["claim"] == ["rec_ai"]  # Flag off면 옛 경로 그대로 살아있음

    def test_other_account_unaffected_by_new_skip_condition(self, monkeypatch, bypass_canary_classification):
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
        monkeypatch.setenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "false")
        monkeypatch.setenv("YUNA_INSTA_IG_USER_ID", "17841476202821375")
        monkeypatch.setenv("YUNA_INSTA_ACCESS_TOKEN", "yuna-real-token")

        from launcher import main as launcher_main

        other_account = {
            "account_code": "IDN-000041", "api_provider": "facebook_login",
            "ig_user_id": "17841476202821375", "credential_key": "YUNA",
            "automation_enabled": True,
        }

        class _FakeRepo:
            def fetch_pending_posts(self, limit=50):
                return [_post(rid="rec_other", account_code_ref="IDN-000041")]

            def get_publish_account(self, account_code):
                return other_account

            def claim_post_for_upload(self, post_id):
                calls["claim"].append(post_id)
                return True

            def mark_post_result(self, post_id, result):
                pass

        calls = {"claim": []}
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo())
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                {"ok": True, "ig_media_id": "m2"}
            ),
        )

        launcher_main._job_insta_upload()

        assert calls["claim"] == ["rec_other"]  # 다른 계정은 신규 skip 조건의 영향을 받지 않음


class TestRuntimeFlagOffDefensiveConsistencyCheck:
    """260804 Codex 2차 리뷰 P1 정정 — 이 클래스는 "재시작 없이 .env만
    고치면 즉시 꺼진다"를 증명하지 않는다(그 서술 자체가 부정확했다).
    `monkeypatch.setenv()`는 프로세스 `os.environ`을 직접 조작하므로, 실제
    운영에서 `.env` 파일만 수정하는 것과 동등하지 않다 — `load_dotenv`가
    이미 import 시점에 값을 프로세스에 고정했기 때문이다(아래
    `TestDotenvDoesNotReloadAfterImport` 참조). 여기서는 대신 "프로세스
    환경값이 실제로 false인 상태(=재시작 이후)라면 함수가 Repository조차
    생성하지 않고 안전하게 스킵한다"는 방어적 일관성만 증명한다."""

    def test_process_env_false_short_circuits_before_any_repository_access(self, monkeypatch):
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "false")
        from launcher import main as launcher_main

        class _ExplodingRepo:
            def __init__(self):
                raise AssertionError("Flag off(프로세스 환경값)인데 Repository가 생성되면 안 됨")

        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", _ExplodingRepo)
        monkeypatch.setattr(launcher_main, "publish_single", lambda *a, **k: pytest.fail("호출되면 안 됨"))

        launcher_main._job_aijomoojin_scheduled_post()  # 예외 없이 조용히 반환돼야 함

    def test_flag_on_at_call_time_proceeds_normally(self, monkeypatch, bypass_canary_classification, _base_env):
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        from launcher import main as launcher_main

        repo, calls = _fake_repo([_post()])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda rid, image_url, caption, token, ig_user_id, api_host="graph.facebook.com": (
                {"ok": True, "ig_media_id": "m1"}
            ),
        )

        launcher_main._job_aijomoojin_scheduled_post()

        assert calls["claim"] == ["rec1"]  # Flag on 정상 경로도 여전히 살아있음(회귀 없음)


# ── Part D: .env 재로드 메커니즘 증명 + Repository 계약 검증 ───────────────

class TestDotenvDoesNotReloadAfterImport:
    """260804 Codex 2차 리뷰 P1 — "`.env`만 고치면 재시작 없이 반영된다"는
    주장이 이 프로젝트의 실제 메커니즘과 맞는지 직접 증명한다(추정 아님).
    `load_dotenv(path, override=True)`를 1회 호출한 뒤 파일을 디스크에서
    수정해도, 재호출 없이는 `os.getenv()`가 새 값을 보지 못함을 확인한다 —
    이것이 `launcher/main.py`가 import 시점에 하는 것과 동일한 패턴이다."""

    def test_editing_env_file_after_load_does_not_change_os_getenv(self, tmp_path, monkeypatch):
        from dotenv import load_dotenv

        env_path = tmp_path / ".env"
        env_path.write_text("PROBE_FLAG=true\n", encoding="utf-8")
        monkeypatch.delenv("PROBE_FLAG", raising=False)

        load_dotenv(str(env_path), override=True)
        assert os.getenv("PROBE_FLAG") == "true"

        # 파일만 false로 수정 — 프로세스 재로드는 하지 않음(재시작 안 한 상태 재현)
        env_path.write_text("PROBE_FLAG=false\n", encoding="utf-8")

        assert os.getenv("PROBE_FLAG") == "true"  # 여전히 예전 값 — 파일 수정만으론 반영 안 됨

        load_dotenv(str(env_path), override=True)  # 재시작에 해당하는 재로드를 해야만
        assert os.getenv("PROBE_FLAG") == "false"  # 비로소 반영됨


class TestFetchPendingPostsForAccountRepositoryContract:
    """260804 Codex 2차 리뷰 P2 — Fake Repository 기반 통합 테스트 외에,
    실제 `requests.get()` 파라미터(filterByFormula/sort/maxRecords)와
    입력검증(계정코드 형식·limit)을 직접 확인한다."""

    def test_sends_account_scoped_formula_with_explicit_sort(self, monkeypatch):
        from unittest.mock import MagicMock, patch
        from modules.infra.airtable_repository import AirtableRepository

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"records": []}
        with patch("modules.infra.airtable_repository.requests.get", return_value=resp) as mock_get, \
             patch("modules.infra.airtable_repository.log_api_call"):
            repo = AirtableRepository()
            repo.fetch_pending_posts_for_account("IDN-000036", limit=1)

        params = mock_get.call_args.kwargs["params"]
        assert "{account_code_ref}='IDN-000036'" in params["filterByFormula"]
        assert params["sort[0][field]"] == "scheduled_upload_at"
        assert params["sort[0][direction]"] == "asc"
        assert params["maxRecords"] == 1

    def test_malformed_account_code_returns_empty_without_http_call(self, monkeypatch):
        from unittest.mock import patch
        from modules.infra.airtable_repository import AirtableRepository

        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            repo = AirtableRepository()
            result = repo.fetch_pending_posts_for_account("IDN-000036, IDN-000037", limit=1)

        assert result == []
        mock_get.assert_not_called()

    def test_blank_account_code_returns_empty_without_http_call(self, monkeypatch):
        from unittest.mock import patch
        from modules.infra.airtable_repository import AirtableRepository

        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            repo = AirtableRepository()
            assert repo.fetch_pending_posts_for_account("", limit=1) == []
            assert repo.fetch_pending_posts_for_account(None, limit=1) == []

        mock_get.assert_not_called()

    @pytest.mark.parametrize("bad_limit", [0, -1, -50, 101, 1000, 1_000_000])
    def test_out_of_range_limit_returns_empty_without_http_call(self, monkeypatch, bad_limit):
        """260804 Codex 3차 리뷰 P2 — 0 이하뿐 아니라 상한(100) 초과도 차단한다.
        이 메서드는 페이지네이션을 처리하지 않으므로 큰 limit을 그대로
        Airtable에 전달하지 않는다."""
        from unittest.mock import patch
        from modules.infra.airtable_repository import AirtableRepository

        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            repo = AirtableRepository()
            result = repo.fetch_pending_posts_for_account("IDN-000036", limit=bad_limit)

        assert result == []
        mock_get.assert_not_called()

    @pytest.mark.parametrize("bad_limit", [None, "5", "abc", 5.0, 1.0, True, False, [], {}])
    def test_non_int_limit_returns_empty_without_http_call(self, monkeypatch, bad_limit):
        """260804 Codex 3차 리뷰 P2 — limit은 순수 int만 허용한다. None/문자열/실수는
        비교 과정에서 TypeError를 일으키거나 잘못된 값으로 새어나가면 안 되고,
        bool은 int의 서브클래스라 별도로 명시 차단한다(True==1, False==0으로
        암묵 통과하는 것을 방지)."""
        from unittest.mock import patch
        from modules.infra.airtable_repository import AirtableRepository

        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            repo = AirtableRepository()
            result = repo.fetch_pending_posts_for_account("IDN-000036", limit=bad_limit)

        assert result == []
        mock_get.assert_not_called()

    @pytest.mark.parametrize("good_limit", [1, 50, 100])
    def test_boundary_valid_limits_proceed_to_http_call(self, monkeypatch, good_limit):
        """상한 도입이 정상 범위(1~100)까지 과도하게 막지 않는지 경계값으로 확인."""
        from unittest.mock import MagicMock, patch
        from modules.infra.airtable_repository import AirtableRepository

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"records": []}
        with patch("modules.infra.airtable_repository.requests.get", return_value=resp) as mock_get, \
             patch("modules.infra.airtable_repository.log_api_call"):
            repo = AirtableRepository()
            result = repo.fetch_pending_posts_for_account("IDN-000036", limit=good_limit)

        assert result == []  # Mock 응답이 빈 records이므로 결과는 빈 목록(HTTP는 호출됨)
        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs["params"]["maxRecords"] == good_limit


# ── Part E: 게시 직전 Gate의 Gemini Credential 격리(260805 Codex 리뷰 P0) ──

def _fake_repo_with_persona(account_posts, persona=None, get_publish_account=lambda code: AI_ACCOUNT, claim_result=True):
    """PUBLISH_TEXT_GATE_ENABLED=true 경로 전용 — get_active_persona_by_account_code_v2()가
    실제로 값을 반환한다(_fake_repo()는 이 경로가 호출되면 즉시 실패하도록 만들어져
    있어 Gate 활성 테스트에는 쓸 수 없다)."""
    calls = {"claim": [], "mark_post_result": [], "fetch_pending_posts_for_account": []}
    persona = persona if persona is not None else {"persona_code": "PER-002", "language": "ko"}

    class _FakeRepo:
        def fetch_pending_posts_for_account(self, account_code_ref, limit=10):
            calls["fetch_pending_posts_for_account"].append((account_code_ref, limit))
            return account_posts

        def get_publish_account(self, account_code):
            return get_publish_account(account_code)

        def claim_post_for_upload(self, post_id):
            calls["claim"].append(post_id)
            return claim_result

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

        def get_active_persona_by_account_code_v2(self, account_code):
            return persona

    return _FakeRepo(), calls


class TestPublishGateCredentialIsolation:
    """260805 Codex 리뷰(P0) — PUBLISH_TEXT_GATE_ENABLED=true일 때 게시 직전
    resolve_publish_gate() 호출이 aijomoojin 전용 Gemini Credential
    (research_to_topic_adapter의 것)로 격리되는지, Key가 없으면 이번 슬롯만
    Fail-closed로 스킵하는지 확인한다."""

    def _gate_env(self, monkeypatch):
        monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
        monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
        monkeypatch.setenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "false")
        monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
        monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "ai-real-token")

    def test_gate_enabled_passes_isolated_client_and_throttle(
        self, monkeypatch, bypass_canary_classification
    ):
        self._gate_env(monkeypatch)
        from launcher import main as launcher_main
        import modules.sns.research_to_topic_adapter as research_adapter

        sentinel_client = object()
        monkeypatch.setattr(research_adapter, "_get_client", lambda: sentinel_client)

        repo, calls = _fake_repo_with_persona([_post()])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda *a, **k: pytest.fail("Gate가 차단했는데 게시가 시도되면 안 됨"),
        )

        captured = {}

        def _spy_gate(caption, account_code_ref, *, source_url="", persona_code="",
                      required_language="", safety_client=None, safety_throttle=None,
                      safety_model=None):
            captured["safety_client"] = safety_client
            captured["safety_throttle"] = safety_throttle
            captured["safety_model"] = safety_model
            return False, "AI_CONTENT_SAFETY_BLOCKED:TEST"

        monkeypatch.setattr(launcher_main, "resolve_publish_gate", _spy_gate)

        launcher_main._job_aijomoojin_scheduled_post()

        assert captured["safety_client"] is sentinel_client  # 전역 caption_generator 것이 아님
        assert captured["safety_throttle"] is research_adapter._throttle
        # 260805 회장 지시 — aijomoojin 전용 고정 모델도 함께 전달됨
        assert captured["safety_model"] == research_adapter.RESEARCH_MODEL == "gemini-3.5-flash-lite"
        assert calls["claim"] == []  # claim은 Gate 통과 이후 단계라, 차단되면 시도조차 안 됨

    def test_missing_isolated_key_skips_slot_without_calling_gate(
        self, monkeypatch, bypass_canary_classification
    ):
        """AIJOMOOJIN_GEMINI_API_KEY가 없으면 전역 Key로 대체(Fallback)하지
        않고, 이번 슬롯만 Fail-closed로 스킵한다 — resolve_publish_gate()도
        publish_single()도 호출되지 않는다."""
        self._gate_env(monkeypatch)
        from launcher import main as launcher_main
        import modules.sns.research_to_topic_adapter as research_adapter

        monkeypatch.setattr(research_adapter, "_client", None)
        monkeypatch.delenv("AIJOMOOJIN_GEMINI_API_KEY", raising=False)

        repo, calls = _fake_repo_with_persona([_post()])
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: repo)
        monkeypatch.setattr(
            launcher_main, "resolve_publish_gate",
            lambda *a, **k: pytest.fail("호출되면 안 됨 — Key 없으면 Gate 도달 전에 스킵"),
        )
        monkeypatch.setattr(
            launcher_main, "publish_single",
            lambda *a, **k: pytest.fail("호출되면 안 됨"),
        )

        launcher_main._job_aijomoojin_scheduled_post()

        assert calls["mark_post_result"] == []  # 확정 결과 없이 조용히 스킵(다음 슬롯에서 재시도 가능)
