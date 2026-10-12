"""261012 P4 — watchdog.ps1 Test-SchedulerHeartbeat 함수만 AST로 추출해 임시 로그로 검증.
watchdog 서비스·루프 실행 없음, 실제 logs/ 미사용. Windows PowerShell 필요.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PS = shutil.which("powershell") or shutil.which("powershell.exe")

pytestmark = pytest.mark.skipif(PS is None, reason="Windows PowerShell 없음")

_HARNESS = r"""
$ErrorActionPreference = 'Stop'
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$null, [ref]$null)
$fn = $ast.FindAll({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-SchedulerHeartbeat' }}, $true) | Select-Object -First 1
. ([scriptblock]::Create($fn.Extent.Text))
$HEARTBEAT_STALE_MIN = 7
$APP_LOG_PATH = Join-Path '{tmp}' 'app.log'
$fresh = (Get-Date).AddMinutes(-1).ToString('yyyy-MM-dd HH:mm:ss')
$stale = (Get-Date).AddMinutes(-30).ToString('yyyy-MM-dd HH:mm:ss')
{setup}
Test-SchedulerHeartbeat -tag '[SchedulerHeartbeat][main]'
"""


def _run(tmp_path, setup):
    script = _HARNESS.format(script=str(ROOT / "watchdog.ps1"), tmp=str(tmp_path), setup=setup)
    out = subprocess.run(
        [PS, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip().splitlines()[-1]


def _line(var):
    return f'"${var} [INFO] __main__ - [SchedulerHeartbeat][main] alive"'


def test_fresh_heartbeat_in_app_log_true(tmp_path):
    assert _run(tmp_path, f"Set-Content -LiteralPath $APP_LOG_PATH -Value {_line('fresh')}") == "True"


def test_rotated_heartbeat_only_in_dot1_true(tmp_path):
    setup = (
        "Set-Content -LiteralPath $APP_LOG_PATH -Value 'x [INFO] other - no tag yet'\n"
        f"Set-Content -LiteralPath \"$APP_LOG_PATH.1\" -Value {_line('fresh')}"
    )
    assert _run(tmp_path, setup) == "True"


def test_both_stale_false(tmp_path):
    setup = (
        f"Set-Content -LiteralPath $APP_LOG_PATH -Value {_line('stale')}\n"
        f"Set-Content -LiteralPath \"$APP_LOG_PATH.1\" -Value {_line('stale')}"
    )
    assert _run(tmp_path, setup) == "False"


def test_stale_in_app_log_does_not_fall_back_to_dot1(tmp_path):
    # app.log 에 태그가 있으면(오래됐어도) 그 값으로 판정 — .1 의 최신값으로 덮지 않는다.
    setup = (
        f"Set-Content -LiteralPath $APP_LOG_PATH -Value {_line('stale')}\n"
        f"Set-Content -LiteralPath \"$APP_LOG_PATH.1\" -Value {_line('fresh')}"
    )
    assert _run(tmp_path, setup) == "False"


def test_no_files_false(tmp_path):
    assert _run(tmp_path, "") == "False"
