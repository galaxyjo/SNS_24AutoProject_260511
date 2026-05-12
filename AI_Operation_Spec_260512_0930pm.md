# PROJECT_MASTER_OVERVIEW.md

## PROJECT NAME

SNS_24AutoProject
24/7 Lead Acquisition Operating System

---

# PROJECT PURPOSE

본 프로젝트의 목적은 Facebook 콘텐츠를 자동 수집(Crawling)하고,
Instagram 콘텐츠로 자동 변환 및 업로드한 뒤,
Instagram DM(Webhook)을 통해 유입되는 고객 문의를 자동 저장·분석·응답·팔로업하여
최종적으로 “24시간 자동 리드 확보 및 주문 전환 시스템”을 구축하는 것이다.

본 시스템은 단순 SNS 자동화 프로그램이 아니라:

Content
→ Lead
→ CRM
→ Revenue

자동화 운영 시스템이다.

핵심 전략:

* 최소비용 최대효율
* 최소 인력 운영
* Event Driven Structure
* Airtable Control Tower
* 다계정 확장 가능 구조
* 운영 안정성 우선

---

# CURRENT REPOSITORY STATE

## ACTIVE REPOSITORY

C:\SNS_24AutoProject_260511

역할:

* git single source of truth
* 실제 실행 기준
* 실제 운영 기준
* 실제 배포 기준

---

## REFERENCE ONLY REPOSITORY

C:\SNS_24AutoProject_250723

역할:

* GPT 1년치 설계/로직 참조용
* 코드 아이디어 참조 가능

금지:

* 실행 금지
* 배포 금지
* git history 참조 금지
* 자동 이식 금지

모든 이식은:
manual review 후 진행.

---

# OVERALL AUTOMATION FLOW

Facebook Crawling
→ Airtable Source_Feeds
→ Content Mapping
→ Instagram_Posts
→ Instagram Upload
→ Meta Webhook
→ DM Receive
→ Lead_Interactions
→ CRM Processing
→ Auto Follow-up
→ Revenue Tracking

---

# CURRENT PROJECT STAGE

현재 단계:

Pre-Production Stabilization

즉:
Prototype 완료 후,
운영 안정화(Operation Stabilization) 단계 진행 중.

현재 핵심 목표:

* watchdog
* retry
* recovery
* centralized logging
* dashboard
* operational resilience

---

# CORE SUCCESS STATUS

## VERIFIED SUCCESS

✅ FB Crawling
✅ AdsPower Attach
✅ Selenium Attach
✅ Airtable Integration
✅ Source_Feeds Pipeline
✅ Content Mapping
✅ Instagram Upload
✅ Meta Webhook Verify
✅ DM Webhook Receive
✅ Lead_Interactions Logging
✅ Event Log Structure
✅ State Machine Structure
✅ CRM Base Structure
✅ Architecture Lock Structure

---

# CURRENT BOTTLENECKS

## OPERATIONAL STABILITY

현재 가장 큰 병목은:
기능 구현이 아니라 운영 안정성이다.

핵심 위험 요소:

* Selenium UI 변경
* ngrok disconnect
* Meta token expiration
* queue deadlock
* process crash
* retry failure
* logging fragmentation

---

# BUSINESS OBJECTIVE

목표:

Instagram DM
→ Lead
→ Follow-up
→ 주문 전환

---

# KPI

핵심 KPI:

* 일일 DM 수신 수
* Lead 전환율
* 주문 전환율
* Follow-up 성공률
* Queue 안정성
* Upload 성공률

---

# CURRENT PRIORITY ROADMAP

## PHASE 1 — STABILIZATION

1. watchdog
2. auto restart
3. retry queue
4. centralized logging
5. dashboard
6. monitoring

---

## PHASE 2 — CRM AUTOMATION

1. auto reply
2. follow-up scheduling
3. lead qualification
4. revenue tracking

---

## PHASE 3 — SCALING

1. multi-account orchestration
2. proxy scaling
3. distributed queue
4. AI response optimization

---

# CURRENT TRUTH DECLARATION

본 문서는:
현재 살아남아 실제 운영에 사용 중인 구조(Current Truth) 기준으로 작성되었다.

과거 실패안/폐기안/실험구조/임시 patch는 포함하지 않는다.
------------------------------------------------------------------------------

# SYSTEM_ARCHITECTURE.md

# SYSTEM DEFINITION

24/7 Lead Acquisition Operating System

---

# CORE ARCHITECTURE

## EVENT DRIVEN STRUCTURE

모든 흐름은:

* event
* state
* log

기반으로 동작한다.

---

# MAIN FLOW

main.py
→ orchestration
→ crawler
→ transformer
→ uploader
→ webhook
→ CRM
→ follow-up

---

# CORE COMPONENTS

| COMPONENT        | ROLE                      |
| ---------------- | ------------------------- |
| main.py          | orchestration only        |
| AdsPower         | browser/account isolation |
| Selenium Attach  | browser control           |
| crawler          | Facebook crawling         |
| transformer      | content mapping           |
| uploader         | Instagram upload          |
| webhook receiver | DM receive                |
| response_engine  | DM reply                  |
| Airtable         | state control tower       |
| dashboard        | visualization only        |
| ngrok            | webhook tunnel            |

---

# AIRTABLE ROLE

Airtable은:
단순 저장소가 아니라
Control Tower(State Control System) 역할이다.

핵심 역할:

* state management
* workflow control
* event tracking
* lead tracking
* CRM flow

---

# STATE MACHINE

## Source_Feeds

New
→ Content Ready
→ Waiting Upload
→ Published

---

## Instagram_Posts

Draft
→ Scheduled
→ Published
→ Archived

---

## Lead_Interactions

New
→ Qualified
→ Proposal
→ Won
→ Lost

---

# EVENT LOG STRUCTURE

모든 이벤트는:
update 기반이 아니라
append log 기반으로 유지한다.

즉:

DM 1건
= event 1건

---

# REPOSITORY AUTHORITY

## ACTIVE REPOSITORY

C:\SNS_24AutoProject_260511

현재 실제 운영 기준.

---

## REFERENCE REPOSITORY

C:\SNS_24AutoProject_250723

참조만 가능.

자동 이식 금지.

---

# MAIN.PY AUTHORITY RULE

현재 실제 orchestration 기준은:

ACTIVE repository의 main.py 이다.

문서/과거 로그보다:
현재 main.py 실행 흐름을 우선 Truth로 사용한다.

---

# ENVIRONMENT LOCK

현재 .env에 존재하는 key만 사용한다.

없는 key 추정 생성 금지.

---

# PLATFORM CONSTRAINTS

## Meta API

개발모드 제한 존재.
Webhook 수신 중심 구조 유지.

---

## AdsPower

로컬 실행 전제.

---

## ngrok

무료 플랜 전제.
고정 URL 불가.

모든 설계는 위 제약 유지 기준으로 진행한다.
--------------------------------------
# CURRENT_SYSTEM_STATE.md

# CURRENT PROJECT STATUS

현재 단계:

Pre-Production Stabilization

---

# VERIFIED COMPLETED

| FEATURE                   | STATUS |
| ------------------------- | ------ |
| FB Crawling               | ✅      |
| AdsPower Attach           | ✅      |
| Selenium Attach           | ✅      |
| Airtable Integration      | ✅      |
| Source_Feeds Pipeline     | ✅      |
| Content Mapping           | ✅      |
| Instagram Upload          | ✅      |
| Meta Webhook Verify       | ✅      |
| DM Receive                | ✅      |
| Lead_Interactions Logging | ✅      |
| Event Log Structure       | ✅      |
| State Machine             | ✅      |
| CRM Base Structure        | ✅      |
| Architecture Lock         | ✅      |

---

# PARTIAL / IN PROGRESS

| FEATURE              | STATUS |
| -------------------- | ------ |
| Auto Reply Engine    | ⚠️     |
| Follow-up Automation | ⚠️     |
| Dashboard            | ⚠️     |
| Queue Retry          | ⚠️     |
| Centralized Logging  | ⚠️     |
| Watchdog             | ⚠️     |
| Crash Recovery       | ⚠️     |

---

# NOT IMPLEMENTED

| FEATURE                    | STATUS |
| -------------------------- | ------ |
| Multi-account scaling      | ❌      |
| Distributed Queue          | ❌      |
| Full autonomous recovery   | ❌      |
| Revenue analytics          | ❌      |
| Full production resilience | ❌      |

---

# KNOWN ISSUES

## VERIFIED

* crawl_and_store: 시작 직후 1초 timing miss 존재
* ngrok reconnect 안정성 부족
* Selenium UI selector 변경 위험 존재
* centralized logging 미완료
* retry queue 미완료

---

# CURRENT RISKS

* Meta token expiration
* ngrok disconnect
* Selenium UI change
* queue deadlock
* process crash
* retry failure
* logging fragmentation

---

# CURRENT PRIORITY

1. watchdog
2. retry
3. recovery
4. monitoring
5. centralized logging
6. dashboard
7. operational resilience
--------------------------------------------------------------------------------------

# CURRENT_SYSTEM_STATE.md

# CURRENT PROJECT STATUS

현재 단계:

Pre-Production Stabilization

---

# VERIFIED COMPLETED

| FEATURE                   | STATUS |
| ------------------------- | ------ |
| FB Crawling               | ✅      |
| AdsPower Attach           | ✅      |
| Selenium Attach           | ✅      |
| Airtable Integration      | ✅      |
| Source_Feeds Pipeline     | ✅      |
| Content Mapping           | ✅      |
| Instagram Upload          | ✅      |
| Meta Webhook Verify       | ✅      |
| DM Receive                | ✅      |
| Lead_Interactions Logging | ✅      |
| Event Log Structure       | ✅      |
| State Machine             | ✅      |
| CRM Base Structure        | ✅      |
| Architecture Lock         | ✅      |

---

# PARTIAL / IN PROGRESS

| FEATURE              | STATUS |
| -------------------- | ------ |
| Auto Reply Engine    | ⚠️     |
| Follow-up Automation | ⚠️     |
| Dashboard            | ⚠️     |
| Queue Retry          | ⚠️     |
| Centralized Logging  | ⚠️     |
| Watchdog             | ⚠️     |
| Crash Recovery       | ⚠️     |

---

# NOT IMPLEMENTED

| FEATURE                    | STATUS |
| -------------------------- | ------ |
| Multi-account scaling      | ❌      |
| Distributed Queue          | ❌      |
| Full autonomous recovery   | ❌      |
| Revenue analytics          | ❌      |
| Full production resilience | ❌      |

---

# KNOWN ISSUES

## VERIFIED

* crawl_and_store: 시작 직후 1초 timing miss 존재
* ngrok reconnect 안정성 부족
* Selenium UI selector 변경 위험 존재
* centralized logging 미완료
* retry queue 미완료

---

# CURRENT RISKS

* Meta token expiration
* ngrok disconnect
* Selenium UI change
* queue deadlock
* process crash
* retry failure
* logging fragmentation

---

# CURRENT PRIORITY

1. watchdog
2. retry
3. recovery
4. monitoring
5. centralized logging
6. dashboard
7. operational resilience
------------------------------------------------------------------------------
# ARCHITECTURE_LOCK.md

# ARCHITECTURE LOCK DECLARATION

본 문서는 현재 프로젝트의
절대 변경 금지 구조(Architecture Lock)를 정의한다.

현재 프로젝트는:

Prototype 단계가 아니라
Pre-Production Stabilization 단계이다.

따라서:
대규모 리팩토링보다
운영 안정성 유지가 최우선이다.

---

# CURRENT TRUTH AUTHORITY

현재 Truth 기준:

1. ACTIVE repository 실제 코드
2. 현재 main.py 실행 흐름
3. 실제 orchestration
4. 실제 실행 로그
5. 현재 운영 중인 State Machine

문서/과거 대화보다:
실제 실행 흐름을 우선한다.

---

# ACTIVE REPOSITORY LOCK

## ACTIVE

C:\SNS_24AutoProject_260511

역할:

* git 기준
* 실행 기준
* 운영 기준
* 배포 기준

---

# REFERENCE ONLY REPOSITORY

## REFERENCE ONLY

C:\SNS_24AutoProject_250723

허용:

* 로직 참조
* 아이디어 참조

금지:

* 자동 코드 이식
* git history 참조
* 실행
* 배포

모든 이식은:
manual review 후 진행.

---

# MAIN.PY AUTHORITY LOCK

현재 orchestration authority는:

ACTIVE repository의 main.py 이다.

절대 변경 금지:

* orchestration flow 임의 변경
* execution order 변경
* main.py 역할 변경

main.py 역할:

orchestration only

---

# AIRTABLE CONTROL TOWER LOCK

Airtable은:
단순 DB가 아니다.

역할:

* state management
* workflow control
* event tracking
* CRM flow
* operational coordination

절대 제거 금지.

---

# EVENT LOG LOCK

모든 이벤트는:
append log 기반 유지.

금지:

* overwrite 중심 구조
* state overwrite 구조
* DM merge overwrite

기준:

DM 1건
= Event 1건

---

# STATE MACHINE LOCK

현재 State Machine 구조 유지.

금지:

* 상태명 임의 변경
* bypass flow
* direct transition
* state skip

현재 구조:

Source_Feeds
→ Content Ready
→ Waiting Upload
→ Published

Lead_Interactions
→ New
→ Qualified
→ Proposal
→ Won / Lost

---

# ROLE SEPARATION LOCK

현재 역할 분리 유지.

절대 merge 금지.

| MODULE          | ROLE                 |
| --------------- | -------------------- |
| main.py         | orchestration only   |
| crawler         | crawling only        |
| transformer     | content mapping only |
| uploader        | upload only          |
| dm_receiver     | webhook receive only |
| response_engine | reply only           |
| dashboard       | visualization only   |
| Airtable        | state control only   |

---

# ADSPOWER LOCK

AdsPower attach 구조 유지.

절대 금지:

* AdsPower 제거
* 일반 Selenium 단독 전환
* browser isolation 제거

AdsPower 목적:

* account isolation
* fingerprint separation
* operational stability

---

# SELENIUM ATTACH LOCK

현재 attach 구조 유지.

절대 금지:

* Selenium architecture rewrite
* attach bypass
* browser recreation 구조 변경

---

# PLATFORM CONSTRAINT LOCK

## Meta API

현재:
개발모드 제한 존재.

Webhook 수신 중심 운영 유지.

---

## ngrok

무료 플랜 전제.

고정 URL 없음.

모든 설계는 위 제약 유지 기준.

---

# FORBIDDEN ACTIONS

절대 금지:

* architecture rewrite
* monolithic merge
* Airtable 제거
* AdsPower 제거
* Selenium 제거
* state machine 제거
* event log 제거
* 운영 중 구조 임의 변경
* speculative refactoring
* dead module 자동 복구
* 추정 기반 migration

---

# ROOT CAUSE FIRST RULE

현재 단계는:

feature expansion 단계가 아니라
operational stabilization 단계이다.

반드시:

Reproduce
→ Isolate
→ Root Cause
→ Fix
→ Verify

순서를 유지한다.

---

# NO SILENT ASSUMPTION RULE

추정 기반 결정 금지.

반드시 명시:

* Verified
* Assumption
* Unverified

불확실한 경우:
“모릅니다”라고 명시한다.

---

# FINAL DECLARATION

현재 프로젝트의 핵심 목표는:

“기능 추가”
가 아니라

“24시간 운영 가능한 안정성 확보”

이다.
--------------------------------------------------------------------
# ERROR_DATABASE.md

# ERROR DATABASE

현재까지 실제 운영/디버깅 과정에서 확인된
핵심 오류 및 Root Cause 정리.

중복/폐기 오류 제외.
Current Truth 기준만 유지.

---

# ERROR-001

## TITLE

Create Button Not Found

---

## LAYER

Instagram UI / Selenium

---

## ROOT CAUSE

실제 Instagram 홈 상태가 아니었음.

nav 존재 여부만 기준으로 판단하여:
잘못된 UI state assumption 발생.

---

## FIX

* login validation 추가
* 실제 homepage state 확인
* popup 처리 추가
* sequential state verification 적용

---

## PREVENTION

UI action 전:
반드시 state validation 수행.

---

# ERROR-002

## TITLE

Meta Webhook Verify Failure

---

## LAYER

Meta Webhook / Network

---

## ROOT CAUSE

* webhook path mismatch
* ngrok dead tunnel
* tester role 미설정

---

## FIX

* /webhook path 검증
* localhost:4040 상태 확인
* Instagram tester role 추가

---

## PREVENTION

Webhook 실패 시:
코드보다 network/state 먼저 검증.

---

# ERROR-003

## TITLE

ERR_NGROK_3200

---

## LAYER

ngrok / tunnel

---

## ROOT CAUSE

ngrok tunnel dead.

URL 존재 ≠ 실제 연결 상태.

---

## FIX

* localhost:4040 확인
* process alive 확인
* tunnel status 검증

---

## PREVENTION

ngrok health monitoring 추가 필요.

---

# ERROR-004

## TITLE

Airtable 403 Forbidden

---

## LAYER

Airtable Schema

---

## ROOT CAUSE

실제 table:
Lead_Interactions

코드:
Leads

table mismatch 발생.

---

## FIX

실제 Airtable schema 직접 조회 후 수정.

---

## PREVENTION

추측 기반 schema 사용 금지.

---

# ERROR-005

## TITLE

latin-1 codec encode failure

---

## LAYER

Environment / Encoding

---

## ROOT CAUSE

.env placeholder 문자열 사용.

기존 환경변수 cache 유지 문제.

---

## FIX

load_dotenv(override=True)

---

## PREVENTION

실제 env value 검증 필수.

---

# ERROR-006

## TITLE

FastAPI object has no attribute run

---

## LAYER

FastAPI Runtime

---

## ROOT CAUSE

Flask 방식 실행 시도.

---

## FIX

uvicorn 기반 실행으로 수정.

---

## PREVENTION

framework runtime 방식 혼용 금지.

---

# ERROR-007

## TITLE

crawl_and_store timing miss

---

## LAYER

Crawler Timing

---

## ROOT CAUSE

시작 직후 1초 timing miss 존재.

---

## STATUS

Verified Known Issue

---

## PREVENTION

retry / startup stabilization 필요.

---

# ERROR-008

## TITLE

Dead Module Import Collision

---

## LAYER

Python Import System

---

## ROOT CAUSE

과거 repository import path 충돌.

---

## FIX

ACTIVE repository 기준 path 고정.

---

## PREVENTION

250723 repository 자동 import 금지.

---

# OPERATIONAL LESSONS

## LESSON-01

실제 운영 흐름 > 설계 아름다움

---

## LESSON-02

실제 코드 > 과거 문서

---

## LESSON-03

운영 단계에서는:
기능 추가보다 안정성이 우선.

---

## LESSON-04

90% Selenium 오류는:
코드보다 state mismatch 문제.

---

## LESSON-05

Network / Webhook 문제는:
코드보다 tunnel/state 검증이 우선.
--------------------------------------------------------------------
# OPERATION_RUNBOOK.md

# OPERATION RUNBOOK

현재 프로젝트 운영 기준 문서.

목적:
24/7 운영 안정성 유지.

---

# CURRENT OPERATION STAGE

Pre-Production Stabilization

현재 핵심 목표:

* watchdog
* retry
* recovery
* centralized logging
* dashboard
* operational resilience

---

# SESSION START RULE

세션 시작 시 반드시:

1. CLAUDE.md 읽기
2. CURRENT_SYSTEM_STATE.md 확인
3. 마지막 운영 상태 확인
4. 현재 known issues 확인

추측 기반 이어서 작업 금지.

---

# CURRENT AUTHORITY

실제 기준:

C:\SNS_24AutoProject_260511

main.py 흐름 우선.

---

# DAILY OPERATION CHECKLIST

## 1. main.py 실행 확인

확인 항목:

* process alive
* orchestration 정상
* queue 동작
* upload 상태
* webhook 상태

---

## 2. ngrok 상태 확인

확인:

* localhost:4040
* tunnel alive
* external access 가능 여부

---

## 3. Webhook 상태 확인

검증:

* Meta Verify
* DM receive
* Lead_Interactions insert

---

## 4. Airtable 상태 확인

검증:

* API 정상
* table access 정상
* schema mismatch 없음

---

## 5. Upload 상태 확인

검증:

* Instagram upload success
* Selenium attach success
* AdsPower attach success

---

# RESTART PROCEDURE

## Flask/Webhook Restart

1. 기존 process 확인
2. dead process 종료
3. Start-Process 기반 재실행
4. localhost verify
5. ngrok verify

---

# NGROK RECOVERY

## 증상

* webhook fail
* ERR_NGROK_3200
* external unreachable

---

## 절차

1. localhost:4040 확인
2. ngrok process 확인
3. tunnel recreate
4. webhook retest

---

# META WEBHOOK VERIFY PROCEDURE

확인 순서:

1. ngrok alive
2. /webhook route alive
3. tester role 정상
4. Meta Verify 재시도

---

# TOKEN ISSUE RESPONSE

## 증상

* Meta auth fail
* Airtable unauthorized
* webhook reject

---

## 대응

1. token expiration 확인
2. env verify
3. override reload 확인
4. API retest

---

# KNOWN ISSUES

## VERIFIED

* crawl_and_store timing miss
* ngrok reconnect 불안정
* Selenium selector 변경 가능성
* centralized logging 미완료
* retry queue 미완료

---

# OPERATION PRIORITY

현재 우선순위:

1. watchdog
2. retry
3. recovery
4. monitoring
5. centralized logging
6. dashboard

---

# CRITICAL OPERATION RULES

## RULE-01

실제 로그 먼저 확인.

---

## RULE-02

추측 기반 수정 금지.

---

## RULE-03

Root Cause 없이 리팩토링 금지.

---

## RULE-04

250723 repository 자동 이식 금지.

---

## RULE-05

실제 운영 흐름 우선.

---

# FAILURE RESPONSE FLOW

장애 발생 시:

Reproduce
→ Isolate
→ Root Cause
→ Fix
→ Verify

순서 유지.

---

# CURRENT MISSION

현재 프로젝트 핵심 목표:

“기능 추가”
가 아니라

“24시간 운영 가능한 안정성 확보”
이다.


