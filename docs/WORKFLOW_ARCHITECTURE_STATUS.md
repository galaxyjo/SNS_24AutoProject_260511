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
| 10 | Metric·수익 검증 | 진행중 | KPI 집계 오류(ERR-078) 해소, 리드전환 유실(ERR-080) 해소. Clean Baseline·테스트/실고객 분리·매출 원본·ROI 경로는 미완료 |
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
| 4 | Approval Action | REUSE+BUILD(최소) | `REQUIRE_APPROVAL_BEFORE_PUBLISH`(`airtable_repository.py:159`) 상태값 분기만 있고, DRAFT→READY로 바꾸는 승인 액션(버튼/트리거) 자체가 없음 | `Instagram_Posts.post_status`(DRAFT/READY) | 신규 SaaS 대신 Airtable UI 직접 사용(0개발) 또는 Streamlit 버튼 1개(최소 BUILD) 중 선택 | 승인 경로 없이 플래그만 켜면 게시가 DRAFT에서 영구 정지 |
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
| P0-2 | 단계 1~5 공식 Evidence 문서 복구 | **이 문서로 완료(A단계)** — B단계(test_dm_close.py 수정)는 별도 승인 대기 |
| P1-1 | 10-B Clean Measurement Baseline(테스트/실고객분리, 기준시점·계정키 확정) | 미착수 |
| P1-2 | 데이터 유실 동일 패턴(예외삼킴) 표적 감사 | 미착수 — order_detector 외 경로 존재 여부 확인 필요 |
| P1-3 | fetch_candidate_phashes() Pagination | 미착수 |
| P1-4 | 단계 6 격리 MVP 완성(Persona·Sourcebook 최소연결+Gate·Approval 통합검증) | 미착수 |
| P2-1~3 | imgbb / ERR-076 자동복구 / account_email SSOT | 미착수(기존 Gate 그대로) |
| P3 | Token 매뉴얼 갱신(장기교환 단계 추가) | 미착수 |
