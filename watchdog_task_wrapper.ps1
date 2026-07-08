$root = "C:\SNS_24AutoProject_260511"
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$logPath = Join-Path $logDir "watchdog_wrapper.log"
$stdoutPath = Join-Path $logDir "watchdog_wrapper_stdout.log"
$stderrPath = Join-Path $logDir "watchdog_wrapper_stderr.log"
$psExe = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
$watchdog = Join-Path $root "watchdog.ps1"

$startTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "[$startTime] WRAPPER START"
Add-Content -Path $logPath -Value "[$startTime] PID=$PID"
Add-Content -Path $logPath -Value "[$startTime] User=$env:USERDOMAIN\$env:USERNAME"
Add-Content -Path $logPath -Value "[$startTime] PWD=$(Get-Location)"
Add-Content -Path $logPath -Value "[$startTime] NOTE: watchdog.ps1 is a long-running loop. If WRAPPER END is absent, it may mean watchdog is still running."

try {
    Set-Location $root
    & $psExe -NoProfile -ExecutionPolicy Bypass -File $watchdog 1> $stdoutPath 2> $stderrPath
    $exitCode = $LASTEXITCODE
} catch {
    $exitCode = -1
    Add-Content -Path $logPath -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] EXCEPTION: $($_.Exception.Message)"
}

$endTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "[$endTime] WRAPPER END — ExitCode=$exitCode"