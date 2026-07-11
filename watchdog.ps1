# watchdog.ps1 — Flask / Streamlit / ngrok / launcher/main.py / n8n 프로세스 감시 및 자동 재시작
# 사용법: .\watchdog.ps1
# run_scheduler.ps1로 서버를 먼저 띄운 뒤 이 스크립트를 별도 터미널에서 실행.

# ExecutionPolicy 자가치유 — 부팅/정책 초기화 후 자동 복구
try {
    if ((Get-ExecutionPolicy -Scope LocalMachine) -ne 'RemoteSigned') { Set-ExecutionPolicy RemoteSigned -Scope LocalMachine -Force }
} catch {
    Add-Content -Path (Join-Path $PSScriptRoot "logs\watchdog.log") -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [FATAL] ExecutionPolicy 설정 실패: $($_.Exception.Message)" -Encoding UTF8
}

Set-Location $PSScriptRoot

# .env에서 SLACK_WEBHOOK_URL 로드 (시스템 환경변수 미설정 시 폴백)
if (-not $env:SLACK_WEBHOOK_URL) {
    $envFile = Join-Path $PSScriptRoot ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | Where-Object { $_ -match '^SLACK_WEBHOOK_URL\s*=' } | ForEach-Object {
            $env:SLACK_WEBHOOK_URL = ($_ -split '=', 2)[1].Trim()
        }
    }
}

$python      = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$streamlit   = Join-Path $PSScriptRoot ".venv\Scripts\streamlit.exe"
$logDir      = Join-Path $PSScriptRoot "logs"
$watchdogLog = Join-Path $logDir "watchdog.log"

$POLL_SEC       = 30   # 감시 주기 (초)
$RESTART_WAIT   = 5    # 재시작 후 대기 (초)
$HTTP_TIMEOUT   = 5    # HTTP 헬스체크 타임아웃 (초)
$FAIL_ALERT_TH  = 3    # 연속 실패 Slack 알림 임계값

$FLASK_URL      = "http://localhost:5000/health"
$STREAMLIT_URL  = "http://localhost:8501"
$NGROK_URL      = "danuta-overdramatic-whirly.ngrok-free.dev"
$NGROK_ARGS     = "http --url=$NGROK_URL 5000"
$NGROK_EXE      = "C:\ngrok\ngrok-v3-stable-windows-amd64\ngrok.exe"
$N8N_URL        = "http://localhost:5678"

# 서비스별 연속 실패 카운터
$failCount = @{
    Flask     = 0
    Streamlit = 0
    Ngrok     = 0
    Launcher  = 0
    N8n       = 0
}

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

# 서비스 실패 처리 — 카운터 증가 및 임계값 도달 시 Slack 알림
function Register-Failure {
    param([string]$service)
    $failCount[$service]++
    if ($failCount[$service] -ge $FAIL_ALERT_TH) {
        $msg = "$service 연속 $($failCount[$service])회 실패 — 수동 점검 필요"
        Write-Log "[ALERT] $msg"
        Send-SlackAlert $msg "error"
    }
}

function Register-Success {
    param([string]$service)
    if ($failCount[$service] -gt 0) {
        Write-Log "[RECOVER] $service 복구 (이전 연속 실패: $($failCount[$service])회)"
    }
    $failCount[$service] = 0
}

# [260527] Start-Flask 주석 처리 — launcher\main.py line 300이 :5000 직접 관리, 독립 기동 불필요
# function Start-Flask {
#     Start-Process -FilePath $python -ArgumentList "-m modules.dm.dm_receiver" `
#         -RedirectStandardOutput "$logDir\webhook_stdout.log" `
#         -RedirectStandardError  "$logDir\webhook_stderr.log" `
#         -WindowStyle Hidden
#     Start-Sleep -Seconds $RESTART_WAIT
# }

function Start-Streamlit {
    try {
        Start-Process -FilePath $streamlit -ArgumentList "run dashboard.py --server.port 8501" `
            -RedirectStandardOutput "$logDir\dashboard.log" `
            -RedirectStandardError  "$logDir\dashboard_err.log" `
            -WindowStyle Hidden
        Start-Sleep -Seconds $RESTART_WAIT
    } catch {
        Write-Log "[FATAL] Start-Streamlit 실패: $($_.Exception.Message)"
    }
}

function Start-Ngrok {
    try {
        Start-Process -FilePath $NGROK_EXE -ArgumentList $NGROK_ARGS -WindowStyle Hidden
        Start-Sleep -Seconds $RESTART_WAIT
    } catch {
        Write-Log "[FATAL] Start-Ngrok 실패: $($_.Exception.Message)"
    }
}

function Test-Launcher {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
    return ($procs | Where-Object { $_.CommandLine -like "*launcher*main.py*" -or $_.CommandLine -like "*launcher\main*" }) -ne $null
}

function Start-Launcher {
    try {
        Start-Process -FilePath $python -ArgumentList "launcher\main.py" `
            -RedirectStandardOutput "$logDir\scheduler.log" `
            -RedirectStandardError  "$logDir\scheduler_err.log" `
            -WindowStyle Hidden
        Start-Sleep -Seconds $RESTART_WAIT
    } catch {
        Write-Log "[FATAL] Start-Launcher 실패: $($_.Exception.Message)"
    }
}

function Start-N8n {
    try {
        Start-Process cmd -ArgumentList "/c npx n8n start > `"$logDir\n8n.log`" 2>&1" -WindowStyle Hidden
        Start-Sleep -Seconds 15  # n8n 초기 기동 대기
    } catch {
        Write-Log "[FATAL] Start-N8n 실패: $($_.Exception.Message)"
    }
}

Write-Log "===== watchdog 시작 (주기: ${POLL_SEC}초 / 연속실패알림: ${FAIL_ALERT_TH}회) ====="

try {
    while ($true) {
        try {

            # [260527] Flask 독립 감시 블록 주석 처리 — launcher\main.py가 Flask(:5000) 직접 관리
            # --- Flask 감시 ---
            # if (-not (Test-Http $FLASK_URL)) {
            #     Write-Log "[WARN] Flask 응답 없음 — 재시작 시도"
            #     Send-SlackAlert "Flask 응답 없음 — 재시작 시도" "warning"
            #     Start-Flask
            #     if (Test-Http $FLASK_URL) {
            #         Write-Log "[OK]   Flask 재시작 성공"
            #         Send-SlackAlert "Flask 재시작 성공" "success"
            #         Register-Success "Flask"
            #     } else {
            #         Write-Log "[ERROR] Flask 재시작 후에도 응답 없음 — webhook_stderr.log 확인 필요"
            #         Send-SlackAlert "Flask 재시작 실패 — webhook_stderr.log 확인 필요" "error"
            #         Register-Failure "Flask"
            #     }
            # } else {
            #     Register-Success "Flask"
            # }

            # --- Streamlit 감시 ---
            if (-not (Test-Http $STREAMLIT_URL)) {
                Write-Log "[WARN] Streamlit 응답 없음 — 재시작 시도"
                Send-SlackAlert "Streamlit 응답 없음 — 재시작 시도" "warning"
                Start-Streamlit
                if (Test-Http $STREAMLIT_URL) {
                    Write-Log "[OK]   Streamlit 재시작 성공"
                    Send-SlackAlert "Streamlit 재시작 성공" "success"
                    Register-Success "Streamlit"
                } else {
                    Write-Log "[ERROR] Streamlit 재시작 후에도 응답 없음 — dashboard_err.log 확인 필요"
                    Send-SlackAlert "Streamlit 재시작 실패 — dashboard_err.log 확인 필요" "error"
                    Register-Failure "Streamlit"
                }
            } else {
                Register-Success "Streamlit"
            }

            # --- ngrok 감시 (프로세스 존재 여부) ---
            if (-not (Get-Process -Name ngrok -ErrorAction SilentlyContinue)) {
                Write-Log "[WARN] ngrok 프로세스 없음 — 재시작 시도"
                Send-SlackAlert "ngrok 프로세스 없음 — 재시작 시도" "warning"
                Start-Ngrok
                if (Get-Process -Name ngrok -ErrorAction SilentlyContinue) {
                    Write-Log "[OK]   ngrok 재시작 성공"
                    Send-SlackAlert "ngrok 재시작 성공" "success"
                    Register-Success "Ngrok"
                } else {
                    Write-Log "[ERROR] ngrok 재시작 실패 — ngrok PATH 확인 필요"
                    Send-SlackAlert "ngrok 재시작 실패 — ngrok PATH 확인 필요" "error"
                    Register-Failure "Ngrok"
                }
            } else {
                Register-Success "Ngrok"
            }

            # --- launcher/main.py 감시 (커맨드라인 검사) ---
            if (-not (Test-Launcher)) {
                Write-Log "[WARN] launcher/main.py 프로세스 없음 — 재시작 시도"
                Send-SlackAlert "launcher/main.py 프로세스 없음 — 재시작 시도" "warning"
                Start-Launcher
                if (Test-Launcher) {
                    Write-Log "[OK]   launcher/main.py 재시작 성공"
                    Send-SlackAlert "launcher/main.py 재시작 성공" "success"
                    Register-Success "Launcher"
                } else {
                    Write-Log "[ERROR] launcher/main.py 재시작 실패 — scheduler_err.log 확인 필요"
                    Send-SlackAlert "launcher/main.py 재시작 실패 — scheduler_err.log 확인 필요" "error"
                    Register-Failure "Launcher"
                }
            } else {
                Register-Success "Launcher"
            }

            # --- n8n 감시 (HTTP 헬스체크) ---
            if (-not (Test-Http $N8N_URL)) {
                Write-Log "[WARN] n8n 응답 없음 — 재시작 시도"
                Send-SlackAlert "n8n 응답 없음 — 재시작 시도" "warning"
                Start-N8n
                if (Test-Http $N8N_URL) {
                    Write-Log "[OK]   n8n 재시작 성공"
                    Send-SlackAlert "n8n 재시작 성공" "success"
                    Register-Success "N8n"
                } else {
                    Write-Log "[ERROR] n8n 재시작 실패 — logs/n8n.log 확인 필요"
                    Send-SlackAlert "n8n 재시작 실패 — logs/n8n.log 확인 필요" "error"
                    Register-Failure "N8n"
                }
            } else {
                Register-Success "N8n"
            }

            Write-Log "[HEARTBEAT] alive"

        } catch {
            Write-Log "[FATAL] 루프 내부 예외: $($_.Exception.Message)"
            Write-Log "[FATAL] StackTrace: $($_.ScriptStackTrace)"
        }

        Start-Sleep -Seconds $POLL_SEC
    }
} finally {
    Write-Log "[FATAL] watchdog.ps1 최상위 종료됨"
}