# DM_RELAY_COMMERCE_RFC — Buyer↔회장님↔Supplier 릴레이 판매대행 시스템

- 상태: **V6.3 — 사용자 리뷰 반영(Non-Goals 재검토 트리거 + 신규 아이디어 Open Question 추가).** 코드·Airtable·git·운영설정 전부 미변경, 사용자 "설계도완성" 선언 대기.
- 작성: Claude Code, 교차검증: Codex (다회차 설계감사)
- 최초 작성일: 2026-07-13
- Git 커밋: 아직 없음 (신규 파일 1개만 존재, `git add/commit` 별도 승인 대상)

---

## 1. Executive Summary

Instagram 댓글/DM으로 들어오는 구매 문의를, 원 게시물을 올린 공급자(FB 그룹 등 제3자)에게 회장님이 중계 전달하고 답변을 다시 buyer에게 전달하는 **판매대행(consignment) 중계 시스템**. Buyer에게는 항상 회장님 브랜드 계정 명의로만 노출되고 공급자 신원은 비노출된다. 이후 3자무역·구매대행으로 확장 가능한 뼈대로 설계한다.

## 2. Business Ownership Model

```
Buyer
  ↕
회장님 브랜드·운영 시스템   ← Buyer가 유일하게 인지하는 판매 주체
  ↕
원천 Supplier              ← 비노출
```

**주의**: "판매자처럼 보이는 것"과 "법적 판매자(Merchant of Record)"는 다른 개념. 회장님이 결제·가격·환불·클레임까지 책임지면 MoR에 가깝고, 연락 전달만 하면 중개/판매대행에 가까움 — 이 책임 경계는 계약·약관 확정 필요(§12 Open Questions Q1/Q2, 미결).

## 3. Goals / Non-Goals

**Goals**: 댓글/DM 문의 자동 대응 시작 → 필요 시 회장님을 통해 공급자와 왕복중계 / 데이터 유실·중복 없이 처리(at-least-once + idempotent) / Kill-switch로 즉시 되돌릴 수 있음 / 향후 확장 시 뼈대 재설계 불필요.

**Non-Goals (이번 범위 밖 — 단, 무기한 보류 아님, V6.3)**: WhatsApp/Kakao/Zalo 연동은 **지금 당장 만들지는 않지만 무기한 보류가 아니다.** 회장님 확인(260713): 실제로는 Messenger보다 WhatsApp·Kakao로 공급자 연락이 오는 경우가 더 많음 — 월 30건/매출20% 기준을 다 채울 때까지 조용히 미루지 않고, **P0-4(Go/No-Go) 시점에 반드시 다시 논의 대상으로 상기시킬 것.** 그때 회장님이 바로 착수할지 계속 보류할지 결정한다. / 공급자 Instagram 사전 온보딩(1단계는 사람이 Messenger로 수동 연락) / 3자무역 특화 규칙(관세·통관·해외결제) / Order/Payment/Fulfillment 전체 구현.

## 4. Alternatives Considered

| 옵션 | 내용 | 결론 |
|---|---|---|
| 공급자도 IG로 온보딩 | 공급자가 먼저 DM해야 24h 윈도우 열림, 완전자동 가능 | 공급자 협조 필요·이탈 위험 → 후순위. **단, 260713 신규 아이디어(회장님 제안)**: buyer 댓글에 자동봇이 답글 달 때, **동시에 원 공급자에게도 "DM 보내주세요" 댓글을 유도**하면 공급자가 먼저 메시지하는 조건이 성립해 24h 윈도우가 자동으로 열릴 수 있음 — **메커니즘 미확정(§12 Open Question 신규)**, 어디에 어떻게 댓글을 다는지 확인 필요 |
| 공급자 연락처를 buyer에 그대로 노출 | 중계 없이 단순 전달 | 플랫폼 이탈(직거래) 위험 → 기각 |
| **사람(회장님) 중계 + 티켓번호 매칭 (채택)** | Messenger로 수동 연락, thread_id로 왕복 매칭 | 기존 Telegram 인프라 재사용, 공급자 사전협조 불필요(단, 응답 시점의 협조는 필요) |

## 5. Invariants (불변조건 — 코드보다 먼저 고정)

1. Buyer에게 나가는 메시지는 항상 회장님 브랜드 계정에서 발송한다
2. Supplier 신원·연락처는 Buyer에게 노출하지 않는다
3. Buyer 개인정보는 필요 범위 외 Supplier에게 노출하지 않는다
4. 모든 메시지는 하나의 `conversation_id`에 속한다
5. 모든 외부 메시지는 고유한 `external_message_id`를 가진다
6. 상품이 확정되지 않으면 가격을 발송하지 않는다
7. **Supplier 답변은 운영자(회장님)의 확인 버튼을 거쳐야 Buyer에게 전달된다** (즉시자동발송 금지)
8. 가격은 원가·마진·통화·`price_verified_at`·적용수량과 함께 버전으로 저장한다
9. 메시지·견적·주문 기록은 덮어쓰지 않고 새 이벤트로 남긴다(append-only)
10. 기본 Kill-switch(PROCESSING 이하)는 외부 발송만 끄고 수신·원장 기록은 유지한다. `COMMENT_CAPTURE_MODE=quarantine`이면 이벤트를 격리 저장하고 후속처리를 중단한다(discard 금지). `disabled`는 극단적 비상 시에만 사용한다
11. DM 발송 전 반드시 24시간창 eligibility를 확인한다 — 정책 거부(§19 Gate F)는 재시도 대상이 아니다
12. **외부 API 호출 성공 여부를 확인할 수 없는 상태(ATTEMPTING 중 크래시)에서는 자동 재발송하지 않는다** — DELIVERY_UNKNOWN으로 전환 후 운영자 수동 확인을 거친다(V6.1 신규, §6/§20)

## 6. Delivery Semantics (멱등성 정의)

"정확히 1회 처리"는 부정확한 표현 — Instagram/Telegram 등 외부 시스템이 낀 이상 진짜 exactly-once는 불가능. 정확한 표현: **at-least-once 수신 + idempotent 처리 + 비즈니스 효과 중복방지**.

```
Webhook/Poller → Durable Inbox → Domain Event → 원장(Airtable/DB) → Outbox → 외부발송 → Delivery Receipt → Reconciliation
```

**Outbox 크래시 처리(V6.1 정정)**: 외부 API 호출 *전* `ATTEMPTING` 기록만으로는 크래시 후 중복을 막지 못한다 — "시도했다"만 알 뿐 "성공했는지"는 알 수 없기 때문이다. Instagram/Telegram 모두 서버측 idempotency key나 결과조회 API를 제공하지 않으므로, 재시작 시 `ATTEMPTING` 상태를 발견하면:
```
자동 재발송 금지
→ DELIVERY_UNKNOWN 전환
→ 운영자 경보
→ 운영자가 실제 플랫폼(Instagram 앱/Telegram)에서 직접 확인
→ 확인 후에만 SENT/FAILED로 수동 확정, 그제서야 재처리 여부 결정
```

## 7. ID / Domain Model

기존 `A-F3-260713-001`(`post_id_generator.py`)은 "수집 출처(Source) 코드"일 뿐 공급자 코드가 아니다. **Source ≠ Supplier ≠ Product**를 분리한다. `Facebook그룹 ≠ Supplier`는 **다대다 관계**이므로 계층형 3단 코드가 아니라 조인 테이블로 표현한다.

```
SRC-A-F003          출처(수집 위치)
SUP-000127           실제 공급회사
PRD-00004218         표준 상품
OFF-00008311         해당 공급자의 판매조건(같은 상품도 공급자마다 가격 다름)
POST-20260713-000184 게시물
CONV-20260713-000091 상담
```

내부 PK는 UUID/불변ID, 사람이 읽는 코드(`A-F3-...`)는 **레거시 표시용 필드로만 유지, PK로 사용 금지**.

**전체 엔티티(지금 구현 안 함, 경계만 확정)**: `Buyers` / `ChannelIdentities`(`Buyer 1:N ChannelIdentity`) / `Sources` / `Suppliers` / `SourceSupplierLinks` / `Products` / `Offers` / `Posts` / `Conversations` / `Messages` / `Quotes` / `Orders`.

## 8. Pricing Validity Rule (Gate C·P0-3 게이트)

**전제 조건이 먼저다**: Post↔Product 매핑이 없는 한 24시간 유효기간은 오발송을 막지 못한다. 따라서:

1. **Post/Product 매핑이 없는 동안은 `PRICE_AUTO_REPLY_ENABLED=false`** — 이 규칙은 **지금 당장 적용해야 하는 살아있는 리스크**다(§19 Gate C 참조 — 현재 코드는 이 플래그 자체가 없어 끌 방법이 없다)
2. 매핑 성립 후에만 `price_verified_at` 기준 **24시간** 유효기간 적용 → 초과 시 Supplier 재확인 또는 운영자 확인 필요

## 9. Kill-switch (7개, 효과별 분리)

```
COMMENT_CAPTURE_MODE        — active | quarantine | disabled
PRICE_AUTO_REPLY_ENABLED    — 기본값 false (Gate C, 신규 도입 시급)
COMMENT_PROCESSING_ENABLED  — 분류·후속작업
COMMENT_PUBLIC_REPLY_ENABLED / COMMENT_PRIVATE_REPLY_ENABLED
DM_GREETING_ENABLED / SUPPLIER_RELAY_ENABLED
```

## 10. Data Classification / Retention (PII, 데이터 종류별 분리)

| 데이터 종류 | 보관기간 | 비고 |
|---|---|---|
| 일반 운영 로그(`logs/*.log`) | 30일 | 현재 마스킹 없이 IGSID·메시지 원문 기록 중 — P0-1 범위에 마스킹 규칙 포함 |
| Telegram 알림 | 보관 대상 아님 | PII 패턴 제거 후 최대 20자 미리보기(원문 앞 20자 그대로 자르기 금지) |
| 상담 원장(`Lead_Interactions` 등, Airtable) | 12개월 | 마지막 상호작용 후 12개월 보관, 이후 파기 검토 — **운영 원장의 SSOT는 여기, Inbox DB가 아님(§20)** |
| `db/comment_inbox.db`(신규, 처리상태 추적용) | DONE 30일 / FAILED_FINAL·QUARANTINE **기본 30일**(V6.2: 90일 제안 철회 — 개인정보 최소수집 원칙상 실제 운영사고 조사 건만 개별 연장) | §20 참조, 영구 원장 아님 |
| 주문·정산 기록 | 미정 | 향후 법적 보존기간 별도 적용 (Order RFC에서 확정) |
| 전화·주소 등 민감정보 | 목적 종료 후 조기 삭제 | 구체 규칙은 Order RFC에서 확정 |

## 11. Walking Skeleton — Rollout Plan (V6.1, Gate C 최우선 추가)

```
P0-0A 핵심 설계·불변조건 확정      ← 완료(본 RFC)
P0-0B Meta 권한·정책 검토         ← 완료(§15/§16, 세부 판정은 §15 참조)
Gate C   Price Safety Interlock  ← 최우선·즉시(§19-1) — 현재 살아있는 오발송 리스크
Gate E-A Graph API 호환성 조사(읽기전용)
Gate E-B Graph API 버전 중앙화·업그레이드
Gate F   DM 24시간 Window Guard
P0-1  댓글 원장 신뢰성(Durable Inbox, webhook/poller 중복제거, JSON캐시이관, 로그 마스킹, 크래시복구)
P0-2  댓글 자동답글 Canary(게시물1/키워드1/buyer1)
P0-3  DM 대화 시작 — 댓글↔DM 연결, Buyer 식별, 상품 식별, 첫인사, 상품 확정 시에만 가격응답
P0-4  24~48시간 관찰 후 Go/No-Go
(이후 P1-A~F Relay 뼈대)
```

**실행 순서**:
```
1. V6.1 RFC 정합성 수정          ← 본 문서
2. Meta 공식정책 독립 증거 확보   ← §15 (Codex 진행 대상, 아직 미완료)
3. 현재 Meta App 설정 읽기전용 확인 ← §16 (완료)
4. 사용자 "설계도완성" 선언
5. 사용자 승인 후 Gate C 구현(최우선)
6. Gate E 구현
7. Gate F 구현
8. P0-1 Durable Inbox
9. P0-2 Canary
```

**P0-1 구현·종료 승인 기준**:
- 동일 `comment_id` → 원장 최대 1건
- 실패 이벤트 재처리 가능(영구 유실 없음)
- Webhook/Poller 동시 수신 시 중복 비즈니스 효과 0건
- stale `PROCESSING` lease 자동 복구
- 기존 `processed_comment_ids.json` 캐시 이관 후 재알림 0건
- 로그·Telegram에 전체 IGSID·메시지 원문 노출 0건
- **크래시(ATTEMPTING 중 종료) 후 재시작 시 자동 재발송 0건, 상태는 `DELIVERY_UNKNOWN`으로 전환(V6.1 정정 — "무조건 중복 0건"이 아니라 이 표현이 정확)**
- **`DELIVERY_UNKNOWN` 발생 시 운영자 경보 발송 확인**
- **운영자 수동 확인 전까지 해당 레코드 자동 재처리 금지**

**P0-2 Canary 최소 Go/No-Go 기준**:
- 테스트 댓글 1건당 공개답글 최대 1회
- Kill-switch/quarantine 모드 실제 동작 실증
- 상품 미확인 상태에서 가격 발송 0회
- 실패 발생 시 자동으로 대상 확대되지 않음

## 12. Open Questions (미결 — Order/Payment RFC 후속)

1. Buyer 결제대금 수령자·세금계산서 발행 주체 — 미정
2. 환불·불량·배송지연 책임(회장님 vs Supplier) — 미정
3. Supplier에게 Buyer PII(이름/주소/전화) 전달 시점·동의 방식 — 미정
4. ~~가격 유효기간~~ → §8에서 확정
5. ~~공급자 답변 전달 방식~~ → §5 불변조건 #7에서 확정
6. **(V6.3 신규)** 공급자에게 "DM 보내달라"는 댓글을 유도하는 아이디어(§4) — 실제로 어디에(원 FB 게시물? Instagram?) 어떤 방식으로(기존 FB 크롤러의 AdsPower+Selenium 세션 활용?) 댓글을 남길지 메커니즘 미정. 회장님 확인 필요
7. **(V6.3 신규)** WhatsApp/Kakao 채널 우선순위 재검토 — §3 Non-Goals 참조, P0-4 시점 재논의 예정

## 13. Known Bugs (총 10건 — 기존 8 + 정책조사 신규 2)

**기존 코드 결함 (8건)**:
1. `Lead_Interactions.conversation_channel` select 옵션에 `instagram_comment` 없음 → 댓글 저장 반복 실패, 실패를 완료로 오판 — **260714 실제 운영에서 최초 실증. 선택지 추가+저장 Canary PASS로 ERR-062/INC-035 RESOLVED, 단 "실패를 완료로 오판"하는 캐시 패턴(FP-047)은 계속 OPEN**
2. `dm_receiver.py`(webhook) · `comment_poller.py`(폴링) 이중 수신, webhook 쪽 중복방지 캐시 없음
3. `post_id_generator.py`의 `_daily_counter`가 프로세스 메모리 변수 — 재시작 시 리셋되어 코드 중복 가능
4. `domaekok`(오타) vs `domeggook`(실제) 표기 불일치 — 도매꾹 파이프라인이 `generate_sku()`를 호출하지 않아 현재는 도달하지 않음(확인됨)
5. `C=원천공급사`는 docstring 주석에만 존재, `SOURCE_MAP` 실제 매핑 0건
6. `vendor_code` 필드 코드 전체 참조 0건 — Airtable 실존 여부 UNKNOWN
7. DM 웹훅에 media_id 미저장 → 상품 미특정 상태 최신가격 응답 위험(§8/Gate C로 즉시차단, 근본해결은 P1-B)
8. `dm_receiver.py`/`comment_auto_reply.py` 로그에 IGSID·메시지 원문 마스킹 없이 기록됨(§10)

**정책조사(P0-0B)로 신규 발견 — 2건, 반복적 운영장애로 격상**:
9. **Graph API `v19.0` 만료(2026-05-21) — 4개 파일(`dm_auto_reply.py`/`comment_poller.py`/`dm_followup_scheduler.py`/`comment_auto_reply.py`), 총 8개 호출부에서 여전히 사용 중**(V6.1 정정 — "8개 파일"이 아니라 "4개 파일 8개 호출부". §19 Gate E 대상)
10. **DM 24시간 창 정책 위반 — `error_subcode 2534022`, 로그 전체 28회.** 정확한 분포(grep 재검증): **2026-05-29 16회 + 2026-05-30 8회 + 2026-07-12 4회 = 28회**(V6.1 정정 — 이전 "15회"는 계산 오류). `dm_followup_scheduler.py`(팔로업, 05-29·05-30)와 `dm_auto_reply.py`(첫응답, 07-12) 양쪽에서 발생, 최소 1.5개월간 반복. 직접원인: 발송 전 24시간창 eligibility 확인 로직 자체가 없음. 추가 의심: 정책거부(2534022)를 재시도 대상 오류로 취급하고 있을 가능성(§19 Gate F에서 재조사)

## 14. Deferred Sections (후속 RFC에서 확정)

Success Metrics 수치 / API·Event Contracts 상세 / Security·Threat Model / Failure Modes 상세 / Capacity·Cost Model / Migration·Backfill 실행계획 / Observability·SLO 수치 / Test Strategy 상세(P0-1 외) / Operational Ownership(Runbook) / Decision Log(ADR) / Go-No-Go 기준 수치.

## 15. P0-0B — Meta 공식 정책 검토 결과 (증거수준 명시, V6.1 판정 정정)

**증거 수준**: 아래 내용은 **Claude Code가 developers.facebook.com을 직접 fetch하여 확인**(단독 조사). Codex는 재감사 시 Meta 사이트 429 오류로 원문 재확인 실패 — **Codex 독립검증 미완료**. Postman 공식 미러 교차확인도 JS 렌더링 페이지라 실패(URL만 확보: https://www.postman.com/meta/instagram/request/23987686-bd5abaa1-8c39-49ee-97f1-cb2170fb0b7c).

| 항목 | 판정 | 확인 URL | 확인 일시 | 근거 원문(발췌) |
|---|---|---|---|---|
| 댓글 공개답글 | CONFIRMED | [private-replies](https://developers.facebook.com/docs/instagram-platform/private-replies/) | 2026-07-13 11:57 KST | `POST /{comment-id}/replies` |
| Private Reply(댓글→DM) | CONFIRMED | 위와 동일 | 2026-07-13 11:57 KST | "sent within 7 days of the creation time of the comment" / "Only one message can be sent to the commenter" |
| DM 시작조건 | CONFIRMED | [messaging-api](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api/) | 2026-07-13 11:57 KST | "Only after an Instagram user has sent your app user's Instagram professional account a message can your app send a message to the Instagram user" |
| 24시간 창 | CONFIRMED | 위와 동일 | 2026-07-13 11:57 KST | "Your app has 24 hours to respond to any message sent from an Instagram user to your app user" |
| Human Agent 예외 | CONFIRMED | 위와 동일 | 2026-07-13 11:57 KST | "your app can tag the response to allow your app to send the message outside the 24 hour messaging window" |
| 필수 권한(메시징) | CONFIRMED | 위와 동일 | 2026-07-13 11:57 KST | `instagram_business_basic`+`instagram_business_manage_messages`(Instagram Login 기준 표기 — 본 프로젝트 실제 스코프는 §16에서 별도 대조) |
| Webhook 필드 | CONFIRMED | 위와 동일 | 2026-07-13 11:57 KST | `messages`/`messaging_optins`/`messaging_postbacks`/`messaging_reactions` 필수 |
| App Review 요건 | CONFIRMED | [overview](https://developers.facebook.com/docs/instagram-platform/overview/) | 2026-07-13 11:57 KST | "Advanced Access is required when your app serves Instagram professional accounts you don't own or manage" |
| Graph API v19.0 만료일 | CONFIRMED | [changelog](https://developers.facebook.com/docs/graph-api/changelog) | 2026-07-13 11:57 KST | v19.0 expires "21/05/2026" |

**판정(V6.1 정정 — Codex 지적 반영, 3단계로 분리)**:
- **정책조사**: 완료(Claude 단독조사, Codex 독립검증 미완료)
- **운영준비상태**: 부분확인(§16 — 핵심권한·계정연결 CONFIRMED, Webhook 일부·Access Level 등은 UNKNOWN)
- **Dashboard 잔여항목**: 사용자 직접 확인 대기(§16 UNKNOWN 3개 항목)

"정책조사 완료"이지 **"Meta 운영준비 전체 PASS"는 아니다.**

## 16. Meta App 실제 설정 확인 결과 (읽기전용 조사)

**방법**: `.env`의 실제 `INSTA_ACCESS_TOKEN`으로 Graph API `debug_token`/`me/accounts`/`{ig_user_id}`/`{page_id}/subscribed_apps`를 직접 조회. **토큰 원문은 조회 스크립트 안에서만 사용, 어디에도 출력·기록하지 않음.** 확인 일시: 2026-07-13 12:20 KST.

| 확인 대상 | 결과 |
|---|---|
| Access Token 유효성 | CONFIRMED — `is_valid: true`, type=USER |
| Token 만료일 | CONFIRMED — `expires_at: 0`(장기 토큰, 만료 없음) |
| Data Access 만료일 | CONFIRMED — 2026-08-08(26일 후, 90일 롤링 정책 — 모니터링 권장) |
| 실제 부여된 scopes | CONFIRMED — 24개, 관련: `instagram_basic`/`instagram_manage_comments`/`instagram_manage_messages`/`instagram_manage_insights`/`instagram_content_publish`/`pages_messaging`/`pages_read_engagement`/`business_management`. §15의 Facebook-Login 경로 요구권한과 **전부 일치 — 권한 부족 없음** |
| Facebook Page 연결 | CONFIRMED — Page ID `868456346356581`("AI+24autoprogram") |
| Instagram Business Account 연결 | CONFIRMED — IG User ID `17841476202821375`(username: `yuna18253`) |
| Webhook 구독 필드(Page 레벨) | 부분 CONFIRMED, 불일치 — `messages`/`messaging_postbacks` 2개만 확인, 공식요구 4종 중 `messaging_optins`/`messaging_reactions` 누락. `comments`는 이 조회에서 안 보이는데 실제로는 동작 중(로그 확인) — **UNKNOWN, 추가조사 필요** |
| App mode / Access Level | **UNKNOWN — Dashboard 전용, API로 조회 불가** |
| 권한별 App Review 승인상태 | **UNKNOWN — Dashboard 전용** |
| Callback URL 상태 | **UNKNOWN — Dashboard 전용** |

## 17. Gate C — Price Safety Interlock (신규, 최우선·즉시)

**배경**: `dm_auto_reply.py`의 `get_base_price()`는 **지금 이 순간에도** 문의 상품을 특정하지 못한 채 "Instagram_Posts 중 price>0 최신값"을 가져와 자동응답 중이다(§13 #7). `PRICE_AUTO_REPLY_ENABLED` 플래그 자체가 코드에 없어 지금은 끌 방법도 없다 — P0-3까지 기다리면 그 사이 계속 오발송될 수 있는 **이미 살아있는 리스크**.

**ROI 판단(사용자 확정)**: 가격 *숫자* 자동응답은 끄되, Buyer 응답 자체는 끄지 않는다 — 잘못된 가격 즉시발송의 비용(마진손실·가격번복·신뢰하락·분쟁)이 정확한 가격을 늦게 보내는 비용(운영자 응답시간)보다 크기 때문.

**흐름**:
```
Buyer 가격 문의
→ 즉시 자동 접수 답변(DM_GREETING/접수확인, 가격 숫자 없음)
→ 상품 링크·게시물 번호·스크린샷 요청
→ 회장님에게 확인 알림(Telegram)
→ 상품 확인 후 원가+10% 가격 수동 안내
→ (P1-B Post/Product 매핑 완성 후) 24시간 내 검증가격+10% 자동응답 조건부 재활성화
```

**범위**:
- `PRICE_AUTO_REPLY_ENABLED` 플래그 신규 도입, **기본값 `false`**
- `false`일 때 `handle_price_inquiry()`는 가격 대신 위 접수·상품확인 요청 템플릿으로 대체(Buyer 응답 자체는 유지)
- Post/Product 매핑(P1-B)이 구현되기 전까지 `DEFAULT_BASE_PRICE` 자동사용 완전 금지
- Gate E/F/P0-1보다 먼저, 실행순서 최우선(§11)

## 18. Gate E — Graph API 버전 호환성 (P0-1과 분리)

**배경**: v19.0이 2026-05-21 만료(§13 #9). **4개 파일, 총 8개 호출부**(`dm_auto_reply.py` 2 / `comment_poller.py` 2 / `dm_followup_scheduler.py` 2 / `comment_auto_reply.py` 2, V6.1 정정)가 만료된 버전을 계속 호출 중. `engagement_tracker.py`/`auto_liker.py`는 이미 v21.0(안전).

**순서**:
```
Gate E-A  읽기전용 호환성 조사 — 목표버전(v21.0 등) 대비 현재 8개 호출의 파라미터·응답스키마 변경사항 확인
Gate E-B  META_GRAPH_API_VERSION 중앙변수 도입, 8개 호출부 하드코딩 제거 → 중앙변수 참조로 교체
          별도 테스트·별도 커밋(P0-1과 절대 섞지 않음)
```

## 19. Gate F — DM 24-Hour Window Guard (긴급, P0-1과 분리)

**배경**: §13 #10 — 24시간창 위반 28회(05-29:16 + 05-30:8 + 07-12:4), 최소 1.5개월 반복. 직접원인은 발송 전 eligibility 확인 로직 부재. 추가 의심: `2534022`(영구적 정책거부)를 네트워크 오류처럼 재시도 중일 가능성.

**설계**:
```
상태전이:
24시간 창 열림 → SEND_ALLOWED
24시간 창 닫힘 → WAITING_FOR_USER
2534022 수신    → 재시도 금지 + WAITING_FOR_USER 전환
Buyer 신규 DM   → 창 재개, SEND_ALLOWED로 복귀
```

**범위**: 마지막 Buyer 메시지 시각 저장(신규 컬럼) / 발송 전 24시간창 확인(공통 적용) / `2534022` non-retryable 분류 → retry_queue 무한재시도 등록 금지 / 자동 팔로업 스케줄 중단(`WAITING_FOR_USER` 동안) / Buyer 신규 메시지 수신 시 자동 재개 / 반복 실패 시 Telegram/Slack 경보.

**주의**: ERR/FP/INC 문서 기록은 이 RFC와 별개로, 사용자 별도 승인 후 진행.

## 20. P0-1 구현 상세계획 (변경파일·DB·테스트)

### 변경 파일
| 파일 | 종류 | 내용 |
|---|---|---|
| `modules/comment/comment_inbox.py` | 신규 | Durable Inbox 상태머신, `process_comment_event()` 단일 진입점 |
| `modules/comment/comment_auto_reply.py` | 수정 | 오케스트레이션을 inbox로 이전, 부작용 함수 성공/실패 명시적 반환 |
| `modules/comment/comment_poller.py` | 수정 | JSON 캐시 제거, `process_comment_event()` 호출 |
| `modules/dm/dm_receiver.py` | 수정 | 댓글 웹훅 처리 → `process_comment_event()` 호출 |
| `tools/migrate_comment_cache.py` | 신규(1회성) | `processed_comment_ids.json` → `comment_inbox.db` DONE 이관 |
| `tests/test_comment_inbox.py` | 신규 | 아래 테스트 목록 |
| `.env.example` | 수정 | 신규 env 변수 문서화 |

### DB 스키마 — `db/comment_inbox.db`
```sql
CREATE TABLE comment_inbox (
    comment_id       TEXT PRIMARY KEY,
    media_id         TEXT,
    username         TEXT,
    text             TEXT,
    status           TEXT NOT NULL,   -- RECEIVED/PROCESSING/AIRTABLE_RECORDED/REPLY_ATTEMPTING/REPLY_SENT/TELEGRAM_ATTEMPTING/TELEGRAM_SENT/DELIVERY_UNKNOWN/DONE/FAILED_RETRYABLE/FAILED_FINAL
    airtable_record_id TEXT,
    reply_sent       INTEGER DEFAULT 0,
    telegram_sent    INTEGER DEFAULT 0,
    attempt_count    INTEGER DEFAULT 0,
    lease_until      TEXT,
    last_error       TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
```
`DELIVERY_UNKNOWN`(V6.1 신규): `*_ATTEMPTING` 상태에서 프로세스가 죽고 재시작됐을 때 전이되는 상태 — 자동 재처리 금지, 운영자 수동 확인 전용.

### `comment_inbox.db` PII 보존·보안 규칙 (V6.2 정정)
- 파일 접근권한: `db/liked_comments.db`와 동일한 OS 파일권한 수준으로 제한 — **단, "기존과 동일"이라는 가정만으로 끝내지 않고 실제 Windows ACL을 조회해 확인하는 것을 P0-1 종료조건에 포함**(V6.2, 아래 테스트 참조)
- `DONE` 상태 이벤트는 30일 후 정리(§10 로그 30일 규칙과 동일 주기)
- `FAILED_FINAL`/`QUARANTINE` 상태도 **기본 30일**(V6.2 정정 — 90일 제안 철회, 개인정보 최소수집 원칙 우선). 실제 운영사고 조사가 필요한 건만 사유를 기록하고 개별 연장
- 백업 스크립트·로그에 `text` 컬럼 원문 복제 금지(길이·요약만)
- **이 DB는 영구 원장이 아니다** — 운영 원장 SSOT는 Airtable(`Lead_Interactions`), Inbox는 처리상태 추적 전용 임시저장소
- 정리(삭제) 작업 실행 시 삭제 건수를 감사로그에 기록

### 신규 `.env` 변수
```
COMMENT_CAPTURE_MODE=active
PRICE_AUTO_REPLY_ENABLED=false        # Gate C
COMMENT_PROCESSING_ENABLED=true
COMMENT_PUBLIC_REPLY_ENABLED=false
COMMENT_PRIVATE_REPLY_ENABLED=false
INBOX_LEASE_SECONDS=120
INBOX_RETRY_BACKOFF_SEC=10,60,300
```

### 처리 순서
`lease 선점(quarantine/disabled면 분기) → Airtable 기록(실패시 중단) → ATTEMPTING 기록 → 마스킹 후 공개답글 → SENT 확정 → ATTEMPTING 기록 → Telegram → SENT 확정 → DONE`. 각 `ATTEMPTING`→`SENT` 전이 사이 크래시 시 `DELIVERY_UNKNOWN`(§6). Webhook·Poller 둘 다 `process_comment_event()` 하나만 호출.

### 로그 마스킹
IGSID 앞4자리만+`***`, 메시지는 로그에 `len=N`만. Telegram은 PII패턴 제거 후 최대 20자 미리보기.

### 테스트 목록 (`tests/test_comment_inbox.py`)
`test_same_comment_webhook_then_poller_processed_once` / `test_same_comment_poller_then_webhook_processed_once` / `test_concurrent_webhook_and_poller_processed_once` / `test_airtable_failure_retries_without_permanent_loss` / `test_stale_processing_lease_recovered` / `test_legacy_json_cache_migrated_no_reprocessing` / `test_capture_mode_quarantine_isolates_without_processing` / `test_capture_mode_disabled_returns_200_without_storage` / `test_log_output_contains_no_full_igsid_or_raw_text` / `test_comment_auto_reply_disabled_flag_still_respected` / `test_crash_during_reply_attempting_transitions_to_delivery_unknown_no_auto_resend` / `test_crash_during_telegram_attempting_transitions_to_delivery_unknown_no_auto_resend` / `test_delivery_unknown_triggers_operator_alert` / `test_delivery_unknown_blocks_reprocessing_until_manual_confirm` / **`test_comment_inbox_db_file_acl_matches_expected_restricted_permissions`(V6.2 — "기존과 동일" 가정이 아니라 실제 Windows ACL 조회로 검증)**

### Rollback
`COMMENT_CAPTURE_MODE=quarantine`(즉시, `.env` 한 줄) → 원인파악 → 필요시 `git revert`. `processed_comment_ids.json`은 마이그레이션 전까지 보존.

## 21. Process Note

본 RFC는 Claude Code와 Codex의 다회차 교차검증(설계감사 5라운드 → P0-0B 정책조사 → 재감사 7건 V6 → 재감사 5건 V6.1 → 재감사 PASS + 비차단메모 2건 V6.2)을 거쳐 Codex PASS 판정을 받았다. **V6.3은 회장님의 직접 검토 결과 반영**: ①§3 Non-Goals의 WhatsApp/Kakao/Zalo를 "무기한 보류"가 아니라 "P0-4 시점 재논의 트리거"로 수정(실제로는 Messenger보다 WhatsApp·Kakao 문의가 더 많다는 회장님 관찰 반영) ②§4/§12에 신규 아이디어(buyer 댓글 자동응답 시 공급자에게도 동시에 "DM 요청" 댓글 유도 → 24시간 윈도우 자동 개방) 추가, 단 실행 메커니즘은 미확정으로 Open Question(§12 #6) 등록. **다음 절차**: 회장님이 본인 말씀으로 "설계도완성"을 선언 → 승인 → Gate C 구현(최우선) → Gate E → Gate F → P0-1 → P0-2. 코드·Airtable·`git add`·commit·운영설정은 전부 아직 미변경.
