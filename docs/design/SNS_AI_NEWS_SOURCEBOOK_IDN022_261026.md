# IDN-000022(951.0606) AI 뉴스 정리 Sourcebook — Canary 1차본

> 261026 회장 지시(STEP 5-B, IDN-000022 콘텐츠 연결 Canary) — IDN-000022 전용 원천. aijomoojin(IDN-000036) 공용 Sourcebook과 분리된 파일이며 022 Producer만 읽는다.
> Persona PER-021 Pillar("국내 이슈 요약 / 해외 이슈 요약 / 키워드 순위 / AI 뉴스 정리법") 중 **해외 이슈 요약**에 맞춘 해외 AI 원문 3건이다. 국내 이슈·키워드 순위는 근거 원천이 아직 없어 넣지 않았다.
> 각 핵심 메시지는 아래 원문 내용만 요약했다(2026-10-26 15:5x ICT 원문 직접 열람 확인). 수치·모델명은 원문 표기 그대로다. 원천 선정 기준은 `docs/design/SOURCE_REGISTRY_6CAT_261026.md`(Primary·자동 접근 확인).
> 형식은 공용 Sourcebook 파서(`modules/sns/source_selector.py`)와 같다: `### N.M 제목` / `상태:` / `URL:` / `SNS 콘텐츠 핵심 메시지:`.

## 1. 해외 AI 이슈 요약 (공식 블로그 원문)

### 1.1 해외 이슈 요약 — IBM Granite Speech 5.0 음성 AI 공개 (Hugging Face 블로그, 2026-10-21)
상태: VERIFIED FACT
URL: https://huggingface.co/blog/ibm-granite/granite-speech-5

SNS 콘텐츠 핵심 메시지:

해외 이슈 요약: IBM이 음성 AI 모델 3종(granite-speech-5.0-2b 신규, granite-speech-5.0-470m-turboctc·granite-speech-4.1-2b-plus 개선판)을 공개했다. 2B 모델은 영어·프랑스어·독일어·스페인어·포르투갈어·일본어를 받아쓰고 영어와 상호 번역하며, 39만 시간 분량의 공개 음성으로 학습했고 제품명·인명을 최대 2,000개 키워드로 지정할 수 있다. Open ASR 리더보드 영어 평균 단어 오류율(WER) 5.06%로 공개 모델 중 2위다. Turbo CTC는 7개 언어 전사와 구두점 자동 처리를 추가하고 속도가 약 1.6배 빨라졌으며, 회의·통화용 4.1-2b-plus는 장문 음성 오류율을 24% 줄였다. 모두 Apache 2.0 라이선스다.

### 1.2 해외 이슈 요약 — GitHub Copilot 앱 작업을 VS Code에서 이어가기 (GitHub 블로그, 2026-10-19)
상태: VERIFIED FACT
URL: https://github.blog/ai-and-ml/github-copilot/how-to-continue-a-github-copilot-app-session-in-vs-code/

SNS 콘텐츠 핵심 메시지:

해외 이슈 요약: GitHub Copilot 앱에서 AI 에이전트가 하던 작업을 VS Code에서 그대로 이어받는 방법이 공개됐다. 세션에서 'Open in VS Code'를 누르면 작업 지시·계획·대화와 변경된 코드(diff), 같은 작업 폴더(worktree)가 함께 열린다. 사람은 변경 내용을 줄 단위로 검토하고 직접 고친 뒤 로컬에서 테스트하고, 같은 대화로 Copilot에 추가 수정을 요청할 수 있다. 마지막에 push하면 그 세션의 Pull Request가 바로 갱신된다. 사전 조건은 Copilot 앱과 VS Code가 같은 GitHub 계정에 연결돼 있고 저장소에 push 권한이 있는 것이다.

### 1.3 해외 이슈 요약 — AnyLanguageModel 1.0, 애플 앱에서 AI 모델 골라 쓰기 (Hugging Face 블로그, 2026-10-20)
상태: VERIFIED FACT
URL: https://huggingface.co/blog/anylanguagemodel-1-0

SNS 콘텐츠 핵심 메시지:

해외 이슈 요약: Hugging Face가 애플 Foundation Models API를 그대로 쓰면서 AI 모델과 제공사를 바꿔 끼울 수 있는 AnyLanguageModel 1.0을 1년 만에 정식 출시했다. import 한 줄만 바꾸면 기기 안의 모델(llama.cpp·MLX·Core ML)과 OpenAI·Anthropic·Gemini·Ollama 같은 외부 API를 같은 코드로 쓸 수 있고, 도구 호출과 이미지 입력도 지원한다. 원문 기준 Gemma 4 E2B(약 3.4GB)와 LFM2.5 2.6B(약 1.7GB)는 아이폰에서 돌아가고, Qwen3.8 27B(약 16GB)는 메모리 32GB 이상 Mac에서 돌아간다.
