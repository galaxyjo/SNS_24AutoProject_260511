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
5. 실제 증거 — 공식 원천·실제 화면·Runtime 결과 중 최소 1개를 근거로 제시한다.
6. 해결 Workflow — "입력 → 자동화 → 결과" 형태로 해결 구조를 제시한다.
7. 구체적 결과 — 그 해결이 만드는 구체적 결과를 제시한다.
8. CTA 1개 — 게시물당 정확히 1개의 행동 유도 문구로 마무리한다.

필수 규칙:

- 첫 문장(Hook)은 타깃 고객이 실제로 사용할 법한 표현이어야 한다.
- Evidence(5단계)는 공식 원천·실제 화면·Runtime 결과 중 최소 1개여야 한다.
- 해결구조(6단계)는 반드시 "입력 → 자동화 → 결과" 형태로 표현한다.
- 출처(Evidence)에 없는 수치·성과·사례를 새로 만들지 않는다.
- CTA는 게시물당 1개만 포함한다(2개 이상 금지).
- 구조(8단계 순서)만 고정하고, Hook 문구·사례·화면·표현·CTA 키워드는 매번 다르게 작성한다.
- Evidence를 확보하지 못하면 생성하지 말고 HOLD한다.

---

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 260807 | 최초 작성 — 확정된 8단계 글쓰기 구조를 Generation Contract로 고정하고, `caption_generator.generate_hook_caption()`에 Runtime 연결. |
