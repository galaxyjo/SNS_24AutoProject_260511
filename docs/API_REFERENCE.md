# API_REFERENCE.md — 환경변수 / API 레퍼런스

> 기준일: 2026-05-14 | 버전: v1.0

---

## 환경변수 전체 목록

### Airtable

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `AIRTABLE_API_KEY` | ✅ | Personal Access Token (`pat_...`) |
| `AIRTABLE_BASE_ID` | ✅ | Base ID (`appXXXXXXXX`) |

### Instagram / Meta

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `INSTAGRAM_ACCESS_TOKEN` | ✅ | 장기 액세스 토큰 (무제한 발급 완료) |
| `INSTAGRAM_BUSINESS_ID` | ✅ | Instagram 비즈니스 계정 ID |
| `META_VERIFY_TOKEN` | ✅ | Webhook Verify Token |

### AI

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `GEMINI_API_KEY` | ✅ | Google Gemini API Key |

### 알림

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `SLACK_WEBHOOK_URL` | 권장 | Incoming Webhook URL (미설정 시 알림 생략) |

### 크롤링 / 실행 제어

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `MAX_POSTS` | `10` | FB 크롤링 최대 게시물 수 |
| `PARALLEL_MAX_WORKERS` | `3` | 다계정 병렬 실행 수 |
| `AUTO_LIKE_MAX_POSTS` | `10` | 자동 좋아요 처리 게시물 수 |

---

## 내부 API — 공통 모듈

### logger

```python
from modules.common.logger import get_logger
log = get_logger('module_name')
log.info("메시지")
log.error("에러", exc_info=True)
```

### retry_queue

```python
from modules.common.retry_queue import get_retry_queue
q = get_retry_queue()
q.enqueue(task_name='ig_upload', payload={'record_id': 'rec123'})
```

### health_monitor

```python
from modules.common.health_monitor import get_health
status = get_health()
# {'services': {...}, 'retry_queue': {...}, 'recent_errors': [...]}
```

### account_manager

```python
from modules.common.account_manager import get_active_accounts
accounts = get_active_accounts()
accounts[0].selenium_proxy_options()  # Selenium 프록시 설정
```

### parallel_runner

```python
from modules.common.parallel_runner import run_parallel
results = run_parallel(task_fn)  # 전체 활성 계정 병렬 실행
```

### slack_notifier

```python
from services.slack_notifier import notify_error, notify_info
notify_error("에러 메시지")
notify_info("정보 메시지")
notify_daily_kpi(kpi_dict)
notify_process_restart("launcher", "restarted")
```

### kpi_collector

```python
from modules.metrics.kpi_collector import collect_kpi
kpi = collect_kpi('today')   # 'today' | '7d' | '30d' | 'all'
```

### ai_reply_generator

```python
from modules.dm.ai_reply_generator import generate_reply
reply = generate_reply(user_message="안녕하세요", context={})
# Gemini 실패 시 템플릿 자동 폴백
```

---

## Flask 엔드포인트

| 메서드 | 경로 | 기능 |
|--------|------|------|
| GET | `/health` | 서비스 상태 확인 |
| GET | `/webhook` | Meta Webhook Verify |
| POST | `/webhook` | Meta Webhook 이벤트 수신 |

---

## Airtable 테이블 구조

| 테이블명 | 주요 필드 |
|----------|-----------|
| `Source_Feeds` | url, status, crawled_at |
| `Instagram_Posts` | ig_media_id, like_count, comments_count, status |
| `Lead_Interactions` | sender_id, message, state, score, created_at |
