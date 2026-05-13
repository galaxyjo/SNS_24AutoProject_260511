# watchdog.ps1 — Flask / Streamlit / ngrok / insta_scheduler 프로세스 감시 및 자동 재시작
# 사용법: .\watchdog.ps1
# run_scheduler.ps1로 서버를 먼저 띄운 뒤 이 스크립트를 별도 터미널에서 실행.

Set-Location $PSScriptRoot

$python      = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$streamlit   = Join-Path $PSScriptRoot ".venv\Scripts\streamlit.exe"
$logDir      = Join-Path $PSScriptRoot "logs"
$watchdogLog = Join-Path $logDir "watchdog.log"

$POLL_SEC       = 30   # 감시 주기 (초)
$RESTART_WAIT   = 5    # 재시작 후 대기 (초)
$HTTP_TIMEOUT   = 5    # HTTP 헬스체크 타임아웃 (초)

$FLASK_URL      = "http://localhost:5000/health"
$STREAMLIT_URL  = "http://localhost:8501"
$NGROK_URL      = "danuta-overdramatic-whirly.ngrok-free.dev"
$NGROK_ARGS     = "http --url=$NGROK_URL 5000"

function Write-Log {
    param([string]$msg)
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Write-Host $line
    Add-Content -Path $watchdogLog -Value $line -Encoding UTF8
}

function Send-SlackAlert {
    param([string]$message, [string]$level = "warning")
    $webhookUrl = $env:SLACK_WEBHOOK_URL
    if (-not $webhookUrl) { return }
    $emoji = if ($level -eq "error") { ":red_circle:" } elseif ($level -eq "success") { ":white_check_mark:" } else { ":warning:" }
    $color = if ($level -eq "error") { "#cc0000" } elseif ($level -eq "success") { "#2eb886" } else { "#ffcc00" }
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss KST"
    $body = @{
        attachments = @(@{
            color  = $color
            title  = "$emoji [Watchdog] $message"
            footer = "SNS_24AutoProject | $ts"
        })
    } | ConvertTo-Json -Depth 4
    try {
        Invoke-RestMethod -Uri $webhookUrl -Method Post -Body $body -ContentType "application/json" | Out-Null
    } catch {}
}

function Test-Http {
    param([string]$url)
    try {
        $null = Invoke-WebRequest -Uri $url -TimeoutSec $HTTP_TIMEOUT -UseBasicParsing -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Start-Flask {
    Start-Process -FilePath $python -ArgumentList "-m modules.dm.dm_receiver" `
        -RedirectStandardOutput "$logDir\webhook_stdout.log" `
        -RedirectStandardError  "$logDir\webhook_stderr.log" `
        -WindowStyle Hidden
    Start-Sleep -Seconds $RESTART_WAIT
}

function Start-Streamlit {
    Start-Process -FilePath $streamlit -ArgumentList "run dashboard.py --server.port 8501" `
        -RedirectStandardOutput "$logDir\dashboard.log" `
        -RedirectStandardError  "$logDir\dashboard_err.log" `
        -WindowStyle Hidden
    Start-Sleep -Seconds $RESTART_WAIT
}

function Start-Ngrok {
    Start-Process -FilePath "ngrok" -ArgumentList $NGROK_ARGS -WindowStyle Hidden
    Start-Sleep -Seconds $RESTART_WAIT
}

function Test-Launcher {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
    return ($procs | Where-Object { $_.CommandLine -like "*launcher*main.py*" -or $_.CommandLine -like "*launcher\main*" }) -ne $null
}

function Start-Launcher {
    Start-Process -FilePath $python -ArgumentList "launcher\main.py" `
        -RedirectStandardOutput "$logDir\scheduler.log" `
        -RedirectStandardError  "$logDir\scheduler_err.log" `
        -WindowStyle Hidden
    Start-Sleep -Seconds $RESTART_WAIT
}

Write-Log "===== watchdog 시작 (주기: ${POLL_SEC}초) ====="

while ($true) {

    # --- Flask 감시 ---
    if (-not (Test-Http $FLASK_URL)) {
        Write-Log "[WARN] Flask 응답 없음 — 재시작 시도"
        Send-SlackAlert "Flask 응답 없음 — 재시작 시도" "warning"
        Start-Flask
        if (Test-Http $FLASK_URL) {
            Write-Log "[OK]   Flask 재시작 성공"
            Send-SlackAlert "Flask 재시작 성공" "success"
        } else {
            Write-Log "[ERROR] Flask 재시작 후에도 응답 없음 — webhook_stderr.log 확인 필요"
            Send-SlackAlert "Flask 재시작 실패 — webhook_stderr.log 확인 필요" "error"
        }
    }

    # --- Streamlit 감시 ---
    if (-not (Test-Http $STREAMLIT_URL)) {
        Write-Log "[WARN] Streamlit 응답 없음 — 재시작 시도"
        Send-SlackAlert "Streamlit 응답 없음 — 재시작 시도" "warning"
        Start-Streamlit
        if (Test-Http $STREAMLIT_URL) {
            Write-Log "[OK]   Streamlit 재시작 성공"
            Send-SlackAlert "Streamlit 재시작 성공" "success"
        } else {
            Write-Log "[ERROR] Streamlit 재시작 후에도 응답 없음 — dashboard_err.log 확인 필요"
            Send-SlackAlert "Streamlit 재시작 실패 — dashboard_err.log 확인 필요" "error"
        }
    }

    # --- ngrok 감시 (프로세스 존재 여부) ---
    if (-not (Get-Process -Name ngrok -ErrorAction SilentlyContinue)) {
        Write-Log "[WARN] ngrok 프로세스 없음 — 재시작 시도"
        Send-SlackAlert "ngrok 프로세스 없음 — 재시작 시도" "warning"
        Start-Ngrok
        if (Get-Process -Name ngrok -ErrorAction SilentlyContinue) {
            Write-Log "[OK]   ngrok 재시작 성공"
            Send-SlackAlert "ngrok 재시작 성공" "success"
        } else {
            Write-Log "[ERROR] ngrok 재시작 실패 — ngrok PATH 확인 필요"
            Send-SlackAlert "ngrok 재시작 실패 — ngrok PATH 확인 필요" "error"
        }
    }

    # --- launcher/main.py 감시 (커맨드라인 검사) ---
    if (-not (Test-Launcher)) {
        Write-Log "[WARN] launcher/main.py 프로세스 없음 — 재시작 시도"
        Send-SlackAlert "launcher/main.py 프로세스 없음 — 재시작 시도" "warning"
        Start-Launcher
        if (Test-Launcher) {
            Write-Log "[OK]   launcher/main.py 재시작 성공"
            Send-SlackAlert "launcher/main.py 재시작 성공" "success"
        } else {
            Write-Log "[ERROR] launcher/main.py 재시작 실패 — scheduler_err.log 확인 필요"
            Send-SlackAlert "launcher/main.py 재시작 실패 — scheduler_err.log 확인 필요" "error"
        }
    }

    Start-Sleep -Seconds $POLL_SEC
}
