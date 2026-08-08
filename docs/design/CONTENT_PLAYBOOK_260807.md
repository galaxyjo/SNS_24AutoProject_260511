# Content Playbook

## 1. Document Control

- Document Purpose: aijomoojin SNS 캡션 생성이 따라야 하는 확정된 글쓰기 구조(Generation Contract)의 SSOT
- Created Date: 2026-08-07
- Status: ACTIVE GENERATION CONTRACT
- Runtime Caller: `modules/sns/caption_generator.py` `generate_hook_caption()` — `load_generation_contract()`로 이 파일의 "Generation Contract" 섹션을 그대로 읽어 프롬프트에 포함한다(코드에 구조를 다시 옮겨적지 않는다 — Drift 방지).
- Update Owner: Claude Code
- Final Approval Owner: User

---

## 2. Usage Rules

1. 이 문서의 "Generation Contract" 섹션이 유일한 구조 SSOT다 — 코드나 다른 문서에 같은 구조를 중복 서술하지 않는다.
2. 구조(8단계 순서)는 고정하되, Hook 문구·사례·화면·표현·CTA 키워드는 매번 다르게 작성한다.
3. Evidence를 확보하지 못하면 생성하지 않고 HOLD한다(추정으로 채우지 않는다).
4. 이 문서를 수정하면 즉시 모든 신규 생성 캡션에 반영된다(코드 재배포 불필요, Runtime 재시작도 불필요 — 매 호출마다 파일을 다시 읽는다).

---

## Generation Contract

구조(8단계, 반드시 이 순서로 구성한다):

1. 고객문장 Hook — 타깃 고객이 실제로 쓸 법한 표현으로 시작한다.
2. 반복상황 — 그 고객이 반복적으로 겪는 상황을 짧게 제시한다.
3. 구체적 손실 — 그 상황이 만드는 구체적 손실(시간·기회·신뢰 등)을 제시한다.
4. 의외의 원인 — 그 손실의 원인 중 의외인 지점을 짚는다.
5. 실제 증거 — 전달받은 공식 원천(Sourcebook 검증된 핵심 메시지)에 실제로 적힌 사실만 근거로 제시한다. 이 파이프라인은 스크린샷·Runtime 실행결과를 별도로 전달받지 않으므로, 그런 화면·결과가 실제로 함께 제공된 경우가 아니면 "실행 화면"·"Runtime 결과"를 확인했다는 식으로 표현하지 않는다.
6. 해결 Workflow — "입력 → 자동화 → 결과" 형태로 해결 구조를 제시한다.
7. 구체적 결과 — 그 해결이 만드는 구체적 결과를 제시한다.
8. CTA 1개 — 게시물당 정확히 1개의 행동 유도 문구로 마무리한다.

필수 규칙:

- 첫 문장(Hook)은 타깃 고객이 실제로 사용할 법한 표현이어야 한다.
- Evidence(5단계)는 전달받은 공식 원천(Verified core message)에 실제로 적힌 내용이어야 한다 — 실제로 전달받지 않은 스크린샷·Runtime 결과·실행 화면을 확인한 것처럼 주장하지 않는다(260808 4차 지시 — 이 파이프라인은 text 입력만 받고 화면·Runtime 데이터를 별도로 받지 않으므로, 그런 증거 유형 주장은 항상 근거 없음으로 간주해 HOLD한다).
- 해결구조(6단계)는 반드시 "입력 → 자동화 → 결과" 형태로 표현한다.
- 출처(Evidence)에 없는 수치·성과·사례를 새로 만들지 않는다.
- CTA는 게시물당 1개만 포함한다(2개 이상 금지).
- 구조(8단계 순서)만 고정하고, Hook 문구·사례·화면·표현·CTA 키워드는 매번 다르게 작성한다.
- Evidence를 확보하지 못하면 생성하지 말고 HOLD한다.
- 최종 결과물(8요소+해시태그 합산)은 350~450자를 권장 목표(Soft Target)로 한다 — 350자 미만이라는 이유만으로 HOLD하지 않는다. 다만 500자를 넘으면 게시하지 않고 HOLD한다(Threads 공식 게시물 글자수 제한 기준 — [Meta 공식 문서](https://developers.facebook.com/documentation/threads/posts)). 8요소를 억지로 길게 늘리지 말고 각 요소를 짧은 문장·절로 압축하되, 가능하면 350~450자대에 오도록 구체적 디테일을 담는다.

---

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 260807 | 최초 작성 — 확정된 8단계 글쓰기 구조를 Generation Contract로 고정하고, `caption_generator.generate_hook_caption()`에 Runtime 연결. |
| 260808 | Threads 공식 500자 제한 대응 — 8요소별 필드 검증(요소 누락/CTA 복수/500자 초과 HOLD) Runtime 연결, 이후 프롬프트에 길이 목표 강화, 최종적으로 350자 미만도 HOLD하도록 Validator 하한 추가(실측상 프롬프트만으로는 하한이 항상 지켜지지 않아 강제 필요). |
| 260808 | Threads 공식 500자 제한(Meta 공식 문서) 대응 — 최종 결과물 350~450자 생성목표/500자 상한 규칙을 필수 규칙에 추가. `generate_hook_caption()`이 8요소를 각각 별도 필드로 요구·검증하고, 500자 초과·요소 누락·CTA 복수 시 HOLD하도록 Runtime 연결(코드 Diff는 caption_generator.py 참조). 현재 Runtime에는 Threads 게시 경로 자체가 없음(Read-only 확인, Instagram 단일 게시) — 이 규칙은 향후 Threads 연결 대비 및 캡션 압축 품질 기준으로 우선 적용한다. |
| 260808 | 3차 지시로 350자 하한 HOLD 제거 — 350~450자는 프롬프트 권장 목표(Soft Target)로만 유지하고, 코드가 강제하는 필수 조건은 8요소 전부 포함·CTA 정확히 1개·최종 500자 이하 3가지로 확정. |
| 260808 | 4차 지시 — Generation Contract 5단계·필수 규칙의 "실제 화면·Runtime 결과" 문구가 이 파이프라인에 실제로 없는 증거 유형을 모델이 주장하게 유도한 근본 원인으로 확인돼 제거. Evidence는 전달받은 공식 원천(Verified core message)에 실제로 적힌 내용만 인정하며, `caption_generator.py`에 스크린샷/Runtime 주장·출처 미근거 Evidence를 HOLD하는 Validator를 Runtime 연결. |
