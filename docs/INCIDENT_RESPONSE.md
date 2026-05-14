# INCIDENT_RESPONSE.md — 장애 대응 매뉴얼

> 기준일: 2026-05-14 | 버전: v1.0

---

## 장애 등급

| 등급 | 기준 | 대응 시간 |
|------|------|-----------|
| P1 (Critical) | 전체 파이프라인 중단 / Webhook 불통 | 즉시 |
| P2 (High) | 업로드 실패 반복 / DM 자동응답 불가 | 30분 내 |
| P3 (Medium) | KPI 집계 오류 / 댓글 자동화 중단 | 2시간 내 |
| P4 (Low) | 로그 누락 / 대시보드 렌더링 오류 | 당일 내 |

---

## 주요 장애 시나리오별 대응

### S-01. ngrok 터널 끊김

**증상:** Meta Webhook Callback 실패 / DM 수신 불가

```powershell
# 1. ngrok 재기동 (watchdog 자동 재시작 확인)
# watchdog.ps1이 자동 감지 → 재시작

# 2. 수동 재시작
Start-Process ngrok -ArgumentList "http 5000"

# 3. 새 터널 URL 확인 후 Meta Webhook Callback URL 업데이트
# Meta Developer Console → Webhook 설정
```

---

### S-02. Instagram 업로드 연속 실패

**증상:** Airtable status = 'failed' 레코드 누적

```python
# 1. 에러 로그 확인
# logs/error/error.log 에서 instagram_uploader 에러 확인

# 2. Access Token 유효성 확인
# .env → INSTAGRAM_ACCESS_TOKEN

# 3. retry_queue 강제 재실행
python -m modules.common.retry_queue
```

---

### S-03. Facebook 크롤러 중단

**증상:** Source_Feeds 신규 레코드 없음 / Selenium 오류

```powershell
# 1. AdsPower 프로세스 확인
Get-Process | Where-Object { $_.Name -like "*adspower*" }

# 2. Chrome Driver 재시작
# AdsPower → 계정 프로필 재기동

# 3. 크롤러 단독 실행 테스트
python -m modules.sns.facebook_crawler
```

---

### S-04. Gemini API 429 (Rate Limit)

**증상:** AI 응답 실패 → 템플릿 폴백 전환 로그

```
# 자동 처리: ai_reply_generator.py 내 재시도 + 스로틀 적용
# 추가 대응: GEMINI_API_KEY 로테이션 (여분 키 있는 경우)
```

---

### S-05. Queue Deadlock / 프로세스 크래시

**증상:** watchdog Slack 알림 수신 / 프로세스 재시작 반복

```powershell
# 1. 헬스 모니터 확인
python -m modules.common.health_monitor

# 2. retry_queue.db 적체 확인 (100건 이상이면 백프레셔 의심)
# 3. 전체 재기동
Stop-Process -Name python -Force
.\run_scheduler.ps1
```

---

## 복구 확인 체크리스트

- [ ] Slack 알림 정상 수신
- [ ] Flask `/health` 엔드포인트 200 응답
- [ ] Airtable 신규 레코드 생성 확인
- [ ] retry_queue 건수 감소 확인
- [ ] 에러 로그 추가 발생 없음
