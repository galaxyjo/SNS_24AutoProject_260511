# Feature Parity — 250723 → 260511

분석 기준일: 2026-05-26  
방향: 250723 설계 자산 → 260511 Gap 식별  
원칙: 실행 금지 / 삭제 금지 / 분석만 / 이식 시 manual review 필수

---

## 탐색 범위 및 발견 경로

| 파일 | 크기 | 성격 |
|------|------|------|
| `docs/manuals_20251121_0057.md` | 5.5MB | SNS AUTO SYSTEM MANUAL v3.4 — 전체 구조 설계 원본 |
| `dashboard/dashboard_full_tabs.py` | 159L | 6탭 대시보드 (DM/Price/Relay/Upload/CoreEngine/AI) |
| `modules/dm/state_machine.py` | 193L | DM 상태머신 완성 구현 |
| `modules/dm/rules.py` | 32L | 메시지 rule-based 필터 (banned/allowed) |
| `modules/price_router_fixed.py` | 55L | 가격 요청 큐잉 + FB_posts JSON 연동 |
| `modules/dm_response_engine_fixed.py` | 36L | 가격 기반 DM 응답 템플릿 + 시간대 말투 보정 |
| `modules/dm_listener_fixed.py` | 51L | DM 수신 시뮬레이터 + post_id 추출 + 가격 조회 |
| `modules/relay_handler.py` | 40L | DM relay 로깅 핸들러 |
| `modules/pipeline/feed_pipeline.py` | 52L | Airtable→FB→Airtable 파이프라인 설계 |
| `modules/adapter/adapter_airtable.py` | 34L | targets.json 기반 크롤링 URL 관리 |
| `modules/sns/wf_instagram_scheduler.py` | 50L | WT-INSTA-UP 워크플로 설계서 + WT-SESSION-V1 참조 |
| `modules/common/airtable_bridge.py` | 42L | 공유 모듈 (260511과 동일 API 서명) |

**주목**: `docs/manuals_20251121_0057.md` + `x0818-27대화 임시파일.txt`(1.3MB) + `섹션 0813.txt`(875KB)는 GPT 1년치 설계 대화 원본. 내용 중 `account_runner`, `cfg_loader`, `fb_crawler`, `log_trace`, `price_router`, `relay_handler` 등이 `__pycache__`에 존재 기록 → 작성 후 삭제된 핵심 모듈 6개 확인.

---

## Feature Parity 표

| # | Source (250723) | Asset Type | 250723 내용 | 260511 존재 여부 | Gap | Action | Priority |
|---|-----------------|------------|-------------|-----------------|-----|--------|----------|
| 1 | `modules/dm/state_machine.py` | 코드 | DM 상태머신 완성 구현. `DMState`: NEW→QUALIFY→QUOTE→CLOSE→FOLLOWUP→DONE. 상태 전이 검증룰 + SQLite 영속화 + 액션 큐잉(REPLY_TEMPLATE / CREATE_QUOTE / SEND_PAYMENT_LINK / FOLLOWUP / TAG_DONE) | ⚠️ 부분 — `dm_auto_reply.py`에 상태 개념 있으나 explicit 상태머신 없음. QUOTE/CLOSE/SEND_PAYMENT_LINK 단계 없음 | **QUOTE·CLOSE·결제링크 상태 전이 없음** — 리드가 관심 표현 후 다음 단계로 자동 진입 불가 | 상태 전이 설계를 260511 lead_scorer + dm_auto_reply에 병합 | **P1** |
| 2 | `modules/dm/rules.py` | 코드 | Rule-based 메시지 필터. banned/allowed 단어 정책 평가. `RuleResult(passed, reason)` 반환 | ❌ 없음 — 260511은 Gemini AI 응답만, 규칙 필터 없음 | **스팸·금지어 차단 레이어 없음** — AI가 모든 DM을 무조건 처리 | DM 수신 시 rules.py 필터 선통과 후 AI 처리로 이식 | **P1** |
| 3 | `modules/price_router_fixed.py` | 코드 | 가격 요청 큐잉. `register_price_request(post_id, fb_user)` → JSON 큐 적재. `simulate_price_reply()` → 가격 확정 후 fb_posts 업데이트 | ❌ 없음 — Phase 3 보류(`modules/trade/`) | **가격 질의→답변 자동화 없음** — 가격 DM 수신 시 수동 처리 필요 | trade/ 모듈 설계 시 price_router 로직 참조 | **P2** |
| 4 | `modules/dm_response_engine_fixed.py` | 코드 | 가격 기반 DM 응답 3종 템플릿. 시간대별 말투 보정(오전→정중, 저녁→캐주얼). `generate_reply(fb_user, price)` | ⚠️ 부분 — `ai_reply_generator.py`에 Gemini 기반 개인화 응답 있음. 가격 변수 반영 없음. 시간대 조정 없음 | **가격 정보를 DM 응답에 자동 주입하는 경로 없음** | ai_reply_generator에 price/시간대 컨텍스트 파라미터 추가 검토 | **P1** |
| 5 | `modules/dm_listener_fixed.py` | 코드 | DM 수신 시 메시지에서 `POST_ID` 추출 → 연관 FB 포스트의 가격 조회 → 자동 응답 생성 흐름 | ⚠️ 부분 — `dm_receiver.py`가 Webhook으로 DM 수신하지만 post_id 추출 → 가격 조회 로직 없음 | **DM과 FB 포스트 가격 간 연결 고리 없음** | dm_receiver에서 post_id 매핑 + 가격 컨텍스트 주입 경로 설계 | **P2** |
| 6 | `modules/relay_handler.py` | 코드 | DM relay 이벤트 로깅. `relay_message(dm_event)` → `log_dm_action(user_id, message, post_id, action)` | ❌ 없음 — 260511은 중앙 logger에 단순 INFO 기록, relay 이벤트 분류 없음 | **DM 릴레이 이벤트가 별도 로그 카테고리로 추적되지 않음** | dm_receiver에 relay 이벤트 전용 로그 추가 | **P2** |
| 7 | `dashboard/dashboard_full_tabs.py` | 코드 | 6탭 대시보드: 홈 / 계정상태 / 메시지흐름 / 자동실행로그 / CoreEngine리스너 / AI예측. DM·Price·Relay·Upload 4종 지표 동시 표시. Auto-refresh 3초. AI 예측 점수 | ⚠️ 부분 — `dashboard.py`에 KPI/Upload/Lead/댓글 탭 있음. Price·Relay·AI 예측 탭 없음. Auto-refresh 없음 | **Price 로그·Relay 로그·AI 예측 시각화 없음** | dashboard.py에 Price/Relay 탭 추가 + Auto-refresh 구현 검토 | **P2** |
| 8 | `modules/pipeline/feed_pipeline.py` | 코드 | Airtable→FB크롤링→Airtable 파이프라인 명시적 설계. `fetch_target_urls()` + `run_facebook_crawler(url)` + `create_source_feed_record(post)` 3단계 명확 분리 | ⚠️ 부분 — 260511에 구현됨. 단, `_job_fb_crawl()`이 main.py에 인라인. 명시적 파이프라인 클래스/함수 없음 | **파이프라인 단계가 인라인 코드에 매몰** — 단계별 테스트·교체 불가 | pipeline_feed_ingest.py 리팩터링 검토 (현재 dead 676L) | **P2** |
| 9 | `modules/adapter/adapter_airtable.py` | 코드 | `config/targets.json` 기반 크롤링 URL 동적 관리. list/dict 구조 양방향 지원 | ⚠️ 부분 — 260511은 accounts.json의 `crawl_urls[]` 또는 .env 하드코딩. targets.json 동적 관리 없음 | **크롤링 대상 URL이 accounts.json에 종속** — Airtable/UI에서 동적 변경 불가 | Airtable Source_Feeds 기반 URL 동적 로딩 검토 | **P2** |
| 10 | `modules/sns/wf_instagram_scheduler.py` | 설계문서 | WT-INSTA-UP: 예약→업로드 5단계 흐름 설계 (check_schedule → load_package → wait_until → upload → log_result). WT-SESSION-V1(쿠키·세션) 후속 설계 참조 | ❌ 없음 — 260511은 APScheduler interval 기반. 예약 시간 지정 업로드 없음 | **시간 지정 예약 업로드 없음** — 현재는 5분 간격 폴링으로만 동작 | Airtable에 `scheduled_at` 필드 추가 + cron 기반 예약 업로드 검토 | **P2** |
| 11 | `modules/common/airtable_bridge.py` | 코드 | `get_table()` / `fetch_ready_one()` / `update_record()` | ✅ 동일 API 서명 — 260511과 완전 공유 | 없음 | 유지 | — |
| 12 | `docs/manuals_20251121_0057.md` | 설계문서 | SNS AUTO SYSTEM MANUAL v3.4 (5.5MB). 전체 시스템 구조·모듈 설명·운영 절차 원본 | ❌ 260511에 동급 운영 매뉴얼 없음 — CLAUDE.md가 개발 지침이지만 운영 절차서는 부재 | **운영 매뉴얼 없음** — 장애 시 대응 절차 미정의 | 260511 기준 운영 매뉴얼 신규 작성 참조용 | **P1** |
| 13 | `modules/dm/bot.py` (instabot) | 코드 | instabot API 기반 DM 읽기·reply 인터랙티브 흐름. `bot.api.get_inbox_v2()` → threads 순회 → 수동 확인 후 응답 | ❌ 없음 — 260511은 Meta Graph API Webhook 수신. 완전히 다른 아키텍처 | 이식 가치 없음 — 아키텍처 상이, Webhook 방식이 더 견고 | 폐기 | — |
| 14 | `modules/core/main_features.py` | 코드 | `account_runner.run_all_accounts()` 비동기 오케스트레이터. `RunFinishedError` 예외 클래스 | ⚠️ 부분 — 260511에 `account_manager` + `parallel_runner`(dead). async 대신 ThreadPoolExecutor | 이식 대상 아님 — account_runner 자체가 250723에서 삭제됨 | 참조 제외 | — |
| 15 | 삭제된 모듈군 (`__pycache__` 기록) | 설계 흔적 | `account_runner.py` / `fb_crawler.py` / `log_trace.py` / `session.py` / `cfg_loader.py` — 250723 핵심 6개 모듈. 현재 .py 삭제, `__pycache__` 기록만 남음 | ✅ 260511이 대체 구현 완료 | 없음 — 역할이 260511에서 더 완성된 형태로 구현됨 | 참조 제외 | — |

---

## Priority 분류 요약

### P0 — 현재 매출/런타임 필수 (즉시 영향)

해당 없음 — 현재 260511 런타임은 정상 동작 중.  
250723의 설계 자산은 **기능 확장** 영역에 해당하며 현재 운영을 차단하지 않음.

---

### P1 — 운영 안정화 (30일 이내 검토)

| # | Feature | 근거 |
|---|---------|------|
| 1 | **DM 상태머신 (QUOTE·CLOSE·결제링크)** | 현재 DM이 lead_scorer 단계에서 멈춤. 가격 문의→결제 유도 자동화가 없으면 리드 전환 수동 처리 필요 |
| 2 | **메시지 rule-based 필터** | AI 응답 전 스팸·욕설 사전 차단 없음. Gemini API 429 급증 시 스팸 DM이 비용 낭비 |
| 4 | **가격 컨텍스트 DM 응답** | 가격 질문에 AI가 일반 응답만 반환. 리드 이탈 위험 |
| 12 | **운영 매뉴얼** | 장애 발생 시 대응 절차 부재. watchdog 재시작 외 수동 복구 절차 미정의 |

---

### P2 — 장기 확장 (Phase 3 이후)

| # | Feature | 근거 |
|---|---------|------|
| 3 | **Price Router (견적 큐)** | `modules/trade/` Phase 3 계획과 일치. 당장 필요 없음 |
| 5 | **DM-FB post_id 가격 연결** | Price Router 완성 후 의존 |
| 6 | **Relay 이벤트 로그** | 로그 분류 고도화 — 현재 운영에 미영향 |
| 7 | **대시보드 Price/Relay/AI탭** | 데이터 없으면 탭 추가해도 의미 없음. Price Router 완성 후 |
| 8 | **파이프라인 명시적 분리** | 리팩터링 — 기능 변화 없음 |
| 9 | **크롤링 URL 동적 관리** | accounts.json 방식으로 현재 충분 |
| 10 | **시간 지정 예약 업로드** | 현재 5분 폴링으로 충분. 컨텐츠 예약 기능은 Phase 3+ |

---

## 이식 우선순위 Top 3

> **이식 시 반드시 manual review. 자동 복사 금지. (CLAUDE.md 규칙)**

| 순위 | 소스 파일 | 이식 대상 (260511) | 작업량 | 주의사항 |
|------|-----------|-------------------|--------|----------|
| 1 | `modules/dm/rules.py` | `modules/dm/dm_auto_reply.py` 앞단에 필터 삽입 | **소 (30L)** | `RuleResult` 클래스 그대로 사용 가능. banned 단어 목록은 운영 환경에 맞게 재정의 필요 |
| 2 | `modules/dm/state_machine.py` 의 `DMState` Enum + `STATE_TRANSITIONS` | `modules/crm/lead_scorer.py` 또는 신규 `modules/dm/dm_state.py` | **중 (100L 추정)** | SQLite 의존성 → Airtable 필드로 전환 필요. `QUOTE`·`CLOSE` 상태는 260511 CRM과 매핑 설계 필요 |
| 3 | `modules/dm_response_engine_fixed.py` 의 시간대 말투 보정 로직 | `modules/dm/ai_reply_generator.py` | **소 (20L)** | Gemini 프롬프트 시스템 인스트럭션에 시간대 컨텍스트 추가로 충분. 코드 직접 이식보다 프롬프트 수정 권장 |

---

## 결론 정정 (dead_module_map_250723.md 수정 필요)

> `dead_module_map_250723.md`의 "이식 가치 없음" 결론은 폐기.

250723은 코드 실행성이 낮은 설계 저장소이나, 아래 설계 자산은 **260511 다음 단계(P1~P2)의 청사진**으로 유효:

- DM 상태머신 설계 (NEW→QUOTE→CLOSE 흐름)
- Rule-based 메시지 필터 개념
- 가격 컨텍스트 기반 응답 엔진
- 6탭 대시보드 레이아웃 설계
- WT-INSTA-UP 예약 업로드 워크플로 설계

코드 직접 이식보다는 **설계 원리 참조 후 260511 아키텍처에 맞게 재구현** 권장.
