# OPS_RUNBOOK.md — 일상 운영 절차 런북

> 기준일: 2026-05-14 | 버전: v1.0

---

## 1. 시스템 기동 절차

### 1-1. 전체 기동 (표준)

```powershell
# 터미널 1 — 메인 스케줄러
.\run_scheduler.ps1

# 터미널 2 — 프로세스 감시 (별도)
.\watchdog.ps1

# 또는 직접 실행
python launcher/main.py
```

### 1-2. 대시보드

```powershell
python dashboard.py
# 접속: http://localhost:8501
```

### 1-3. 기동 확인 체크리스트

- [ ] Flask Webhook 서버 응답 (`http://localhost:5000/health`)
- [ ] ngrok 터널 활성 (Meta Webhook Callback URL 유효)
- [ ] Airtable 연결 정상 (Source_Feeds 레코드 조회)
- [ ] Slack 알림 수신 (기동 알림 메시지 확인)
- [ ] retry_queue 잔여 건수 확인

---

## 2. 일일 운영 루틴

| 시간 | 항목 | 확인 방법 |
|------|------|-----------|
| 09:00 | Slack 일간 KPI 리포트 수신 확인 | Slack 채널 |
| 09:10 | Upload 성공률 확인 | dashboard.py > KPI 탭 |
| 09:20 | Lead 전환 현황 확인 | Airtable Lead_Interactions |
| 수시 | 에러 로그 확인 | `logs/error/error.log` |
| 수시 | retry_queue 적체 확인 | `python -m modules.common.health_monitor` |

---

## 3. 스케줄 잡 목록

| 잡 이름 | 주기 | 기능 |
|---------|------|------|
| fb_crawl | 매 2시간 | Facebook 콘텐츠 크롤링 |
| ig_upload | 크롤 후 | Instagram 업로드 |
| engagement_track | 30분 | like_count / comments_count 갱신 |
| auto_like | 15분 | 댓글 자동 좋아요 |
| dm_followup | 매 1시간 | 팔로업 DM 발송 |
| comment_poll | 15분 | 댓글 수집 및 자동 답글 |
| lead_score | 매 1시간 | 리드 점수 갱신 |
| kpi_snapshot | 매 1시간 | KPI SQLite 저장 |
| daily_report | 매일 09:00 | 일간 리포트 Slack 발송 |

---

## 4. 로그 위치

```
logs/summary/app.log       — INFO+ 전체 통합 로그
logs/error/error.log       — ERROR+ 에러 전용
logs/function/{모듈명}.log  — DEBUG+ 모듈별 상세
```

---

## 5. 정상 종료 절차

```powershell
# watchdog / scheduler PID 확인
Get-Process python | Select-Object Id, ProcessName, MainWindowTitle

# 종료
Stop-Process -Id <PID> -Force
```
