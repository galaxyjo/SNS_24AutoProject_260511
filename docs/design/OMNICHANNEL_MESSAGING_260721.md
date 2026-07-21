# 옴니채널 메시징(Kakao/WhatsApp/Instagram DM 통합) 설계 — 260721

**상태:** **Stage 1(설계·시장조사) 완료 — Stage 2(실측 검증) 착수 전.** 코드·Airtable·git·운영설정 전부 미변경, 신규 파일 1개만 생성(`git add/commit` 별도 승인 대상).

**출처:** 본 문서의 "확정된 것/미해결/다음 액션" 내용은 별도 세션(claude.ai, 세션명 `[260721_03:10pm]옴니채널 메시징 시스템 설계 및 AI 역할 분리 전략`, 260721 15:10~20:49)에서 Perplexity/Gemini/GPT/Claude 5개 AI와 회장이 직접 협업 검증한 결과를 회장이 전달한 것이다. **Claude Code는 이 내용을 독립적으로 재검증하지 않았다** — 아래 "확정된 것" 표는 그 세션의 결론을 그대로 기록한 것이며, Evidence Rule 기준으로는 아직 "출처 세션의 주장"이지 "Claude Code가 raw 근거로 재확인한 사실"이 아니다. Stage 2에서 이 문서의 각 항목을 실측 재검증하는 것이 다음 작업이다.

**관련 배경:** 이 주제는 260713 [[DM_RELAY_COMMERCE_RFC]] §3 Non-Goals에서 이미 한 번 언급됐다 — "WhatsApp/Kakao/Zalo 연동은 지금 당장 만들지는 않지만 무기한 보류가 아니다... P0-4(Go/No-Go) 시점에 반드시 다시 논의 대상으로 상기시킬 것." 이번 260721 세션이 그 재논의에 해당한다. 또한 같은 날(260721) 이 세션(Claude Code)에서도 별도로 옴니채널 백로그를 `docs/CURRENT_RUNTIME_CONTEXT.md`에 기록한 바 있다(코드 전수조사로 "현재 미구현"만 확인, 벤더 비교는 하지 않음) — 이 문서가 그 후속 심화 조사에 해당한다.

---

## 1. Executive Summary

Instagram DM은 자체 시스템(Meta 직접 연동)으로 유지하고, WhatsApp도 자체 Meta 직접 연동 경로를 유지한다. **카카오톡만** Meta 생태계 밖이라 자체 직접 연동이 불가능하므로, 카카오 공식 딜러사(Channel.io/채널코퍼레이션)를 경유하는 구조로 설계 방향이 좁혀졌다. 5개 AI 교차검증 과정에서 여러 대안(Chatwoot, SOLAPI/TasOn, ManyChat 확장, Airbnb/Grab 참조사례)이 탈락했고, 탈락 사유가 각각 다르다(아래 §3).

## 2. Goals / Non-Goals

**Goals:**
1. 카카오톡으로 들어오는 문의를 자체 파이프라인(Airtable Lead_Interactions 등)으로 통합 수신한다.
2. Buyer↔Supplier 매칭/라우팅 로직은 전부 자체 Airtable/Core에 유지하고, 벤더(Channel.io 등)의 bot builder에는 위임하지 않는다 — 기존 [[DM_RELAY_COMMERCE_RFC]]의 "회장님 계정 명의로만 노출" 불변조건과 동일한 원칙.
3. AI(Gemini 등)의 역할을 의도추출/번역/초안 생성으로만 한정하고, 수신자 결정이나 실제 전송 승인 권한은 주지 않는다 — PII Gate 통과 전에는 실데이터를 어떤 외부 AI에도 전송하지 않는다.

**Non-Goals(이번 Stage 1 범위 밖):**
- Instagram/WhatsApp 자체 연동 구조 변경 — 이번 조사는 카카오 경로 추가만 다룬다.
- 실제 Channel.io 연동 코드 작성 — Stage 2 실측 검증 전에는 코드 착수하지 않는다.
- 다계정(1,000개 목표) 확장 설계 — [[project_manychat_hybrid_decision_260716]]와 동일하게, 매출 전환 증거 없이 대량 확장 인프라를 미리 설계하지 않는다는 원칙을 여기도 적용한다.

## 3. Alternatives Considered (탈락 확정)

| 후보 | 탈락 사유 |
|---|---|
| Chatwoot | 카카오톡 자체를 지원하지 않음 |
| SOLAPI / TasOn | 카카오 공식 딜러사가 아님(비공식 경로로 판단됨) |
| ManyChat 확장 | 워크스페이스당 과금 구조로 비용 폭증 — [[project_manychat_hybrid_decision_260716]]에서 이미 같은 이유로 대량확장 기각된 것과 동일 패턴 |
| Airbnb/Grab 참조사례 | AI가 제시한 사례가 **조작된(fabricated) 근거로 판명** — 세션 중 교차검증으로 걸러짐. **방법론 교훈**: AI가 제시하는 사례연구는 1차 출처 인용 없이는 신뢰하지 않는다(이번 세션에서 Perplexity/Gemini에게 보낸 프롬프트에도 "1차 출처 URL 필수, 추측 금지" 조건을 명시한 것이 이 교훈 반영) |

## 4. 확정된 것 (FACT — 출처 세션 결론, Claude Code 재검증 전)

| 항목 | 결론 |
|---|---|
| 아키텍처 방향 | Instagram/WhatsApp = 기존 Meta 직접 연동 유지, **카카오만** 외부 딜러(Channel.io) 경유 |
| 카카오 딜러 후보 | Channel.io(채널코퍼레이션)가 카카오 공식 8대 딜러 중 하나로 확인됨 — `feedback@channel.io` 이메일로 카카오 공식 문서에 등재된 것을 근거로 제시 |
| 매핑 로직 원칙 | Buyer↔Supplier 매칭은 전부 자체 Airtable/Core에 유지, 벤더 bot builder에 위임 금지 |
| Gemini 역할 제한 | 의도추출/번역/초안만 허용. 수신자 결정·전송 승인 금지. PII Gate 통과 전 실데이터 전송 금지 |

## 5. 미해결 — UNKNOWN, Stage 2 실측 필요

1. Channel.io webhook이 워크플로우(유료 Flow Builder 등)를 우회해서 raw event를 직접 전달하는지 — 안 되면 ManyChat 때처럼 요금제 제약에 다시 걸릴 수 있음.
2. Kakao 채널 ID·사업자 계정 ID가 webhook payload에 실제로 포함되는지.
3. 다계정 자동화가 Channel.io ToS(이용약관) 위반에 해당하는지 — 확인 없이 진행하면 계정 정지 위험.
4. MAU(월간활성사용자) 초과 시 정확한 단가 — 현재 1건 비공식 확인뿐, 공식 재검증 필요.
5. WhatsApp Cloud API 자체 연동은 "가능성"으로만 남아있고 아직 미검증.

## 6. 다음 액션 (순서대로)

1. 채널톡 위젯에 서면질문 10개 발송 — **회장 직접**, 미완료
2. 카카오 상담톡 인증 신청 제출 — **회장 직접**, 미완료
3. IG DM Runtime Evidence 확인 — 게시 API(`instagram_content_publish`)와 메시징 API(`instagram_manage_messages`) 혼동 여부 재확인 — **Claude Code 담당**, 착수 전
4. WhatsApp Cloud API 문서 조사 — 가능 시점에 진행
5. **우선순위 결론(회장 확정): 인스타 안정화(PENDING-A Phase 3, DI Canary)를 먼저 진행하고, 옴니채널은 회장의 위 1·2번 대기시간을 이용해 병행 조사한다.** 즉 인스타 안정화가 옴니채널보다 우선순위가 높다.

## 7. Kill-switch / Rollback

Stage 1은 문서만 존재하고 코드/설정 변경이 전혀 없으므로 별도 kill-switch가 필요 없다. Stage 2 이후 실제 연동 착수 시점에는 [[DM_RELAY_COMMERCE_RFC]] §5 불변조건 10번(`COMMENT_CAPTURE_MODE=quarantine` 등 blast-radius 한정 패턴)과 동일한 원칙을 재사용할 것을 권장 — 카카오 경로 실패 시 자동 재시도/오발송 대신 격리 후 운영자 수동 확인.

## 8. 관련 문서

[[DM_RELAY_COMMERCE_RFC]](§3 Non-Goals에서 최초 언급), `docs/CURRENT_RUNTIME_CONTEXT.md`(260721 13:51 백로그 최초 등록분), [[project_manychat_hybrid_decision_260716]](비용 스케일링 판단 기준 재사용)
