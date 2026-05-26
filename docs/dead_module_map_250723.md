# Dead Module Map — 250723 (Reference Repository)

분석 기준: `insta_scheduler.py` / `launcher/main.py` / `tools/run_production.py` 복수 진입점 기점  
도구: `ast.walk()` 기반 정적 분석 (`_fixed.py` · `backup_auto_fixes/` · `z_trash/` 제외)  
대상 경로: `C:\SNS_24AutoProject_250723`

> ⚠️ 이 저장소는 Reference Only — 실행·배포 금지. 코드 이식 시 manual review 필수.

---

## 요약

| 구분 | 수량 |
|------|------|
| 전체 .py 파일 (`_fixed.py` · 제외 디렉토리 제외) | 544개 |
| Reachable (3개 진입점 합산) | 5개 |
| Dead (미참조) | 539개 |
| Broken Import (참조 대상 미존재) | 1건 |
| `_fixed.py` 자동생성 쌍 (별도 분류) | 약 512개 |

**Dead 비율: 99%.** 250723은 설계·프로토타입 저장소로, 모듈 간 연결이 거의 없는 상태.

---

## Import Graph — 진입점 기점

### 진입점 1 — `insta_scheduler.py` (실제 SNS 파이프라인)

```
insta_scheduler
+-- modules.common.airtable_bridge    ✅ 존재
L-- modules.sns.facebook_crawler      ❌ 250723에 미존재 (260511에서 신규 작성)
```

**핵심 문제**: `modules/sns/facebook_crawler.py`가 250723에 없음.  
`insta_scheduler.py`는 실행 불가 상태. 260511의 `facebook_crawler`는 이 저장소를 참조하지 않고 독자 구현됨.

---

### 진입점 2 — `launcher/main.py` (프로토타입)

```
launcher.main
    (imports: account_runner)    ❌ 프로젝트 내 .py 파일 미존재
```

`account_runner`는 `logs/account_runner.log` (로그 파일)만 존재. Python 모듈 없음.  
`launcher/main.py`는 실행 불가 상태.

---

### 진입점 3 — `tools/run_production.py` (고도화 시도)

```
tools.run_production
L-- modules                    (패키지 마커만 resolve됨)
    modules.log_trace          ❌ 미존재 (log_trace_fixed.py만 있음)
    modules.account_runner     ❌ 미존재
```

`modules.log_trace`와 `modules.account_runner` 모두 미존재. 실행 불가.

---

### Broken Import 목록

| 출발 모듈 | 참조 대상 | 상태 |
|-----------|-----------|------|
| `launcher.main` | `account_runner` | ❌ .py 없음 (log 파일만 존재) |

---

## Dead Module 분류

### A. SNS 핵심 모듈 — 250723 설계 산출물 (미연결)

260511로 이식 검토 시 수동 review 필요한 모듈군.

| 모듈 | 비고 |
|------|------|
| `modules.sns.uploader_instagram` | Instagram 업로더 (260511 dead 목록과 동일 파일) |
| `modules.sns.pipeline_feed_ingest` | FB→Instagram 파이프라인 (676L, 260511에도 dead) |
| `modules.sns.insta_dm_sender` | DM 발송 |
| `modules.sns.bot_*` (19개) | Instagram bot 동작 모듈군 (follow/like/comment 등) |
| `modules.sns.wf_instagram_scheduler` | 워크플로 설계 문서 (코드 없음, 주석만) |
| `modules.dm.*` (21개) | DM 봇·라우터·상태머신·큐 모듈군 |
| `modules.common.airtable_bridge` | ✅ 유일하게 reachable — 260511과 공유 |
| `modules.common.airtable_autorun_engine` | 미연결 (260511에도 dead) |

---

### B. 유틸리티 모듈 대량 축적 (공통 기능 중복)

`modules/common/` 하위에 150개 이상의 유틸 모듈 존재.  
`common_3` ~ `common_35`, `_io_common_1`, `_mapping_04f7dcdb` 등 자동생성/복사 패턴.  
260511은 이 중 `airtable_bridge` 1개만 사용.

---

### C. 독립 실행 스크립트 (정상 — import 대상 아님)

| 분류 | 파일 수 | 예시 |
|------|---------|------|
| `scripts/export_*.py` | 60개+ | 로그 내보내기 스크립트 |
| `scripts/verify_*.py` | 다수 | 세션 무결성 검증 |
| `db/insert_*.py` / `db/init_*.py` | 20개+ | DB 초기화·삽입 |
| `validator/check_*.py` | 16개 | 로그 검증 |
| `tests/test_*.py` | 120개+ | pytest (대부분 _fixed 쌍) |
| `tools/e2e_*.py` | 7개 | E2E 시나리오 스크립트 |
| `tools/fix_*.py` | 10개 | 코드 자동 수정 도구 |
| `reports/gen_exports*.py` | 3개 | 리포트 생성 |

---

### D. 기타 Dead

| 모듈 | 비고 |
|------|------|
| `core.run_engine` | `trio` async 타입 체크 테스트 코드 — SNS 파이프라인과 무관 |
| `core.task_router` | 40L, 내용 불명 |
| `core.add_docstrings` | docstring 자동 추가 도구 |
| `modules.interaction_engine` | `__init__.py`만 존재 (실제 코드 없음) |
| `modules.notifier.*` | email/kakao/line/telegram 알림 (5개, 260511에서 Slack으로 대체) |
| `modules.pipeline.feed_pipeline` | 미연결 피드 파이프라인 |
| `modules.metrics.collector` | KPI 수집기 초기 버전 |
| `modules.transformer.content_mapper` | 콘텐츠 변환기 |
| `patch`, `rand_util_core`, `type_util` | 루트 레벨 유틸 |
| `get-pip` | pip 설치 스크립트 |

---

## 260511과 250723 비교

| 항목 | 260511 (Active) | 250723 (Reference) |
|------|-----------------|---------------------|
| 총 .py 파일 | 83개 | 1,056개 (fixed 포함) / 544개 (fixed 제외) |
| Reachable | 27개 (33%) | 5개 (1%) |
| Dead | 56개 | 539개 |
| 실제 진입점 | `launcher/main.py` ✅ 동작 | `insta_scheduler.py` ❌ 실행불가 |
| Instagram 업로더 | main.py 80줄 인라인 | `uploader_instagram.py` (dead) |
| facebook_crawler | ✅ 구현됨 | ❌ 미존재 |
| Airtable bridge | ✅ reachable | ✅ reachable (유일) |
| `_fixed.py` 쌍 | 없음 | 약 512개 |
| 통보 체계 | Slack (구현됨) | email/kakao/line (dead) |

---

## 이식 가능성 평가

250723 → 260511 이식 시 실질 검토 대상:

| 모듈 | 이식 가치 | 비고 |
|------|-----------|------|
| `modules.dm.rules` | ⭐ 중간 | DM 응답 규칙 설계 참조 가능 |
| `modules.dm.state_machine` | ⭐ 중간 | 상태머신 설계 참조 |
| `modules.sns.bot_comment` | ⭐ 낮음 | 260511 comment_auto_reply로 대체됨 |
| `modules.common.airtable_bridge` | ✅ 동일 | 두 저장소 공유, 이식 불필요 |
| `modules.sns.uploader_instagram` | ❌ 불필요 | 260511 main.py 인라인으로 대체됨 |
| `modules.notifier.*` | ❌ 불필요 | Slack으로 충분 |
| `modules.common.common_*` (35개) | ❌ 불필요 | 자동생성 중복 유틸 |

> 결론: 250723에서 260511로 이식할 실질적 코드 없음.  
> 설계 참조(DM rules, state_machine) 정도만 활용 가능.  
> 자동 이식 금지 — CLAUDE.md 준수.
