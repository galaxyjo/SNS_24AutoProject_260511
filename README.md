# SNS Auto Scheduler

Facebook 그룹 크롤링 → Instagram 자동 업로드 파이프라인

## 구조

```
launcher/main.py          # 통합 진입점 (Flask + APScheduler + RetryQueue)
modules/
  sns/
    facebook_crawler.py   # Facebook 그룹 크롤링 (AdsPower + Selenium)
    insta_uploader.py     # Instagram Graph API 업로드
    ...
  common/
    airtable_bridge.py    # Airtable 연동 (get_table, fetch/update)
db/
  migrate_airtable_instagram.py  # Airtable 컬럼 마이그레이션
  init_instagram_db.py           # SQLite 초기화
  schema_instagram.sql           # DB 스키마
```

## 설정

```bash
cp .env.example .env
# .env 편집 후 Airtable / Instagram 키 입력
```

## 실행

```powershell
.\run_scheduler.ps1
```

또는 직접:

```bash
python launcher/main.py
```

## 스케줄

| 잡 | 주기 | 설명 |
|---|---|---|
| `fb_crawl` | 30분 | Facebook 그룹 최신 포스트 크롤링 → Airtable 저장 |
| `insta_poll` | 5분 | Airtable `ready` 레코드 업로드 → `posted`/`failed` 마킹 |

## Airtable 마이그레이션

```bash
python db/migrate_airtable_instagram.py
```

`Instagram_Posts` 테이블에 `retry_count`, `last_error_msg` 컬럼 추가 (멱등).

## 재시도 정책

업로드 실패 시 10초 간격으로 최대 3회 재시도.  
3회 모두 실패 시 `post_status=failed`, `last_error_msg`에 에러 내용 기록.

## Heartbeat 감시 (tools/heartbeat_monitor.py)

watchdog.ps1과 완전히 독립된 heartbeat 정지 감지 스크립트. watchdog이 죽어도 이 스크립트는 별도로 살아서 Slack 알림을 보낸다 (watchdog 감시 공백이 3시간12분 지속됐던 사고를 계기로 추가).

```bash
python tools/heartbeat_monitor.py
```

의존성: `python-dotenv`, `requests`(`services/slack_notifier.py` 경유), 프로젝트 `.env`의 `SLACK_WEBHOOK_URL`.

Task Scheduler 등록: `SNS_HeartbeatMonitor_Independent` (5분 주기, RunLevel=Limited, WorkingDirectory=`C:\SNS_24AutoProject_260511`).

| 항목 | 값 |
|---|---|
| 정지 판정 임계치 | 180초 (watchdog 정상 주기 30초의 6배) |
| 재알림 억제 | 30분 |
| 로컬 로그 | `logs/heartbeat_monitor.log` (판정 기록) |
| 재알림 상태 파일 | `logs/heartbeat_monitor_state.txt` |

180초 임계치는 대시보드 `get_watchdog_status()`의 90초 기준과 의도적으로 다르다 — 경고(대시보드 즉시성) < 페이징(Slack 알림) 임계치 패턴.
