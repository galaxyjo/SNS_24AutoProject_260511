# SNS 자동화 서버 재시작 스크립트
# 사용법: .\run_scheduler.ps1
# 순서: (ngrok은 유지) → 기존 python 종료 → launcher/main.py 시작 → 대시보드 재시작

Set-Location $PSScriptRoot

$python    = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$streamlit = Join-Path $PSScriptRoot ".venv\Scripts\streamlit.exe"
$logDir    = Join-Path $PSScriptRoot "logs"

# 1. 기존 python 프로세스 종료
Write-Host "[STOP] 기존 python 프로세스 종료..."
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -Confirm:$false
Start-Sleep -Seconds 2

# 2. ngrok 상태 확인 (없으면 시작)
$ngrokRunning = Get-Process -Name ngrok -ErrorAction SilentlyContinue
if (-not $ngrokRunning) {
    Write-Host "[NGROK] ngrok 시작..."
    Start-Process -FilePath "ngrok" -ArgumentList "http --url=danuta-overdramatic-whirly.ngrok-free.dev 5000" -WindowStyle Hidden
    Start-Sleep -Seconds 3
} else {
    Write-Host "[NGROK] 이미 실행 중 (유지)"
}

# 3. 통합 서버 시작 (Flask + APScheduler + RetryQueue 통합)
#    launcher/main.py = Flask(5000) + 8개 스케줄 잡 + RetryQueue 워커
Write-Host "[START] 통합 서버 시작 (launcher/main.py)..."
Start-Process -FilePath $python -ArgumentList "launcher\main.py" `
    -RedirectStandardOutput "$logDir\scheduler.log" `
    -RedirectStandardError  "$logDir\scheduler_err.log" `
    -WindowStyle Hidden
Start-Sleep -Seconds 15

# 4. Flask 헬스체크
try {
    $health = Invoke-RestMethod -Uri "http://localhost:5000/health" -TimeoutSec 5
    Write-Host "[OK] Flask 정상 응답: status=$($health.status)"
} catch {
    Write-Host "[ERROR] Flask 응답 없음 — logs\scheduler_err.log 확인"
}

# 5. Streamlit 대시보드 시작
Write-Host "[START] Streamlit 대시보드 시작 (port 8501)..."
Start-Process -FilePath $streamlit -ArgumentList "run dashboard.py --server.port 8501" `
    -RedirectStandardOutput "$logDir\dashboard.log" `
    -RedirectStandardError  "$logDir\dashboard_err.log" `
    -WindowStyle Hidden
Start-Sleep -Seconds 4

try {
    $st = Invoke-WebRequest -Uri "http://localhost:8501" -TimeoutSec 5 -UseBasicParsing
    Write-Host "[OK] Streamlit 정상 응답: HTTP $($st.StatusCode)"
} catch {
    Write-Host "[ERROR] Streamlit 응답 없음 — logs\dashboard.log 확인"
}

Write-Host "`n[DONE] 서버 시작 완료"
Write-Host "  통합 서버  : logs\scheduler.log / scheduler_err.log"
Write-Host "  Flask      : http://localhost:5000/health"
Write-Host "  Dashboard  : http://localhost:8501"
Write-Host "  Webhook    : https://danuta-overdramatic-whirly.ngrok-free.dev/webhook"
Write-Host "`n[NEXT] watchdog 별도 터미널에서 실행:"
Write-Host "  .\watchdog.ps1"
