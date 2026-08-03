"""8단계 Approval W1 — 영속 Boot Policy와 Watchdog 전달 계약."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from modules.common.canary_safe_mode import (
    CanarySafeModeError,
    CanarySafeModeState,
    DEFAULT_RUNTIME_BOOT_POLICY_PATH,
    _cli,
    get_canary_safe_mode_state,
    load_runtime_boot_policy,
    safe_mode_health_fields,
)


_NOW = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)
_ROOT = Path(__file__).resolve().parents[1]


def _policy_document(**overrides):
    document = {
        "schema_version": 1,
        "mode": "safe",
        "state": "armed",
        "purpose": "approval_r",
        "context_id": "approval-r-260728-context-001",
        "run_id": "approval-r-260728-run-001",
        "expires_at": "2099-07-28T16:00:00+07:00",
    }
    document.update(overrides)
    return document


def _write_policy(tmp_path: Path, **overrides) -> Path:
    path = tmp_path / "runtime_boot_policy.json"
    path.write_text(
        json.dumps(_policy_document(**overrides), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


class TestBootPolicyContract:
    def test_default_path_is_machine_local_and_outside_repository(self):
        normalized = str(DEFAULT_RUNTIME_BOOT_POLICY_PATH).replace("/", "\\")
        assert normalized.endswith(
            r"ProgramData\SNS_24AutoProject\runtime_boot_policy.json"
        )
        assert str(_ROOT).lower() not in str(DEFAULT_RUNTIME_BOOT_POLICY_PATH).lower()

    def test_missing_required_policy_fails_closed(self, tmp_path):
        with pytest.raises(
            CanarySafeModeError,
            match="Boot Policy 파일 없음",
        ):
            get_canary_safe_mode_state(
                now=_NOW,
                require_boot_policy=True,
                policy_path=tmp_path / "missing.json",
            )

    @pytest.mark.parametrize("error_type", [PermissionError, OSError])
    def test_policy_path_probe_os_error_fails_closed(
        self, monkeypatch, error_type
    ):
        def deny_exists(_path):
            raise error_type("access denied")

        monkeypatch.setattr(Path, "exists", deny_exists)

        with pytest.raises(
            CanarySafeModeError,
            match="Boot Policy 상태 확인 실패",
        ) as exc_info:
            get_canary_safe_mode_state(now=_NOW)

        assert isinstance(exc_info.value.__cause__, error_type)

    def test_explicit_production_policy_is_the_only_normal_boot(self, tmp_path):
        path = _write_policy(
            tmp_path,
            mode="production",
            state="active",
            purpose="production",
            context_id="",
            run_id="",
            expires_at="",
        )

        state = get_canary_safe_mode_state(
            now=_NOW,
            require_boot_policy=True,
            policy_path=path,
        )

        assert state.enabled is False
        assert state.source == "boot_policy"
        assert state.policy_state == "active"

    def test_safe_policy_requires_approved_purpose_and_future_expiry(
        self, tmp_path
    ):
        path = _write_policy(tmp_path)

        policy = load_runtime_boot_policy(now=_NOW, policy_path=path)

        assert policy.mode == "safe"
        assert policy.purpose == "approval_r"
        assert policy.expires_at > _NOW

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"state": "completed"}, "state는 armed 또는 active"),
            ({"purpose": "other"}, "purpose=approval_r"),
            ({"context_id": ""}, "context_id 필수"),
            ({"run_id": ""}, "CANARY_RUN_ID 필수"),
            (
                {"expires_at": "2026-07-28T06:00:00Z"},
                "Context 만료",
            ),
            ({"mode": "unknown"}, "production 또는 safe"),
        ],
    )
    def test_invalid_completed_or_expired_policy_blocks_boot(
        self, tmp_path, overrides, message
    ):
        path = _write_policy(tmp_path, **overrides)
        with pytest.raises(CanarySafeModeError, match=message):
            load_runtime_boot_policy(now=_NOW, policy_path=path)

    def test_unknown_or_duplicate_fields_are_rejected(self, tmp_path):
        path = _write_policy(tmp_path, unexpected="value")
        with pytest.raises(CanarySafeModeError, match="허용되지 않은 필드"):
            load_runtime_boot_policy(now=_NOW, policy_path=path)

        path.write_text(
            '{"schema_version":1,"schema_version":1}',
            encoding="utf-8",
        )
        with pytest.raises(CanarySafeModeError, match="중복 필드"):
            load_runtime_boot_policy(now=_NOW, policy_path=path)

    def test_armed_policy_is_atomically_activated(self, tmp_path):
        path = _write_policy(tmp_path)

        state = get_canary_safe_mode_state(
            now=_NOW,
            require_boot_policy=True,
            activate_boot_policy=True,
            policy_path=path,
        )

        assert state.enabled is True
        assert state.policy_state == "active"
        assert json.loads(path.read_text(encoding="utf-8"))["state"] == "active"
        assert not path.with_name(f"{path.name}.lock").exists()

    def test_active_policy_can_be_reused_only_for_runtime_recovery(
        self, tmp_path
    ):
        path = _write_policy(tmp_path, state="active")

        first = get_canary_safe_mode_state(
            now=_NOW,
            require_boot_policy=True,
            activate_boot_policy=True,
            policy_path=path,
        )
        second = get_canary_safe_mode_state(
            now=_NOW + timedelta(minutes=1),
            require_boot_policy=True,
            activate_boot_policy=True,
            policy_path=path,
        )

        assert first.context_id == second.context_id
        assert second.policy_state == "active"

    def test_existing_activation_lock_fails_closed(self, tmp_path):
        path = _write_policy(tmp_path)
        path.with_name(f"{path.name}.lock").write_text("locked", encoding="utf-8")

        with pytest.raises(CanarySafeModeError, match="Lock 존재"):
            get_canary_safe_mode_state(
                now=_NOW,
                require_boot_policy=True,
                activate_boot_policy=True,
                policy_path=path,
            )


class TestBootPolicyEvidence:
    def test_health_marks_expiry_without_enabling_production(self):
        state = CanarySafeModeState(
            enabled=True,
            run_id="approval-r-260728-run-001",
            expires_at=_NOW,
            purpose="approval_r",
            context_id="approval-r-260728-context-001",
            policy_state="active",
            source="boot_policy",
        )

        payload = safe_mode_health_fields(
            state,
            now=_NOW + timedelta(seconds=1),
        )

        assert payload["canary_safe_mode"] is True
        assert payload["canary_expired"] is True
        assert payload["runtime_boot_policy_state"] == "active"

    def test_cli_masks_run_id(self, tmp_path, capsys):
        path = _write_policy(tmp_path)

        exit_code = _cli(
            [
                "--validate-boot-policy",
                "--policy-path",
                str(path),
            ]
        )
        output = capsys.readouterr()

        assert exit_code == 0
        assert "BOOT_POLICY_VALID" in output.out
        assert "app***001" in output.out
        assert "approval-r-260728-run-001" not in output.out


class TestWatchdogContract:
    def test_watchdog_validates_policy_before_start_process(self):
        text = (_ROOT / "watchdog.ps1").read_text(encoding="utf-8-sig")
        function_start = text.index("function Start-Launcher")
        function_end = text.index("function Start-N8n")
        function_text = text[function_start:function_end]

        assert (
            r'C:\ProgramData\SNS_24AutoProject\runtime_boot_policy.json'
            in text
        )
        assert "--validate-boot-policy" in text
        assert "$_.ParentProcessId -eq $PID" in text
        assert function_text.index("Test-RuntimeBootPolicy") < function_text.index(
            "Start-Process"
        )
        assert "Launcher 시작 0건" in text

    def test_watchdog_powershell_syntax(self):
        powershell = shutil.which("powershell")
        if not powershell:
            pytest.skip("Windows PowerShell unavailable")
        command = (
            "$tokens=$null; $errors=$null; "
            "[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{_ROOT / 'watchdog.ps1'}',[ref]$tokens,[ref]$errors) | Out-Null; "
            "if($errors.Count -gt 0){$errors | ForEach-Object {$_.Message}; exit 1}"
        )
        result = subprocess.run(
            [powershell, "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout
