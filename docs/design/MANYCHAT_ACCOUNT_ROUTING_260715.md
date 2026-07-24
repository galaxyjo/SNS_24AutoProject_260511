# ManyChat 계정별 병렬 라우팅 설계 (RFC) — 260715

**상태:** DRAFT — Codex/GPT 리뷰 전, 실행 승인 전. 회장 지시로 설계 문서만 우선 작성.

## 배경

`yura`(Instagram Business 계정)는 현재 Meta App Review(Advanced Access) 심사가 진행 중이며(260715 00:35 제출), 심사가 끝나기 전까지는 앱 테스터로 등록되지 않은 일반 손님과의 DM 왕복이 제한될 수 있음(ERR-064/FP-048/INC-036, 미확정 가설). 이 문제를 우회하기 위해, `yura`를 제외한 **다른 모든 계정은 이미 Meta 공식 Business Partner로 Advanced Access를 보유한 ManyChat으로 운영**하기로 결정.

## Goals

1. `yura`는 지금처럼 우리 자체 Python 스택(Flask webhook + Gate C/G 안전장치 + Gemini AI 응답)으로 계속 운영한다.
2. `yura`를 제외한 신규/추가 계정은 우리 시스템에 연결하지 않고 ManyChat에서 독립적으로 자동화를 구성한다.
3. 두 경로가 서로의 웹훅·크레덴셜·상태를 침범하지 않는 명확한 경계를 문서로 고정한다.

## Non-Goals (이번 설계 범위 밖)

- `yura`를 ManyChat으로 전환하는 것 — 이번 결정과 무관, `yura`는 계속 우리 시스템
- 우리 코드베이스에 "계정별 라우팅 로직"을 새로 구현하는 것 — 아래 "왜 코드 변경이 거의 없는가" 참조. 다계정 DM/댓글 자동응답 엔진을 만드는 게 아니라, **다른 계정은 애초에 우리 웹훅에 연결하지 않는 것**이 설계의 핵심
- ManyChat 쪽 자동화 로직(플로우/키워드/AI 설정) 구현 — ManyChat 자체 UI에서 각 계정 담당자가 구성, 이 저장소의 범위 밖
- Airtable CRM(Lead_Interactions)과 ManyChat 리드 데이터의 통합 — 현재는 완전히 분리된 두 시스템으로 남음(아래 Risk 참조)
- `modules/common/account_manager.py`/`accounts.json`(FB 크롤링 다계정) 구조 변경 — 이건 콘텐츠 소싱용이고 DM/댓글 자동응답과는 이미 별개 시스템

## 현재 아키텍처 사실관계 (Evidence-based)

- `modules/dm/dm_receiver.py`는 애초에 **다계정 구조가 아님** — `.env`의 `INSTA_ACCESS_TOKEN`/`INSTA_IG_USER_ID` 단일 값만 사용(코드 확인, [dm_receiver.py:26-27](modules/dm/dm_receiver.py:26)). `configs/accounts.json`(FB 크롤링용)에도 계정 1개(`account1`)만 등록돼 있고, `ig_access_token`/`fb_page_id` 필드는 전부 빈 문자열.
- 즉 **"다른 계정을 우리 시스템에서 떼어내는" 마이그레이션이 아니라, 애초에 등록된 적 없는 계정들을 처음부터 ManyChat에만 연결하는 것** — Expand-Contract 마이그레이션 대상 자체가 없음(기존 라이브 트래픽 이전이 아님).
- Meta 웹훅 구독은 **앱 단위가 아니라 IG 비즈니스 계정 단위**로 걸림(Meta Graph API `subscribed_apps` 계약) — `yura`는 우리 앱에, 다른 계정은 ManyChat 앱에 각각 독립적으로 구독하면 서로 간섭하지 않음. 이 사실은 Meta 공식 문서 기반 추정이며, **우리가 직접 두 계정을 동시에 운영해 충돌 없음을 실증한 적은 없음(UNKNOWN, Canary 필요)**.
- ManyChat이 실제로 Advanced Access를 보유하는지는 회장 언급 기반이며, **우리가 ManyChat 대시보드에서 직접 확인한 적 없음(UNKNOWN)** — 착수 전 확인 게이트 필요(Non-Goal #11 참조).

## 왜 코드 변경이 거의 없는가

`yura` 외 계정은 우리 `.env`/`accounts.json`/Meta 웹훅 구독 어디에도 등록하지 않으면, 그 자체로 우리 시스템과 완전히 분리된다. "라우팅"은 코드가 아니라 **등록 여부의 문제** — 10살 기준 설명: 각 계정마다 "이 손님은 누가 받을지" 이름표를 붙여서, 어떤 계정은 우리 프로그램이 받고 어떤 계정은 ManyChat이 받게 나눠주는 것뿐(회장 확인 표현 그대로).

다만 **완전히 0줄은 아닐 수 있는 부분**(착수 전 결정 필요, 아래 "결정 필요 항목" 참조):
- KPI/일일 리포트(`modules/metrics/kpi_collector.py`)가 "우리가 운영하는 계정 = yura 1개"라는 암묵적 가정으로 짜여 있다면, ManyChat 계정들의 리드/매출은 이 리포트에 아예 잡히지 않음 — 의도된 것인지 확인 필요.
- `modules/common/account_manager.py`의 FB 크롤링 다계정 확장과, 이번 ManyChat DM 라우팅은 **서로 다른 계정 셋일 수도, 겹칠 수도 있음**(예: FB 크롤링은 계정 A/B/C로 하되, 그 중 Instagram DM 응대는 A만 우리 시스템, B/C는 ManyChat) — 이 매핑을 어디에 기록할지(Airtable? `accounts.json`에 필드 추가? 그냥 사람이 기억?) 결정 필요.

## Kill-switch / Rollback

- `yura` 경로: 기존 `COMMENT_AUTO_REPLY_ENABLED`/`PRICE_AUTO_REPLY_ENABLED` 플래그가 이미 kill-switch 역할 — 변경 없음.
- ManyChat 경로: 계정별 on/off는 **ManyChat 자체 UI**에서 각 봇/플로우를 끄는 것으로 통제 — 우리 코드에 별도 kill-switch를 만들 필요 없음(우리 시스템에 애초에 연결되지 않으므로).
- Rollback 시나리오: 특정 계정을 ManyChat에서 우리 시스템으로 되돌리고 싶다면, 그건 "롤백"이 아니라 **신규 온보딩**(그 계정의 크레덴셜을 처음으로 `.env`/`accounts.json`에 등록하고 웹훅을 우리 쪽으로 재구독) — 별도 작업량 있음, 무료가 아님.

## Risk

| 리스크 | 내용 | 완화 |
|---|---|---|
| 리포트 분절 | ManyChat 계정들의 리드/매출이 Airtable KPI에 안 잡힘 | Non-Goal로 명시, 필요시 추후 ManyChat→Airtable 연동(Zapier/Webhook)을 별도 과제로 분리 |
| ManyChat Access Level 미검증 | ManyChat이 실제 Advanced Access 보유한다는 근거가 회장 언급뿐, 우리가 직접 확인 안 함 | 착수 전 ManyChat 대시보드에서 직접 확인(Platform Policy 게이트, 아래 참조) |
| 계정 매핑 기록 부재 | "어느 계정이 우리 것, 어느 게 ManyChat 것"인지 기록할 곳이 현재 없음 | 착수 시 `docs/CURRENT_RUNTIME_CONTEXT.md` 또는 Airtable에 계정 레지스트리 표 추가 결정 필요 |
| 비용 | ManyChat Pro $29~/월 × 계정 수 | 계정 수 확정 후 예산 확인 |

## Platform Policy 검토 게이트 (착수 전 필수 확인)

1. ManyChat 워크스페이스가 실제로 Meta Advanced Access를 보유하는지 ManyChat 대시보드에서 직접 확인
2. ManyChat 1개 워크스페이스/플랜에 계정을 몇 개까지 연결 가능한지 확인(Pro 플랜 계정당 1개인지, 다중 연결 가능한지)
3. `yura`의 Meta 앱과 ManyChat의 Meta 앱이 동일 Meta Business Manager 내에서 서로 다른 IG 계정에 각각 구독해도 충돌 없는지 — 가능하면 계정 1개로 실제 Canary(다른 계정 하나를 ManyChat에 먼저 연결해보고 웹훅 정상 작동 확인) 선행

## SLO/모니터링

- `yura`: 기존 `health_monitor.py`/KPI 파이프라인 그대로 적용.
- ManyChat 계정: **모니터링 공백** — ManyChat 자체 대시보드로만 확인 가능, 우리 Slack 알림/watchdog 대상 아님. 이번 설계 범위에서는 이 공백을 그대로 인정하고 넘어감(Non-Goal), 계정 수가 늘어나 운영 부담이 커지면 별도 과제로 통합 검토.

## 결정 필요 항목 (회장 확인 대상)

1. ManyChat으로 갈 계정이 지금 몇 개/어떤 계정인지 구체적 리스트
2. 위 Platform Policy 게이트 1~3번 확인 여부
3. 계정 매핑을 어디에 기록할지(문서 vs Airtable)

## 관련 문서
- ERR-064, FP-048, INC-036 (Standard Access 의심, App Review 제출)
- `docs/design/META_APP_REVIEW_SCRIPT_260714.md`
- memory: `project_manychat_pivot_consideration`, `feedback_sv_methodology`
