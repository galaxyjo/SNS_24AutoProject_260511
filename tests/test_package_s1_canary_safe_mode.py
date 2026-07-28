"""8단계 Safety Package S1 — Runtime 자동 Side Effect 차단 테스트."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from modules.common.canary_safe_mode import (
    CanarySafeModeState,
    CanarySafeModeError,
    get_canary_safe_mode_state,
)


_NOW = datetime(2026, 7, 28, 4, 30, tzinfo=timezone.utc)


def _enable_safe_mode(monkeypatch):
    monkeypatch.setenv("CANARY_SAFE_MODE", "true")
    monkeypatch.setenv("CANARY_RUN_ID", "canary-260728-s1")
    monkeypatch.setenv("CANARY_EXPIRES_AT", "2099-07-28T05:00:00Z")


class TestSafeModeConfiguration:
    @pytest.mark.parametrize("value", ["", "false", "FALSE"])
    def test_disabled_values_keep_normal_runtime(self, monkeypatch, value):
        monkeypatch.setenv("CANARY_SAFE_MODE", value)
        assert get_canary_safe_mode_state(now=_NOW).enabled is False

    def test_valid_context_enables_safe_mode(self, monkeypatch):
        _enable_safe_mode(monkeypatch)
        state = get_canary_safe_mode_state(now=_NOW)
        assert state.enabled is True
        assert state.run_id == "canary-260728-s1"
        assert state.expires_at is not None

    @pytest.mark.parametrize(
        ("mode", "run_id", "expires_at"),
        [
            ("invalid", "canary-260728-s1", "2099-07-28T05:00:00Z"),
            ("true", "", "2099-07-28T05:00:00Z"),
            ("true", "bad run id", "2099-07-28T05:00:00Z"),
            ("true", "canary-260728-s1", ""),
            ("true", "canary-260728-s1", "not-a-time"),
            ("true", "canary-260728-s1", "2026-07-28T04:30:00Z"),
        ],
    )
    def test_invalid_or_expired_context_fails_before_start(
        self, monkeypatch, mode, run_id, expires_at
    ):
        monkeypatch.setenv("CANARY_SAFE_MODE", mode)
        monkeypatch.setenv("CANARY_RUN_ID", run_id)
        monkeypatch.setenv("CANARY_EXPIRES_AT", expires_at)
        with pytest.raises(CanarySafeModeError):
            get_canary_safe_mode_state(now=_NOW)


class TestLauncherIsolation:
    def test_safe_mode_scheduler_contains_zero_jobs(self):
        from launcher import main as launcher_main

        scheduler = launcher_main._build_scheduler(canary_safe_mode=True)
        assert scheduler.get_jobs() == []

    def test_safe_mode_starts_no_retry_or_scheduler(self, monkeypatch):
        from launcher import main as launcher_main

        scheduler = MagicMock()
        scheduler.running = False
        scheduler.get_jobs.return_value = []
        monkeypatch.setattr(
            launcher_main,
            "_build_scheduler",
            lambda canary_safe_mode=False: scheduler,
        )
        get_retry_queue = MagicMock(side_effect=AssertionError("RetryQueue 시작 금지"))
        monkeypatch.setattr(launcher_main, "get_retry_queue", get_retry_queue)
        register_retry = MagicMock(side_effect=AssertionError("Retry handler 등록 금지"))
        monkeypatch.setattr(
            launcher_main,
            "_register_comment_retry_handlers",
            register_retry,
        )

        rq, returned_scheduler = launcher_main._start_background_services(True)

        assert rq is None
        assert returned_scheduler is scheduler
        get_retry_queue.assert_not_called()
        register_retry.assert_not_called()
        scheduler.start.assert_not_called()

    def test_invalid_startup_context_prevents_all_background_start(
        self, monkeypatch
    ):
        from launcher import main as launcher_main

        get_state = MagicMock(side_effect=CanarySafeModeError("invalid"))
        start_services = MagicMock()
        monkeypatch.setattr(
            launcher_main,
            "get_canary_safe_mode_state",
            get_state,
        )
        monkeypatch.setattr(
            launcher_main,
            "_start_background_services",
            start_services,
        )

        with pytest.raises(CanarySafeModeError):
            launcher_main.main()

        get_state.assert_called_once_with(
            require_boot_policy=True,
            activate_boot_policy=True,
        )
        start_services.assert_not_called()

    def test_normal_scheduler_contract_is_unchanged(self):
        from launcher import main as launcher_main

        scheduler = launcher_main._build_scheduler()
        assert {job.id for job in scheduler.get_jobs()} == {
            "fb_crawl",
            "insta_upload",
            "kpi_snapshot",
            "engagement_update",
            "dome_crawl",
            "dome_export",
            "comment_dead_monitor",
        }


class TestRunEngineIsolation:
    def test_safe_mode_constructs_zero_tasks_jobs_and_retry_queue(
        self, monkeypatch
    ):
        from core import run_engine

        _enable_safe_mode(monkeypatch)
        state = get_canary_safe_mode_state(now=_NOW)
        get_state = MagicMock(return_value=state)
        monkeypatch.setattr(
            run_engine,
            "get_canary_safe_mode_state",
            get_state,
        )
        get_retry_queue = MagicMock(
            side_effect=AssertionError("RetryQueue 생성 금지")
        )
        register_retry = MagicMock(
            side_effect=AssertionError("Retry handler 등록 금지")
        )
        monkeypatch.setattr(run_engine, "get_retry_queue", get_retry_queue)
        monkeypatch.setattr(
            run_engine,
            "_register_comment_retry_handlers",
            register_retry,
        )

        engine = run_engine.RunEngine()

        assert engine._rq is None
        assert engine.router.registered() == []
        assert engine.scheduler.get_jobs() == []
        get_retry_queue.assert_not_called()
        register_retry.assert_not_called()

        scheduler_start = MagicMock()
        monkeypatch.setattr(engine.scheduler, "start", scheduler_start)
        engine.start()
        scheduler_start.assert_not_called()
        get_state.assert_called_once_with(
            require_boot_policy=True,
            activate_boot_policy=True,
        )

    def test_invalid_context_fails_before_runtime_objects(self, monkeypatch):
        from core import run_engine

        get_state = MagicMock(side_effect=CanarySafeModeError("invalid"))
        task_router = MagicMock()
        scheduler = MagicMock()
        retry_queue = MagicMock()
        monkeypatch.setattr(
            run_engine,
            "get_canary_safe_mode_state",
            get_state,
        )
        monkeypatch.setattr(run_engine, "TaskRouter", task_router)
        monkeypatch.setattr(run_engine, "BlockingScheduler", scheduler)
        monkeypatch.setattr(run_engine, "get_retry_queue", retry_queue)

        with pytest.raises(CanarySafeModeError):
            run_engine.RunEngine()

        get_state.assert_called_once_with(
            require_boot_policy=True,
            activate_boot_policy=True,
        )
        task_router.assert_not_called()
        scheduler.assert_not_called()
        retry_queue.assert_not_called()

    def test_normal_runtime_keeps_all_registered_jobs(self, monkeypatch):
        from core import run_engine

        get_state = MagicMock(return_value=CanarySafeModeState(enabled=False))
        monkeypatch.setattr(
            run_engine,
            "get_canary_safe_mode_state",
            get_state,
        )
        retry_queue = MagicMock()
        monkeypatch.setattr(
            run_engine,
            "get_retry_queue",
            MagicMock(return_value=retry_queue),
        )
        monkeypatch.setattr(
            run_engine,
            "_register_comment_retry_handlers",
            MagicMock(),
        )

        engine = run_engine.RunEngine()

        assert engine._rq is retry_queue
        assert len(engine.router.registered()) == 12
        assert len(engine.scheduler.get_jobs()) == 12
        get_state.assert_called_once_with(
            require_boot_policy=True,
            activate_boot_policy=True,
        )


class TestWebhookIsolation:
    def test_safe_mode_health_survives(self, monkeypatch):
        from modules.dm import dm_receiver

        monkeypatch.setattr(dm_receiver, "CANARY_SAFE_MODE_ENABLED", True)
        response = dm_receiver.app.test_client().get("/health")
        assert response.status_code == 200
        assert response.get_json()["canary_safe_mode"] is True

    @pytest.mark.parametrize(
        "path",
        ["/webhook", "/webhook/ai-strategist", "/api/v1/ingest/domeggook/training"],
    )
    def test_safe_mode_blocks_mutating_http_before_business_logic(
        self, monkeypatch, path
    ):
        from modules.dm import dm_receiver

        monkeypatch.setattr(dm_receiver, "CANARY_SAFE_MODE_ENABLED", True)
        process = MagicMock()
        monkeypatch.setattr(dm_receiver, "_process_webhook_event", process)

        response = dm_receiver.app.test_client().post(path, json={"object": "instagram"})

        assert response.status_code == 503
        assert response.get_json()["status"] == "canary_safe_mode_blocked"
        process.assert_not_called()

    def test_safe_mode_blocks_dm_scheduler_registration(self, monkeypatch):
        from modules.dm import dm_receiver

        monkeypatch.setattr(dm_receiver, "CANARY_SAFE_MODE_ENABLED", True)
        underlying = MagicMock()
        monkeypatch.setattr(dm_receiver, "_start_followup_scheduler", underlying)

        assert dm_receiver.start_scheduler() is None
        underlying.assert_not_called()

    def test_direct_entrypoint_requires_and_activates_boot_policy(
        self, monkeypatch
    ):
        from modules.dm import dm_receiver

        state = CanarySafeModeState(
            enabled=True,
            run_id="canary-direct-001",
            source="boot_policy",
        )
        get_state = MagicMock(return_value=state)
        monkeypatch.setattr(
            dm_receiver,
            "get_canary_safe_mode_state",
            get_state,
        )

        returned = dm_receiver._activate_direct_runtime_boot_policy()

        assert returned is state
        assert dm_receiver.CANARY_SAFE_MODE_ENABLED is True
        get_state.assert_called_once_with(
            require_boot_policy=True,
            activate_boot_policy=True,
        )

    def test_normal_runtime_does_not_replace_signature_gate_with_safe_mode(
        self, monkeypatch
    ):
        from modules.dm import dm_receiver

        monkeypatch.setattr(dm_receiver, "CANARY_SAFE_MODE_ENABLED", False)
        response = dm_receiver.app.test_client().post(
            "/webhook",
            json={"object": "instagram"},
        )
        assert response.status_code == 403
