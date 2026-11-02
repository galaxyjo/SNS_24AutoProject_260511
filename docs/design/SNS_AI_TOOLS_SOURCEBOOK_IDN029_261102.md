# SNS AI 도구·자동화 Sourcebook — IDN-000029 전용 (261102)

> 목적: IDN-000029(AI new tool) 계정이 하루 3건 이상 서로 다른 Topic을 쓸 수 있도록 계정 전용 Sourcebook을 둔다. 공용 AI Sourcebook(260723)은 aijomoojin(036)의 SSOT라 건드리지 않고, 이 파일은 계정 전용이다.
> 범위: AI 도구 사용기·자동화 사례 범위의 Topic 3개
> 주의: 신규 항목은 검색 요약에서 확인한 범위만 적었고 원문 전문은 확인하지 않았다. 상태는 USE_WITH_CAUTION이며 수치·기능은 게시 전 원문 재확인 대상이다. 1.1은 공용 Sourcebook의 기존 항목을 그대로 가져왔다.
> 연결: 이 파일은 launcher `CONTENT_ACCOUNTS`의 sourcebook_path를 설정하기 전에는 어떤 잡도 읽지 않는다(코드 변경은 별도 승인).

---

### 1.1 Radical Candor

상태: VERIFIED FACT

정확한 영문 제목: Radical Candor: Be a Kick-Ass Boss Without Losing Your Humanity

저자: Kim Scott

한국어 공식 출간명: 《실리콘밸리의 팀장들》(청림출판, 2019)

공식 URL: https://www.radicalcandor.com/the-book

검증된 설명:
- Kim Scott은 Google에서 AdSense·YouTube·DoubleClick 관련 팀을 이끌었다.
- 이후 Apple University에서 근무했다.
- 핵심 구조는 `Care Personally + Challenge Directly`이다.
- 사람을 존중하면서도 문제를 직접 말하는 피드백 방식이다.

SNS 콘텐츠 핵심 메시지:
좋은 피드백은 친절하기만 하거나 공격적이기만 한 것이 아니라, 사람을 배려하면서 문제를 직접 말하는 것이다.

사용 금지 표현: `레디 피플`

정확한 교체 표현: `Radical Candor / 한국어판 《실리콘밸리의 팀장들》`

---

### 1.2 Wellness Coach 자동화 사례 — Zapier

상태: USE_WITH_CAUTION

공식 URL: https://zapier.com/blog/how-wellness-coach-scales-with-automation-and-ai/

검증 범위:
- Zapier 블로그의 고객 사례를 검색 요약으로 확인했다(원문 전문 미확인). 업체가 직접 공개한 자체 보고다.
- AI를 결합한 Slack 워크플로와 업무 자동화로 주당 약 10.6시간, 연 550시간 이상을 절약한 것으로 추정된다고 소개된다.

SNS 콘텐츠 핵심 메시지:
Zapier가 소개한 Wellness Coach 자동화 사례에서는 AI를 결합한 Slack 워크플로와 업무 자동화로 주당 약 10.6시간, 연 550시간 이상을 절약한 것으로 추정된다. 자동화 사례를 볼 때 핵심은 어떤 반복 업무를 자동화했는지이며, 절약 시간은 업체가 직접 밝힌 자체 추정이다.

주의:
절약 시간을 다른 기업에도 같은 수치로 적용된다고 쓰지 않는다. 특정 도구 구매를 권유하지 않는다. 가격·플랜을 쓰지 않는다.

이미지 개념: simple workflow of connected app icons with a clock saving hours, clean flat style
카드 사실: Zapier 고객 사례 | 업체 자체 추정치 | 주당 약 10.6시간 절약 | 반복 업무를 먼저 고름
주제 해시태그: 자동화사례 | Zapier | 업무자동화 | 생산성

---

### 1.3 n8n Build your first AI agent — AI 도구 사용기

상태: USE_WITH_CAUTION

공식 URL: https://n8n.io/workflows/6270-build-your-first-ai-agent/

검증 범위:
- n8n 템플릿 페이지를 검색 요약으로 확인했다(원문 전문 미확인).
- 채팅 트리거, AI 에이전트 노드, Google Gemini 모델에 날씨·뉴스(RSS) 도구를 붙인 구성이며, 무료 Google AI API 키로 약 2분이면 설정할 수 있다고 소개된다.

SNS 콘텐츠 핵심 메시지:
n8n 템플릿 "Build your first AI agent"는 채팅 트리거와 AI 에이전트 노드, Google Gemini 모델에 날씨·뉴스(RSS) 도구를 붙인 구성이며, 무료 Google AI API 키로 약 2분이면 설정할 수 있다고 소개된다. AI 도구 사용기로 따라 해 볼 만한 가장 작은 에이전트 예시다.

주의:
설정 시간(약 2분)을 모든 환경에서 같다고 단정하지 않는다. 템플릿 노드·API가 바뀔 수 있음을 전제로 쓴다. 특정 도구 구매를 권유하지 않는다.

이미지 개념: chat bubble connected to a small agent node and two tool icons, clean flat style
카드 사실: n8n 템플릿 | 채팅 트리거+AI 에이전트 | Gemini 모델에 날씨·뉴스 도구 연결 | 무료 키로 약 2분
주제 해시태그: AI도구 | n8n | 에이전트 | 사용기
