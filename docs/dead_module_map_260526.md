# Dead Module Map — 2026-05-26

분석 기준: `launcher/main.py` 기점 AST import graph 전수 추적  
도구: `ast.walk()` 기반 정적 분석 (함수 내 lazy import 포함)  
백업: `C:\backup_(4)_260526_1544_phase3_before_merge.zip`

---

## 요약

| 구분 | 수량 |
|------|------|
| 전체 .py 파일 (snapshots·.venv 제외) | 83개 |
| Reachable (launcher.main 기점) | 27개 |
| Dead (미참조) | 56개 |

---

## Import Graph — launcher.main 기점

```
launcher.main
├── core.error_handler
│   └── modules.common.logger
├── core.log_initializer
│   └── modules.common.logger [*]
├── modules.common.health_monitor
│   ├── modules.common.crawl_url_checker
│   │   ├── modules.common.account_manager
│   │   │   └── modules.common.logger [*]
│   │   ├── modules.common.logger [*]
│   │   └── services.slack_notifier
│   │       └── modules.common.logger [*]
│   └── modules.common.logger [*]
├── modules.common.logger [*]
├── modules.common.retry_queue
│   └── modules.common.logger [*]
├── modules.dm.dm_receiver
│   ├── modules.comment.comment_auto_reply
│   ├── modules.crm.lead_scorer
│   │   └── modules.common.logger [*]
│   ├── modules.crm.order_detector
│   │   └── modules.common.logger [*]
│   ├── modules.dm.dm_auto_reply
│   │   ├── modules.dm.ai_reply_generator
│   │   ├── modules.dm.dm_followup_scheduler
│   │   │   ├── modules.comment.comment_poller
│   │   │   │   └── modules.comment.comment_auto_reply [*]
│   │   │   ├── modules.crm.daily_report
│   │   │   │   └── services.slack_notifier [*]
│   │   │   ├── modules.common.retry_queue [*]
│   │   │   └── modules.common.logger [*]
│   │   ├── modules.common.retry_queue [*]
│   │   └── modules.common.logger [*]
│   └── modules.dm.dm_followup_scheduler [*]
├── modules.interaction_engine.interaction_scheduler
│   ├── modules.interaction_engine.auto_liker
│   │   └── modules.common.airtable_bridge
│   ├── modules.interaction_engine.engagement_tracker
│   │   └── modules.common.airtable_bridge [*]
│   └── modules.common.logger [*]
├── modules.metrics.kpi_collector
│   ├── modules.common.airtable_bridge [*]
│   └── modules.common.retry_queue [*]
├── modules.sns.facebook_crawler
│   ├── modules.common.account_manager [*]
│   ├── modules.common.airtable_bridge [*]
│   ├── modules.metrics.crawl_monitor
│   └── modules.sns.caption_generator
└── services.slack_notifier [*]

[*] = 이미 출력된 노드 (재귀 생략)
```

---

## Dead Module 분류

### A. __init__.py 패키지 마커 (정상 — 삭제 불가)

import 대상이 아닌 패키지 선언 파일. 삭제 시 import 경로 파괴.

`adapters.legacy_bridge` / `configs` / `core` / `data` / `launcher` / `launcher.scheduler` /
`modules` / `modules.avatar` / `modules.comment` / `modules.common` / `modules.crm` /
`modules.dm` / `modules.interaction_engine` / `modules.metrics` / `modules.sns` /
`modules.trade` / `services` / `tests` / `tools` / `tools.integrity`

---

### B. 독립 실행 스크립트 (정상 — import 대상 아님)

| 경로 | 용도 |
|------|------|
| `dashboard.py` | Streamlit 대시보드 (별도 프로세스 실행) |
| `run_e2e_manual.py` | 수동 E2E 점검 스크립트 |
| `db/init_instagram_db.py` | DB 초기화 (1회성) |
| `db/migrate_airtable_instagram.py` | DB 마이그레이션 |
| `db/migrate_state_machine.py` | DB 마이그레이션 |
| `logs/check_airtable.py` | Airtable 연결 점검 |
| `logs/check_e2e.py` | E2E 파이프라인 점검 |
| `logs/check_followup_result.py` | 팔로업 결과 확인 |
| `logs/check_qualified.py` | 리드 자격 확인 |
| `logs/find_page.py` | 페이지 탐색 |
| `logs/show_schema.py` | 스키마 출력 |
| `logs/test_autoreply.py` | 자동응답 테스트 |
| `logs/test_followup.py` | 팔로업 테스트 |
| `logs/test_real_send.py` | 실제 DM 발송 테스트 |
| `tests/test_smoke_common.py` | smoke 테스트 |
| `tests/test_smoke_crawler.py` | smoke 테스트 |
| `tests/test_smoke_crm.py` | smoke 테스트 |
| `tests/test_smoke_metrics.py` | smoke 테스트 |
| `tools/add_instagram_posts_fields.py` | Airtable 필드 추가 (1회성) |
| `tools/check_account_registry.py` | Account_Registry 검증 |
| `tools/check_runtime_health.py` | 런타임 헬스 점검 |
| `tools/create_persona_profile_table.py` | Persona_Profile 테이블 생성 (1회성) |

---

### C. 대체 진입점 — 의도적 dead, 동기화 주의

| 경로 | 규모 | 설명 |
|------|------|------|
| `core/run_engine.py` | 266L | `launcher/main.py` 대체 진입점. `ngrok_monitor` + `airtable_integrity` 추가 wiring. main.py와 Job 구성이 **동기화되지 않은 상태** |
| `core/task_router.py` | 40L | run_engine 전용. main.py에서 미사용 |

**위험**: run_engine을 실행하면 main.py와 다른 Job set로 동작함. 두 파일 중 하나를 기준으로 정리 필요.

---

### D. 진짜 Dead — 검토 필요

| 경로 | 규모 | 문제 |
|------|------|------|
| `modules/sns/pipeline_feed_ingest.py` | **676L** | 내·외부 참조 0건. 프로젝트 최대 orphan 파일 |
| `modules/sns/insta_uploader.py` | 88L | 업로드 로직이 main.py:159-239에 80줄 인라인 구현됨 → 완전 우회 |
| `modules/sns/instagram_uploader.py` | 104L | 동일 사유. uploader 3중 중복 파일 중 하나 |
| `modules/sns/uploader_instagram.py` | 64L | 동일 사유. uploader 3중 중복 파일 중 하나 |
| `modules/sns/wf_instagram_scheduler.py` | 50L | 미참조 워크플로 스케줄러 |
| `modules/sns/bot_crawler.py` | 82L | `modules.cfg_loader` (존재하지 않는 모듈) 참조 — 구 버전 |
| `modules/sns/bot_uploader.py` | 57L | 구 버전 업로더 |
| `modules/common/parallel_runner.py` | 69L | 다계정 병렬 실행 구현됨, main.py에 미연결 |
| `modules/common/airtable_autorun_engine.py` | 216L | 내·외부 참조 전무 |
| `modules/common/ngrok_monitor.py` | 114L | run_engine에서만 참조 (run_engine 자체가 dead) |
| `modules/metrics/airtable_integrity.py` | 63L | run_engine에서만 참조 |
| `adapters/legacy_bridge/bridge_base.py` | 92L | 레거시 브릿지. 미사용 |

**D그룹 합계: 12개 파일, 약 1,675L**

---

## 핵심 이슈

### 이슈 1 — Instagram 업로더 3중 중복 + inline 구현

`insta_uploader.py` / `instagram_uploader.py` / `uploader_instagram.py` 3개(합계 256L)가 전부 dead.  
실제 업로드 로직은 `launcher/main.py:159-239`에 80줄 인라인 직접 구현.  
모듈 파일들과 실행 코드가 완전히 분리된 상태 — 모듈 수정이 runtime에 반영되지 않음.

### 이슈 2 — core/run_engine.py vs launcher/main.py 경쟁

두 파일이 동일한 역할(APScheduler + Flask + RetryQueue)을 하지만 Job wiring이 다름.

| 항목 | launcher/main.py | core/run_engine.py |
|------|------------------|--------------------|
| ngrok_monitor | ✗ | ✓ |
| airtable_integrity | ✗ | ✓ |
| 현재 실행 기준 | ✅ | ✗ |
| CLAUDE.md 언급 | ✅ | ✅ |

run_engine을 실수로 기동하면 main.py와 다른 동작이 발생할 수 있음.

---

## 처리 권고

| 우선순위 | 대상 | 조치 |
|----------|------|------|
| P1 | D그룹 12개 파일 | 삭제 검토 (특히 uploader 3중복 + pipeline_feed_ingest) |
| P2 | run_engine vs main.py | 기준 파일 1개 선택 후 나머지 폐기 또는 동기화 |
| P3 | parallel_runner | 다계정 전환 시 main.py에 wiring, 현재는 보류 |

> 수정 금지 — 이 문서는 분석 결과 기록 전용. 실제 삭제는 별도 단계에서 진행.
