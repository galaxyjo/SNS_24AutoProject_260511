# DEPLOYMENT.md — 설치 및 배포 가이드

> 기준일: 2026-05-14 | 버전: v1.0

---

## 전제 조건

| 항목 | 버전 / 조건 |
|------|-------------|
| OS | Windows 10/11 |
| Python | 3.10 이상 |
| AdsPower | 설치 및 로그인 완료 |
| ngrok | 설치 및 authtoken 설정 완료 |
| Meta Developer App | Webhook 구독 완료 (messages, comments) |

---

## 초기 설치

```powershell
# 1. 저장소 클론 (또는 기존 폴더 사용)
cd C:\SNS_24AutoProject_260511

# 2. 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경변수 설정
cp .env.example .env
notepad .env
```

---

## 환경변수 설정 (.env)

```env
# Airtable
AIRTABLE_API_KEY=pat_xxxx
AIRTABLE_BASE_ID=appXXXXXXXX

# Instagram / Meta
INSTAGRAM_ACCESS_TOKEN=EAAG...
INSTAGRAM_BUSINESS_ID=1234567890
META_VERIFY_TOKEN=your_verify_token

# Gemini
GEMINI_API_KEY=AIza...

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz

# 크롤링 설정
MAX_POSTS=10
PARALLEL_MAX_WORKERS=3
AUTO_LIKE_MAX_POSTS=10
```

---

## Meta Webhook 등록

1. Meta Developer Console 접속
2. App → Webhooks → Instagram 구독
3. Callback URL: `https://{ngrok-url}/webhook`
4. Verify Token: `.env`의 `META_VERIFY_TOKEN` 값
5. 구독 필드: `messages`, `comments`

---

## 다계정 설정

```json
// configs/accounts.json
[
  {
    "account_id": "account_1",
    "instagram_business_id": "111111",
    "access_token": "EAAG...",
    "proxy": "http://user:pass@proxy-host:port"
  }
]
```

계정 없으면 `.env` 단일 계정 자동 폴백.

---

## 기동

```powershell
# 전체 기동
.\run_scheduler.ps1

# watchdog (별도 터미널)
.\watchdog.ps1

# 대시보드 (별도 터미널)
python dashboard.py
```

---

## Airtable 필드 초기화

```powershell
# Instagram_Posts 필드 추가 (최초 1회)
python tools/add_instagram_posts_fields.py

# DB 스키마 초기화
python db/init_instagram_db.py
```

---

## 버전 업데이트 절차

1. `git pull origin master`
2. `pip install -r requirements.txt` (의존성 변경 시)
3. DB 마이그레이션 실행 (필요 시)
4. 전체 재기동
