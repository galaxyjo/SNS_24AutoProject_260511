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

$envFile = Join-Path $PSScriptRoot ".env"

# .env에서 SLACK_WEBHOOK_URL 로드 (시스템 환경변수 미설정 시 폴백)
if (-not $env:SLACK_WEBHOOK_URL) {
    if (Test-Path $envFile) {
        Get-Content $envFile | Where-Object { $_ -match '^SLACK_WEBHOOK_URL\s*=' } | ForEach-Object {
            $env:SLACK_WEBHOOK_URL = ($_ -split '=', 2)[1].Trim()
        }
    }
}

# n8n은 운영 미승인 상태이므로 기본 비활성화. 환경변수 또는 .env에서 true일 때만 감시한다.
$n8nWatchdogRaw = $env:N8N_WATCHDOG_ENABLED
if (-not $n8nWatchdogRaw -and (Test-Path $envFile)) {
    $n8nWatchdogLine = Get-Content $envFile | Where-Object { $_ -match '^N8N_WATCHDOG_ENABLED\s*=' } | Select-Object -First 1
    if ($n8nWatchdogLine) {
        $n8nWatchdogRaw = ($n8nWatchdogLine -split '=', 2)[1].Trim()
    }
}
$N8N_WATCHDOG_ENABLED = $n8nWatchdogRaw -match '^(true|1|yes|on)$'

$python      = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$streamlit   = Join-Path $PSScriptRoot ".venv\Scripts\streamlit.exe"
$logDir      = Join-Path $PSScriptRoot "logs"
$watchdogLog = Join-Path $logDir "watchdog.log"
$bootPolicyPath = "C:\ProgramData\SNS_24AutoProject\runtime_boot_policy.json"

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
    Flask                  = 0
    Streamlit              = 0
    Ngrok                  = 0
    Launcher               = 0
    N8n                    = 0
    SchedulerHeartbeatMain = 0
    SchedulerHeartbeatDm   = 0
}
$APP_LOG_PATH        = Join-Path $logDir "summary\app.log"
$HEARTBEAT_STALE_MIN = 7   # ERR-089 후보 B(회장 확정, 260730)

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

# ERR-089 관측 보강(260730) — app.log 안의 [SchedulerHeartbeat][tag] 마지막 줄 시각을
# 확인해 스케줄러 루프 생존 여부를 판정한다. 파일이 없거나(Runtime 미기동 등 다른
# 사유) 태그 자체가 최근 구간에 없으면 stale(=false)로 fail-closed 처리한다.
function Test-SchedulerHeartbeat {
    param([string]$tag, [int]$staleMinutes = $HEARTBEAT_STALE_MIN)
    if (-not (Test-Path -LiteralPath $APP_LOG_PATH)) { return $false }
    $lastLine = Get-Content -LiteralPath $APP_LOG_PATH -Tail 300 -ErrorAction SilentlyContinue |
        Select-String -Pattern $tag -SimpleMatch | Select-Object -Last 1
    if (-not $lastLine) { return $false }
    if ($lastLine.Line -match '^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})') {
        $ts = [datetime]::ParseExact($matches[1], "yyyy-MM-dd HH:mm:ss", $null)
        return (((Get-Date) - $ts).TotalMinutes -lt $staleMinutes)
    }
    return $false
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
    # 외부에서 직접 실행한 Launcher가 Watchdog 자식으로 오인되는 것을 막는다.
    return ($procs | Where-Object {
        $_.ParentProcessId -eq $PID -and (
            $_.CommandLine -like "*launcher*main.py*" -or
            $_.CommandLine -like "*launcher\main*"
        )
    }) -ne $null
}

function Test-RuntimeBootPolicy {
    # W1: Watchdog와 Python Runtime이 같은 영속 Policy를 각각 검증한다.
    # 파일 누락·손상·만료 시 Launcher를 시작하지 않으며 Production fallback도 없다.
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        Write-Log "[BLOCKED] Runtime Python 없음 — Launcher 시작 0건"
        return $false
    }
    try {
        $policyOutput = & $python -B -m modules.common.canary_safe_mode `
            --validate-boot-policy --policy-path $bootPolicyPath 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Log "[BLOCKED] Runtime Boot Policy 검증 실패 — Launcher 시작 0건"
            return $false
        }
        $summary = ($policyOutput | Select-Object -Last 1)
        Write-Log "[BOOT] $summary"
        return $true
    } catch {
        Write-Log "[BLOCKED] Runtime Boot Policy 검사 예외 — Launcher 시작 0건"
        return $false
    }
}

function Start-Launcher {
    if (-not (Test-RuntimeBootPolicy)) {
        return $false
    }
    try {
        Start-Process -FilePath $python -ArgumentList "launcher\main.py" `
            -RedirectStandardOutput "$logDir\scheduler.log" `
            -RedirectStandardError  "$logDir\scheduler_err.log" `
            -WindowStyle Hidden
        Start-Sleep -Seconds $RESTART_WAIT
        return $true
    } catch {
        Write-Log "[FATAL] Start-Launcher 실패: $($_.Exception.Message)"
        return $false
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
if (-not $N8N_WATCHDOG_ENABLED) {
    Write-Log "[INFO] n8n watchdog 감시 비활성화 — N8N_WATCHDOG_ENABLED=false"
}

# 260814 FP-075 대응 — 이 기기는 전통적 Sleep(S1~S3)을 펌웨어가 지원하지 않고
# Modern Standby(S0)만 지원한다(powercfg /a 확인). 기존 전원설정
# (STANDBYIDLE=절대안함)은 Modern Standby에는 적용되지 않아, 유휴 상태가 길어지면
# 시스템 전체(스케줄러 포함)가 몇 시간씩 멈추는 현상이 실측 확인됐다(Kernel-Power
# 이벤트 506/507, "Idle Timeout"/"Austerity Battery Drain Budget Exceeded").
# Windows 공식 API(SetThreadExecutionState)로 watchdog.ps1이 살아있는 동안 시스템이
# 유휴 절전에 들어가지 않도록 요청한다 — 화면(Display)은 꺼져도 되고 시스템만
# 깨어있게 한다(ES_DISPLAY_REQUIRED 미사용). 프로세스 종료 시 요청은 자동 해제된다.
try {
    Add-Type -Name Kernel32Power -Namespace WatchdogPower -MemberDefinition '
        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        public static extern uint SetThreadExecutionState(uint esFlags);
    '
    # 260814 — 0x80000000을 그대로 쓰면 PowerShell이 부호있는 Int32(-2147483648)로
    # 먼저 해석해 [uint32] 변환이 실패한다(실측 확인). 10진수 리터럴로 우회.
    $ES_CONTINUOUS = [uint32]2147483648        # 0x80000000
    $ES_SYSTEM_REQUIRED = [uint32]1            # 0x00000001
    $null = [WatchdogPower.Kernel32Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
    Write-Log "[INFO] SetThreadExecutionState 요청 완료 — Modern Standby 유휴 절전 방지 활성화"
} catch {
    Write-Log "[WARN] SetThreadExecutionState 실패 — 절전 방지 미적용: $($_.Exception.Message)"
}

try {
    while ($true) {
        try {

            # [260730] ERR-089 관측 보강 — Alert-only. launcher\main.py가 Flask(:5000)를
            # 직접 관리하므로 여기서 Start-Flask/Start-Launcher를 호출하면 이미 살아있는
            # (내부만 멎었을 수 있는) 프로세스 옆에 새 프로세스가 추가로 뜨는 중복게시
            # 위험이 있다(Start-Launcher는 기존 프로세스를 죽이지 않음, 260730 Gate 확인).
            # 그래서 자동 재시작 없이 로그+Slack 알림만 남긴다.
            # --- Flask 응답성 감시(Alert-only, 재시작 없음) ---
            if (-not (Test-Http $FLASK_URL)) {
                Write-Log "[WARN] Flask 응답 없음(launcher 내부 무응답 가능성) — 자동 재시작 없음, 수동 확인 필요"
                Send-SlackAlert "[ERR-089] Flask 응답 없음 — 자동 재시작 안 함, 수동 확인 필요" "warning"
                Register-Failure "Flask"
            } else {
                Register-Success "Flask"
            }

            # --- Scheduler Heartbeat 감시(Alert-only, ERR-089, 재시작 없음) ---
            if (-not (Test-SchedulerHeartbeat -tag "[SchedulerHeartbeat][main]")) {
                Write-Log "[WARN] Scheduler(main) Heartbeat 끊김(${HEARTBEAT_STALE_MIN}분 초과) — 자동 재시작 없음, 수동 확인 필요"
                Send-SlackAlert "[ERR-089] Scheduler(main) Heartbeat 끊김 — 수동 확인 필요" "warning"
                Register-Failure "SchedulerHeartbeatMain"
            } else {
                Register-Success "SchedulerHeartbeatMain"
            }
            if (-not (Test-SchedulerHeartbeat -tag "[SchedulerHeartbeat][dm]")) {
                Write-Log "[WARN] Scheduler(dm) Heartbeat 끊김(${HEARTBEAT_STALE_MIN}분 초과) — 자동 재시작 없음, 수동 확인 필요"
                Send-SlackAlert "[ERR-089] Scheduler(dm) Heartbeat 끊김 — 수동 확인 필요" "warning"
                Register-Failure "SchedulerHeartbeatDm"
            } else {
                Register-Success "SchedulerHeartbeatDm"
            }

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
                $launcherStarted = Start-Launcher
                if (-not $launcherStarted) {
                    Write-Log "[BLOCKED] Launcher 사전조건 실패 — 자동 Production 기동 금지"
                    Register-Failure "Launcher"
                } elseif (Test-Launcher) {
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

            # --- n8n 감시 (운영 승인 전 기본 비활성화) ---
            if ($N8N_WATCHDOG_ENABLED) {
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
