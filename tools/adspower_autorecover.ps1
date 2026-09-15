<#
AdsPower Local API 자동 복구 (ERR-130)

사용자 세션 예약작업에서 5분마다 실행한다(SNS_Watchdog은 Session 0이라 AdsPower 재실행에 부적합).
판정 순서: API 정상 -> 종료 / 연속 실패 기준 미달 -> 대기 / 인터넷 미연결 -> 대기 /
SunBrowser 실행 중 -> 건드리지 않음 / 실행 3분 미만 -> 대기 / 15분 쿨다운 -> 대기 /
미실행 -> 시작 / 실행 중 -> 종료 후 재시작.

  -DryRun          판정만 출력(프로세스 조작·Slack·상태파일·로그 쓰기 0)
  -SimulateApiDown API 실패로 간주(DryRun과 함께 경로 확인용)
  -NoRun           함수만 로드(테스트용 dot-source)
#>
param(
    [switch]$DryRun,
    [switch]$NoRun,
    [switch]$SimulateApiDown,
    [string]$StatePath = "",
    [int]$FailThreshold = 2,
    [int]$MinUptimeSec = 180,
    [int]$CooldownMin = 15,
    [int]$StartWaitSec = 90
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $StatePath) { $StatePath = Join-Path $ProjectRoot "db\adspower_autorecover_state.json" }
$LogPath = Join-Path $ProjectRoot "logs\adspower_autorecover.log"
$ApiUrl = "http://127.0.0.1:50325/status"
$AdsPowerExe = "C:\Program Files\AdsPower Global\AdsPower Global.exe"
$AdsPowerProcName = "AdsPower Global"
$BrowserProcName = "SunBrowser"
$StampFormat = "yyyy-MM-dd HH:mm:ss"

function Get-AdsPowerRecoverDecision {
    param(
        [hashtable]$Obs,
        [int]$FailThreshold = 2,
        [int]$MinUptimeSec = 180,
        [int]$CooldownMin = 15
    )
    if ($Obs.ApiOk) { return "OK" }
    if ($Obs.ConsecutiveFailures -lt $FailThreshold) { return "WAIT_FAILCOUNT" }
    if (-not $Obs.InternetOk) { return "WAIT_NO_INTERNET" }
    if ($Obs.BrowserOpen) { return "SKIP_BROWSER_OPEN" }
    if ($Obs.AdsPowerRunning -and $Obs.UptimeSec -lt $MinUptimeSec) { return "WAIT_STARTING" }
    if ($null -ne $Obs.MinutesSinceRestart -and $Obs.MinutesSinceRestart -lt $CooldownMin) { return "WAIT_COOLDOWN" }
    if (-not $Obs.AdsPowerRunning) { return "START" }
    return "RESTART"
}

function Get-MinutesSince {
    param([string]$Stamp)
    if (-not $Stamp) { return $null }
    try {
        return ((Get-Date) - [datetime]::ParseExact($Stamp, $StampFormat, $null)).TotalMinutes
    } catch {
        # 기록이 깨졌으면 방금 재시작한 것으로 보고 쿨다운을 건다(연속 재시작 방지)
        return 0
    }
}

function Read-RecoverState {
    param([string]$Path)
    $state = @{ consecutive_failures = 0; last_restart = ""; last_action = ""; last_check = "" }
    if (-not (Test-Path $Path)) { return $state }
    try {
        $j = Get-Content -Path $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        $state.consecutive_failures = [int]$j.consecutive_failures
        $state.last_restart = [string]$j.last_restart
        $state.last_action = [string]$j.last_action
        $state.last_check = [string]$j.last_check
    } catch {
        Write-RecoverLog "상태파일 읽기 실패 — 기본값 사용: $($_.Exception.Message)"
    }
    return $state
}

function Write-RecoverState {
    param([string]$Path, [hashtable]$State)
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $tmp = "$Path.tmp"
    ($State | ConvertTo-Json) | Set-Content -Path $tmp -Encoding UTF8
    Move-Item -Path $tmp -Destination $Path -Force
}

function Write-RecoverLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format $StampFormat), $Message
    Write-Host $line
    if ($DryRun) { return }
    try { Add-Content -Path $LogPath -Value $line -Encoding UTF8 } catch {}
}

function Test-AdsPowerApi {
    try {
        $r = Invoke-RestMethod -Uri $ApiUrl -TimeoutSec 5
        return ($r.code -eq 0)
    } catch {
        return $false
    }
}

function Test-InternetConnected {
    try {
        $profiles = @(Get-NetConnectionProfile -ErrorAction Stop | Where-Object {
            $_.IPv4Connectivity -eq "Internet" -or $_.IPv6Connectivity -eq "Internet"
        })
        return ($profiles.Count -gt 0)
    } catch {
        return $false
    }
}

function Send-RecoverSlack {
    param([string]$Text)
    $url = $env:SLACK_WEBHOOK_URL
    if (-not $url) {
        $envFile = Join-Path $ProjectRoot ".env"
        if (Test-Path $envFile) {
            $line = Get-Content -Path $envFile -Encoding UTF8 | Where-Object { $_ -match '^SLACK_WEBHOOK_URL\s*=' } | Select-Object -First 1
            if ($line) { $url = ($line -split '=', 2)[1].Trim().Trim('"') }
        }
    }
    if (-not $url) { return $false }
    try {
        $body = [Text.Encoding]::UTF8.GetBytes((@{ text = $Text } | ConvertTo-Json -Compress))
        Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 10 | Out-Null
        return $true
    } catch {
        Write-RecoverLog "Slack 발송 실패: $($_.Exception.GetType().Name)"
        return $false
    }
}

function Invoke-AdsPowerAutoRecover {
    $now = Get-Date -Format $StampFormat
    $state = Read-RecoverState -Path $StatePath

    $apiOk = $false
    if (-not $SimulateApiDown) { $apiOk = Test-AdsPowerApi }
    if ($apiOk) {
        if ($state.consecutive_failures -gt 0 -and -not $DryRun) {
            Write-RecoverLog "API 정상 (직전 연속 실패 $($state.consecutive_failures)회)"
        }
        $state.consecutive_failures = 0
    } else {
        $state.consecutive_failures = [int]$state.consecutive_failures + 1
    }

    $procs = @(Get-Process -Name $AdsPowerProcName -ErrorAction SilentlyContinue)
    $uptimeSec = 0
    if ($procs.Count -gt 0) {
        $oldest = $procs | ForEach-Object { $_.StartTime } | Sort-Object | Select-Object -First 1
        $uptimeSec = [int]((Get-Date) - $oldest).TotalSeconds
    }
    $obs = @{
        ApiOk               = $apiOk
        ConsecutiveFailures = $state.consecutive_failures
        InternetOk          = $true
        BrowserOpen         = (@(Get-Process -Name $BrowserProcName -ErrorAction SilentlyContinue).Count -gt 0)
        AdsPowerRunning     = ($procs.Count -gt 0)
        UptimeSec           = $uptimeSec
        MinutesSinceRestart = (Get-MinutesSince -Stamp $state.last_restart)
    }
    if (-not $apiOk) { $obs.InternetOk = Test-InternetConnected }

    $decision = Get-AdsPowerRecoverDecision -Obs $obs -FailThreshold $FailThreshold -MinUptimeSec $MinUptimeSec -CooldownMin $CooldownMin
    $sinceText = "none"
    if ($null -ne $obs.MinutesSinceRestart) { $sinceText = [string][int]$obs.MinutesSinceRestart }
    $summary = "decision={0} fails={1} internet={2} browser_open={3} running={4} uptime_sec={5} since_restart_min={6}" -f `
        $decision, $obs.ConsecutiveFailures, $obs.InternetOk, $obs.BrowserOpen, $obs.AdsPowerRunning, $obs.UptimeSec, $sinceText

    if ($DryRun) {
        Write-Host "[DRYRUN] $summary"
        return $decision
    }
    if ($decision -ne "OK") { Write-RecoverLog $summary }

    if ($decision -eq "START" -or $decision -eq "RESTART") {
        # 조작 전에 기록 — 스크립트가 도중에 죽어도 쿨다운이 유지된다
        $state.last_restart = $now
        $state.last_action = $decision
        $state.last_check = $now
        Write-RecoverState -Path $StatePath -State $state

        if ($decision -eq "RESTART") {
            Stop-Process -Name $AdsPowerProcName -Force -ErrorAction SilentlyContinue
            for ($i = 0; $i -lt 15; $i++) {
                if (@(Get-Process -Name $AdsPowerProcName -ErrorAction SilentlyContinue).Count -eq 0) { break }
                Start-Sleep -Seconds 1
            }
        }
        $up = $false
        try {
            # Electron(AdsPower)이 헬퍼의 숨김 콘솔에 붙으면 작업 인스턴스가 끝나지 않는다(ERR-130 실행수명 결함)
            $env:ELECTRON_NO_ATTACH_CONSOLE = "1"
            Start-Process -FilePath $AdsPowerExe
            for ($i = 0; $i -lt [Math]::Ceiling($StartWaitSec / 5); $i++) {
                Start-Sleep -Seconds 5
                if (Test-AdsPowerApi) { $up = $true; break }
            }
        } catch {
            Write-RecoverLog "AdsPower 실행 실패: $($_.Exception.Message)"
        }

        if ($up) {
            $state.consecutive_failures = 0
            Write-RecoverLog "복구 성공 — $decision 후 Local API 응답"
            Send-RecoverSlack -Text ":white_check_mark: [AdsPower 자동복구] $decision 성공 — Local API 응답 확인 ($now)" | Out-Null
        } else {
            Write-RecoverLog "복구 실패 — $decision 후 ${StartWaitSec}초 내 Local API 무응답"
            Send-RecoverSlack -Text ":red_circle: [AdsPower 자동복구] $decision 후 ${StartWaitSec}초 내 Local API 무응답 — 다음 시도는 ${CooldownMin}분 뒤 ($now)" | Out-Null
        }
    }

    $state.last_action = $decision
    $state.last_check = $now
    Write-RecoverState -Path $StatePath -State $state
    return $decision
}

if (-not $NoRun) {
    Invoke-AdsPowerAutoRecover | Out-Null
}
