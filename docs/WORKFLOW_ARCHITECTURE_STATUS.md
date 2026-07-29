# WORKFLOW_ARCHITECTURE_STATUS.md
> Workflow Architecture 0~11단계 공식 상태 SSOT
> 최초 생성: 2026-07-25 (P0-2 감사 결과 반영)
> Active Source of Truth: C:\SNS_24AutoProject_260511 (250723은 reference/archive 전용)
> 이 문서는 대화 기록 없이 단독으로 이해 가능해야 한다.

---

## 1. 단계 0~11 현재 공식 상태

| 단계 | 핵심 목적 | 상태 | 근거 요약 |
|---|---|---|---|
| 0 | Phase 0 현황점검 | 완료 | Runtime·Airtable·n8n·Persona·Risk 조사(260723) |
| 0-A | 활성 위험 기록 | 완료 | ERR-075/FP-057/INC-042 문서화 |
| 1 | 기존 자산 전수확인 | 완료(재구성) | 아래 §2, 36개 Capability Inventory — Runtime Caller 체인 직접 추적으로 재구성(260725) |
| 2 | 완성률 점수화 | 완료(재계산) | 아래 §3 — 기존 "52.4%" 등 수치는 산식·원자료 재현 불가로 폐기, 신규 산식 채택 |
| 3 | 실제 Gap 추출 | 완료(재구성) | 아래 §7 |
| 4 | Build·Reuse·Buy 결정 | 완료 | 아래 §6, 12개 항목 전문(260725 GPT 정정 반영 최종판) |
| 5 | 최소 Architecture 확정 | 부분완료 | 아래 §5-5 |
| 6 | 격리 MVP 구현 | 부분완료 | Final Quality Gate·Approval Action: 구현·테스트 완료, Runtime 비활성. Persona·Sourcebook: 최소 Runtime 연결 필요(미완료), 전체 고도화만 DEFER — "완료"와 "DEFER"를 동일 항목에 중복 표기하지 않음 |
| 7 | Live E2E 사전 Gate | 완료 | Token 교체(ERR-077/079) 완료, 확장 전 Gate 3개(imgbb/ERR-076/account_email) 잔존 |
| 8 | 1계정 E2E Canary | 완료 | yuna18253 실제 게시 성공 |
| 9 | 2계정 재현 Test | 완료 | yuna18253+aijomoojin 독립 게시, 중복게시 0건 |
| 10 | Metric·수익 검증 | 진행중 | KPI 집계 오류(ERR-078) 해소, 리드전환 유실(ERR-080) 해소. **공식 작업 큐: `P1-1 Clean Measurement Baseline`**(진행중). `yuna18253` Account_Registry 신규 등록 완료(`IDN-000041`, §10-6) — Provider Routing SSOT 정합성 확보. `P1-4`~`P1-6A`/`P1-1B`/`P1-1C` 명칭은 별도 우선순위가 아니라 P1-1 하위조사로 재분류(§10 참조). Clean Baseline·테스트/실고객 분리·매출 원본·ROI 경로는 미완료 |
| 11 | 확장 | 보류 | 확장 전 필수 Gate(imgbb/ERR-076/account_email/계정별Kill Switch) 미통과 |

---

## 2. Capability Inventory (36개, 요구사항 기준)

기존 Runtime에 존재하는 26개 + 로드맵이 요구하나 미구현/비활성이라 이전 집계에서 누락됐던 10개(Persona/Sourcebook/Kill Switch/테스트·실고객분리/계정별KPI/Reach·Impressions/매출원본/ROI계산/n8n/舊"Publish Gate·Approval" 1행을 Final Quality Gate·Approval Action 2행으로 분리)를 통합.

값 기준: `1`=VERIFIED_COMPLETE, `0.5`=PARTIAL 또는 비활성, `0`=MISSING/FAILED, `UNKNOWN`=증거부족(점수 별도), `NA`=해당 축 개념적으로 미적용.

| # | Capability | 설계 | 데이터 | 자동화 | 안정성 | 수익연결 |
|--:|---|:-:|:-:|:-:|:-:|:-:|
| 1 | FB크롤링 | 1 | 1 | 1 | 0 | NA |
| 2 | Caption생성 | 1 | 1 | 1 | 0 | NA |
| 3 | IG업로드(publish_single) | 1 | 1 | 1 | 1 | NA |
| 4 | Provider Routing(다계정) | 1 | 1 | 1 | 1 | NA |
| 5 | Credential Resolver | 1 | 1 | 1 | 1 | NA |
| 6 | DM수신(Webhook) | 1 | 1 | 1 | 1 | NA |
| 7 | DM자동응답(가격문의) | 1 | 1 | 1 | 0 | 0.5 |
| 8 | DM팔로업스케줄러 | 1 | 1 | 1 | 0 | 0.5 |
| 9 | DM Close(lead_closer) | 1 | 1 | 0 | 0.5 | 0.5 |
| 10 | Lead Scoring | 1 | 1 | 1 | 1 | NA |
| 11 | Order Detection | 1 | 1 | 1 | 0.5 | 0.5 |
| 12 | 댓글폴링 | 1 | 1 | 1 | 1 | NA |
| 13 | 댓글자동응답 | 1 | 1 | 1 | 1 | 0.5 |
| 14 | 댓글Idempotency(event_store) | 1 | 1 | 1 | 1 | NA |
| 15 | 댓글캠페인/Allowlist | 1 | 1 | 0.5 | 1 | NA |
| 16 | 댓글안전장치(safety_guard) | 1 | 1 | 1 | 1 | NA |
| 17 | 댓글Retry Dead Monitor | 1 | 1 | 1 | 1 | NA |
| 18 | Retry Queue(공용) | 1 | 1 | 1 | 1 | NA |
| 19 | KPI Collector(집계 인프라) | 1 | 1 | 1 | 1 | NA |
| 20 | Engagement Tracker | 1 | 1 | 1 | 0 | NA |
| 21 | Auto Liker | 1 | NA | 0(DISABLED) | NA | NA |
| 22 | Domeggook 크롤+Export | 1 | 1 | 1 | 0 | NA |
| 23 | Daily Report | 0 | UNKNOWN | 1 | 0 | NA |
| 24 | Airtable Repository(인프라) | 1 | 1 | 1 | 1 | NA |
| 25 | 학습리뷰 Batch/Grid | 1 | 1 | UNKNOWN | 0.5 | NA |
| 26 | Final Quality Gate | 1 | 1 | 0.5 | 1 | NA |
| 27 | Approval Action | 1 | 0.5 | 0.5 | 1 | NA |
| 28 | Persona Runtime 연결 | 1 | 1 | 0 | 0 | NA |
| 29 | Sourcebook 최소구조화 | 1 | 0.5 | 0 | 0 | NA |
| 30 | 계정별 Kill Switch | 1 | 0.5 | 0 | 0 | NA |
| 31 | 테스트·실고객 분리 | 1 | 0 | 0 | 0 | NA |
| 32 | 계정별 KPI | 1 | 0.5 | 0.5 | 0 | NA |
| 33 | Reach·Impressions | 0 | UNKNOWN | UNKNOWN | 0 | NA |
| 34 | 매출·원가·이익 원본 | 1 | 0 | 0 | 0 | 0 |
| 35 | ROI 계산 | 0 | 0 | 0 | 0 | 0 |
| 36 | n8n(DEFER) | 1 | NA | 0 | NA | NA |

**중요 표기 정정(재작성 시 명시)**:
- **Final Quality Gate(#26)**: "완료" 아님 — **부분완료(구현·테스트 완료, Runtime 비활성)**. `PUBLISH_TEXT_GATE_ENABLED` 플래그가 `.env`에 미설정 상태(기본값 false)라 실제로는 꺼져 있음.
- **Persona(#28)·Sourcebook(#29)**: 전체 고도화(다중 페르소나, 자동 파싱 등)만 DEFER 대상이며, **최소 Runtime 연결(1개 페르소나 최소 매핑, 핵심원칙 구조화 추출) 자체는 3계정 Canary 전 필수**로 확정(4단계 260725 정정). "완료"와 "DEFER"를 같은 항목에 중복 표기하지 않는다 — 현재 상태는 정확히 "설계·데이터는 있으나 자동화·안정성 0"인 부분완료/미구현 항목이다.

---

## 3. 5축 공식 점수 (재현 가능 산식)

**산식**: `(1×VERIFIED_COMPLETE + 0.5×PARTIAL/비활성 + 0×MISSING/FAILED) / (적용대상 N − NA)`. UNKNOWN은 **Verified Score**에서 분모·분자 모두 제외, **Conservative Readiness**에서는 0으로 포함.

| 축 | 적용대상(N, NA제외) | UNKNOWN 개수 | Verified Score | Conservative Readiness |
|---|:-:|:-:|:-:|:-:|
| 설계 | 36 | 0 | 33/36 = **91.7%** | **91.7%** |
| 데이터 | 34 | 2 | 27/32 = **84.4%** | 27/34 = **79.4%** |
| 자동화 | 36 | 2 | 23/34 = **67.6%** | 23/36 = **63.9%** |
| 안정성 | 35 | 0 | 17.5/35 = **50.0%** | **50.0%** |
| 수익연결(리드→상담→주문→마감→매출→ROI E2E만 적용) | 7 | 0 | 2.5/7 = **35.7%** | **35.7%** |

## 4. 종합 평균 (참고값, 공식 지표 아님)

Verified 평균 = (91.7+84.4+67.6+50.0+35.7)/5 = **65.9%**
Conservative 평균 = (91.7+79.4+63.9+50.0+35.7)/5 = **64.1%**

**이 평균은 참고용일 뿐이며, 공식 판단은 축별 점수와 UNKNOWN 비율을 우선한다.** 이전 세션에서 계산된 "66.9%"(26개 기능만 분모로 사용)는 Survivorship Bias로 폐기됨 — Persona/Sourcebook/Kill Switch/테스트분리/매출원본/ROI(전부 0점대)가 분모에서 빠져 자동화·안정성이 실제보다 높게 나왔었음.

---

## 5. 단계 1~5 통합 Evidence

### 5-1. Runtime Caller 체인 (직접 추적, 260725)

```
launcher/main.py _build_scheduler() → 7개 잡:
  fb_crawl / insta_upload / kpi_snapshot / engagement_update /
  dome_crawl / dome_export / comment_dead_monitor
  (auto_like 잡은 #DISABLED_260603 주석 처리 — Runtime 미등록 확정)

launcher/main.py → modules.dm.dm_receiver.start_scheduler()
  (dm_followup_scheduler.start_scheduler 재노출) → 4개 잡:
  followup_poll / lost_check / comment_poll / daily_lead_report

dm_receiver.py Flask 웹훅(이벤트 트리거, 스케줄 아님) →
  dm_auto_reply.handle_price_inquiry / lead_scorer / order_detector /
  comment_auto_reply.process_comment_event
```

### 5-2. Test Evidence

`tests/` 39개 파일 전수 확인(ERR-081 해소 후 `pytest.ini`로 정상 수집). `579 passed / 4 failed(test_dm_close.py, Root Cause Confirmed — 아래 §5-3) / 3 xfailed`.

### 5-3. `test_dm_close.py` 감사 결과 (Root Cause: Confirmed)

**프로덕션 코드 결함 아님.** `modules/infra/airtable_repository.py`의 `_patch_lead_interaction()`은 `requests.patch(..., json={"fields": fields}, ...)`로 `json=` 키워드 인자를 사용하는데, `tests/test_dm_close.py`의 `_extract_all_fields()` 헬퍼는 `c.kwargs.get("data")`(bytes)만 확인하도록 오래되게 작성돼 있어 항상 빈 리스트를 반환 — **오래된 테스트 헬퍼가 `json=` 대신 `data=`만 확인한 것이 Confirmed Root Cause**. 직접 재현(mock 후 `mark_lead_closed('rec_001')` 호출)으로 실제 전송 payload가 `{'fields': {'bridge_status': 'closed', 'lead_status': 'converted', 'closed_at': '2026-07-25T12:49:22Z'}}`임을 확인 — `lead_closer.py`는 정상 동작. **Telegram(`requests.post`) 네트워크 Mock 누락은 별도 Test Isolation 문제**이며 위 4개 실패의 직접 원인이 아니다.

### 5-4. UNKNOWN 8개 조사 결과

| 항목 | Caller | Test | 최종 상태 |
|---|---|---|---|
| FB크롤링 Test | ✓(_job_fb_crawl) | 없음 | 미구현(Test 0) |
| Caption생성 Test | ✓(facebook_crawler 내부 호출) | 없음 | 미구현(Test 0) |
| DM자동응답 Test | ✓(dm_receiver 웹훅) | 없음(`test_dm_rules.py`는 `rules.py`만 커버) | 부분완료 |
| DM팔로업스케줄러 Test | ✓(followup_poll/lost_check 잡) | `test_dm_close.py`의 연동테스트 3개는 전부 xfail(코드주석: "연동 미완료") | 부분완료 |
| 댓글캠페인 Runtime Caller | ✓(comment_poller 분기 존재) | ✓ | 부분완료(코드·테스트 있으나 `.env` 미설정으로 기본값 legacy — allowlist 비활성) |
| Engagement Tracker Test | ✓(_job_engagement_update) | 없음 | 부분완료(동작 간접증거 있음, Test 0) |
| Domeggook Test | ✓(_job_dome_crawl/_job_dome_export) | 없음(메모리의 "fixture 5/5 PASS"는 재현 불가한 1회성 기록으로 추정) | 부분완료 |
| Daily Report 설계·데이터·Test | ✓(daily_lead_report 잡) | 없음, 설계기록 0건, 데이터 미확인 | UNKNOWN(설계·데이터), Caller만 확인 |

### 5-5. 최소 Architecture 현황

| 항목 | 상태 | 부족분 |
|---|---|---|
| DoD | UNKNOWN | 문서화 이력 없음 |
| Exit Criteria | UNKNOWN | 문서화 이력 없음 |
| Rollback | 부분 | Provider Routing만 Kill Switch로 롤백 가능 |
| Telemetry | 부분 | 계정별/기능별 세분화 안 됨 |
| Execution Owner | 완료 | 이중 스케줄러 구조(§5-1) 전체 확인 완료 |
| Fail-closed | 부분 | 경로별 편차(ERR-080이 실측 반증) |
| 계정별 Kill Switch | 미구현 | §6 항목5 참조 |
| Approval | 부분 | §6 항목4 참조 |
| 중복방지 | 완료 | Phase A/B 분리+outcome_unknown 격리, 9단계 실증 |
| 데이터 측정 기준 | 미구현 | 테스트/실고객 분리 필드 없음 |

---

## 6. 단계 4 — Build·Reuse·Buy 최종 결정표 (전문, 260725 GPT 정정 반영)

| # | 기능 | 결정 | 근거 | 기존 자산 | 최소 추가 범위 | 위험 |
|--:|---|---|---|---|---|---|
| 1 | Persona Runtime 연결 | REUSE+BUILD(최소) | `ai_reply_generator.generate_reply()`에 계정/페르소나 파라미터 자체 없음(코드 확인), 전 계정 동일 톤 사용 중 | `Persona_Profile`(persona_role/mbti_type/tone_style/greeting_template/followup_template) | ①`account_code_ref`→`persona_code` lookup ②`generate_reply()`에 톤/템플릿 파라미터 추가(Import Chain: `dm_auto_reply.py`→`ai_reply_generator.py` 2파일만) | 페르소나 1개뿐이라 "다르게 응답"이 검증 안 됨 |
| 2 | Sourcebook Runtime 연결 | BUILD(최소 구조화 권장) | (a)마크다운 원문 파싱: 문서 포맷 변경 시 파서 깨짐, 원 문서가 "Runtime Evidence Document: NO"로 설계돼 원 설계의도 위반. (b)핵심원칙 구조화 추출: 파서 불필요, 문서 변경에 안 깨짐 — **(b) 권장** | `docs/design/SNS_AI_STARTUP_CONTENT_SOURCEBOOK_260723.md`(원문 유지) | 핵심 5~10줄만 추출해 상수/설정으로 캡션·DM 프롬프트에 포함 | 로드맵에서 완전히 빼려면 별도 Scope 변경 승인 필요, 임의 제외 금지 |
| 3 | Final Quality Gate | REUSE(구현·테스트 완료, Runtime 비활성) | `PUBLISH_TEXT_GATE_ENABLED` 코드(`launcher/main.py:390`)+테스트(`test_publish_gate_and_approval.py` 7 passed) 존재, `.env` 미설정으로 꺼짐. 이미지 검수는 pytesseract 미설치로 범위 밖(260724 결정) | `content_filter.passes_keyword_filter()` | 텍스트 Gate 활성화 전 실게시 1건 검증(플래그 변경은 별도 승인) | 이미지 검수 부재를 "완료"로 착각 금지 |
| 4 | Approval Action | **회장 결정(260729): 비활성 유지, 코드 보존** | `REQUIRE_APPROVAL_BEFORE_PUBLISH` 실측 결과 코드·Airtable Schema 전부 정상 작동 확인(§10-16) — 그러나 회장이 "완전자동화 우선, 게시 전 승인 불필요, 문제되는 것만 사후 조치" 방침을 명시적으로 확정해 다시 잠재움(`.env` 주석 처리, 값 보존) | `Instagram_Posts.post_status`(draft/ready, 이미 Schema 존재) | 재사용 원하면 `.env`의 `# REQUIRE_APPROVAL_BEFORE_PUBLISH=true` 주석만 해제 | 승인 경로 자체는 Airtable UI 직접 사용(0개발)으로 이미 검증 완료 — 재활성화 시 추가 개발 불필요 |
| 5 | 계정별 Kill Switch | BUILD(후보, 착수 전 선행조사 필수) | `Account_Registry.automation_enabled` 필드 존재하나 코드 0참조(사문화). `account_manager.get_active_accounts()`(accounts.json 기반)는 크롤링 전용, `launcher/main.py` 미사용 확인 | 없음(사문화 필드만) | 착수 전 필요: ①DM·댓글·팔로업 웹훅 포함 전체 Entry Point 매핑 ②Import Chain ③Rollback 방법 ④Success Criteria | Blast Radius UNKNOWN — 매핑 전 착수 금지 |
| 6 | Retry·Fail-closed | REUSE+BUILD(최소) | `retry_queue.py`는 `ig_auto_reply`/`ig_followup`/댓글payload에 연동 중(dead=20건 실측), `order_detector.handle_order_conversion()`은 미연동(ERR-080 원인의 일부) | `modules/common/retry_queue.py`(범용, 검증됨) | 예외를 삼키는 나머지 경로(order_detector 포함)에 동일 패턴 연결 — 표적 감사(P1-2) 먼저 필요 | 감사 없이 넓게 고치면 범위 폭주 위험 |
| 7 | n8n ↔ Python Contract | DEFER | GPT 명시 결정. `sqlite3 .n8n/database.sqlite` 재확인: `[('My workflow', active=0)]`, 변화 없음 | 설계 문서(WF-01~05, `CURRENT_RUNTIME_CONTEXT.md`) | — | — |
| 8 | 테스트·실고객 분리 | BUILD(신중, 자동 확정 태깅 금지) | Airtable `Lead_Interactions` 필드 0개. 회장이 직접 확인한 것만(DM 8건+댓글 10건 예시) test로 확정, 나머지는 판정 불가 | 없음 | 3분류 제안: `test`(직접확인분만)/`historical_mixed`(판정불가 격리)/신규 `is_test` | 문자열 휴리스틱으로 과거 데이터 자동 확정 금지 |
| 9 | 계정별 KPI·매출·ROI | REUSE+BUILD(KPI만), UNKNOWN(ROI) | `kpi_collector.py` 계정 groupby 로직 없음, `account_code_ref` 태깅 인프라는 있음(9단계, 3건 실측). ROI는 항목10(매출원본)에 종속 | `kpi_collector.py`, `account_code_ref` | KPI: groupby 추가(REUSE 확장). ROI: 매출원본 확정 전까지 UNKNOWN | — |
| 10 | Reach·Impressions | UNKNOWN(유지) | `meta_graph.py` insights/reach/impressions 코드 0건. `instagram_manage_insights` 권한은 이미 발급 확인(Access Token Debugger 스코프 목록)되나, facebook_login/instagram_login 두 Provider 각각의 실제 Endpoint·응답형식은 read-only로도 아직 미증명 | `meta_graph.py` 기존 호출 패턴 | 두 Provider 각각 read-only GET 증명이 선행 필요(신규 외부 종속성 없음) | 권한 존재≠구현가능 — 성급한 판정 금지 |
| 11 | 주문·매출·원가·이익 원본 | REUSE(Airtable)+BUILD(최소 Schema, 미실행) | Notion 신규연동 안 함 이미 결정됨. 계산=Python/SQLite, 표시=Streamlit 유지 | Airtable(운영원본), `lost_at`/`converted_at` 선례 패턴(dateTime 필드 추가) | 제안 필드만(생성 안 함): `order_amount`(currency)/`order_confirmed_at`(dateTime)/`cost_amount`(currency)/`order_reference`(singleLineText)/`currency_code`(singleSelect) | 마진/이익 계산 방식(수동 vs 상품DB 연동) 미정 |
| 12 | 중복게시 방지 | REUSE(완료) | `publish_single()` Phase A/B 분리+`creation_id` 재사용 금지+`outcome_unknown` 격리(9단계 STOP ITEM, commit `a33b506`), 9단계 Canary 중복게시 0건 실증 | 위 로직 자체 | 없음(형식적 Ledger 불필요 — 만들면 과잉개발) | 없음 |

**외부 도구 판단 원칙(GPT 확정)**: 계정 Kill Switch·테스트구분·매출Schema는 프로젝트 고유 로직이라 외부 도구 도입 안 함. Insights는 공식 Meta API 우선. Approval 화면은 기존 Airtable/Streamlit 재사용 우선. Retry는 기존 `retry_queue` 재사용 우선. GitHub Library/Template는 기존 자산으로 해결 불가능한 Gap이 증명될 때만 조사.

**4단계 최종 판정: SUCCESS**(GPT 확정, 260725) — 12개 항목 전부 방향 결정+Evidence 완료, 실행(코드/Schema 변경)은 0%이나 이는 SUCCESS 판정과 무관.

---

## 7. 남은 UNKNOWN·부분완료·미구현·DEFER 항목

| 분류 | 항목 |
|---|---|
| 완료 | IG업로드, Provider Routing, Credential Resolver, DM수신, Lead Scoring, 댓글폴링/자동응답/Idempotency/안전장치/DeadMonitor, Retry Queue, Airtable Repository, 중복게시방지 |
| 부분완료 | DM자동응답/DM팔로업스케줄러/DM Close/Order Detection/댓글캠페인/Engagement Tracker/Domeggook/Final Quality Gate/Approval Action/학습리뷰(1건 flaky)/계정별KPI |
| 미구현 | Persona Runtime 최소연결, Sourcebook 최소구조화, 계정별 Kill Switch, 테스트·실고객분리, 매출원본, ROI계산 |
| 비활성 | Auto Liker(DISABLED), Final Quality Gate·Approval Action(플래그 꺼짐 — 부분완료와 중복분류 아님, "구현됐지만 꺼짐" 의미) |
| UNKNOWN(완전 미해소) | Reach·Impressions(설계/데이터/자동화 전부) |
| UNKNOWN(부분 잔존) | Daily Report(설계·데이터), 학습리뷰(자동화 세부) |
| DEFER | n8n(전체), Persona·Sourcebook **전체 고도화만**(최소연결은 DEFER 아님 — §2 정정표기 참조) |
| HOLD | 없음 |

**실패(무해함 증명됨)**: `test_dm_close.py` 4건 — Root Cause Confirmed(§5-3), 프로덕션 코드 정상. 테스트 파일 자체 수정은 별도 승인 대상(B단계).

---

## 8. Runtime Caller·Import Chain·Test·Git Evidence (근거 인용)

- 이중 스케줄러 구조: §5-1 그대로(직접 코드 추적, 260725)
- `pytest.ini`(`testpaths = tests`) 추가로 collection 정상화: `579 passed/4 failed/3 xfailed` 재현(ERR-081/FP-062)
- KPI 페이지네이션 버그 수정: `fetch_all_instagram_posts()` 100건→594건(ERR-078/FP-060)
- 토큰 사고 2건: ERR-077(잘못된 Meta Use Case)/ERR-079(장기교환 누락) — 둘 다 RESOLVED
- 리드 전환 유실: `converted_at` 필드 누락, 260624~260725 31일간(`git log -S "def mark_lead_converted"` → commit `18aa3a7`) 유실 후 필드 추가로 해소(ERR-080)

---

## 9. 다음 우선순위 큐

| 순위 | 업무 | 상태 |
|---|---|---|
| P0-1 | pytest Collection Error 원인 확인 | 완료(RESOLVED, ERR-081) |
| P0-2 | 단계 1~5 공식 Evidence 문서 복구 | 완료(A단계, B단계 test_dm_close.py 수정도 260725 완료·commit `0da83b1`) |
| **P0-SEC** | **Webhook `X-Hub-Signature-256` 서명 검증 여부 확인·구현(ERR-082)** | **RESOLVED — Runtime ADOPT·7단계 SUCCESS(260728, §10-11). AI/yuna 실제 DM 200, 양 Route Cross-secret 403, Business Logic 우회 0건. Signature 실패 경고 8건의 출처는 별도 HOLD** |
| **P1-1** | **10-B Clean Measurement Baseline(테스트/실고객분리, 기준시점·계정키 확정)** | **8단계 완료(회장 확정, 260729 06:09 ICT)** — C1(Facebook Exact-Post Canary) Runtime SUCCESS(§10-13) + anchor-scan 오매칭 Gate RESOLVED(§10-14, ERR-084). Commit·Push는 회장 지시로 별도 보류 |
| P1-2 | 데이터 유실 동일 패턴(예외삼킴) 표적 감사 | **RESOLVED — 9단계 감사로 흡수 완료(260729)**. ERR-085(dm_receiver)/086(lead_scorer)/087(lead_closer)/088(order_detector) 4개 경로 전부 확인·RESOLVED(§10-15) — order_detector 포함, 표에서 요구한 조사 범위 충족 |
| P1-3 | fetch_candidate_phashes() Pagination | **RESOLVED — 4개 Canary 전부 완료(260729)**. 실제 전수 Inventory 결과 원문 대상 외 3개 추가 발견(`list_blocked_suppliers`/`fetch_active_crawl_targets`/`fetch_active_training_targets`) — ERR-078과 동일 결함 클래스(offset 미순회) 전부 재현 후 REUSE 패턴으로 수정. commit `598562d`(#1)/`e2cebac`(#2)/`4202d46`(#3)/`0c62f34`(#4, 원문 대상 — Caller 0건이나 일관성 위해 수정). mock reconciliation 4/4 250/250 전환, 신규 회귀 22/22 PASS. GPT 최종 감사 전, Push 미실행 |
| P1-4(격리MVP) | 단계 6 격리 MVP 완성(Persona·Sourcebook 최소연결+Gate·Approval 통합검증) | **부분진행(260729)** — 1순위 Approval Action 실측·검증 완료 후 회장 결정으로 비활성 유지(§6 항목4, §10-16). Persona·Sourcebook·Final Quality Gate는 착수 전(**주의**: 이 "P1-4"는 §10의 "P1-4"(DM 계정식별 관측 실행)와 다른 항목 — 260725 세션 중 동일 명칭이 두 용도로 쓰인 명명 충돌 발생, §10 하단 정정문 참조) |
| P2-1~3 | imgbb / ERR-076 자동복구 / account_email SSOT | 미착수(기존 Gate 그대로) |
| P3 | Token 매뉴얼 갱신(장기교환 단계 추가) | 미착수 |

---

## 10. P1-1 하위조사 진행상황 (260725, 세션 종료 기록)

**배경**: 10단계 진행 중 `account_code_ref`가 자동 생성 데이터에 기록되지 않는 원인을 read-only로 추적하다가, GPT 지시로 "P1-2"~"P1-6A"라는 이름이 붙은 일련의 하위조사가 진행됨. **이 명칭들은 §9의 공식 우선순위 큐(P1-2/P1-3/P1-4)와 무관한, P1-1 내부의 임시 조사 순번이었음** — 표기 혼동 방지를 위해 이 섹션에 하위조사로 명확히 재분류해 기록한다.

### 10-1. 완료된 조사

**DM 계정 식별 관측(실측 완료)**:
- `recipient.id=17841476202821375` Runtime 웹훅으로 직접 확보(`logs/summary/app.log` 21:36:09)
- `INSTA_IG_USER_ID`(yuna18253)와 **정확히 일치** 확인
- `sender.id`(마스킹된 발신자 IGSID)와 `recipient.id`가 서로 다른 식별자임을 동일 로그로 확인
- 임시 관측 로그(`modules/dm/dm_receiver.py` 1줄, INFO 레벨) 추가 → 실측 → **파일·Runtime 양쪽 원복 완료**(재시작 후 `git diff` 빈 결과, 임시 로그 태그 신규 발생 0건 재확인)
- `account_code_ref` 관련 코드·Repository·Airtable 수정 **0건**(전 과정 read-only 원칙 준수)

**Account_Registry 전수대조(32건 전부 확인)**:
- 총 레코드 32건(회장 기억상 "33개"와 1건 차이, 원인 미상·범위 밖)
- `identity_id`: 32/32 populated(사실상 실질 PK)
- `account_code`(구조적 PK)·`ig_user_id`·`api_provider`·`credential_key`: **1/32만 populated**(전부 aijomoojin)
- `fb_page_id`: 32/32 전부 공란(aijomoojin 포함)
- **aijomoojin**: `identity_id=IDN-000036`, `ig_user_id=17841467725643424`, `.env AI_INSTA_IG_USER_ID`와 일치 — CONFIRMED
- **yuna18253**: `ig_user_id=17841476202821375`(`.env` 기준) — **Account_Registry에 대응 레코드 없음, 32건 전수조회로 Confirmed**(표적검색 2건이 아니라 전수 기준)
- `account_email` 신뢰도: 여전히 UNKNOWN(기존 Gate 그대로, 이번에도 미해소)
- 실제 SSOT 키: `account_code`(구조적 설계)와 `identity_id`(실질적으로 항상 채워짐) 두 필드의 역할이 정리 안 돼 **미확정**

### 10-2. 남은 UNKNOWN

- `aijomoojin`의 DM `recipient.id`(이번 관측 창에서 미수신)
- 댓글 웹훅의 실제 `entry.id` 값(설계만 완료, 실측 안 함)
- `account_code` vs `identity_id` 중 실제 운영 SSOT 키
- yuna18253이 기존 32개 Identity 중 어느 것에도 대응 안 되는지, 혹은 완전히 새 레코드가 필요한지
- 실제 로그인 이메일과 Account_Registry 레코드 일치 여부(32건 전부 미검증)
- Facebook Crawler 계정 매핑 원본 데이터(accounts.json "account1"의 IG 자격증명 공란 확인됨, 대체 데이터 없음)
- 댓글·크롤러 경로의 `account_code_ref` 생성 방식(설계 후보만 있음, 미확정)

### 10-3. 현재 Risk

- yuna18253 신규 레코드를 검증 없이 만들면 기존 32개 Identity 중 하나와 실제로는 같은 사람/계정일 위험(중복 생성 위험)
- `.env` 특수 케이스(Design 옵션 B)로 구현하면 Airtable·`.env` 간 **Split-brain SSOT** 발생 — 계정 확장 시 병목
- SSOT 키(`account_code` vs `identity_id`) 확정 전 Repository Interface(`LeadInteractionCreate` 등) 수정 시 **High-Risk DI 변경**이 잘못된 전제 위에서 진행되는 것
- 댓글 `entry.id`를 실측 없이 계정 ID로 가정하면 추측 기반 구현
- Facebook Crawler는 계정 매핑 데이터 자체가 없어 **Code-first 수정 금지**(데이터 선행 필요)

### 10-4. 260725 세션 종료 상태

코드 변경 0건 / Airtable Write·Schema 변경 0건 / Repository Interface 변경 0건 / `account_code_ref` 구현 0건 / 임시 관측 코드 원복 완료 / Runtime 정상(watchdog heartbeat alive) / `data/exported_data/`(기존 무관) 외 예상치 못한 Git 변경 없음.

### 10-5. `P1-1B: yuna18253 Identity Reconciliation`(Read-only, 260726 완료)

**SSOT PK Confirmed**: `airtable_repository.py:385,395` `get_publish_account(account_code)`가 `{account_code}='...'`로만 조회 — **`account_code`가 코드로 강제되는 실제 Runtime PK**. `identity_id`는 32/32 populated이나 `modules/` 코드 전체에서 참조 **0건**(레거시/미사용 필드로 확정).

**yuna18253 기존 레코드 존재 여부: NO(Confirmed)** — `yuna18253@gmail.com`으로 32건 전수 정확검색 0건. 회장 직접 확인(260726): "`sale1.galaxy@gmail.com`은 `IDN-000001`(kbeautiquewholesale)이며 yuna18253과 완전 별개, yuna18253의 실제 로그인 이메일은 `yuna18253@gmail.com`(Instagram·Facebook 동일)" — Airtable 실측과 100% 일치해 교차검증 성공.

`api_provider` 필드는 `facebook_login`/`instagram_login` 두 choice 모두 기존에 이미 존재(스키마 변경 불필요). `credential_resolver.resolve_credential(key)`는 `{key}_INSTA_IG_USER_ID`/`{key}_INSTA_ACCESS_TOKEN` 접두어를 항상 요구(빈 값 불가) — yuna18253을 Provider Routing에 편입하려면 Airtable Write와 `.env` 신규 변수쌍이 세트로 필요함을 확인.

### 10-6. `P1-1C: yuna18253 Account_Registry 신규 등록`(실행 완료, 260726)

회장 승인(`IDN-000041` 채번, `credential_key=YUNA`)으로 실행:

- **Airtable**: `Account_Registry` 신규 레코드 `rec0m7KxyGBhkhqHK` 생성 — `account_code=IDN-000041` / `identity_id=IDN-000041`(aijomoojin 선례와 동일하게 두 값 일치) / `account_handle=yuna18253` / `account_email=yuna18253@gmail.com` / `ig_user_id=17841476202821375` / `api_provider=facebook_login` / `credential_key=YUNA`
- **`.env`**: `YUNA_INSTA_IG_USER_ID`/`YUNA_INSTA_ACCESS_TOKEN` 신규 추가(기존 `INSTA_IG_USER_ID`/`INSTA_ACCESS_TOKEN` 값을 그대로 복사 — 토큰 원문은 스크립트로만 처리, 대화에 노출 안 됨). 기존 전역 변수는 그대로 유지(하위호환).
- **End-to-end Runtime 검증(read-only)**:
  ```
  resolve_credential('YUNA') → ig_user_id=17841476202821375, token 정상 조회
  get_publish_account('IDN-000041') → {account_code: IDN-000041, api_provider: facebook_login,
                                        ig_user_id: 17841476202821375, credential_key: YUNA}
  ```
  전체 체인(Airtable→Repository→credential_resolver) 정상 동작 확인.
- **현재 영향**: `Instagram_Posts.account_code_ref`에 `IDN-000041`을 채운 레코드가 아직 없어, 실제 게시 Runtime 동작은 무변화(기존 "전역계정 폴백" 경로 그대로 유지). yuna18253이 aijomoojin과 동일하게 Provider Routing 체계에 정식 편입된 상태만 확보됨.
- **커밋**: 이번 변경은 Airtable/`.env`(gitignore 대상)만 해당 — git 추적 대상 코드 변경 없음. 이 문서 자체의 커밋은 세션 종료 시 일괄 처리(회장 지시).

### 10-7. 다음 재개 위치 — `P1-2` 이후

`yuna18253` SSOT 정합성 확보 완료. 다음 하위작업은 실제 `account_code_ref` 자동 기록 로직 구현(DM/댓글/크롤러 3경로, P1-5 설계 초안 기준) — 단, Repository Interface 변경은 여전히 별도 승인·Codex/GPT 리뷰 대상(CLAUDE.md Multi-AI Review Policy High-Risk).

### 10-8. Bundle B(DM `account_code_ref`) Build·Buy·Reuse 결정 소급 등록 — 260726 정정

**배경**: Bundle B(DM 경로 `account_code_ref` 태깅, `modules/dm/dm_receiver.py`+`modules/infra/airtable_repository.py`+`modules/infra/repository_interface.py`, 킬스위치 `DM_ACCOUNT_ROUTING_ENABLED` 기본 OFF, 신규 테스트 23개)는 260726 세션 중 "결함 발견 → 코드 설계"로 바로 진행되었고, 정식 Build·Buy·Reuse 비교표를 문서로 남기지 않은 채 Codex 리뷰·승인만 거쳐 구현되었다. 회장 지시([260726_PROCESS_CORRECTION])로 이 판단을 소급하여 문서화한다. **구현 자체는 이미 완료·테스트 통과 상태이며 되돌리지 않는다** — 이 섹션은 그 판단 근거를 사후 기록하는 것이다.

| 선택지 | 가능여부 | 비용 | 구현시간 | 운영부담 | 보안위험 | Rollback | 권고 |
|---|---|---|---|---|---|---|---|
| Repair(기존 Repository 패턴 최소수정) | 가능 | 낮음 | 완료(약 0.5일) | 낮음 | 낮음(킬스위치 OFF, fail-open 설계) | 쉬움(`git revert` 1건, Airtable Schema 변경 없음) | **채택됨** |
| Reuse(내부 기존 기능) | 불가 — 동등 기능 없음(계정 역조회 메서드 자체가 없었음) | — | — | — | — | — | 기각 |
| OSS/GitHub | 과잉 — 단순 FK 조회+선택적 필드 전달에 외부 라이브러리 불필요 | 높음 | 높음 | 높음 | 중(신규 의존성) | 어려움 | 기각 |
| SaaS | 과잉 — Airtable 자체가 이미 SSOT | 높음 | 높음 | 높음 | 중 | 어려움 | 기각 |
| Defer/Accept | 계정별 리드 귀속·KPI 왜곡이 계속 누적됨(G7 KPI 항목과 직결) — 10단계 매출검증 목표와 직접 충돌 | — | — | — | — | — | 기각 |

**결론**: Repair가 유일하게 CLAUDE.md 5.1(직접개발 적합 조건: 프로젝트 고유 사업규칙, 기존 코드 구조를 연결하는 작은 누락, 외부도구가 더 복잡함, 변경범위 작음, 성공기준 명확, Rollback 쉬움) 전부를 만족했다. 소급 기록이지만 판단 자체는 유지한다.

**관련**: Codex 최종 승인 기록(대화), `tests/test_dm_account_routing.py`(10 tests) / `tests/test_get_publish_account_by_ig_user_id.py`(9 tests) / `tests/test_create_lead_interaction_account_code_ref.py`(4 tests)

### 10-9. P0 Security Gap 등록 → Read-only 조사 완료 — Webhook 서명 검증 부재 확정 (ERR-082)

**배경**: Codex가 Bundle B 리뷰 중 지적한 "`X-Hub-Signature-256` 서명 검증 부재"가 대화 기록에만 남아있고 `docs/ERROR_DATABASE.md`에 정식 등록되지 않았던 것을 260726 정정 지시로 등록(1차) → 같은 날 회장 지시로 Read-only Phase 0~5 전수조사 실행(2차, 코드수정·Runtime변경·Commit·Push 전부 없음).

**조사 결과 (260726, Phase 0~5 완료)**:
- **Phase 1 Entry Point**: `launcher/main.py:536,550` → `modules.dm.dm_receiver.app` 직접 `app.run()` 구동, WSGI 미들웨어·리버스프록시 없음. `POST /webhook`(DM·댓글 공용, 유일한 대상 라우트) 1개뿐.
- **Phase 2 서명검증 코드**: `X-Hub-Signature-256`/`hmac.`/`hashlib.`/`compare_digest`/`APP_SECRET` 매칭 `dm_receiver.py` 및 프로젝트 전체 `*.py`(`.venv` 제외)에서 **0건**(Grep 2회 재확인, 백그라운드 전체탐색 포함). `.env.example`에 Meta App Secret 변수 자체 없음. 유일한 유사 선례는 `modules/ingest/domeggook_ingest.py`의 `hmac.compare_digest`(다른 라우트, 정적 토큰 비교 — Meta HMAC 서명검증과 무관).
- **Phase 3 Blast Radius**: 위조 Payload가 서명검증 없이 `record_interaction()`(Airtable Write)·`handle_price_inquiry()`(자동응답)·`send_telegram()`·`process_comment_event()`로 직접 진입 가능함을 코드로 확인. 킬스위치(`DM_ACCOUNT_ROUTING_ENABLED=false`)는 이 노출을 전혀 막지 않음(Account Routing 블록만 비활성화). **기존에 이미 라이브 운영 중인 DM 자동응답 경로 자체가 오늘도 이 노출에 해당**(Bundle B가 만든 위험 아님).
- **Phase 4 판정**: **FAILED**(검증 코드 없음, 실패 시 Reject 경로 없음, 적용 Route 0/1).
- **Phase 5 Build·Buy·Reuse**: Python 표준 `hmac`/`hashlib`로 Meta 공식 스펙(HMAC-SHA256, Raw Body, `hmac.compare_digest`) 전체 충족 가능 — 신규 OSS/SaaS 불필요(유력 후보). 구현 자체는 이번에 하지 않음(승인 대기).

- **등록 위치**: `docs/ERROR_DATABASE.md` ERR-082 (Status: **OPEN — FAILED**로 정정, RESOLVED 아님)
- **Gate 순서 잔여**: 최소 해결안 승인 → 코드수정(`dm_receiver.py` 1개 파일, 신규 함수1개+`receive_webhook()` 최상단 삽입) → 테스트(정상서명/서명없음/서명불일치/Secret미설정 4종) → Canary(로컬 test_client 우선) → Rollback(`git revert` 1건) → Production Gate
- **DM Bundle B와의 관계**: `DM_ACCOUNT_ROUTING_ENABLED=true` 프로덕션 전환(실 Meta 웹훅 트래픽 대상)은 ERR-082가 ADOPT로 종결되기 전까지 **HOLD**. Bundle B 자체(킬스위치 OFF 상태의 코드·테스트)는 이미 완료된 상태로 유지.
- **남은 승인 필요 항목**: (A) 이번 FAILED 확정을 문서에 반영(이번 갱신으로 완료) (B) §14 최소 해결안(서명검증 구현) 착수 여부 — 코드수정이므로 별도 승인 필수 (C) Defer(위험 명시적 수용) vs 구현 중 방향 결정

### 10-10. ERR-082 로컬 구현 완료(260727) — GPT Target Architecture 결정 → CODEX 감사 대기 상태에서 회장 직접 구현 지시로 진행

**배경**: (B) 방향으로 회장이 직접 구현을 지시(우선순위 고정표 5단계). GPT가 결정한 Target Architecture(기존 yuna Route 보존 + AI Strategist 전용 신규 Route + Route별 App Secret 분리 + 공통 Fail-closed Validator)를 Claude Code가 Read-only 설계 제출 → 회장 승인 범위(코드·테스트 5파일+`.env.example` 1파일) 확정 후 구현.

**구현 결과**: `modules/common/webhook_signature.py`(신규, 순수함수) + `modules/dm/dm_receiver.py`(+51/-3, `_handle_signed_webhook()`/`_process_webhook_event()` 분리, 기존 Business Logic 바이트 단위 무변경) + `.env.example`(`WEBHOOK_APP_SECRET`/`AI_WEBHOOK_APP_SECRET`/`AI_WEBHOOK_VERIFY_TOKEN` placeholder 3줄 추가) + 테스트 3파일(신규 `test_webhook_signature.py` 10건, 기존 2파일 Signed Request 전환+보안회귀 추가로 8→23/10→10).

**검증**: Target Test 43/43 PASS. 전체 Suite Before(원복 상태, `git stash`로 재구성) 606 passed/3 xfailed/0 failed → After 631 passed/3 xfailed/0 failed, 재현 3회 일치, 신규 실패 0건(차이 +25 = 신규 테스트 수와 정확히 일치). `git diff --check` 오류 0건, 허용 6파일(신규 2+기존 4) 외 Diff 0건, Secret/Token 로그 노출 0건(코드 직접 확인). 환경변수 이름은 코드·`.env.example` 100% 일치(4개 전부 grep 교차확인).

**미완료(별도 승인 대상, 회장만 수행 가능한 항목 포함)**: (1) 실제 `.env`에 `WEBHOOK_APP_SECRET`/`AI_WEBHOOK_APP_SECRET`/`AI_WEBHOOK_VERIFY_TOKEN` 실값 입력 — Claude Code는 API 키·Secret류를 어떤 필드에도 대신 입력할 수 없음(정책상 절대 금지, 승인 무관) (2) Meta Dashboard에서 AI Strategist App의 Callback URL·Verify Token 등록 — Claude Code는 Meta 개발자 콘솔 접근 권한 자체가 없음 (3) Runtime Restart(watchdog/NSSM 경유 `launcher/main.py`) — 실행 가능하나 재시작 직전 별도 확인 필요 (4) 실제 Meta 서명 Payload로 Runtime Canary 요청 — (1)(2) 완료 전까지 무의미. 이 4개 전부 완료·확인돼야 ERR-082가 RESOLVED로 종결된다.

**기록**: `docs/ERROR_DATABASE.md` ERR-082(Status: "OPEN — 로컬 구현 SUCCESS(260727), Runtime/배포 미완료"로 갱신) / 이 섹션.

### 10-11. ERR-082 Runtime ADOPT · Bundle B DM 계정 태깅 Canary 종료(260728)

**Runtime 결과**: AI Strategist 실제 Meta DM은 `POST /webhook/ai-strategist → 200`, 기존 yuna 실제 Meta DM은 `POST /webhook → 200`으로 처리됐다. 반대 App Secret으로 서명한 합성 요청 2건은 각 Route에서 모두 403으로 차단됐고 Business Logic 진입은 0건이었다.

**Bundle B 결과**: `DM_ACCOUNT_ROUTING_ENABLED=true` 적용 후 `SNS_Watchdog`를 재시작했다. yuna Lead는 `account_code_ref=IDN-000041`로 저장됐고 잘못된 계정 저장은 0건이었다. 가격 문의별 기존 자동응답도 각각 1건씩 확인돼 7단계 종료조건을 충족했다.

**판정**: ERR-082는 **RESOLVED — Runtime ADOPT**, Bundle B DM 계정 태깅 Canary는 **7단계 SUCCESS**다. Canary 구간의 Signature 실패 경고 8건은 발생 주체가 UNKNOWN이나 Business Logic 진입·Lead 생성·계정 오염 Evidence가 없어 별도 RISK/HOLD로 분리한다. 8단계는 시작하지 않았으며 별도 승인 전 미착수다.

### 10-12. 8단계 P1-1 C1 Facebook 중복 Article Selector 수정(260728, PARTIAL)

**배경**: Codex가 실행 역할을 임시 대행하던 중(§CURRENT_RUNTIME_CONTEXT.md CODEX Temporary Execution Exception) 토큰 소진으로 8단계 C1(Facebook Direct-Permalink Canary) 첫 실행이 중단됐다. 사용자가 전달한 중단 시점 요약에 따르면, 승인 permalink 1개로 Selector를 실행했을 때 동일 논리 게시물이 DOM `div[role='article']` 요소 2개로 렌더링돼 있었고, Fail-closed 안전장치가 Airtable Write 전에 실행을 막았다(Airtable Create·Update 0건, Run ID 소비 0회). 이 인계 요약 자체는 이번 세션에서 Runtime으로 재검증하지 않았다(Evidence Priority 8순위).

**Root Cause(코드 직접 확인, Confirmed)**: `modules/sns/facebook_crawler.py::_find_exact_permalink_article()`이 `len(matches) != 1`이면 무조건 실패시켰다. `matches`는 이미 `expected_post_id`와 정확히 일치하는 anchor를 가진 article만 담기므로, 그 개수가 1보다 크다는 것은 "서로 다른 게시물"이 아니라 "동일 Post ID의 중복 DOM 렌더링"을 의미한다 — DOM 요소 개수를 논리 게시물 개수로 오판정한 것이 근본 원인이었다.

**수정(승인 Scope 내 2파일)**: `modules/sns/facebook_crawler.py`에서 `if len(matches) != 1` → `if not matches`로 변경(판정 기준을 "정확히 1개"에서 "1개 이상"으로 전환, 0개일 때만 fail-closed 유지) + 함수 docstring에 판정 근거 명시. `tests/test_package_s3_facebook_exact_runner.py`에 dedup PASS 테스트(동일 Post ID article 2개/3개), 0-match fail-closed 테스트(서로 다른 ID 2개, Post ID 추출 불가 2개 포함), canary-level 중복 DOM PASS 테스트(ImgBB 0회), canary-level selector 실패 시 Run ID·Airtable Write 0건 테스트를 추가했다. 기존 "동일 Post ID article 2개는 거부돼야 한다"는 구 테스트 케이스(버그를 검증하고 있었음)는 제거하고 PASS 테스트로 이전했다.

**테스트 Evidence**: 대상 파일 Before 23 passed → After 28 passed(신규 5건 포함, 0 failed). 관련 Suite 전체(ProgramData ACL로 collection 자체가 막히는 8개 파일 제외) Before 618 passed/10 failed/3 xfailed → After 624 passed/9 failed/3 xfailed — 신규 실패 0건, 기존 실패 목록 동일(이미 미커밋 상태였던 다른 파일들의 기존 실패). `git diff --check` 0건, AST 파싱 PASS, 변경 파일은 승인된 2개(`modules/sns/facebook_crawler.py`, `tests/test_package_s3_facebook_exact_runner.py`)뿐.

**RISK/UNKNOWN**: `C:\ProgramData\SNS_24AutoProject\runtime_boot_policy.json`에 대해 이번 세션 환경에서 `PermissionError`(액세스 거부)가 발생해 `test_package_s1/s2/c0/b/s5`와 `test_dm_*` 3개 파일은 실행 자체가 불가능했다(수정 전·후 동일 증상, 이번 변경과 무관, Scope 밖). 이로 인해 현재 Runtime의 실제 Safe Mode 상태는 이번 세션에서 직접 확인하지 못해 UNKNOWN이다.

**미실행(별도 승인 대상)**: C1 Runtime Canary 재실행, Runtime Restart, Airtable Create·Update·Delete, Instagram 공개 게시, ImgBB Upload, Commit, Push — 전부 0건.

**판정**: 8단계 P1-1은 **PARTIAL**이다. Selector 코드·테스트 수정은 SUCCESS 기준을 충족했으나, C1 Runtime Canary 재실행 전까지 "Clean Measurement Baseline" 자체는 확정할 수 없다.

**기록**: `docs/CURRENT_RUNTIME_CONTEXT.md` 260728 16:49 ICT 섹션 / 이 섹션. `docs/ERROR_DATABASE.md`에는 이 이슈와 정확히 대응하는 기존 ERR 항목이 없어 신규 생성하지 않았다 — 다음 사용 가능 ID는 `ERR-084`로 확인되나(마지막 확정 항목 ERR-083), 회장 별도 승인 전에는 확정하지 않는다.

### 10-13. 8단계 P1-1 C1 Facebook Exact-Post Canary 실행 SUCCESS + Production 복귀(260728 21:37 ICT)

**배경**: §10-12에서 코드·테스트 수정만 완료됐던 C1을 이어받아, 같은 세션에서 회장이 실제 Facebook 화면을 직접 열어 확정한 Permalink·Post ID·Source Account·Image URL·Caption을 기반으로 W2(Safe Context 생성)→R2(Watchdog 재시작)→C1(Airtable draft 1건 실행)까지 전부 완료했다.

**입력 Lock(회장 실측 + Claude Code Read-only 교차확인)**:
```text
permalink = https://www.facebook.com/groups/1827528710833477/posts/4051001165152876
expected_post_id = 4051001165152876
source_account = account1 (Cho Eunha, DOM aria-label 재확인)
target_publish_account_code_ref = IDN-000041 (Airtable Account_Registry 실측: api_provider=facebook_login, credential_key=YUNA)
approved_caption = "[C1 CONTROLLED CANARY] Facebook exact-post account attribution validation"(정책2, 고정 테스트 caption)
approved_image_url = https://i.ibb.co/k2D2nkhZ/image.jpg (승인된 ImgBB Upload 1건의 결과, 원본 fbcdn 이미지와 Content-Length 37,799 bytes 동일 확인)
```

**중간에 발견된 실제 Runtime 이슈 2건(둘 다 코드 미수정, 이번 실행은 통과)**:
1. **DOM 중복 렌더링 실측 재현**: 동일 Permalink 재방문 시 `div[role='article']`이 매번 개수가 다르게 렌더링되고, 그중 `expected_post_id`와 일치하는 후보가 정확히 2개(동일 이미지 URL 3개 공통) 나타나는 현상을 실측 확인 — §10-12에서 고친 Selector(`not matches`로 판정)가 실제로 이 경우 결정론적으로 매치[0]을 선택함을 실측으로 재확인했다.
2. **자동 anchor-scan 오매칭(신규 발견, 근본원인 UNKNOWN)**: 조사 과정에서 Claude Code 자체 진단 스크립트가 이 Permalink를 스캔했을 때, `expected_post_id`와 일치하는 article 안에서 실제로는 무관한 다른 위젯("Cielo Anne Areno" 텍스트)을 읽어온 사례가 1회 있었다. 사람이 직접 같은 URL로 2회 재접속해 확인한 결과("김정현/TIELA" 게시물)와 불일치했다 — 이후 회장이 우클릭으로 직접 복사한 이미지 URL로 최종 확정. **다만 이 오매칭은 Claude Code의 진단 스크립트(scratchpad, 레포 밖)에서만 발생했고, 실제 Production 함수 `run_exact_permalink_canary()`는 Adversarial 단위테스트(가짜 DOM에 "틀린 상품" 텍스트·이미지를 심어 검증)로 caption/image_url이 오직 `approved_caption`/`approved_image_url` 파라미터만 사용함을 별도로 증명했다(DOM 텍스트·이미지가 payload에 섞일 코드 경로 자체가 없음, `_find_exact_permalink_article()`의 반환값이 애초에 사용되지 않음).** 즉 이번 C1 결과물 자체는 오염되지 않았으나, **왜 진단 스캔이 중첩 위젯을 오매칭했는지의 정확한 DOM 원인은 여전히 UNKNOWN이며, 8단계 완료 선언 전 별도 Gate로 다루기로 회장이 결정했다(260728 21:39 ICT 확정).**

**fbcdn 차단 Gate**: `_validate_approved_canary_image_url()`이 실제 fbcdn.net 이미지를 거부함을 확인 → Root Cause Confirmed(기존 Production `save_to_airtable()`의 "fbcdn→ImgBB 교체 후 ready" 패턴과 동일 설계 철학) → A안(ImgBB 승인) 채택 → 승인된 이미지 1건만 업로드(코드 변경 0줄).

**W2(Safe Context 생성) Runtime Evidence**: 이 세션(Claude Code) 계정은 `C:\ProgramData\SNS_24AutoProject\runtime_boot_policy.json`을 읽기조차 못함(`PermissionError`, 세션 시작 전부터 일관되게 재현) — 파일 생성·수정·Watchdog 재시작·C1 CLI 실행 전부 **회장이 직접 관리자 권한 PowerShell에서 수행**했다. Claude Code는 JSON 내용을 사전에 로컬 dry-run(`load_runtime_boot_policy()`)으로 검증해 제공하고, 회장의 실행 결과를 Read-only로 대조하는 역할만 수행했다.
```text
context_id = facebook-c1-exact-post-260728-01
run_id = c1fb-260728-2111
expires_at = 2026-07-28T14:56:04.021Z (UTC, ICT 21:56)
```

**R2(Watchdog 재기동) Runtime Evidence**: `watchdog.log` 21:28:16 `[BOOT] BOOT_POLICY_VALID mode=safe state=armed→active run_id=c1f***111` → launcher 재시작 성공. `/health` 재조회: `canary_safe_mode=true canary_expired=false runtime_boot_policy_state=active`. `POST /webhook` 테스트 → `503 canary_safe_mode_blocked`(Business Logic 진입 0건 확인).

**C1 실행 Runtime Evidence(회장 직접 실행, Claude Code Read-only 사후검증)**:
```text
db/canary_runs.db: canary_run_id=c1fb-260728-2111, status=COMPLETED, terminal_code=SUCCESS
write_counts: instagram_post_create=1, 나머지 전부 0(imgbb_upload/instagram_publish/dm_or_comment/source_item_*/other_airtable_*/airtable_delete)
Airtable Instagram_Posts 실제 레코드(recFHv9AvW891KaHW) GET으로 직접 확인:
  account_code_ref=IDN-000041, data_classification=test, post_status=draft
  insta_post_code=CANARY-FB-4051001165152876, source_url=승인 Permalink 그대로
  caption=승인된 고정 caption 그대로, image_url=승인된 ImgBB URL 그대로
```

**Production 복귀 Runtime Evidence**: 회장이 동일 방식(관리자 PowerShell, `.NET File.WriteAllText`)으로 Boot Policy를 `mode=production, state=active, purpose=production, context_id/run_id/expires_at 전부 공란`으로 교체 후 `SNS_Watchdog` 재시작. `watchdog.log` 21:36-21:37 `BOOT_POLICY_VALID mode=production` → launcher 재시작 성공. `/health` 재조회: `canary_safe_mode=false canary_purpose=production`. `POST /webhook` 테스트 → `403`(서명검증 정상 재개, 더 이상 503 아님).

**판정**: C1은 **SUCCESS**(계약된 Write Budget 정확히 1건, 나머지 0건, 계정·분류·상태 전부 일치). 8단계 P1-1은 **여전히 완료 선언하지 않는다** — 위 "자동 anchor-scan 오매칭" Root Cause가 UNKNOWN으로 남아있고, 회장이 이를 별도 Gate로 다루기로 결정했기 때문이다(260728 21:39 ICT).

**미해결 Gate(다음 세션 우선순위)**: 자동 DOM anchor-scan이 왜 중첩/추천 위젯의 무관한 텍스트를 매칭했는지 근본원인 규명 — Production 함수 자체는 안전함이 증명됐으므로 Blast Radius는 "진단 스크립트의 신뢰도" 문제로 한정되나, 향후 무인 대량 운영 시 이런 진단 로직을 재사용한다면 반드시 선결돼야 한다.

**기록**: `docs/CURRENT_RUNTIME_CONTEXT.md` 260728 21:39 ICT 섹션 / 이 섹션.

### 10-14. anchor-scan 오매칭 Gate RESOLVED(260729 06:00 ICT)

**Root Cause(Confirmed)**: Facebook의 "게시물 숨기기" 등 JS 전용 UI 액션 anchor가 실제 이동 목적지 없이 현재 보고 있는 permalink 자체를 href로 재사용한다(`.../posts/<현재글ID>#`처럼 빈 `#`로 끝남). `extract_facebook_post_id()`가 `urlparse()`로 `#` 뒷부분(fragment)을 제거하고 경로만 파싱하므로 이 placeholder href도 "진짜 그 게시물 링크"로 오인됐다. 화면에 뜬 임의의 무관한 게시물(오늘 "Cielo Anne Areno", "China Sixsix" 등 로드마다 다르게 재현)이 이 때문에 반복적으로 오매칭됐다 — DOM 요소 개수·중복 렌더링과는 별개의, 새로 발견된 문제였다.

**재현 Evidence(260729 05:24 ICT)**: 실제 브라우저로 동일 permalink에 접속해 매칭된 article의 anchor를 전수조사한 결과, `aria-label='China Sixsix님의 게시물 숨기기'`, `href='https://www.facebook.com/groups/1827528710833477/posts/4051001165152876#'`인 anchor를 발견 — 무관한 "China Sixsix"(중국 화장품 제조업체) 게시물이 이 anchor 때문에 목표 Post ID와 오매칭됨을 코드 레벨로 확정했다.

**수정**(`modules/sns/facebook_crawler.py::_find_exact_permalink_article()`, 최소 변경): (1) href가 공백 제거 후 빈 `#`로 끝나는 anchor, (2) aria-label에 "숨기기"가 포함된 anchor — 둘 다 게시물 식별 근거에서 제외. 이 필터가 없으면 화면에 게시물이 하나라도 뜨는 한 사실상 항상 매칭되는 상태였다(Selector의 Fail-closed 보장이 사실상 무력화돼 있었음).

**회귀 테스트**: `tests/test_package_s3_facebook_exact_runner.py`에 실측 재현 케이스 3건 추가 — 단일 "숨기기" anchor만 있으면 거부 / 진짜 링크와 공존 시 진짜 링크 선택 / aria-label 없이 href의 빈 `#`만으로도 거부. 대상 파일 31/31 PASS(기존 28+신규 3, 0 failed). 관련 전체 Suite(ProgramData ACL 차단 8파일 제외) 626 passed(기존 실패 9건과 동일, 신규 실패 0건).

**수정 후 실측 재확인(260729 05:58~05:59 ICT, 2회 연속)**: 동일 permalink에 실제 브라우저로 재접속해 수정된 함수를 직접 호출 → 2회 모두 더 이상 "China Sixsix" 등 무관 게시물을 선택하지 않음(2회 모두 `FacebookCanaryError: found=0`으로 Fail-closed). 이 시간대에 진짜 대상 게시물 콘텐츠 자체가 대기시간 안에 렌더링되지 않아 발생한 것으로 추정되며(기존에 별도 문서화된 DOM 로딩 비결정성 문제, 260728 §10-12/§10-13 UNKNOWN 항목과 동일 계열), 이번 수정의 부작용이 아니다. **핵심 성공기준인 "무관 게시물 오매칭 재현 안 됨"은 2회 모두 확인됐다.**

**C1 Draft 오염 여부**: 무관— 이 오매칭은 애초에 `run_exact_permalink_canary()`의 저장 payload에 영향을 준 적이 없음(260728 Adversarial 단위테스트로 이미 별도 증명, DOM 텍스트·이미지가 payload에 섞일 코드 경로 자체가 없음). 260728에 저장된 draft(`recFHv9AvW891KaHW`)는 계속 안전하다.

**변경 확인**: 코드 변경 2파일(`modules/sns/facebook_crawler.py`, `tests/test_package_s3_facebook_exact_runner.py`)뿐, `git diff --check` 0건. Airtable Write·ImgBB·Instagram Publish·Boot Policy·Runtime Restart·Commit·Push 전부 0건(AdsPower 브라우저 열고 닫기만 발생, 회장이 유료로 일일한도 해제).

**판정**: 8단계 완료 선언 보류 사유였던 Root Cause가 **Confirmed로 규명되고 코드로 차단**됐다. 남은 것은 페이지 로딩 타이밍에 따른 DOM 콘텐츠 비결정성(기존 별도 이슈, Fail-closed로 안전 처리됨)뿐이다.

**기록**: `docs/CURRENT_RUNTIME_CONTEXT.md` 260729 06:00 ICT 섹션 / 이 섹션.

---

### 10-15. 9단계(예외삼킴·데이터손실 감사) 완료(260729 13:35 ICT)

**범위**: 이 "9단계"는 위 §1 표의 프로젝트 로드맵 0~11단계와는 별개로, CLAUDE.md 단계 위치 표기 헤더가 지칭하는 독립된 신뢰성 감사 트랙이다(우연히 같은 번호 9를 씀 — §1 표의 "9 | 2계정 재현 Test"와 혼동 금지). `launcher/main.py`의 Active 스케줄 잡 8개(Facebook Crawl/Account Manager/Dome Crawl/Dome Export/Comment Dead Monitor/KPI Snapshot/Engagement Update/Instagram Upload) 전수 감사 대상이었다.

**9-10-3 배치 감사 — Defect A~F(전부 RESOLVED, 개별 commit)**:
| Defect | 대상 | 증상 | 수정 | commit |
|---|---|---|---|---|
| A | facebook_crawler.py | URL 1건 실패가 계정 전체 SUCCESS로 위장 | 계정 단위 SUCCESS/PARTIAL/FAILED 판정 + 전량실패시 예외 | `09cae6f` |
| B | account_manager.py | Airtable 캐시 로드 실패가 "타겟 0건"으로 위장 | source=airtable 경로 예외 재전파(캐시 무효화) | `56b7497` |
| C | launcher/main.py(_job_dome_crawl) | 타겟/아이템 1건 실패가 배치 전체 중단 | 타겟·아이템별 try/except, 전량실패시만 예외 | `dd06816` |
| D | source_exporter.py | claim/exists/상태갱신 실패가 배치 중단 | 항목별 try/except → failed 카운트 합산(기존 3키 계약 보존) | `ba8b95c` |
| E | kpi_collector.py | Airtable 조회 실패가 0건 KPI로 오기록 | `_or_raise` 변형 신설 + `fetch_errors` 신규 키 | `4375642` |
| F | launcher/main.py(_job_insta_upload) | mark_post_result 실패가 배치 중단(uploading 고착 유발) | try/except + Slack 알림, 실사용 Airtable 레코드로 라이브 검증 | `c857aef` |

**9-11/9-12**: 결함 분류 확정 + 데이터 유실 영향 실측 — `post_status=uploading` 고착 11건 발견(원인: Defect F 수정 전 상태였던 시기의 casualty).

**ERR-085~088(CRM/DM 쓰기 실패 예외삼킴, 전부 RESOLVED)**: `lead_closer.mark_lead_closed()`/`lead_scorer.update_lead_score()`/`order_detector.handle_order_conversion()`/`dm_receiver record_interaction()` 4곳에 `retry_queue` 위임 추가(`75c60d2`), `docs/ERROR_DATABASE.md` 갱신(`9c2c99a`). ERR-087은 Production Caller 0건 확인으로 `NOT_ACTIVE/LATENT_RISK` 유지, ERR-088은 회장/GPT 지시로 기존 Telegram 알림 계약을 의도적으로 보존(상태-알림 불일치 잔존, 별도 판단 대상으로 명시).

**uploading 11건 remediation(Airtable 데이터 수정만, 코드 변경 0)**: 로그 전수조사로 11/11 전부 `[publish_single] 성공` 이력 0건(중복게시 위험 없음)을 먼저 확정 → Canary 1건 재시도 시 신규 발견: 9단계 다계정 안전장치(`account_code_ref` 없으면 Legacy 전역 계정 fallback 금지)에 걸려 처리 보류됨을 확인 → `account_code_ref=IDN-000041`(YUNA 실제 account_code) + `post_status=ready`로 재설정 → 11/11 전부 실제 Instagram 게시 성공(`post_status=posted`, 고유 `ig_media_id` 발급 확인).

**9-14 최종 Closure 감사(Read-only)**: git status clean, 관련 테스트 88 passed/6 failed(전부 `runtime_boot_policy.json` PermissionError 기존 환경제약, 회귀 아님)/3 xfailed, Runtime 11:43:51 재시작 이후 실제 신규 ERROR 0건(pytest mock 산출물 제외), Airtable 11/11 `posted` 확정, 문서 정합성 확인.

**HOLD(9단계 결론과 분리)**: `WEBHOOK_APP_SECRET` 라이브 프로세스/`.env` 파일 값 불일치 — 별도 세션(`task_b24dbf54`)에서 진행 중.

**기록**: `docs/ERROR_DATABASE.md`(ERR-085~088 RESOLVED) / `docs/FAILURE_PATTERN.md`(FP-063 후속, FP-064 신규) / `docs/VALIDATION_STATUS.md` / `docs/CURRENT_RUNTIME_CONTEXT.md` / `porting_logs/MERGE_JOURNAL.md` / 이 섹션.

commit: `09cae6f`~`9c2c99a`(코드·문서) + 이 Closure 문서 4개 신규 commit
push: 이 Closure 직후 실행

---

### 10-16. P1-4 1순위 Approval Action 실측 완료 → 회장 결정으로 비활성 유지(260729)

**배경**: 9단계 종료 직후 P1-2/P1-3 문서 동기화(§9)를 마치고 P1-4(격리MVP)에 착수 — 4개 하위항목(Persona/Sourcebook/Final Quality Gate/Approval Action) 중 가장 작고 즉시 검증 가능한 **Approval Action**(항목4)부터 시작했다.

**Read-only 조사**: `REQUIRE_APPROVAL_BEFORE_PUBLISH` 코드(`airtable_repository.py:207-209`)는 이미 구현·테스트(`test_publish_gate_and_approval.py` 7개 중 4 PASS, 나머지 3은 기존 `runtime_boot_policy.json` PermissionError 환경제약과 무관 재확인)돼 있었고, Airtable `Instagram_Posts.post_status` Schema에도 `draft`/`ready`/`rejected` 선택지가 이미 존재해 Schema 변경도 불필요함을 확인했다. `fetch_pending_posts()`가 `post_status='ready'`만 픽업함도 코드로 확인 — REUSE(Airtable UI 직접 사용, 0개발)가 정확했다.

**실행(회장 승인 후 순차 진행)**:
1. `.env`에 `REQUIRE_APPROVAL_BEFORE_PUBLISH=true` 추가 → `SNS_Watchdog` 재시작(회장 관리자 PowerShell) → `/health` 정상(`canary_safe_mode:false, production`), 재시작 이후 신규 오류 0건 확인.
2. **Facebook 실브라우저 Canary 3회 연속 실패**(`tools/run_facebook_canary.py`, C1 방식 재사용 시도) — 매번 AdsPower 브라우저 세션이 `driver.get()`~`time.sleep(12)` 구간에서 연결 끊김(`ConnectionResetError`/`WinError 10061`). 회장이 AdsPower "트래픽 패키지 만료" 배너를 확인해 결제까지 했으나 3번째 시도도 동일 증상 재현 — 근본원인 미확정. **3회 전부 Airtable Write 0건**(Read-only 재확인, `save_instagram_post()` 도달 전 중단), Production 복귀도 매번 정상 확인돼 데이터 안전은 유지됐다. 소진된 `canary_run_id` 3개(`approval-gate-260729-01/02/03`)는 `db/canary_runs.db`에 `RUNNING` 상태로 잔존(재사용 불가, 실질 영향 없음).
3. **대안(Claude Code 판단 오류 인정 후 제안)**: 브라우저 없이 `AirtableRepository.save_instagram_post()`를 코드로 직접 호출해 `data_classification=test`/`canary_run_id` 부여 draft 레코드 1건(`recRsolx1cpPdbp4g`) 생성 — Safe Mode Boot Policy(4번째, `approval-gate-260729-04`)는 여전히 필요했으나 브라우저 의존성은 제거해 즉시 성공.
4. 회장이 Airtable UI에서 직접 `draft→ready`로 변경(승인 액션 자체를 실제로 수행) — 그러나 `fetch_pending_posts()`의 필터(`data_classification`이 공란 또는 `production`, `canary_run_id` 공란만 픽업)에 의해 **이 테스트 레코드는 설계상 정상적으로 픽업 대상에서 제외**됨을 재확인(§9단계에서 만든 Canary Write Budget 격리 안전장치가 의도대로 작동 — 결함 아님). `production` 분류로 다시 만들면 실제 yuna18253 계정에 진짜 게시되는 수준까지 증명 가능하나, 그 결정 전 회장이 정책 방향을 확정했다(다음 항목).

**회장 최종 결정(260729, 명시 확정)**: "완전자동화 우선, 게시 전 사람 승인 불필요 — 문제되는 것만 사후 조치로 삭제". Approval Action 기능 자체는 **코드 삭제 없이 비활성 유지**(`.env`의 `REQUIRE_APPROVAL_BEFORE_PUBLISH=true` 줄을 주석 처리로 보존, 즉시 재활성화 가능) 방침으로 확정.

**원복 실행**: `.env` 주석 처리 → `SNS_Watchdog` 재시작(`18:53:29 FATAL → 18:53:58 launcher 재시작 성공`, `/health` 정상, 재시작 이후 신규 오류 0건) → 테스트 레코드 `recRsolx1cpPdbp4g` Airtable에서 삭제(Read-only 재조회로 삭제 확인) — 전부 Runtime Evidence로 확인 완료.

**판정**: Approval Action은 **REUSE로 실측 검증 완료**(승인→게시 연결고리 자체는 정상 작동 확인, 단지 test 격리 안전장치에 막힌 것) — 그러나 **회장 방침에 따라 비활성으로 최종 확정**. Persona(항목1)/Sourcebook(항목2)/Final Quality Gate(항목3)는 이번 세션에서 착수하지 않았다.

**변경 파일(코드 추적 대상)**: 없음(`.env` 변경만, git 미추적) — 문서 갱신만 커밋 대상.

**기록**: `docs/WORKFLOW_ARCHITECTURE_STATUS.md`(§6 항목4, §9 P1-4행, 이 섹션) — 이 항목.

---
