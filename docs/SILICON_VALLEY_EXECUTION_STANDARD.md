# 실리콘밸리 업무 정석 — Execution Standard (SSOT)

> **이 문서는 프로젝트의 단일 실행 기준(SSOT)이다.** 판단 누락과 AI(Claude/Codex/GPT)별 기준 불일치를 막기 위해 존재한다.
> 새 원칙이 생기면 이 파일에 섹션을 추가한다 — 별도 파일로 쪼개거나 메모리에만 남기지 않는다.
> 세션마다 이 문서를 가장 먼저 읽는다(§7, CLAUDE.md Session Start Rule 4번 항목).
>
> **이 문서는 CLAUDE.md·ERROR_DATABASE.md·MERGE_JOURNAL.md·CURRENT_RUNTIME_CONTEXT.md의 내용을 복사하지 않는다.** 각 원칙마다 "원본 위치"를 명시하고, 이 문서는 그 원칙들을 하나의 흐름(Stage Gate)으로 엮는 역할만 한다. 원문이 바뀌면 원본 파일만 고치고, 이 문서는 참조 표시만 갱신한다.

---

## 1. Stage Gate — AI 답변을 바로 실행하지 않는다

```
Research
→ Evidence Audit
→ Decision Memo
→ Claim Lock
→ Single Canary
→ Measure (실제 반응 측정)
→ Continue / Modify / Kill
```

이 프로세스는 새로 만든 것이 아니라, 이 프로젝트가 260527 이후 실제로 해온 작업 방식을 하나의 이름으로 통합한 것이다. 각 단계와 **원본 근거**:

| 단계 | 의미 | 원본 위치 (복사 아님, 참조) |
|---|---|---|
| Research | AI가 자유롭게 조사·제안한다. 이 단계의 산출물은 아직 사실이 아니라 가설이다. | — (신규 개념, 이 문서가 처음 명명) |
| Evidence Audit | 제안 근거를 우선순위대로 재검증한다. 근거 없으면 UNKNOWN. | CLAUDE.md §Runtime Governance "Evidence Rule": `우선순위: Runtime log > DB/API > grep > file > git > docs. 추정 금지. 없으면 UNKNOWN.` |
| Decision Memo | 무엇을, 왜 하는지 기록하고 사용자의 명시적 실행 승인("N단계 진행하자")을 받는다. Plan 승인 ≠ 실행 승인. | [[feedback_plan_approval_vs_execution_gate]] (260711/260712 확정) + CLAUDE.md "승인 범위 명시 원칙" |
| Claim Lock | 승인받은 범위를 고정한다. 로컬 pytest는 포함, Airtable Write·git commit·서비스 재시작은 항상 별도 승인. | [[feedback_plan_approval_vs_execution_gate]] "단계 승인의 구체적 범위" 표 (260712 확정) |
| Single Canary | 전체 적용이 아니라 최소 단위 1개로만 먼저 실행한다. | 실제 선례: `docs/VALIDATION_STATUS.md`의 `di_canary1~3_*`(Repository DI 마이그레이션), `gate_c_price_safety_260713`(가격 자동응답 차단 Canary), `gate_g_comment_private_reply_260714`(실계정 tgbtgbnate 댓글 1건), `gate_e_b_v25_migration_260714`(4경로 중 3경로 라이브 Canary) |
| Measure | Canary의 실제 결과를 관찰한다 — 예상이 아니라 실측. | 위 각 Gate 항목의 "앱 로그 대조", "Airtable 재조회", "화면 육안 확인"(회장이 tgbtgbnate DM함에서 직접 확인) 등 |
| Continue / Modify / Kill | 측정 결과로 명시적으로 결정한다. | 예: `gate_e_b_v25_migration_260714`의 `comment_auto_reply` 경로는 재시작 직전 운영 위험 판단으로 **Kill**(재시작 취소, `.env` 즉시 원복). `fp047_enforce_precondition_a/b`는 A·B 완료 후에도 enforce 모드 전환은 별도 승인 대상으로 **Hold**. |

---

## 2. Blast Radius 최소화 원칙 (기존 실무에서 반복 확인된 패턴, 이번에 명명)

신규 안전장치가 실패해도 **그 기능 범위 안에서만** 죽는다 — 전체 시스템을 막지 않는다.

- 원본 위치: `docs/VALIDATION_STATUS.md`의 `fp047_enforce_precondition_a_260716`/`fp047_enforce_precondition_b_260716` — "실패해도 launcher 전체(FB크롤링/IG업로드/DM 등)는 막지 않고 **enforce 모드의 댓글 처리만** 거부(회장 결정: blast radius를 댓글 도메인 안으로 한정)"가 A/B 양쪽에 동일하게 적용된 원칙.
- Kill-switch(12대 체크리스트 §8-5)를 설계할 때 "무엇이 죽어야 하는가"를 항상 최소 범위로 먼저 정한다.

---

## 3. 표준 결과 출력 포맷 (신규 — 다른 문서에 없음)

**모든 작업 결과를 보고할 때, 다음 블록을 반드시 포함한다** (ONE-LINE ELI10 PREFIX 다음, 응답 말미):

```
요약:
완성도: __%
채택/폐기: 채택 / 폐기 / 보류
현재 단계: (Stage Gate §1 중 하나)
다음 담당자: 회장 / Claude Code / Codex / GPT
성공 기준: (측정 가능한 구체적 기준)
```

- "완성도 %"는 감이 아니라 §4 Evidence Rule로 확인된 항목 수 기준으로 산정한다.
- "다음 담당자"를 비워두지 않는다.
- 이 블록은 CLAUDE.md의 [[feedback_step_subtitle_format|단계 소제목 표기]] · ONE-LINE ELI10 PREFIX · [[feedback_datetime_prefix|날짜시간 프리픽스]] · "단계별 Bookending 원칙"과 중복이 아니라 그 뒤에 붙는 마무리 블록이다 — 저 넷은 응답 스타일 규칙이고 이것은 작업 자체의 상태 요약이다.

---

## 4. FACT / INFERENCE / UNKNOWN / RISK 분리 (신규 라벨, Evidence Rule 위에 얹는 것)

| 라벨 | 정의 |
|---|---|
| FACT | CLAUDE.md Evidence Rule 우선순위(Runtime log>DB/API>grep>file>git>docs) 중 하나로 직접 확인된 사실 |
| INFERENCE | 여러 FACT로부터 논리적으로 추론했으나, 그 자체로 직접 확인되지는 않은 것 |
| UNKNOWN | 확인할 증거가 없거나 접근할 수 없음 — 추정해서 채우지 않는다 |
| RISK | 확정된 사실은 아니지만 잠재적 위험이라 반드시 표기해야 하는 것 |

**기존 `docs/VALIDATION_STATUS.md`의 PASS/PARTIAL/OPEN/UNKNOWN/UNCLASSIFIED 라벨과는 층위가 다르다** — 그쪽은 "작업 항목 전체"의 상태이고, 이 라벨은 "문장/주장 단위"의 확실성 표기다. 예: `gate_e_b_v25_migration_260714` 항목 전체는 PARTIAL(전체 상태)이지만, 그 안의 "3/4 경로 라이브 PASS"는 FACT, "4번째 경로도 될 것"은 말하지 않는다(INFERENCE조차 아니고 UNKNOWN으로 남김).

---

## 5. Evidence Rule (원본: CLAUDE.md, 링크만)

```
우선순위: Runtime log > DB/API > grep > file > git > docs
추정 금지. 없으면 UNKNOWN.
```

Runtime 증거 없는 기능·수치·완료 주장 금지. 대화 기록·직전 응답의 자기 진술은 증거가 아니다. (전문은 CLAUDE.md §Runtime Governance 참조, 이 문서에서 재복사하지 않음)

---

## 6. Single Canary Rule

**한 번에 하나의 Canary만 실행한다.** 여러 계정·여러 기능·여러 변형을 동시에 검증하지 않는다.

실제 이 프로젝트에서 위반 없이 지켜진 사례: `gate_g_comment_private_reply_260714`는 계정 1개(tgbtgbnate)·댓글 1건으로만 실증했고, 캠페인 allowlist는 여전히 빈 배열로 유지해 전체 확산을 막았다. `gate_e_b_v25_migration_260714`는 4개 경로를 한 번에 라이브 전환하지 않고 경로별로 순차 실증했으며, 위험이 감지된 4번째 경로(`comment_auto_reply`)는 그 자리에서 진행을 멈췄다.

---

## 7. 상태변경 실행 주체 — Claude Code 단독

**상태변경은 사용자(회장) 승인 후 Claude Code만 수행한다.** Codex와 GPT는 리뷰·전략·감사 역할이며(원본: CLAUDE.md Multi-AI Review Policy `### Roles`), 이 저장소에 대한 실제 상태변경(파일 쓰기, git commit/push, Airtable Write, 설정 변경, 서비스 재시작 등)을 직접 실행하지 않는다.

**근거 — 두 가지 다른 위반 사례, 둘 다 이 원칙을 뒷받침:**
- **260721 (Codex, 역할 위반)**: Codex가 read-only 조사 권한을 넘어 AdsPower 설정 수정·n8n watchdog 비활성화·git commit(`5165b8e`)까지 직접 실행. 보고 내용 자체는 재검증 결과 CONFIRMED였으나, 실행 주체가 Claude Code가 아니었던 절차 위반. (원본: `docs/CURRENT_RUNTIME_CONTEXT.md` 260721 섹션)
- **ERR-053/260710 (Claude Code 자신, 승인범위 위반)**: 사용자가 승인한 것은 read-only 진단 명령뿐이었는데, Claude Code가 별도 승인 없이 그 결과로 `ERROR_DATABASE.md`/`FAILURE_PATTERN.md`/`INCIDENT_TIMELINE.md`를 작성하고 git commit(`d49ab61`)까지 이어서 실행. (원본: CLAUDE.md "승인 범위 명시 원칙" 근거 문단, `docs/ERROR_DATABASE.md` ERR-053)

두 사례 모두 "누가 실행하든, 승인받은 범위를 넘어서면 안 된다"는 같은 결론으로 수렴 — 이 문서 §1의 Decision Memo/Claim Lock 단계가 바로 그 재발 방지책이다.

---

## 8. 세션 시작 시 필수 선행 확인

이 문서는 **CLAUDE.md의 Session Start Rule에 등록되어 있다**(4번 항목) — 매 세션 시작 시 `CURRENT_RUNTIME_CONTEXT.md` / `MERGE_JOURNAL.md` / `git status`와 함께 가장 먼저 읽는다. 실제 실행 명령은 CLAUDE.md 본문 참조(중복 기재하지 않음).

---

## 9. 신규 설계 12대 체크리스트 (원본: [[feedback_sv_methodology]], 260713 확정)

신규 기능/모듈 설계 시 기본으로 훑는다 — 각 항목이 이미 실제로 적용된 사례를 병기한다:

1. **Design Doc/RFC 먼저** — 코드 짜기 전 설계문서로 합의. 사례: `docs/design/DM_RELAY_COMMERCE_RFC.md`
2. **Goals & Non-Goals** — 범위 안/밖을 문서에 명시. 사례: `docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md`
3. **Inbox/Outbox + Idempotency Key** — 외부 이벤트 중복수신 방지. 사례: `modules/comment/comment_event_store.py`(fencing token)
4. **Surrogate Key vs Display Code 분리**
5. **Kill-switch/Feature Flag + Rollback** — 사례: `COMMENT_EVENT_STORE_MODE`(disabled/shadow/enforce), `COMMENT_POLL_ALLOWLIST_MODE`(legacy/allowlist), `PRICE_AUTO_REPLY_ENABLED`
6. **Expand-Contract Migration** — 사례: `di_canary1~3`(Repository DI 병행 전환), `gate_e_b_v25_migration_260714`(v19→v21→v25 단계적 전환)
7. **Adversarial Two-Reviewer** — 사례: `gate_g_comment_private_reply_260714`(Codex 4라운드), `package1_phase_a_allowlist_polling_260716`(Codex 9라운드)
8. **Evidence-based** — §5 Evidence Rule과 동일 원칙
9. **Risk-Tiered Review** — 원본: CLAUDE.md Multi-AI Review Policy High-Risk/Low-Risk Fast Path 구분
10. **ROI-Gated Rollout** — 사례: ManyChat 1000계정 확장 보류 결정(월 $14,000+ 비용 확정 후 "소수 대표계정만" 축소, [[project_manychat_hybrid_decision_260716]])
11. **Platform Policy 정식 검토** — 사례: Meta App Review 진행 상황 추적(ERR-064, [[project_manychat_pivot_consideration]])
12. **SLO/모니터링 + Canary 배포** — §1, §6과 직결

---

## 10. [260723 실리콘밸리 업무 정석 — 메모장 원문 이전]

> **이 섹션은 회장이 `docs/실리콘밸리업무정석260722.txt`(메모장)에 계속 모아온 원문을 Claude Code가 재해석·재작성 없이 그대로 옮긴 것이다.** 원문의 표현·순서·구분선(`----`)을 그대로 보존했다 — 위 §1~§9(이미 구조화된 SSOT 본문)와 이 섹션은 층위가 다르다: §1~§9는 이 프로젝트의 실제 선례로 재작성된 "운영 절차" 규정이고, 이 섹션은 회장이 여러 세션에 걸쳐 GPT/Perplexity 등과 나눈 대화에서 수집한 "실리콘밸리 업무 방식" 원자료(raw material)다. 둘이 충돌하는 것처럼 보이면 자동으로 어느 한쪽을 우선시키지 않고 **즉시 STOP, 회장 판단 후 정정**한다(현재까지는 충돌 발견 안 됨 — 아래는 주로 제품/성장 전략 층위이고 §1~§9는 주로 운영/승인 프로세스 층위라 서로 다른 질문에 답한다).
>
> 원본 파일: `docs/실리콘밸리업무정석260722.txt` (512줄, 최초 이전 260723). **앞으로 메모장이 갱신되면 이 섹션은 diff로만 갱신한다 — 기존 원문 삭제·덮어쓰기 금지, 추가분만 append하고 하단 변경 이력에 날짜와 함께 기록한다.**

<details>
<summary>원문 전체 (펼치기) — 260723 최초 이전</summary>

```text
제목: 실리콘밸리업무정석 
docs/SILICON_VALLEY_EXECUTION_STANDARD.md 파일 하나로 고정 , CLAUDE.md Session Start Rule에 "매 세션 시작 시 이 파일부터 읽는다
----------------------------------------------------------------
방지책 (실리콘밸리 디버깅 원칙)

명령을 원자 단위로 쪼갠다 — 한 셸 호출에 파일 1개, 목적 1개만. 여러 파일 동시 조회 금지.
결과를 요약 금지, 원문 그대로 요구 — "설명하지 말고 파일 내용만 출력"을 명시.
부수 발견은 즉시 기록만 하고 조사 안 함 — OUT OF SCOPE 태그 붙이고 진행.
1개 명령 = 1개 산출물 확인 후 다음 명령 — 배치 처리 금지, 순차 처리 강제.

----------------------------------------
gpt 진행 오류

저는 아래 다섯 가지를 한 번에 전달했어야 한다.

결과 요약
→ 기대치 대비 점수
→ 채택할 부분
→ 폐기·수정할 부분
→ 다음 담당자와 정확한 다음 단계

사용자가 매번 "다음은 무엇을 해야 하나?"라고 별도로 물을 필요가 없어야 한다.

실리콘밸리 업무 정석

실무에서는 AI 답변을 바로 실행하지 않고 Stage Gate로 통제한다.

Research
→ Evidence Audit
→ Decision Memo
→ Claim Lock
→ Single Canary
→ 실제 반응 측정
→ Continue / Modify / Kill

핵심은 5개를 한꺼번에 게시하지 않는 것이다. 현재 실제 프로그램과 가장 가까운 1개만 먼저 검증한다.


-----------------------------------

Sns 자동 업로드 =아바타 작업하려고하는데 2가지로 설계해야하지 
하나는 ㅡwork flow= 즉 어떤도구들 어떻게업무흘러가는지 
두번째는 컨텐츠 설계 =어느 주제 그리고 어떻게알고리즘 타게해야하는지 

맞아? 
실리콘벨리는 어떻게 설계를 진행하나 
실리콘밸리 업무장석은 뭐야?10줄이내로 아주쉽게 15살버젼으로 설명해줘

260721_0728pm
결론 — 맞다. 실리콘밸리는 최소 2개가 아니라 보통 3개 레이어로 분리해서 설계한다.

우선순위	설계	목적
1️⃣	Workflow Architecture	어떤 도구가 어떤 순서로 데이터를 처리하는가
2️⃣	Content Strategy	무엇을 올리고 누구에게 보여줄 것인가
3️⃣	Growth System	알고리즘·SEO·추천·댓글·DM으로 어떻게 성장시킬 것인가
실리콘밸리 업무 정석 (15살 버전)
먼저 시스템을 그린다. (Workflow)
그다음 콘텐츠를 설계한다. (Content)
마지막으로 성장 엔진을 붙인다. (Growth)
좋은 콘텐츠만으로는 실패한다.
자동화만으로도 실패한다.
시스템 + 콘텐츠 + 성장이 함께 돌아가야 성공한다.
도구는 언제든 교체 가능하게 만든다(DI).
콘텐츠는 계속 바뀌지만 시스템은 오래 유지한다.
모든 것은 데이터(조회수·댓글·DM·매출)로 검증한다.
제품을 만드는 것이 아니라 '성장하는 시스템(Growth Machine)'을 만든다.

이 방식이 현재 Meta, TikTok, YouTube 기반 자동화 SaaS와 실리콘밸리 Growth 팀에서 가장 일반적으로 사용하는 설계 접근이다.
-------------------------------
실리콘밸리 상위 자동화팀도 "직접 전부 개발"보다:

Core Engine(핵심 엔진) = 자체 보유
Execution Layer(실행 레이어) = 외부 SaaS 활용
Infrastructure(인프라) = 검증된 툴 조합

구조로 감.
--------------------------
중요한 핵심 원칙 (Critical Principle)

❌ "하나의 거대한 올인원 시스템" 만들기
→ 유지보수 지옥(Maintenance Hell)

✅ "모듈형(Module-based) 운영체계"
→ 각각 독립 교체 가능해야 함

실무 기준 구조:

역할(Role)	담당
Core Logic	자체 Python 시스템
Workflow Automation	n8n
Browser Isolation	AdsPower
AI Processing	OpenAI / Claude
Storage / CMS	Notion
Queue / State	Airtable or DB
Monitoring	Dashboard / Logs

👉 이게 실리콘밸리식 "Composable Architecture" 구조.
------------------------------

6️⃣ Persona(페르소나) 전략 평가 (Critical)

이 방향은 매우 고급 전략임.

현재 회장님 사고:

1 Gmail
= 1 Persona
= 1 Identity
= 1 Browser
= 1 AI Stack

✅ 이 방향 맞음.

실리콘밸리 실무에서는:

Identity Isolation
Browser Fingerprint Isolation
Behavioral Separation
AI Tone Separation

매우 중요하게 봄.

7️⃣ 하지만 지금 가장 위험한 실수 (Danger)

❌ "모든 툴에 모든 계정 연결"

이건 매우 위험.

회장님 방향처럼:

Persona A → Gmail A → AdsPower A → AI Tool A
Persona B → Gmail B → AdsPower B → AI Tool B

이게 정석.

특히 Meta 계열은:

세션(Session)
행동패턴(Behavior)
쿠키(Cookie)
로그인 관계(Relationship Graph)

다 본다.

--------------------------------------
실리콘밸리 실무진 기준 현재 가장 좋은 전략 (Best Strategy)

지금 단계에서 정답:

✅ "완벽한 초거대 구조" 만들지 말 것
✅ "작은 성공 루프(Small Stable Loop)" 먼저 완성할 것

즉:

1 Source
→ 1 Blog
→ 1 Instagram
→ 1 Video
→ 1 Persona
→ Revenue 발생

이 루프를 완전 안정화한 뒤:

1 → 10 → 30 → 100 → 1000

로 확장.
-----------------------------------
실리콘밸리식 구조

❌ Source → Instagram

아님.

✅

Source(여러 곳)

↓

Content Pool

↓

AI 정제

↓

필터

↓

Instagram
Threads
TikTok

중앙 Content Pool을 만든다.

Source 우선순위
Source	목적	주기
공급사 지정	신뢰 확보	매일
Facebook 그룹	실재고	실시간
Google 이미지	미끼 콘텐츠	주 1~2회

Google은 "운영 데이터"가 아니라 콘텐츠 보강용이다.

이미지 자동 가공

→ 지금 하는 것이 맞다.

이유

한 번 만들면 모든 Source 재사용.
공급사가 100개가 되어도 동일 파이프라인 적용.
유지보수 비용이 낮다.

다만

❌ 완벽한 AI 편집부터 만들기

아님.

✅ 간단한 자동 Crop + Resize + 워터마크부터.

YOLO 같은 고도화는 안정화 후.

매출 관점

매출은

좋은 사진

보다

꾸준한 업로드

영향이 더 크다.

즉

품질 80점
업로드 지속

이

품질 100점
업로드 없음

보다 낫다.

실행 순서
Source 3개 확정
공급사
Facebook
Google
Content Pool 하나로 통합
자동 Crop/Resize 최소 기능 추가
AI 필터
Instagram 자동 업로드
리스크

❌ Source마다 별도 로직 개발

→ 유지보수 증가

→ 안정화 지연

→ 확장 시 코드 중복
------------------------------------------------
실리콘밸리의 실무 정석인 "Interface Now, Infrastructure When Proven (인터페이스 추상화는 지금 하되, 무거운 인프라는 수치로 증명될 때 도입하라)" 법칙
-----------------------------
실리콘밸리 실무에서는 의뢰인은 단일 Excel에서 ID_가입계정 최종과 SNS 연결만 검증하고, 엔지니어가 그 확정본을 Airtable의 계정표와 SNS표로 분리 이관한다.
-------------------------
내가 지금 페르소나 =영업마케팅할 아바타를 만들려고한다면 어느 회사 . 어떤사람 담당자를 만나서 상담하나? 일진행순서가 어떻게되나? 실리콘밸리실무진은 어떻게하나? 각각 한줄답 0613 1123p
6s 동안 생각함
질문	한줄답
어느 회사를 만나나?	AI Automation Consulting + Growth Marketing + CRM/SNS 운영 전문사를 만나되, 플랫폼 정책·보안 검토 역량이 있는 회사를 선택한다.
어떤 담당자를 만나나?	총괄은 Automation/Solution Architect, 실무는 Growth Strategist·Data Architect·Security/Compliance Lead가 함께 맡는다.
진행 순서	Discovery 인터뷰 → 목표/KPI 확정 → 계정·데이터 감사 → Persona/DB 설계 → 30개 Pilot → 정책·보안 검증 → 100→500→1000 확장 순이다.
실리콘밸리 방식	처음부터 1000개를 만들지 않고, 30개로 Runtime Evidence를 만든 뒤 성과·차단률·오류율 기준을 통과할 때만 단계 확장한다.
---------------------------------------
실리콘밸리 표준 규격  [인프라 → 페르소나 → 수익화] 순서로 정렬된 헤더 키워드를 기준
-----------------------------------------

검증 안 된 큰 그림 위에 세부 설계·코드를 전부 먼저 그리는 건("Big Design Up Front") 실리콘밸리에서 오히려 구식·고위험으로 취급되고, "제일 불확실한 것부터 싸게 검증(Kakao Gate) → 그걸 바탕으로 나머지 세부 채워넣기"가 표준
------------------------
실리콘밸리 실무 표준 방법 (Evidence: 업계 표준 관행)
1단계 — 처음부터 AI를 새로 만들지 않는다

바닥부터 이미지 인식 모델을 학습시키는 건 실무에서 거의 안 함. 대신:

사진 → 이미 잘 만들어진 공개 AI(CLIP 같은 것)에 통과 → 사진의 "특징 숫자"만 뽑음
→ 그 숫자 위에 아주 작고 가벼운 판정기 하나만 학습

비유: 사람 눈은 이미 훈련된 상태고, 너는 "합격/불합격" 도장 찍는 법만 가르치는 거야. 이러면 수만 장이 아니라 수백~수천 장만 라벨링해도 충분함.

2단계 — 아무 사진이나 무작위로 라벨링 안 시킨다 (Active Learning)

가장 손이 많이 가는 실수: 크롤링한 사진 전부를 순서대로 하나씩 합격/불합격 표기하는 것.
실무 방법: AI가 "이건 헷갈려요" 하는 사진만 먼저 사람한테 보여줌 → 그것만 표기 → AI가 그 부분만 배움 → 다시 헷갈리는 것만 골라줌. 반복.
→ 같은 정확도를 손 훨씬 적게 대고 도달하는 방법. 이게 네가 원하는 "손이 너무 많이 간다" 문제의 실제 해법.

3단계 — 지금 만든 룰 필터를 버리지 않는다

지금 있는 quality_gate.py/content_filter.py를 폐기하는 게 아니라 1차 거름망으로 그대로 씀. 룰이 확실히 걸러줄 수 있는 것(명백한 스팸 단어 등)은 룰이 계속 처리하고, 애매한 것만 AI 분류기로 넘김. 룰 → AI 순서의 2단 필터.

4단계 — 데이터 나누는 법 (지난 질문의 답: (a) 진짜 ML)
구분	용도	주의
Train	AI가 배우는 데이터	—
Val	학습 중간중간 실력 체크	—
Test	최종 진짜 실력 시험	Train과 절대 섞이면 안 됨

중요 (실무에서 자주 틀리는 부분): 무작위로 섞어서 나누면 안 됨. 같은 판매자/같은 배경 사진이 Train과 Test에 동시에 들어가면 "시험 문제를 미리 본 것"과 같아서 실제 성능이 뻥튀기됨. 날짜/판매자 기준으로 나눠야 진짜 실력이 나옴.

5단계 — 배포 후에도 사람 검토는 안 끝난다

AI를 실전에 투입한 뒤에도 "AI가 자신 없어하는 사진"은 계속 사람이 봐줌. 새 판매자, 새 워터마크가 나타나면 AI가 또 헷갈리기 때문 — 이건 영구적인 운영 루프임, 한 번 학습시키고 끝이 아님.
---------------------------

실리콘밸리에서도 "dev machine"과 "prod machine"을 분리하는 게 표준
--------------------------
실리콘밸리 SRE들이 실제로 하는 것 (원칙 3가지)
원칙	지금 프로젝트에 없는 것	왜 필요한가
1. "Watch the watcher" — 감시자를 감시하는 별도의 독립 경로	watchdog 죽으면 알림도 같이 죽음	감시 대상과 알림 발신 주체가 같으면 안 됨. 최소한 Task Scheduler에 "5분마다 watchdog.log 최신 시각만 확인해서 Slack 보내는" 완전히 별개의 5줄짜리 스크립트가 있어야 함 — watchdog 본체와 무관하게 독립 실행
2. 진짜 서비스로 등록 (사람 세션과 분리)	foreground 창에 생명이 걸려있음	Windows Service(NSSM 등) 또는 "로그온 여부와 무관하게 실행" 옵션으로 등록해야 터미널/세션과 완전히 분리됨. 지금 ERR-047 조사가 이 방향으로 가는 중이지만 아직 안 됨
3. 매 작업 전후 상태확인 습관화(bookending)	새 작업 시작 전 "지금 운영 살아있나" 확인 안 함	아무 진단/수정 작업이든 시작 직전에 heartbeat 나이 확인 한 줄, 끝난 직후 한 줄 — 이게 있으면 "언제부터 죽어있었는지" 3시간 뒤가 아니라 그 자리에서 바로 압니다
-----------------------------------
실리콘밸리 실무 방식 — 원칙만 먼저
로그 종류	실무 표준
명령 실행 감사로그(지금 이거)	OS/정책 레벨 자동 캡처 유지 — 이건 원래 좋은 관행이다(보안 감사, 재현성). 다만 이름을 내용에 맞게 짓는다: logs\powershell_transcripts
AI 대화 자체(Claude Code와 나눈 대화)	직접 스크립트로 캡처하지 않는다. Claude Code는 자체적으로 대화 이력을 로컬에 별도 저장하는 기능이 있다 — 이게 있는지부터 확인이 먼저다. 없다면 그건 "버그"가 아니라 "아직 이 프로젝트에 없는 기능"이다
원칙	관심사 분리(Separation of Concerns) — 명령 실행 로그, 애플리케이션 로그(watchdog.log), 대화 로그는 서로 다른 폴더/다른 메커니즘. 하나를 억지로 다른 용도로 겸용하지 않는다
----------------------------

실리콘밸리 관행 기준으로는 "소스 오브 트루스를 직접 읽을 수 없는 주체는 그 소스에 들어갈 콘텐츠를 저작하지 않는다"
-----------------------------
실리콘밸리는  
 말로 안 하게 만드는 구조 
CI/CD 파이프라인은 AI한테 diff를 "말해달라" 안 하고, git diff 결과를 파일째로 그대로 아티팩트에 올리거나 PR에 첨부
사람이 검수할 땐 AI의 설명이 아니라 원본 파일/diff 파일 자체를 봄

----------------------------
실리콘밸리가 이런 걸 막는 방법 (일반적 관행):

Stale assumption 체크를 절차에 강제로 박아넣음 — "이전에 안 사실"을 새 명령에 쓰기 전에 "그게 지금도 유효한가?"를 한 줄 확인하는 습관. 사람이 아니라 체크리스트가 강제함.
작은 실수는 즉시 고치고 넘어감, 대규모 재설계 안 함 — 지금 한 것처럼 "1단계 재수행"으로 바로 넘어가는 게 맞는 방식. 지침서 전체를 뜯어고치는 건 과잉대응.
반복되면 그때 규칙화 — 한 번 실수는 그냥 고치고, 같은 패턴이 2~3번 반복되면 그때 지침에 항목 추가. 매번 지침을 고치면 지침서가 비대해지고 오히려 안 지켜짐.----
-------------------------
 , "규칙화 + 반복 감사 + 발견 시 즉시 교정"의 반복  
-------------------------------------------
실리콘밸리는 어떻게 하나

핵심 차이: 사람이 매 단계 승인하는 게 아니라, AI 에이전트가 자율적으로 여러 스텝을 연속 실행하고, 사람은 "결과만" 검토
-------------------
실리콘밸리 방식은 "기존 게시물 손대지 말고, 재발 방지 필터부터 코드에 심어라(prevent future harm first, clean up history later)"다.
-------------
실리콘밸리 표준 : 초반부터 완벽한 통합 아키텍처를 짜지 않고, Repository/Adapter 패턴으로 각 외부 의존성(DB, AI API, 알림 등)을 개별적으로 추상화하며 검증된 것만 하나씩 편입시킨다(Strangler Fig 패턴/Canary 배포 방식)-
----------------------

방지책 (실리콘밸리 디버깅 원칙)

명령을 원자 단위로 쪼갠다 — 한 셸 호출에 파일 1개, 목적 1개만. 여러 파일 동시 조회 금지.
결과를 요약 금지, 원문 그대로 요구 — "설명하지 말고 파일 내용만 출력"을 명시.
부수 발견은 즉시 기록만 하고 조사 안 함 — OUT OF SCOPE 태그 붙이고 진행.
1개 명령 = 1개 산출물 확인 후 다음 명령 — 배치 처리 금지, 순차 처리 강제.
--------------------------
실리콘밸리 인시던트 대응 원칙은 "발견된 새 증상마다 새 트랙을 열지 않는다
--------------------------
실리콘밸리 실무 방식:

원칙	적용
Upstream-first	입력→처리→출력 순. 입력 0이면 하류 안 본다
Cheapest test first	눈으로 볼 수 있으면 코드 짜지 않는다 (브라우저 1개 = 계측 5개)
Bisection	파이프라인 중간을 찍어 앞/뒤 이분. 순차 추격 금지
Time-box	가설당 15분. 초과 시 상류로 후퇴
---------------------------------
실리콘밸리 실무진 접근법 — 원칙 먼저,직설적으로,
-----------------------------
실리콘밸리 실무진이 하는 방법
설계 확정 (빈 틀 만들기)
↓
검증된 계정부터 투입 (43개 메인)
↓
비밀번호 확인하면서 status 업데이트
↓
나머지 보조 계정 추가
↓
확장

-----------------------------------
어느 회사: 퍼포먼스 마케팅 에이전시 또는 SNS 자동화 전문 개발사.

어떤 사람: CTO 또는 시니어 자동화 엔지니어 + 퍼포먼스 마케터 동시에.

일 진행 순서: 요구사항 정의 → 견적 → 계약 → 설계 승인 → 개발 → 테스트 → 운영.

실리콘밸리 실무진 방식: 직접 고용 대신 Upwork에서 Airtable/n8n 전문가 프리랜서 2명 계약 — 한 명은 DB 설계, 한 명은 자동화 구현, 동시 병렬 진행.
--------------------------
실리콘밸리 페르소나 설계 방식

핵심 철학: 페르소나는 "가짜 사람"이 아니라 "특정 고객의 욕구를 대변하는 전략 도구"다.

실리콘밸리가 페르소나 만드는 방식
단계	방법	핵심
1. 데이터 수집	실제 고객 인터뷰 5~10명	추측 금지. 실제 말 그대로 사용
2. 패턴 추출	공통 불만/욕구/행동 분류	감이 아닌 빈도 기준
3. 페르소나 정의	이름/나이/직업/욕구/두려움 1장으로	팀 전체가 같은 그림 보게
4. 검증	실제 고객에게 보여주고 "맞아요?" 확인	내부 승인 말고 고객 승인
5. 자동화 연결	페르소나별 메시지/채널/시간대 분리	1 페르소나 = 1 실행 흐름
실리콘밸리만의 노하우 3가지

① Jobs-to-be-Done 프레임
고객이 "이 상품을 사는 이유"가 아니라 "이 상품으로 해결하려는 일"을 찾는다.
베트남 여성이 화장품을 사는 게 아니라 "한국인처럼 보이고 싶어서" 산다 — 이게 다르다.

② 안티 페르소나 설계
누구한테 팔지만큼 누구한테 팔지 않을지를 먼저 정한다.
타겟이 좁을수록 전환율이 높다.

③ Living Document 원칙
페르소나는 한 번 만들고 끝이 아니다.
매달 실제 DM/댓글 데이터로 업데이트한다.
-----------------------
실리콘밸리 방식
단계	실리콘밸리	일반적 방식
순서	페르소나 먼저 → 아바타 설계	계정 만들고 나중에 생각
페르소나	실제 고객 인터뷰 데이터 기반	감으로 추측
아바타	페르소나 1개당 아바타 1~3개 매핑	계정마다 따로 따로
자동화	아바타 설정값이 곧 자동화 파라미터	자동화와 캐릭터 분리
핵심 노하우	페르소나가 아바타의 말투/콘텐츠/시간대를 결정	운영하면서 감으로 조정
----------------------------

실리콘밸리 방식	데이터 샘플 먼저 보고 → 그 데이터에 맞는 Schema 설계 → 전체 이관

---------------------
실리콘밸리 설계 원칙 — Identity-Centric 구조
아바타 1개 (중심)
├── 이메일 계정 1개 (크롬 로그인 기준)
├── Facebook 1개
├── Instagram 1개
├── TikTok 1개
├── YouTube 1개
├── AdsPower 프로필 1개
└── Proxy IP 1개

--------------------

실리콘밸리  

"지금 필요한 것만 만들고, 필요해지면 분리한다."
----------------
실리콘밸리 설계 원칙 — Identity-Centric
사람(Identity) 1명이 중심
↓
그 사람이 가진 SNS 계정들은 별도 TABLE
↓
Linked Record로 연결
-------
실리콘밸리 원칙
Done is better than perfect.
지금 돌아가는 것 > 완벽한 설계
---------------------
실리콘밸리 표준 순서:

일단 작동하게 만든다 (지금 단계 — 완료)
중간 레이어 삽입해서 교체 가능하게 만든다 (다음 단계)
실제 교체한다 (필요할 때만)
----------------
실리콘밸리 원칙: YAGNI (You Aren't Gonna Need It) — 필요 증명 전 구현 금지.
---------------------
'실리콘밸리 업무 정석 대표 자료'===>넷플릭스 컬처 데크 (Netflix Culture Deck):"자유와 책임"을 바탕으로 한 실리콘밸리 조직문화의 바이블로 불립니다. 인터넷에 'Netflix Culture'를 검색하면 슬라이드 형태로 전문이 공개되어 있어 누구나 볼 수 있습니다.《스타트업 바이블》 또는 《스타트업 창업가 매뉴얼》(The Startup Owner's Manual - 스티브 블랭크):실리콘밸리식 고객 개발(Customer Development)과 린 스타트업 방법론의 뼈대가 된 대표적인 실행 매뉴얼입니다.《레디 피플》(Radical Candor - 킴 스콧):전직 구글·애플 임원이 쓴 책으로, 실리콘밸리식 피드백과 소통 규칙을 다룬 실무 지침서입니다.  각종 글로벌 VC(벤처캐피털)의 플레이북:세쿼이아(Sequoia Capital)나 Y 바이오네이터(Y Combinator) 같은 실리콘밸리 명문 액셀러레이터들은 웹사이트를 통해 창업가들을 위한 가이드와 템플릿(피치덱 작성법, 지표 관리법 등)을 무료로 배포하고 있습니다.

-------------------------------
실리콘밸리식 진행 순서
순서	목적	실행 방식
1	Stop bleeding	현재 추가 오게시 위험 확인. 필요 시 Domeggook posted 경로 임시 HOLD 검토
2	Define label	사용자 노란색 정정을 정답 라벨로 고정
3	Locate gate	어느 파일에서 막을지 결정: quality_gate.py 우선
4	Dry-run first	실제 게시/수정 없이 최근 20건 재분류
5	Canary fix	최소 코드 1곳만 수정
6	Test	기존 정상 상품이 막히지 않는지 확인
7	Runtime proof	실제 경로에서 FILTERED 로그 확인
8	Cleanup later	이미 올라간 게시물은 수동 삭제/문서 기록. KPI는 건드리지 않음
------------------------------
AI 멀티모델 실무 역할 분리 원칙 (실리콘밸리 엔지니어링 기준)
역할 분리 원칙
Perplexity = 실시간 리서치 및 레퍼런스 수집 (웹 검색, 최신 공식 문서, 오픈소스 트렌드 탐색)

Gemini = 대규모 데이터 분석 및 멀티모달 컨텍스트 통합 (방대한 로그 분석, 아키텍처 다이어그램 해석, 비즈니스 문서 요약)

GPT = 시스템 아키텍처 설계 및 핵심 로직 구조화 (복잡한 시스템 스펙 정의, 프로토타입 시퀀스 기획, 트러블슈팅 가이드 수립)

Claude = 핵심 코드 구현 및 고도화 (클린 코드 작성, 리팩토링, 대규모 프로젝트 단위의 시맨틱 로직 구현)

Claude Code = 터미널 기반 에이전트 워크플로우 수행 (로컬 파일 시스템 조작, 테스트 실행, 깃(Git) 브랜치 관리 및 자동화 빌드)

Codex = 코드 리뷰 및 보안 취약점 감사 (정적 분석, 예외 케이스 검증, 성능 병목 구간 탐지)

----------------------------


실리콘밸리 업무 정석

실리콘밸리 방식은 완벽해질 때까지 기다리는 것이 아니다.

현황 확인
→ 가장 위험한 누수 차단
→ 최소 테스트
→ Runtime 반영
→ 다음 핵심 문제 해결
→ 본래 설계로 복귀
```

</details>

---

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 260722 (v1) | 최초 통합본 — `docs/SILICON_VALLEY_STANDARD_WORKFLOW.md` 최초 작성 |
| 260722 (v2) | 회장 지시로 SSOT 강화 재작성 — 표준 결과 출력 포맷/FACT·INFERENCE·UNKNOWN·RISK/Single Canary/상태변경 실행주체/Session Start 등록 추가, `SILICON_VALLEY_EXECUTION_STANDARD.md`로 개명·승격. CLAUDE.md Session Start Rule에 등록. |
| 260722 (v3) | CLAUDE.md/CURRENT_RUNTIME_CONTEXT.md/MERGE_JOURNAL.md/ERROR_DATABASE.md/VALIDATION_STATUS.md/system_prompt_v2.md 조사 후 **중복 제거 + 실제 선례로 재작성**. 모든 원칙에 "원본 위치" 표기 추가(§1~§9 표). 신규 §2 Blast Radius 최소화 원칙 추가(실무에서 이미 반복 사용 중이던 패턴을 처음 명명). §7 상태변경 실행주체의 근거를 정정 — 260721(Codex)과 ERR-053/260710(Claude Code 자신)은 서로 다른 위반이며 둘 다 인용. 12대 체크리스트(§9) 각 항목에 실제 적용 사례 병기. **미해결로 남긴 것**: `docs/system_prompt_v2.md`가 CLAUDE.md의 Multi-AI Review Policy를 그대로 중복 보유 중임을 발견했으나, 이번 작업 범위(이 문서의 통합) 밖이라 손대지 않음 — 별도 확인 필요. |
| 260723 (v4, 이번) | 회장 지시로 §10 신설 — `docs/실리콘밸리업무정석260722.txt`(회장이 메모장에 계속 모아온 원문, 512줄) **최초 전량 이전, 재해석·재작성 없이 원문 그대로**. §1~§9(운영절차 SSOT)와 §10(제품/성장전략 원자료)은 층위가 달라 충돌 자동판정 안 함 — 이번 이전 시점엔 직접 충돌 발견 안 됨. 앞으로 메모장 갱신 시 §10은 diff로만 추가(덮어쓰기 금지). |
