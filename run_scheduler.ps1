# Instagram 자동 업로드 스케줄러 실행
# 사용법: .\run_scheduler.ps1

$venv = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$script = Join-Path $PSScriptRoot "insta_scheduler.py"

if (-Not (Test-Path $venv)) {
    Write-Host "[SETUP] 가상환경 생성 중..."
    python -m venv .venv
    & ".venv\Scripts\pip.exe" install -r requirements.txt --quiet
}

Write-Host "[START] 스케줄러 시작 (Ctrl+C 로 종료)"
& $venv $script
