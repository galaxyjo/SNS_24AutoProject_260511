# Instagram 계정 추가 · Webhook 보안 연결 표준 운영 매뉴얼

문서 버전: v1.0
작성일: 2026-07-27
적용 Runtime: `C:\SNS_24AutoProject_260511`
적용 범위: Instagram DM 웹훅 계정 추가, 서명검증(Signature), 계정 라우팅, 실제 Canary
기준 사고: ERR-082 — AI Strategist Webhook Signature 검증 장애(2026-07-27 해결)
상호참조: `docs/Instagram_토큰발급_매뉴얼.md`(Meta 앱 생성·Instagram 테스터 등록·초대수락·최소권한 설정의 화면 조작 절차 — 이 문서는 그 위에 Signature 검증·Secret 종류 구분·Route 라우팅을 추가한다. 겹치는 화면 조작 단계는 그 문서를 따르고, 이 문서는 왜 그렇게 해야 하는지와 실패 진단에 집중한다)

> FACT 표시가 없는 서술은 이 프로젝트의 실제 Runtime Evidence(2026-07-27 ERR-082 해결 세션)로 확인된 것이다. **[ASSUMPTION]** 표시가 붙은 항목은 아직 이 프로젝트에서 실제로 검증되지 않은 예시·가정이다.

---

## 1. 가장 중요한 구조 정정

**모든 신규 Instagram 계정마다 전체 작업을 처음부터 반복하는 것이 아니다.** 설정은 아래 4개 층위로 나뉘고, 층위마다 반복 빈도가 다르다.

| 구분 | 반복 횟수 | 작업 |
|---|---|---|
| Meta 앱 단위 | 앱마다 1회 | 앱 생성, Callback Route 설계, Verify Token 결정, App Secret 확인, 개인정보처리방침, Live 전환 |
| Instagram 계정 단위 | 계정마다 반복 | 계정 연결, Access Token 발급, IG User ID 확인, Webhook 구독, Account_Registry 매핑, 실제 DM Canary |
| Runtime Route 단위 | 보안 경계마다 1회 | Route 생성, Route별 Secret 지정, Signature 검증 코드 |
| 테스트 계정 단위 | 필요할 때 | Tester 등록·초대 수락·DM 발신 |

Meta의 Instagram Login 구조는 하나의 앱이 여러 Instagram Professional 계정을 관리하도록 설계되어 있다. 즉 **"계정 1개 = 앱 1개"가 기본 가정이 아니다.**

### 1.1 신규 계정 추가 유형 판정

**유형 A — 기존 앱 재사용**: 아래가 전부 같으면 기존 앱에 계정만 추가한다.
- 같은 Login Provider(`facebook_login` / `instagram_login`)
- 같은 보안 경계(같은 App Secret을 공유해도 되는 신뢰 범위)
- 같은 Callback Route
- 같은 서비스 목적

이 경우 반복하는 작업은 "Instagram 계정 연결 → Access Token 발급 → IG User ID 확인 → Webhook 구독 → Account_Registry 매핑 → 실제 DM Canary"뿐이다. 개인정보처리방침·Live 전환·Callback URL·App Secret 설정은 반복하지 않는다.

**유형 B — 별도 앱 생성**: 아래 중 하나라도 해당하면 별도 앱을 검토한다.
- Login Provider가 다름
- 기존 앱과 서비스 목적이 다름
- 장애·보안 경계를 완전히 분리해야 함
- 기존 Route를 보호해야 함

**FACT(이 프로젝트 실제 사례)**: AI Strategist(App ID `4522543077982497`)는 기존 Galaxy International 앱(App ID `860604299884476`)과 App ID·Login Provider·Secret이 전부 다른 별도 앱이므로 유형 B로 전체 작업을 수행했다.

---

## 2. 역할 분담

| 담당 | 역할 |
|---|---|
| 사용자(회장) | Meta 화면 입력, Secret 직접 저장(`.env`), 상태변경 승인, 실제 DM 발신 |
| GPT | 아키텍처 설계, 단계 설계, 오류 원인 가설, 증거 감사 |
| Claude Code | 실제 파일 확인, Runtime 확인, 코드 수정, 로그 검증, Read-only 진단 |
| CODEX | 필요할 때 Read-only 보안·반론 검토 |
| Meta Dashboard | 앱·계정·권한·Webhook 구독 관리(사용자만 조작 가능) |
| Runtime | Signature 검증, 계정 라우팅, DM 처리 |

**금지 원칙**: 실제 파일 생성·Runtime 재시작·Secret 변경·Webhook 정상 수신·Airtable 저장 성공은 GPT의 설계 문서만으로 "완료"로 선언하지 않는다. 최종 판정은 항상 Runtime Evidence 또는 Claude Code의 실제 실행 결과로 한다(CLAUDE.md Multi-AI Review Policy·SVES.md §5 Evidence Priority와 동일 원칙).

---

## 3. 계정별 등록표(작업 시작 전 먼저 채운다)

**Secret의 실제 값은 이 표에도, 어떤 문서에도 기록하지 않는다.**

| 필드 | 기록값 예시 |
|---|---|
| 계정 목적 | |
| account_code(Account_Registry PK) | |
| Instagram Handle | |
| Instagram Professional 계정 여부 | |
| Instagram User ID(ig_user_id) | |
| Login Provider | `facebook_login` / `instagram_login` |
| Meta 앱 이름 | |
| 상위 Meta App ID | |
| Instagram App ID(있는 경우) | |
| credential_key | |
| Callback Route | |
| Verify Token 환경변수명 | |
| Signature Secret 환경변수명 | |
| Access Token 환경변수명 | |
| 개인정보처리방침 URL | |
| 데이터 삭제 안내 URL | |
| DM 테스트 발신 계정 | |
| 앱 Live 상태 | |
| Webhook 구독 상태 | |
| 실제 POST 결과 | |
| Airtable 매핑 결과 | |

### 3.1 보안정보 기록 규칙

| 값 | 문서 기록 |
|---|---|
| App ID | 가능 |
| Instagram User ID | 가능 |
| Callback URL | 가능 |
| 환경변수 이름 | 가능 |
| Verify Token 실제 값 | 금지 |
| App Secret 실제 값 | 금지 |
| Access Token 실제 값 | 금지 |
| DM Raw Body | 금지 |
| Signature 원문 | 금지 |

---

## 4. 자격증명 4종 구분(이번 장애의 핵심)

이번 ERR-082 장애의 근본 원인은 **서로 다른 값을 같은 것으로 착각한 것**이다.

| 값 | 역할 | 생성 주체 | 사용 시점 |
|---|---|---|---|
| App ID | 앱 식별번호 | Meta | 앱 구분 |
| Verify Token | Callback 소유 확인용 문자열 | 사용자가 직접 정함 | GET Callback 검증 |
| App Secret | Webhook POST 서명검증 | Meta | `X-Hub-Signature-256` HMAC 검증 |
| Access Token | API 호출 권한 | Meta | 메시지·게시·댓글 API 호출 |

### 4.1 핵심 규칙

**Verify Token**
- 사용자가 임의로 정하는 문자열이다.
- Callback URL의 GET 검증에만 사용한다.
- App Secret이 아니다.
- **GET 검증 성공은 POST Signature가 정상이라는 증거가 아니다.**(이번 장애에서 가장 크게 오해했던 지점)

**Signature Secret(App Secret)**
- 실제 Meta POST 요청의 HMAC 검증에 사용한다.
- Route와 정확히 1:1로 연결돼야 한다.
- **FACT(이번 장애로 확인됨)**: Meta Dashboard에는 앱 종류에 따라 서로 다른 위치에 Secret이 2개 이상 보일 수 있다 — "앱 설정 → 기본 설정"의 상위 Meta App Secret과, "이용 사례 → Instagram API 설정"의 Instagram 앱 시크릿 코드는 **서로 다른 값**이다.

**Access Token**
- Instagram API를 호출할 때(발행·조회 등) 사용한다.
- Webhook Signature 검증용 Secret이 아니다.
- 계정마다 다를 수 있다.

---

## 5. Tester · DM 발신 계정 · DM 수신 계정 역할 구분

| 역할 | 설명 |
|---|---|
| RECEIVER(자동화 대상 계정) | Webhook 구독을 켜야 하는 계정. DM을 실제로 받는 Instagram Professional 계정 |
| SENDER_TESTER(발신 테스트 계정) | 개발 중(Live 아님) 상태의 앱에 Tester로 등록·초대 수락해야 하는 계정. 이 계정에서 RECEIVER로 DM을 보내 테스트한다 |
| APP_ADMIN | Meta 앱 관리자 |

**FACT(이 프로젝트 실제 사례)**:

| 역할 | 계정 |
|---|---|
| RECEIVER | aijomoojin |
| SENDER_TESTER | 951.0606 |
| APP_ADMIN | Jo Moo Jin |

**실수 방지**: 발신 테스트 계정의 Webhook 구독을 켜는 것이 아니다. 자동화 대상인 **수신** Instagram Professional 계정을 앱에 연결하고 구독한다.

---

## 6. Callback Route 설계 원칙

각 앱의 Callback Route는 미리 고정하고, Route마다 자기 Secret만 허용한다.

**FACT(이 프로젝트 실제 Route, `modules/dm/dm_receiver.py`)**:

| Route | 소유 앱 | Signature 환경변수 | Verify Token 환경변수 |
|---|---|---|---|
| `GET/POST /webhook` | Galaxy International(yuna) | `WEBHOOK_APP_SECRET` | `WEBHOOK_VERIFY_TOKEN` |
| `GET/POST /webhook/ai-strategist` | AI Strategist(aijomoojin) | `AI_WEBHOOK_APP_SECRET` | `AI_WEBHOOK_VERIFY_TOKEN` |

**FACT(코드 구조)**: 두 Route는 서로 다른 환경변수 이름을 코드 레벨에서 고정 참조한다(`_handle_signed_webhook(WEBHOOK_APP_SECRET)` vs `_handle_signed_webhook(AI_WEBHOOK_APP_SECRET)`, `modules/dm/dm_receiver.py:171,192`). 따라서 다음은 사람이 두 환경변수 값을 실수로 맞바꿔 넣지 않는 한 코드 구조상 발생할 수 없다:
- Payload 내용을 보고 Secret을 선택하는 것
- 여러 Secret을 순차적으로 대입해보는 것
- 한 Route의 실패를 다른 Route의 Secret으로 재시도하는 것

이 구조는 Route 우회와 Secret 오선택을 막기 위한 Fail-closed 설계다. Caller/Import Chain: `launcher/main.py:536,550` → `dm_receiver.app` → `_handle_signed_webhook()`(`dm_receiver.py:151`) → `verify_meta_signature()`(`modules/common/webhook_signature.py`) → `_process_webhook_event()`(`dm_receiver.py:195`).

---

## 7. Callback GET 검증과 실제 POST Signature 검증의 차이

| 검증 | 사용하는 값 | 확인되는 것 | 확인되지 않는 것 |
|---|---|---|---|
| Callback GET(`hub.challenge`) | Verify Token | URL 도달 가능·Route 존재·Verify Token 일치·Challenge 응답 정상 | App Secret 정상 여부, POST Signature 정상 여부, 계정 구독 상태, DM 처리 정상 여부 |
| 실제 Webhook POST | App Secret 기반 HMAC(`X-Hub-Signature-256`) | Payload가 진짜 Meta에서 온 것인지 | (통과 시) 위 전부 |

**GET 200을 전체 Webhook 성공으로 해석하지 않는다** — 이번 ERR-082에서 GET 검증은 처음부터 정상이었지만 POST Signature는 계속 실패했다.

---

## 8. Webhook 구독 · Live 전환 · 개인정보처리방침 절차

### 8.1 Webhook 이벤트 구독
DM 자동화에 필요한 대표 이벤트: `messages`, `messaging_postbacks`. 종료 증거는 화면 토글이 켜졌다는 것이 아니라 **실제 이벤트가 지정된 Route로 도착하는 것**이다(§10 참조).

### 8.2 개인정보처리방침 · Live 전환(신규 앱일 때만)
기존 앱에 계정만 추가하는 경우 기존 앱의 정책 페이지와 Live 상태를 재사용한다.

**FACT(이 프로젝트 실제 URL, 260727 배포 완료·200 확인)**:
- `https://galaxyjo.github.io/privacy-policy/ai-strategist/`
- `https://galaxyjo.github.io/privacy-policy/ai-strategist/data-deletion/`

확인 순서: URL 공개 상태 → 로그인 없이 열림 → HTTP 200 → Meta 앱 기본 설정에 입력 → 저장 → App Live 전환.

**주의**: Dashboard에 과거 안내 문구가 남아 있을 수 있다. 판정 우선순위는 항상 "실제 Meta POST 도착 → Signature 검증 통과 → HTTP 200"이 Dashboard 문구보다 우선한다(단, 문구를 무조건 무시하지는 않는다 — 상충하면 Live 전환 기록과 Runtime 결과를 함께 확인한다).

---

## 9. Secret 매핑 — ERR-082 확정 Root Cause

**FACT(2026-07-27, ngrok Inspector Read-only 캡처 + 메모리 내 HMAC A/B 비교로 확정, Raw Body·Signature·Secret 원문은 어디에도 저장하지 않음)**:

| 후보 | 결과 |
|---|---|
| 상위 Meta App Secret("앱 설정 → 기본 설정"의 앱 시크릿 코드) | NO MATCH |
| Instagram 앱 시크릿 코드("이용 사례 → Instagram API 설정" 표의 Secret) | MATCH |

**결론**: AI Strategist처럼 Instagram Login(instagram_login) 방식 앱은, Webhook POST 서명에 **상위 Meta App Secret이 아니라 별도 Instagram 앱 시크릿 코드**를 사용한다. `AI_WEBHOOK_APP_SECRET` 환경변수에는 이 Instagram 앱 시크릿 코드 값이 들어가야 한다.

**FACT(최종 Runtime 성공 증거)**:
```
20:08:44 [DM] from=1374*** | text_len=26
20:08:49 POST /webhook/ai-strategist → 200
```

### 9.1 확장 시 Secret 규칙
- 같은 Instagram App을 여러 계정이 공유할 경우: Signature Secret은 앱 단위로 동일할 수 있다. Access Token·account_code·credential_key는 계정별로 구분한다.
- 별도 Meta App을 만들 경우: 별도 Secret·별도 환경변수·별도 Route(또는 명시적 Route 매핑)를 사용한다. 기존 앱 Secret을 재사용하지 않는다.

---

## 10. 실제 DM Signature Canary

**방법**: SENDER_TESTER 계정에서 RECEIVER 계정으로 새 DM 1건을 보낸다. Claude Code는 지정 Route의 POST 도착 여부·Signature 결과·HTTP 상태·Business Logic 진입 여부를 로그로 확인한다.

**성공 기준**: 실제 Meta POST → 해당 Route → HTTP 200 (§9 FACT 증거 참조)

### 10.1 실패 상태표

| 증상 | 우선 조사 영역 |
|---|---|
| POST 자체가 없음 | 계정 연결, Webhook 구독, App 모드(개발 중/Live), Callback Route |
| GET도 실패 | URL, Verify Token, Route |
| POST 도착 후 403 | Signature Secret 종류(§9), Raw Body, Header |
| POST 200이나 DM 처리 없음 | Payload Parser, 계정 라우팅, Business Logic |
| 같은 요청이 반복됨 | 서버가 403/5xx를 반환해 Meta가 자동 재시도 중(정상 동작) |
| 엉뚱한 계정에 저장 | Account_Registry·ID 매핑(§11) |
| 기존 계정까지 실패 | Route·Cross-secret 회귀(§12) |

---

## 11. Account_Registry 라우팅 검증

Signature 통과 후에도 계정 라우팅이 맞아야 한다.

**FACT(코드 확인, `modules/infra/airtable_repository.py`)**: `PublishAccount`는 `account_code` / `api_provider` / `ig_user_id` / `credential_key` 필드로 구성되며, `get_publish_account_by_ig_user_id()`가 수신 `recipient.id`(ig_user_id)로 Account_Registry를 역조회해 `account_code`를 반환한다(Bundle B, 260726). `identity_id` 필드는 32/32 populated이나 `modules/` 코드에서 참조되지 않는 레거시 필드다(260726 세션 확인).

확인 항목: 수신 Instagram User ID / account_code / credential_key / api_provider / Account_Registry Record / 사용 Access Token.

성공 기준: DM이 올바른 계정으로 식별됨 / 다른 계정 Token을 사용하지 않음 / 다른 계정 Airtable Record를 오염시키지 않음 / 중복 처리 없음 / 기존 계정 Route에 영향 없음.

---

## 12. 기존 계정 회귀 Canary

새 계정 성공만으로 작업을 종료하지 않는다.

| 테스트 | 예상 결과 | 상태(FACT/미검증) |
|---|---|---|
| 신규 계정 + 신규 Route + 올바른 Secret | 200 | **FACT — 확인됨**(§9) |
| 신규 Route + 잘못된 Secret | 403 | **FACT — 확인됨**(§9, 상위 Meta Secret로 다수 재현) |
| 기존 계정(yuna) + 기존 Route + 기존 Secret | 200 | **FACT — 2026-07-28 실제 Meta DM 회귀 성공** |
| 신규 Route(`/webhook/ai-strategist`) + 기존(Galaxy) Secret 교차 사용 | 403 | **FACT — 2026-07-28 Runtime Cross-secret 요청으로 확인** |
| 신규 계정 DM | 신규 계정(`aijomoojin`)으로 저장 | 부분 확인 — Signature 통과·DM 처리 로그는 FACT, Account_Registry 저장 결과 재확인 필요 |
| 기존 계정 DM | 기존 계정으로 저장 | **FACT — yuna Lead `account_code_ref=IDN-000041`, 오계정 0건** |

### 12.1 ERR-082 전체 종료 조건(2026-07-28 Runtime 기준 완료)

- [x] AI Strategist 실제 Meta DM POST 200(FACT)
- [x] 위조/잘못된 Signature 403(FACT)
- [x] 기존 yuna Route 실제 회귀 성공(FACT)
- [x] Cross-secret 차단 재확인(양 Route 모두 403, Business Logic 진입 0건)
- [x] Account_Registry 올바른 매핑 확인(`IDN-000041`)
- [x] 잘못된 계정 저장 0건 확인
- [x] Secret·Raw Body 노출 0건(FACT, 진단 전 과정에서 유지)
- [x] 위 항목 전체 충족으로 ERR-082 Runtime 종료 선언(2026-07-28)

**RISK/HOLD**: Canary 구간에서 Signature 실패 경고 8건이 관측됐으나 발생 주체는 UNKNOWN이다. Business Logic 진입·Lead 생성·계정 오염 Evidence는 없으며, ERR-082 종료와 분리한 후속 조사 항목으로 유지한다.

---

## 13. Signature 403 안전 진단 절차

### 13.1 먼저 하지 말아야 할 것
App Secret 즉시 재설정 / `.env` 값을 추측으로 반복 변경 / Route 변경 / 코드와 Secret을 동시에 변경 / Signature 검증 비활성화 / Raw Body 전체를 일반 로그 파일에 저장.

### 13.2 안전한 진단 순서
1. 실제 POST가 지정 Route로 도착했는지 확인(Read-only 로그)
2. `X-Hub-Signature-256` 헤더 존재 여부 확인
3. Runtime이 올바른 환경변수를 읽었는지 확인(길이·앞뒤 2글자만 마스킹 확인, 전체 값 출력 금지)
4. Meta Dashboard에 Secret 종류가 둘 이상 있는지 확인(§4.1, §9)
5. **가능하면 ngrok Inspector(`http://127.0.0.1:4040/api/requests/http`)에서 이미 캡처된 실패 요청의 Raw Body+Signature를 Read-only로 가져온다(코드 수정 불필요, 이번 ERR-082에서 실제 사용한 방법)**
6. Inspector로 확보 불가능한 경우에만, 다음 요청 1건을 메모리에서 후보 Secret별로 비교하는 임시 코드를 승인받아 추가
7. 결과는 `CANDIDATE_A: MATCH / NO MATCH`, `CANDIDATE_B: MATCH / NO MATCH` 형태로만 출력. Body·Signature·Secret은 어디에도 저장하지 않는다
8. MATCH된 Secret이 확인된 뒤에만 환경변수 교체 → 재시작 승인 → 실제 DM 재시험

---

## 14. 이번 장애의 실수 목록과 예방(요약)

| 실수 | 예방 |
|---|---|
| 상위 Meta App Secret을 Instagram Webhook Secret으로 착각 | 계정 등록표에 상위 Meta App ID와 Instagram App ID를 별도 항목으로 기록(§3) |
| GET 검증 성공을 전체 Webhook 성공으로 해석 | Gate A(GET 200)/B(POST 도착)/C(Signature 통과)/D(Business Logic 처리)를 분리 판정(§7) |
| Signature 불일치 시 오타부터 의심 | Secret 종류 → 매핑 → 값 → Runtime 반영 순서로 확인(§9) |
| 종류를 확인하지 않고 Secret을 재발급(Reset) | A/B MATCH 확인 전에는 Reset하지 않는다(§13) |
| Dashboard 문구를 실제 상태와 동일시 | Runtime POST 결과 > Meta 상태변경 기록 > Dashboard 현재 상태 > 안내 문구 순으로 판정(§8.2) |
| 테스터 계정·발신 계정·수신 계정 역할 혼동 | 계정마다 RECEIVER/SENDER_TESTER/APP_ADMIN 역할을 고정 표기(§5) |
| 로컬 Unit Test 통과를 실제 Meta 연동 성공으로 착각 | Unit Test(알고리즘)/Runtime Synthetic Test(실행 코드)/실제 Meta Canary(운영 설정)를 별도 증거로 판정 |
| Raw Body를 일반 로그에 남기려 시도 | DM 내용·사용자 ID·시각 등 PII 포함 가능 — 메모리 1회 비교 후 결과만 남김(§13) |
| 앱 단위 설정과 계정 단위 설정 혼동 | §1의 유형 A/B 판정을 작업 시작 전 먼저 수행 |

---

## 15. 절대 금지사항

- Secret을 채팅·문서·로그에 붙여넣지 않는다.
- Secret이 보이는 스크린샷을 공유하지 않는다.
- Raw Body와 Signature를 일반 로그 파일에 함께 남기지 않는다.
- Signature 검증을 임시로 끄지 않는다.
- Secret 후보를 순차 Fallback하지 않는다.
- App Secret Proof와 Webhook Signature를 혼동하지 않는다.
- GET 성공을 E2E 성공으로 선언하지 않는다.
- Unit Test 성공을 Runtime 성공으로 선언하지 않는다.
- Secret 종류를 확인하지 않고 재설정(Reset)하지 않는다.
- 여러 변수와 코드를 동시에 바꾸지 않는다(Gate당 한 가지만 변경).
- 신규 계정 때문에 기존 Route를 임의 변경하지 않는다.
- 모든 계정에 새 Meta App이 필요하다고 가정하지 않는다(§1).
- 사용자 승인 없이 Runtime Restart·Commit·Push하지 않는다.
- 기존 Galaxy Secret과 AI Secret을 서로 교환하지 않는다.
- `250723`을 Active Runtime으로 취급하지 않는다.

---

## 16. 계정 확장 시 반복 작업 구분 **[ASSUMPTION — 아래 구체 시나리오는 이 프로젝트에서 아직 실제로 검증되지 않은 예시다]**

계정이 늘어나도 앱 설정 자체를 반복해서 만드는 것은 아니라는 원칙(§1)을 수치 예시로 보여주기 위한 것이며, 아래 표의 구체적인 계정 수·서비스 구분(화장품/의료관광 등)은 이 프로젝트에서 실제로 운영된 적이 없다.

**예시 — AI 앱 1개에 AI 계정 10개를 연결하는 구조[ASSUMPTION]**

| 작업 | 횟수 |
|---|---|
| Meta App 생성 | 1회 |
| Privacy Policy | 1회 |
| App Live 전환 | 1회 |
| App Secret 설정 | 1회 |
| 계정 연결 | 10회 |
| 계정 Token | 10개 |
| Account_Registry Record | 10개 |
| 계정별 Canary | 10회 |

**예시 — 서비스별 앱 3개(각 10계정)로 분리하는 구조[ASSUMPTION]**: 이 경우 App-level 설정은 3회, Account-level 설정은 30회가 된다는 것이 §1 원칙의 산술적 귀결이나, 실제 운영 검증은 없음.

**SSOT 원칙(FACT, 코드 구조상 성립)**: One account = One Account_Registry mapping. 그러나 **One account = One Meta App은 아니다**(§1).

---

## 17. 계정 추가 완료 Snapshot 템플릿

```text
[ACCOUNT WEBHOOK ONBOARDING SNAPSHOT]
시각:
계정 목적:
Instagram Handle:
Instagram User ID:
Account Code:
Provider:
Credential Key:
기존 앱 재사용 / 신규 앱:
Meta App ID:
Instagram App ID(있는 경우):
Callback Route:
Verify Token 변수명:
Signature Secret 변수명:
Access Token 변수명:
Tester 상태:
Instagram 계정 연결:
Webhook 구독:
Privacy URL:
Deletion URL:
App Live 상태:
GET Callback:
실제 Meta POST:
Signature 결과:
HTTP 결과:
Account Routing:
Airtable/Runtime 저장:
기존 계정 회귀:
Cross-secret 차단:
Secret 노출:
Raw Body 저장:
Git Diff:
Commit:
Push:
남은 UNKNOWN:
최종 Runtime 판정:
```

---

## 18. 신규 계정용 빠른 체크표

- [ ] 기존 앱 재사용인지 신규 앱인지 판정했다(§1).
- [ ] Login Provider를 확인했다.
- [ ] 상위 Meta App ID를 기록했다.
- [ ] Instagram App ID가 별도로 존재하는지 확인하고 기록했다(§4, §9).
- [ ] 자동화 수신 계정(RECEIVER)과 DM 테스트 발신 계정(SENDER_TESTER)을 구분했다(§5).
- [ ] Tester 초대를 수락했다.
- [ ] 수신 Instagram 계정을 앱(Instagram Business Login 이용 사례)에 연결했다.
- [ ] 대상 계정(RECEIVER) Webhook 구독을 켰다.
- [ ] Callback Route를 임의로 만들지 않고 기존 설계(§6)와 대조했다.
- [ ] GET Callback 검증이 200이다.
- [ ] Verify Token과 App Secret을 구분했다(§4.1).
- [ ] 사용할 Signature Secret이 상위 Meta App Secret인지 Instagram App Secret인지 확인했다(§9).
- [ ] 실제 Secret은 채팅·문서·로그에 남기지 않았다.
- [ ] 환경변수를 저장했다.
- [ ] 승인 후 Runtime을 재시작했다.
- [ ] 실제 Meta POST가 도착했다.
- [ ] 실제 Signature가 통과해 200이다.
- [ ] 올바른 계정으로 라우팅됐다(§11).
- [ ] Airtable 또는 Runtime 저장 결과가 맞다.
- [ ] 기존 계정 회귀 Canary가 성공했다(§12).
- [ ] 잘못된 Signature는 403으로 차단됐다.
- [ ] Secret과 Raw Body 노출이 0건이다.
