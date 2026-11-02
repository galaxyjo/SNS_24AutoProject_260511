# SNS AI 리스크·원리 Sourcebook — IDN-000027 전용 (261102)

> 목적: IDN-000027(Neuron.xray) 계정이 하루 3건 이상 서로 다른 Topic을 쓸 수 있도록 계정 전용 Sourcebook을 둔다. 공용 AI Sourcebook(260723)은 aijomoojin(036)의 SSOT라 건드리지 않고, 이 파일은 계정 전용이다.
> 범위: AI 리스크 관리·AI 원리 설명 범위의 Topic 3개
> 주의: 신규 항목은 검색 요약에서 확인한 범위만 적었고 원문 전문은 확인하지 않았다. 상태는 USE_WITH_CAUTION이며 수치·기능은 게시 전 원문 재확인 대상이다. 1.1은 공용 Sourcebook의 기존 항목을 그대로 가져왔다.
> 연결: 이 파일은 launcher `CONTENT_ACCOUNTS`의 sourcebook_path를 설정하기 전에는 어떤 잡도 읽지 않는다(코드 변경은 별도 승인).

---

### 1.1 NIST AI Risk Management Framework (AI RMF 1.0)

상태: VERIFIED FACT

공식 URL: https://www.nist.gov/itl/ai-risk-management-framework

검증된 설명:
- NIST AI RMF 1.0은 조직이 AI 위험을 관리하도록 제공하는 자발적 프레임워크다.
- 핵심 기능은 Govern, Map, Measure, Manage로 구성된다.
- NIST는 AI RMF 1.0 개정 작업을 진행 중이다.

SNS 콘텐츠 핵심 메시지:
AI 도입은 성능뿐 아니라 설계·개발·사용·평가 전 과정의 거버넌스와 위험 식별·측정·대응을 함께 관리해야 한다.

주의:
NIST가 특정 제품이나 기업을 인증·보증하거나 모든 AI 위험을 제거한다는 표현은 금지한다.

---

### 1.2 EU AI Act 위험 기반 접근 — AI 리스크 관리

상태: USE_WITH_CAUTION

공식 URL: https://artificialintelligenceact.eu/assessment/eu-ai-act-compliance-checker/

검증 범위:
- EU AI Act 정리 페이지(artificialintelligenceact.eu)를 검색 요약으로 확인했다. 이 페이지는 EU 공식 규정 원문이 아니므로 Regulation (EU) 2024/1689 원문과 대조가 필요하다.
- AI 시스템을 금지(허용 불가)·고위험·제한(투명성)·최소 위험의 4단계로 나누어 의무를 달리 정하는 위험 기반 접근이라고 요약한다.

SNS 콘텐츠 핵심 메시지:
EU AI법은 AI 시스템을 위험 수준에 따라 금지(허용 불가)·고위험·제한(투명성)·최소 위험의 4단계로 나눠 의무를 달리 정하는 위험 기반 접근을 취한다고 정리된다. 고위험 시스템에는 위험관리·데이터 거버넌스·기술 문서·사람의 감독 같은 요구가 붙고, 챗봇 같은 제한 위험 시스템에는 사용자에게 AI임을 알리는 투명성 의무가 붙는다고 한다. AI 리스크 관리를 위한 하나의 규제 틀로 볼 수 있다.

주의:
비공식 정리 페이지 기반이라 조항 번호·시행일·과징금 수치를 단정하지 않는다. 특정 제품이 어느 등급인지 판단하지 않는다. 법률 자문처럼 쓰지 않는다.

이미지 개념: four-tier pyramid diagram with flat clean colors, minimal tech style
카드 사실: EU AI Act 정리 | 4단계 위험 기반 접근 | 고위험은 위험관리·감독 요구 | 챗봇은 투명성 의무
주제 해시태그: AI리스크 | EUAIAct | AI규제 | AIgovernance

---

### 1.3 LLM이 답을 만드는 방식 — AI 원리 설명

상태: USE_WITH_CAUTION

공식 URL: https://huggingface.co/blog/prismberry-technologies/how-llm-inference-actually-work

검증 범위:
- Hugging Face 블로그의 LLM 추론 해설을 검색 요약으로 확인했다(원문 전문 미확인). 공식 문서가 아니라 실무 해설 글이다.
- 입력을 토큰으로 나눠 트랜스포머 층을 통과시키고 토큰별 점수(logit)를 확률로 바꿔 다음 토큰 하나를 고른 뒤 문맥에 붙여 반복한다는 흐름이 서술된다.

SNS 콘텐츠 핵심 메시지:
LLM은 입력을 토큰으로 쪼개 트랜스포머 층을 통과시키고, 각 토큰 후보의 점수(logit)를 확률로 바꿔 다음 토큰 하나를 고른 뒤 그것을 문맥에 이어 붙여 같은 과정을 반복한다. 문장을 한 번에 이해해서 쓰는 것이 아니라 확률에 따라 다음 토큰을 계속 예측하는 방식이라는 것이 AI 원리 설명의 핵심이다.

주의:
실무 해설 글 기반이라 특정 모델의 내부 구조·성능을 단정하지 않는다. LLM이 사람처럼 이해하거나 생각한다고 쓰지 않는다.

이미지 개념: simple flow diagram of tokens flowing through layers into one next token, clean tech style
카드 사실: 토큰으로 분해 | 트랜스포머 층 통과 | 점수를 확률로 변환 | 다음 토큰을 골라 이어 붙임
주제 해시태그: AI원리 | LLM | 트랜스포머 | 리스크
