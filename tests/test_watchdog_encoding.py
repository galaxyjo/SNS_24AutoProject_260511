import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WATCHDOG = ROOT / "watchdog.ps1"
UTF8_BOM = b"\xef\xbb\xbf"


def test_watchdog_has_utf8_bom_for_windows_powershell_51():
    assert WATCHDOG.read_bytes().startswith(UTF8_BOM), (
        "watchdog.ps1 must keep its UTF-8 BOM so Windows PowerShell 5.1 "
        "does not misparse Korean text after a cold start"
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 regression check")
def test_watchdog_parses_in_windows_powershell():
    env = os.environ.copy()
    env["SNS_WATCHDOG_TEST_PATH"] = str(WATCHDOG)
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:SNS_WATCHDOG_TEST_PATH,[ref]$tokens,[ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { "
        "$errors | ForEach-Object { [Console]::Error.WriteLine($_.Message) }; "
        "exit 1 }"
    )

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
