# SNS Auto Scheduler - Windows Task Scheduler 등록
# 관리자 권한으로 실행 필요

$TaskName   = "SNS_InstaScheduler"
$PythonExe  = "C:\SNS_24AutoProject_260511\.venv\Scripts\python.exe"
$Script     = "C:\SNS_24AutoProject_260511\insta_scheduler.py"
$WorkingDir = "C:\SNS_24AutoProject_260511"
$LogFile    = "C:\SNS_24AutoProject_260511\logs\scheduler.log"

# logs 디렉토리 생성
New-Item -ItemType Directory -Path "$WorkingDir\logs" -Force | Out-Null

# 기존 태스크 제거
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[INFO] 기존 태스크 제거 완료"
}

# 액션: python insta_scheduler.py (로그는 RotatingFileHandler가 직접 관리)
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$Script`"" `
    -WorkingDirectory $WorkingDir

# 트리거: 시스템 시작 시 + 1분 지연
$Trigger = New-ScheduledTaskTrigger -AtStartup

# 설정: 항상 실행, 실패 시 1분 후 재시작 (최대 3회)
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Principal: 현재 로그인 사용자, 최고 권한
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

# 태스크 등록
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "SNS 자동 업로드 스케줄러 (FB 크롤링 → Instagram 게시)" `
    -Force | Out-Null

Write-Host "[OK] 태스크 등록 완료: $TaskName"
Write-Host "     실행 조건: 시스템 시작 시 자동 실행"
Write-Host "     로그 경로: $LogFile"
Write-Host "     재시작: 실패 시 1분 후 재시도 (최대 3회)"
