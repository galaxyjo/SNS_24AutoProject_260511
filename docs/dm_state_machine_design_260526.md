# DM 상태머신 설계 — 260526

설계 기준일: 2026-05-26  
상태: **설계 전용 — 미구현 (구현 승인 전 코드 변경 금지)**  
참조: `C:\SNS_24AutoProject_250723\modules\dm\state_machine.py` (250723 설계 자산)  
현행 운영: `modules/dm/dm_receiver.py` + `dm_auto_reply.py` + `dm_followup_scheduler.py`

---

## 전환 흐름

```
NEW → QUOTE → NEGOTIATING → PAYMENT_LINK_SENT → PAID → FOLLOWUP → CLOSE
                                                              ↓
                                                            LOST
```

| 전환 | 트리거 |
|------|--------|
| NEW → QUOTE | 단가/가격 키워드 수신 + rules.evaluate 통과 |
| QUOTE → NEGOTIATING | 고객이 가격 조건 협의 키워드 발신 |
| NEGOTIATING → PAYMENT_LINK_SENT | 운영자 승인 또는 최저가 합의 감지 |
| PAYMENT_LINK_SENT → PAID | 입금 확인 키워드 or Webhook |
| PAID → FOLLOWUP | 결제 완료 후 일정 시간 경과 |
| FOLLOWUP → CLOSE | 팔로업 완료 or 운영자 수동 전환 |
| FOLLOWUP → LOST | 팔로업 미응답 타임아웃 |
| NEGOTIATING → LOST | 협의 포기 감지 또는 타임아웃 |

---

## 상태별 상세 설계

---

### STATE: NEW

| 항목 | 내용 |
|------|------|
| **Trigger** | DM Webhook POST 수신 (`/webhook`), `record_interaction()` 호출 완료 |
| **Action** | Lead_Interactions 레코드 생성, lead_status="new", bridge_status="dm_received", rules.evaluate 실행 (banned → 즉시 차단, allowed/no_match → QUOTE 전환 대기) |
| **Airtable field** | `bridge_status="dm_received"`, `lead_status="new"`, `lead_score`, `lead_grade` |
| **Retry** | 없음 (수신 단계 — Webhook은 Meta가 재전송) |
| **Timeout** | 없음 (상태 진입만, 타임아웃은 FOLLOWUP 단계에서 관리) |
| **Telegram alert** | ✅ 현재 `send_telegram()` 호출 중 — 수신자 IGSID + 문의 내용 전송 |
| **Fail case** | Airtable PATCH 실패 → `last_error_msg` 기록, retry queue 등록 |
| **Current 260511 support** | ✅ **완전 지원** — `dm_receiver.py:record_interaction()` |
| **250723 참조** | `state_machine.py:DMState.NEW`, `process_dm()` 진입 분기 |

---

### STATE: QUOTE

| 항목 | 내용 |
|------|------|
| **Trigger** | `detect_price_inquiry()` True + `rules.evaluate()` passed → `handle_price_inquiry()` 호출 |
| **Action** | `get_base_price()` 조회 → 10% 마진 계산 → AI 응답 생성(Gemini) or 템플릿 폴백 → `send_ig_reply()` → `update_lead_replied()` |
| **Airtable field** | `bridge_status="auto_replied"`, `lead_status="qualified"`, `replied_at`, `response_delay_sec` |
| **Retry** | ✅ IG DM 발송 실패 시 retry_queue 등록 (`ig_auto_reply` 핸들러, 백오프 10s/60s/300s) |
| **Timeout** | 없음 (발송 즉시 실행) |
| **Telegram alert** | ✅ `send_telegram_autoreply()` — 발송 단가 + 발신 IGSID |
| **Fail case** | get_base_price=None → 응답 생략 + WARNING 로그 / IG DM 실패 → retry queue |
| **Current 260511 support** | ✅ **완전 지원** — `dm_auto_reply.py:handle_price_inquiry()` |
| **250723 참조** | `state_machine.py:DMState.QUOTE`, action=`REPLY_TEMPLATE` / `CREATE_QUOTE` |

---

### STATE: NEGOTIATING

| 항목 | 내용 |
|------|------|
| **Trigger** | QUOTE 발송 후 고객 재문의: 협의 키워드("조건","협의","더 싸게","네고","할인") 포함 DM 수신 |
| **Action** | bridge_status 갱신, 협의 플래그 기록, (선택) 운영자 Telegram 알림 발송 — 자동 응답 X, 운영자 개입 대기 |
| **Airtable field** | `bridge_status="negotiating"` (신규 값 필요), `negotiation_note` (신규 필드 필요) |
| **Retry** | 없음 (상태 기록 단계) |
| **Timeout** | 48h 무응답 → LOST 자동 전환 권장 |
| **Telegram alert** | ✅ 운영자 알림 필수 — "협의 요청 발생 | {IGSID} | {문의내용[:100]}" |
| **Fail case** | 키워드 분류 오탐 → lead_status 오염 위험 → rules.evaluate 2단계 정책으로 보완 |
| **Current 260511 support** | ❌ **미지원** — bridge_status에 "negotiating" 없음, 협의 키워드 감지 로직 없음 |
| **250723 참조** | `state_machine.py:DMState.QUALIFY` (유사 개념), `_classify_state()` 협의 키워드 분기 |

---

### STATE: PAYMENT_LINK_SENT

| 항목 | 내용 |
|------|------|
| **Trigger** | 운영자가 결제 링크 수동 발송 OR 자동화 규칙으로 링크 포함 DM 발송 완료 |
| **Action** | bridge_status 갱신, payment_link + sent_at 기록, 입금 확인 Polling 또는 Webhook 대기 |
| **Airtable field** | `bridge_status="payment_link_sent"` (신규), `payment_link` (신규), `payment_link_sent_at` (신규) |
| **Retry** | 24h 내 입금 미확인 시 리마인더 DM 재발송 (1회) |
| **Timeout** | 72h 무입금 → LOST 전환 권장 |
| **Telegram alert** | ✅ "결제 링크 발송 | {IGSID}" |
| **Fail case** | DM 발송 실패 → retry queue, 링크 만료 → 재발급 후 재발송 |
| **Current 260511 support** | ❌ **미지원** — 결제 링크 발송 플로우 없음 |
| **250723 참조** | `state_machine.py` action=`SEND_PAYMENT_LINK` (정의만 존재, 구현 없음) |

---

### STATE: PAID

| 항목 | 내용 |
|------|------|
| **Trigger** | 입금 확인 키워드("입금","결제완료","보냈","송금") 포함 DM 수신 OR 외부 결제 Webhook |
| **Action** | `handle_order_conversion()` 호출 → lead_status="converted", converted_at 기록, Telegram 🎉 알림 |
| **Airtable field** | `bridge_status="converted"`, `lead_status="converted"`, `converted_at` |
| **Retry** | 없음 |
| **Timeout** | 없음 (전환 완료 상태) |
| **Telegram alert** | ✅ 현재 `order_detector.py` — "🎉 주문 전환 완료" 알림 전송 중 |
| **Fail case** | 오탐(입금 키워드이나 실제 미결제) → 운영자 수동 수정 필요, 자동 롤백 불가 |
| **Current 260511 support** | ✅ **완전 지원** — `order_detector.py:handle_order_conversion()` |
| **250723 참조** | `state_machine.py:DMState.CLOSE`, action=`TAG_DONE` (유사 개념) |

---

### STATE: FOLLOWUP

| 항목 | 내용 |
|------|------|
| **Trigger** | QUOTE 발송 후 `set_followup_schedule()` 호출 → 24h/48h/72h 지연 발송 |
| **Action** | `process_due_followups()` 폴링 (5min 간격) → 단계별 템플릿 DM 발송 → bridge_status 갱신 |
| **Airtable field** | `bridge_status`: auto_replied→followup1_sent→followup2_sent→followup3_sent |
| **Retry** | ✅ IG DM 실패 시 retry queue 등록 |
| **Timeout** | followup3_sent 이후 72h 무응답 → LOST 전환 권장 (현재 미구현) |
| **Telegram alert** | ✅ 각 단계별 알림 (followup1/2/3_sent) |
| **Fail case** | `send_ig_reply()` 실패 → bridge_status="followup_error" 기록 |
| **Current 260511 support** | ✅ **완전 지원** — `dm_followup_scheduler.py:process_due_followups()` |
| **250723 참조** | `state_machine.py:DMState.FOLLOWUP`, action=`FOLLOWUP` |

---

### STATE: CLOSE

| 항목 | 내용 |
|------|------|
| **Trigger** | PAID 완료 후 팔로업 완료 OR 운영자 수동 전환 |
| **Action** | 최종 상태 마킹, 추가 DM 발송 중단, KPI 집계 대상 포함 |
| **Airtable field** | `bridge_status="closed"` (신규), `lead_status="converted"`, `closed_at` (신규) |
| **Retry** | 없음 (종료 상태) |
| **Timeout** | 없음 |
| **Telegram alert** | 선택적 — "거래 완료 | {IGSID}" |
| **Fail case** | 없음 (종료 상태) |
| **Current 260511 support** | ⚠️ **Partial** — converted 상태가 CLOSE에 해당하나 명시적 CLOSE 상태 없음 |
| **250723 참조** | `state_machine.py:DMState.DONE`, transitions CLOSE→DONE |

---

### STATE: LOST

| 항목 | 내용 |
|------|------|
| **Trigger** | NEGOTIATING 48h 무응답 / PAYMENT_LINK_SENT 72h 미결제 / FOLLOWUP3 이후 72h 무응답 |
| **Action** | bridge_status 갱신, 추가 DM 발송 중단, KPI 집계에서 lost_count 반영 |
| **Airtable field** | `bridge_status="lost"` (신규), `lead_status="disqualified"` (신규), `lost_reason` (신규), `lost_at` (신규) |
| **Retry** | 없음 (포기 상태) |
| **Timeout** | 없음 (타임아웃이 트리거) |
| **Telegram alert** | 선택적 — "⚠️ 리드 소실 | {IGSID} | reason={lost_reason}" |
| **Fail case** | 오탐(단순 지연인데 LOST 처리) → 운영자 수동 복구 경로 필요 |
| **Current 260511 support** | ❌ **미지원** — bridge_status에 "lost" 없음, 타임아웃 로직 없음 |
| **250723 참조** | `state_machine.py` 명시적 LOST 없음 — 현 설계에서 신규 추가 |

---

## 상태 지원 현황 요약

| State | 260511 지원 | 필요 신규 작업 |
|-------|------------|----------------|
| NEW | ✅ 완전 | 없음 |
| QUOTE | ✅ 완전 | 없음 |
| NEGOTIATING | ❌ 미지원 | bridge_status 값 추가, 키워드 감지 로직, Telegram 알림 |
| PAYMENT_LINK_SENT | ❌ 미지원 | bridge_status 값 추가, Airtable 필드 3개, 발송 로직 |
| PAID | ✅ 완전 | 없음 (order_detector.py converted 상태가 대응) |
| FOLLOWUP | ✅ 완전 | LOST 타임아웃 전환만 추가 필요 |
| CLOSE | ⚠️ Partial | 명시적 CLOSE 상태 분리 필요 |
| LOST | ❌ 미지원 | bridge_status 값 추가, Airtable 필드 4개, 타임아웃 감지 로직 |

---

## 신규 Airtable 필드 목록 (구현 시 추가 필요)

| 테이블 | 필드명 | 타입 | 용도 |
|--------|--------|------|------|
| Lead_Interactions | `negotiation_note` | Long text | 협의 내용 메모 |
| Lead_Interactions | `payment_link` | URL | 발송한 결제 링크 |
| Lead_Interactions | `payment_link_sent_at` | DateTime | 링크 발송 시각 |
| Lead_Interactions | `closed_at` | DateTime | 거래 종료 시각 |
| Lead_Interactions | `lost_reason` | Single select | negotiation_timeout / payment_timeout / followup_timeout / manual |
| Lead_Interactions | `lost_at` | DateTime | LOST 전환 시각 |

bridge_status 허용값 추가 필요: `negotiating`, `payment_link_sent`, `closed`, `lost`  
lead_status 허용값 추가 필요: `disqualified`

---

## 구현 우선순위 (Phase 구분)

| Phase | 대상 State | 작업 규모 | 근거 |
|-------|-----------|-----------|------|
| **현재** | NEW, QUOTE, PAID, FOLLOWUP | — | 이미 운영 중 |
| **Phase A (P1)** | CLOSE, LOST | 소 (~50L) | 타임아웃 + bridge_status 값만 추가, KPI 개선 직결 |
| **Phase B (P2)** | NEGOTIATING | 중 (~100L) | 운영자 개입 플로우, 키워드 정책 확장 |
| **Phase C (P3)** | PAYMENT_LINK_SENT | 대 (~150L) | 결제 연동 필요, 외부 Webhook 또는 폴링 설계 별도 |

---

## 참조 소스 매핑

| 설계 요소 | 260511 소스 | 250723 소스 |
|-----------|------------|------------|
| State enum | 없음 (bridge_status 문자열) | `state_machine.py:DMState` |
| 전환 검증 | 없음 | `state_machine.py:validate_transition()` |
| 키워드 → 상태 분류 | `dm_receiver.py:detect_price_inquiry()` (단순) | `state_machine.py:_classify_state()` |
| 액션 큐잉 | `retry_queue.py` (DM 발송 전용) | `state_machine.py:enqueue_action()` (ig_actions 테이블) |
| 팔로업 스케줄 | `dm_followup_scheduler.py` (3단계) | `state_machine.py` action=FOLLOWUP |
| 결제 링크 발송 | 없음 | `state_machine.py` action=SEND_PAYMENT_LINK (정의만) |
| Rules 필터 | `rules.py` (260526 신규 이식) | `state_machine.py` 분기 조건 |

---

*이 문서는 설계 전용입니다. 구현 승인 전 코드 변경 금지.*  
*다음 단계: 사용자 승인 → Phase A (CLOSE/LOST) 구현 순서로 진행.*
