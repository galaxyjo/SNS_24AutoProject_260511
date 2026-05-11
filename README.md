# SNS Auto Scheduler

Facebook 그룹 크롤링 → Instagram 자동 업로드 파이프라인

## 구조

```
insta_scheduler.py        # 메인 스케줄러 (APScheduler)
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
python insta_scheduler.py
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
