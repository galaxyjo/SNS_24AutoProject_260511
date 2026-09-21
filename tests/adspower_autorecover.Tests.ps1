# Pester 3.4 — tools/adspower_autorecover.ps1 (ERR-130)
# 실행: Invoke-Pester -Script tests\adspower_autorecover.Tests.ps1
# 실제 프로세스 조작·네트워크·Slack은 전부 Mock — AdsPower를 건드리지 않는다.

$ScriptUnderTest = Join-Path (Split-Path -Parent $PSScriptRoot) "tools\adspower_autorecover.ps1"

Describe "Get-AdsPowerRecoverDecision" {
    . $ScriptUnderTest -NoRun

    function New-Obs {
        param([hashtable]$Override = @{})
        $o = @{
            ApiOk = $false; ConsecutiveFailures = 2; InternetOk = $true; BrowserOpen = $false
            AdsPowerRunning = $true; UptimeSec = 600; MinutesSinceRestart = $null
        }
        foreach ($k in $Override.Keys) { $o[$k] = $Override[$k] }
        return $o
    }

    It "API 정상이면 OK" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ ApiOk = $true; ConsecutiveFailures = 0 }) | Should Be "OK"
    }
    It "연속 실패 1회는 대기" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ ConsecutiveFailures = 1 }) | Should Be "WAIT_FAILCOUNT"
    }
    It "인터넷 미연결이면 대기 (260914 재부팅 사례)" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ InternetOk = $false }) | Should Be "WAIT_NO_INTERNET"
    }
    It "SunBrowser 실행 중이면 건드리지 않음" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ BrowserOpen = $true }) | Should Be "SKIP_BROWSER_OPEN"
    }
    It "실행 3분 미만이면 대기" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ UptimeSec = 120 }) | Should Be "WAIT_STARTING"
    }
    It "마지막 재시작 15분 이내면 대기" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ MinutesSinceRestart = 10 }) | Should Be "WAIT_COOLDOWN"
    }
    It "미실행이면 START (260911 미기동 사례)" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ AdsPowerRunning = $false; UptimeSec = 0 }) | Should Be "START"
    }
    It "실행 중 무응답이면 RESTART" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ MinutesSinceRestart = 20 }) | Should Be "RESTART"
    }
    It "인터넷 판정이 브라우저·쿨다운보다 먼저" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ InternetOk = $false; BrowserOpen = $true; MinutesSinceRestart = 1 }) | Should Be "WAIT_NO_INTERNET"
    }
    It "복구 3회 연속 실패면 GIVE_UP" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ RestartFailures = 3 }) | Should Be "GIVE_UP"
    }
    It "GIVE_UP은 쿨다운보다 먼저 판정" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ RestartFailures = 3; MinutesSinceRestart = 1 }) | Should Be "GIVE_UP"
    }
    It "브라우저 충돌방지는 GIVE_UP보다 먼저" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ RestartFailures = 5; BrowserOpen = $true }) | Should Be "SKIP_BROWSER_OPEN"
    }
    It "2회 실패까지는 기존대로 복구 시도" {
        Get-AdsPowerRecoverDecision -Obs (New-Obs @{ RestartFailures = 2; MinutesSinceRestart = 20 }) | Should Be "RESTART"
    }
}

Describe "Get-MinutesSince / 상태파일" {
    . $ScriptUnderTest -NoRun
    $LogPath = Join-Path $TestDrive "recover.log"

    It "기록 없음은 null" {
        (Get-MinutesSince -Stamp "") -eq $null | Should Be $true
    }
    It "깨진 기록은 0 (쿨다운 적용)" {
        Get-MinutesSince -Stamp "garbage" | Should Be 0
    }
    It "20분 전 기록은 약 20분" {
        $stamp = (Get-Date).AddMinutes(-20).ToString("yyyy-MM-dd HH:mm:ss")
        [Math]::Round((Get-MinutesSince -Stamp $stamp)) | Should Be 20
    }
    It "상태파일 왕복" {
        $p = Join-Path $TestDrive "state.json"
        Write-RecoverState -Path $p -State @{ consecutive_failures = 3; last_restart = "2026-09-15 10:00:00"; last_action = "RESTART"; last_check = "2026-09-15 10:05:00" }
        $s = Read-RecoverState -Path $p
        $s.consecutive_failures | Should Be 3
        $s.last_restart | Should Be "2026-09-15 10:00:00"
        Test-Path "$p.tmp" | Should Be $false
    }
    It "깨진 상태파일은 기본값" {
        $p = Join-Path $TestDrive "broken.json"
        Set-Content -Path $p -Value "{not json" -Encoding UTF8
        (Read-RecoverState -Path $p).consecutive_failures | Should Be 0
    }
}

Describe "Invoke-AdsPowerAutoRecover" {
    . $ScriptUnderTest -NoRun
    $LogPath = Join-Path $TestDrive "recover.log"
    $StartWaitSec = 10

    Mock Start-Sleep {}
    Mock Stop-Process {}
    Mock Start-Process {}
    Mock Send-RecoverSlack { $true }
    Mock Test-InternetConnected { $true }
    Mock Get-Process { @() } -ParameterFilter { $Name -eq "SunBrowser" }
    Mock Get-Process { @([pscustomobject]@{ StartTime = (Get-Date).AddMinutes(-30) }) } -ParameterFilter { $Name -eq "AdsPower Global" }

    It "API 정상이면 조작 0, 실패 횟수 0" {
        $StatePath = Join-Path $TestDrive "s_ok.json"
        Mock Test-AdsPowerApi { $true }
        Invoke-AdsPowerAutoRecover | Should Be "OK"
        (Read-RecoverState -Path $StatePath).consecutive_failures | Should Be 0
        Assert-MockCalled Start-Process -Times 0 -Exactly -Scope It
        Assert-MockCalled Stop-Process -Times 0 -Exactly -Scope It
    }

    It "첫 실패는 기록만 하고 조작 0" {
        $StatePath = Join-Path $TestDrive "s_first.json"
        Mock Test-AdsPowerApi { $false }
        Invoke-AdsPowerAutoRecover | Should Be "WAIT_FAILCOUNT"
        (Read-RecoverState -Path $StatePath).consecutive_failures | Should Be 1
        Assert-MockCalled Start-Process -Times 0 -Exactly -Scope It
    }

    It "두 번째 실패에 RESTART — 종료·실행·Slack 각 1회, 복구 시 실패 0" {
        $StatePath = Join-Path $TestDrive "s_restart.json"
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 1; last_restart = ""; last_action = "WAIT_FAILCOUNT"; last_check = "" }
        $script:apiCalls = 0
        Mock Test-AdsPowerApi { $script:apiCalls++; $script:apiCalls -gt 1 }
        Invoke-AdsPowerAutoRecover | Should Be "RESTART"
        Assert-MockCalled Stop-Process -Times 1 -Exactly -Scope It
        Assert-MockCalled Start-Process -Times 1 -Exactly -Scope It
        Assert-MockCalled Send-RecoverSlack -Times 1 -Exactly -Scope It -ParameterFilter { $Text -match "성공" }
        $s = Read-RecoverState -Path $StatePath
        $s.consecutive_failures | Should Be 0
        $s.last_action | Should Be "RESTART"
        $s.last_restart | Should Not BeNullOrEmpty
    }

    It "재시작 후에도 무응답이면 실패 Slack, 쿨다운 기록 유지" {
        $StatePath = Join-Path $TestDrive "s_fail.json"
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 1; last_restart = ""; last_action = ""; last_check = "" }
        Mock Test-AdsPowerApi { $false }
        Invoke-AdsPowerAutoRecover | Should Be "RESTART"
        Assert-MockCalled Send-RecoverSlack -Times 1 -Exactly -Scope It -ParameterFilter { $Text -match "무응답" }
        $s = Read-RecoverState -Path $StatePath
        $s.consecutive_failures | Should Be 2
        $s.last_restart | Should Not BeNullOrEmpty
    }

    It "쿨다운 중이면 조작 0" {
        $StatePath = Join-Path $TestDrive "s_cool.json"
        $recent = (Get-Date).AddMinutes(-5).ToString("yyyy-MM-dd HH:mm:ss")
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 3; last_restart = $recent; last_action = "RESTART"; last_check = "" }
        Mock Test-AdsPowerApi { $false }
        Invoke-AdsPowerAutoRecover | Should Be "WAIT_COOLDOWN"
        Assert-MockCalled Stop-Process -Times 0 -Exactly -Scope It
        Assert-MockCalled Start-Process -Times 0 -Exactly -Scope It
    }

    It "SunBrowser 실행 중이면 조작 0" {
        $StatePath = Join-Path $TestDrive "s_browser.json"
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 1; last_restart = ""; last_action = ""; last_check = "" }
        Mock Test-AdsPowerApi { $false }
        Mock Get-Process { @([pscustomobject]@{ StartTime = (Get-Date) }) } -ParameterFilter { $Name -eq "SunBrowser" }
        Invoke-AdsPowerAutoRecover | Should Be "SKIP_BROWSER_OPEN"
        Assert-MockCalled Stop-Process -Times 0 -Exactly -Scope It
    }

    It "미실행이면 START — 종료 없이 실행만" {
        $StatePath = Join-Path $TestDrive "s_start.json"
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 1; last_restart = ""; last_action = ""; last_check = "" }
        $script:apiCalls = 0
        Mock Test-AdsPowerApi { $script:apiCalls++; $script:apiCalls -gt 1 }
        # Pester 3.4는 It 안의 Mock이 다음 It까지 남으므로 SunBrowser 없음으로 재설정
        Mock Get-Process { @() } -ParameterFilter { $Name -eq "SunBrowser" }
        Mock Get-Process { @() } -ParameterFilter { $Name -eq "AdsPower Global" }
        Invoke-AdsPowerAutoRecover | Should Be "START"
        Assert-MockCalled Stop-Process -Times 0 -Exactly -Scope It
        Assert-MockCalled Start-Process -Times 1 -Exactly -Scope It
    }

    It "START는 ELECTRON_NO_ATTACH_CONSOLE=1 상태에서 AdsPower를 1회만 실행 (ERR-130 실행수명)" {
        $StatePath = Join-Path $TestDrive "s_start_env.json"
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 1; last_restart = ""; last_action = ""; last_check = "" }
        Remove-Item Env:\ELECTRON_NO_ATTACH_CONSOLE -ErrorAction SilentlyContinue
        $script:envAtStart = "unset"
        $script:apiCalls = 0
        Mock Test-AdsPowerApi { $script:apiCalls++; $script:apiCalls -gt 1 }
        Mock Get-Process { @() } -ParameterFilter { $Name -eq "SunBrowser" }
        Mock Get-Process { @() } -ParameterFilter { $Name -eq "AdsPower Global" }
        Mock Start-Process { $script:envAtStart = [string]$env:ELECTRON_NO_ATTACH_CONSOLE }
        try {
            Invoke-AdsPowerAutoRecover | Should Be "START"
            Assert-MockCalled Start-Process -Times 1 -Exactly -Scope It
            Assert-MockCalled Stop-Process -Times 0 -Exactly -Scope It
            $script:envAtStart | Should Be "1"
        } finally {
            if ($null -eq $prevEnv) { Remove-Item Env:\ELECTRON_NO_ATTACH_CONSOLE -ErrorAction SilentlyContinue } else { $env:ELECTRON_NO_ATTACH_CONSOLE = $prevEnv }
        }
    }

    It "3회째 복구 실패에 GIVE_UP Slack 정확히 1회 — 무응답 Slack은 보내지 않음" {
        $StatePath = Join-Path $TestDrive "s_giveup_alert.json"
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 1; restart_failures = 2; last_restart = ""; last_action = ""; last_check = "" }
        Mock Test-AdsPowerApi { $false }
        Mock Get-Process { @() } -ParameterFilter { $Name -eq "SunBrowser" }
        Mock Get-Process { @([pscustomobject]@{ StartTime = (Get-Date).AddMinutes(-30) }) } -ParameterFilter { $Name -eq "AdsPower Global" }
        Invoke-AdsPowerAutoRecover | Should Be "RESTART"
        Assert-MockCalled Send-RecoverSlack -Times 1 -Exactly -Scope It -ParameterFilter { $Text -match "자동복구를 중단" }
        Assert-MockCalled Send-RecoverSlack -Times 0 -Exactly -Scope It -ParameterFilter { $Text -match "다음 시도는" }
        (Read-RecoverState -Path $StatePath).restart_failures | Should Be 3
    }

    It "GIVE_UP 이후에는 프로세스 조작·Slack 0, API 확인은 계속" {
        $StatePath = Join-Path $TestDrive "s_giveup_hold.json"
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 5; restart_failures = 3; last_restart = ""; last_action = "GIVE_UP"; last_check = "" }
        Mock Test-AdsPowerApi { $false }
        Mock Get-Process { @() } -ParameterFilter { $Name -eq "SunBrowser" }
        Mock Get-Process { @([pscustomobject]@{ StartTime = (Get-Date).AddMinutes(-30) }) } -ParameterFilter { $Name -eq "AdsPower Global" }
        Invoke-AdsPowerAutoRecover | Should Be "GIVE_UP"
        Assert-MockCalled Start-Process -Times 0 -Exactly -Scope It
        Assert-MockCalled Stop-Process -Times 0 -Exactly -Scope It
        Assert-MockCalled Send-RecoverSlack -Times 0 -Exactly -Scope It
        Assert-MockCalled Test-AdsPowerApi -Times 1 -Exactly -Scope It
        (Read-RecoverState -Path $StatePath).restart_failures | Should Be 3
    }

    It "GIVE_UP 상태에서 API 정상이면 restart_failures 초기화 (수동복구 재개)" {
        $StatePath = Join-Path $TestDrive "s_giveup_reset.json"
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 5; restart_failures = 3; last_restart = ""; last_action = "GIVE_UP"; last_check = "" }
        Mock Test-AdsPowerApi { $true }
        Invoke-AdsPowerAutoRecover | Should Be "OK"
        $s = Read-RecoverState -Path $StatePath
        $s.restart_failures | Should Be 0
        $s.consecutive_failures | Should Be 0
        Assert-MockCalled Start-Process -Times 0 -Exactly -Scope It
    }

    It "복구 성공 시 restart_failures 초기화" {
        $StatePath = Join-Path $TestDrive "s_giveup_success.json"
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 1; restart_failures = 2; last_restart = ""; last_action = ""; last_check = "" }
        $script:apiCalls = 0
        Mock Test-AdsPowerApi { $script:apiCalls++; $script:apiCalls -gt 1 }
        Mock Get-Process { @() } -ParameterFilter { $Name -eq "SunBrowser" }
        Mock Get-Process { @([pscustomobject]@{ StartTime = (Get-Date).AddMinutes(-30) }) } -ParameterFilter { $Name -eq "AdsPower Global" }
        Invoke-AdsPowerAutoRecover | Should Be "RESTART"
        (Read-RecoverState -Path $StatePath).restart_failures | Should Be 0
    }

    It "DryRun은 판정만 — 조작·상태파일·로그·Slack 0" {
        $StatePath = Join-Path $TestDrive "s_dry.json"
        $DryRun = $true
        $SimulateApiDown = $true
        Mock Get-Process { @() } -ParameterFilter { $Name -eq "SunBrowser" }
        Mock Get-Process { @([pscustomobject]@{ StartTime = (Get-Date).AddMinutes(-30) }) } -ParameterFilter { $Name -eq "AdsPower Global" }
        Write-RecoverState -Path $StatePath -State @{ consecutive_failures = 1; last_restart = ""; last_action = ""; last_check = "" }
        $before = Get-Content -Path $StatePath -Raw
        Invoke-AdsPowerAutoRecover | Should Be "RESTART"
        Assert-MockCalled Stop-Process -Times 0 -Exactly -Scope It
        Assert-MockCalled Start-Process -Times 0 -Exactly -Scope It
        Assert-MockCalled Send-RecoverSlack -Times 0 -Exactly -Scope It
        Get-Content -Path $StatePath -Raw | Should Be $before
        $DryRun = $false
        $SimulateApiDown = $false
    }
}
