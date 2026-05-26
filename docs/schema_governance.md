# Schema Governance

> 작성일: 2026-05-16
> 목적: Airtable 4개 테이블 현재 컬럼 구조 기록 및 거버넌스 규칙 명시
> 기준: `audit/airtable_export/260516/` CSV 익스포트 기준

---

## 규칙 선언

- **이 문서는 현재 상태 기록 전용이다. 컬럼 수정·삭제·추가를 승인하는 문서가 아니다.**
- Airtable 스키마(컬럼 추가/삭제/이름 변경)는 반드시 이 문서에 변경 이력을 기록한 후 실행한다.
- **Migration Forbidden**: 이 문서에 명시된 이슈 컬럼을 코드에서 임의로 수정하거나, 250723 참조 저장소의 구버전 스키마를 자동 이식하는 것을 금지한다.
- 스키마 변경이 필요한 경우 `porting_logs/MERGE_JOURNAL.md`에 사유·일자·담당자를 기록하고 수동으로 진행한다.

---

## 테이블 컬럼 목록

### 1. Account_Registry (17컬럼)

| # | 컬럼명 | 비고 |
|---|--------|------|
| 1 | account_code | PK |
| 2 | platform | |
| 3 | account_email | |
| 4 | account_handle | |
| 5 | owner_name | |
| 6 | persona_role | |
| 7 | mbti_type | |
| 8 | account_status | |
| 9 | credential_key | |
| 10 | ads_power_id | |
| 11 | proxy_group | |
| 12 | target_url | |
| 13 | crawl_enabled | |
| 14 | daily_post_limit | |
| 15 | daily_dm_limit | |
| 16 | cooldown_until | |
| 17 | last_error_msg | |

---

### 2. Instagram_Posts (25컬럼)

| # | 컬럼명 | 비고 |
|---|--------|------|
| 1 | insta_post_code | PK |
| 2 | source_feed_code_ref | FK → Source_Feeds |
| 3 | account_code_ref | FK → Account_Registry |
| 4 | vendor_code | |
| 5 | hashtag | |
| 6 | post_status | |
| 7 | moderation_status | |
| 8 | generated_image_asset | |
| 9 | scheduled_upload_at | |
| 10 | published_at | |
| 11 | post_url | |
| 12 | visibility_check | |
| 13 | last_error_msg | ⚠ error_message와 중복 |
| 14 | post_code | |
| 15 | caption copy | ⚠ caption 중복 의심 |
| 16 | source_url | |
| 17 | image_url | |
| 18 | price | |
| 19 | post_url copy | ⚠ post_url 중복 의심 |
| 20 | caption | |
| 21 | retry_count | |
| 22 | error_message | ⚠ last_error_msg와 중복 |
| 23 | ig_media_id | engagement_tracker 연동 |
| 24 | like_count | engagement_tracker 연동 |
| 25 | comments_count | engagement_tracker 연동 |

---

### 3. Lead_Interactions (16컬럼)

| # | 컬럼명 | 비고 |
|---|--------|------|
| 1 | interaction_code | PK |
| 2 | source_feed_code_ref | FK → Source_Feeds |
| 3 | insta_post_code_ref | FK → Instagram_Posts |
| 4 | account_code_ref | FK → Account_Registry |
| 5 | post_code | |
| 6 | inquiry_user_handle | |
| 7 | inquiry_message | |
| 8 | bridge_status | |
| 9 | lead_status | |
| 10 | conversation_channel | |
| 11 | response_delay_sec | |
| 12 | relay_scheduled_at | |
| 13 | replied_at | |
| 14 | last_error_msg | |
| 15 | lead_score | |
| 16 | lead_grade | |

---

### 4. Source_Feeds (15컬럼)

| # | 컬럼명 | 비고 |
|---|--------|------|
| 1 | source_feed_code | PK |
| 2 | external_source_type | |
| 3 | source_url | ⚠ source_url (URL)과 중복 |
| 4 | raw_content | |
| 5 | normalized_content | |
| 6 | processing_status | |
| 7 | processing_status = gpt_ready | ⚠ 컬럼명 오염 (수식 잔재) |
| 8 | account_code_ref | FK → Account_Registry |
| 9 | vendor_code | |
| 10 | source_url (URL) | ⚠ source_url과 중복 |
| 11 | insta_post_code_ref | FK → Instagram_Posts |
| 12 | ingested_at | |
| 13 | is_duplicate | |
| 14 | last_error_msg | |
| 15 | Instagram_Posts | ⚠ 컬럼명 오염 (Airtable 링크필드 잔재 의심) |

---

## 발견된 이슈 목록

| 우선순위 | 테이블 | 문제 컬럼 | 이슈 유형 | 조치 방향 |
|----------|--------|-----------|-----------|-----------|
| ~~P1~~ **완료** | Instagram_Posts | `error_message` | 중복 컬럼 | ✅ 삭제 확정 260526 — `last_error_msg` 로 통합 |
| ~~P1~~ **완료** | Instagram_Posts | `caption copy` | 중복 컬럼 | ✅ 삭제 확정 260526 — 코드 참조 0건 |
| ~~P1~~ **완료** | Instagram_Posts | `post_url copy` | 중복 컬럼 | ✅ 삭제 확정 260526 — 코드 참조 0건 |
| ~~P2~~ **완료** | Source_Feeds | `source_url (URL)` | 중복 컬럼 | ✅ 삭제 확정 260526 — 코드 참조 0건 |
| P2 **유지** | Source_Feeds | `processing_status = gpt_ready` | 컬럼명 오염 | 🔒 삭제 금지 — runtime 상태값 정상 사용 중 |
| P2 **유지** | Source_Feeds | `Instagram_Posts` | 컬럼명 오염 | 🔒 삭제 금지 — Airtable 링크필드 정상 관계 |

---

## 삭제 확정 필드 목록 (260526)

> 근거: `Select-String -Path "*.py" -Pattern ...` grep 전수조사 결과 코드 참조 0건 확인

### 삭제 대상 (Airtable에서 직접 삭제 가능)

| 테이블 | 필드명 | 판정 근거 | 확정일 |
|--------|--------|-----------|--------|
| Instagram_Posts | `caption copy` | 코드 참조 0건 — `caption` 중복 孤兒 필드 | 260526 |
| Instagram_Posts | `post_url copy` | 코드 참조 0건 — `post_url` 중복 孤兒 필드 | 260526 |
| Instagram_Posts | `error_message` | 코드 참조 0건 — `last_error_msg` 로 통합, 로컬 변수로만 존재 | 260526 |
| Source_Feeds | `source_url (URL)` | 코드 참조 0건 — `source_url` 중복 孤兒 필드 | 260526 |

---

## 삭제 금지 필드 (260526 확정)

| 테이블 | 필드명 / 값 | 사유 |
|--------|-------------|------|
| Source_Feeds | `processing_status` 값: `gpt_ready` | `airtable_autorun_engine.py:152`, `pipeline_feed_ingest.py:437,468,486` — 정상 runtime 상태값. 절대 삭제 금지 |
| Source_Feeds | `Instagram_Posts` 링크필드 | Airtable 테이블 간 연결 관계 필드 — 절대 삭제 금지 |

---

## 변경 이력

| 날짜 | 변경 내용 | 담당자 |
|------|-----------|--------|
| 2026-05-16 | 최초 작성 — 현재 상태 기록 | galaxyjo |
| 2026-05-26 | 孤兒 필드 삭제 확정 — grep 전수조사 기준 (Instagram_Posts 3건, Source_Feeds 1건) | galaxyjo |
