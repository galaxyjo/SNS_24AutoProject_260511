# 세션 인수인계 — A_BEAUTY 크롤링 → 완전 자동 게시 (261028, B_MED 세션 종료 시점)

> 목적: 새 세션이 이 문서만 읽고 이어서 진행한다. 목표는 **IDN-000041(yuna18253)이 이미 자동화된 방식(크롤링 → 게시)을 다른 A_BEAUTY 계정에 확장해 자동 게시**하는 것이다.
> 작성: Claude Code, 261028 15:00 KST. 아래 FACT는 이 세션에서 직접 확인한 것이고, 확인하지 못한 것은 UNKNOWN으로 표시했다. 상태변경은 CLAUDE.md의 승인 규칙(코드 수정·Airtable 쓰기·`.env`·재시작·Commit·Push는 각각 승인)을 따른다.

## 1. 지금 상태 (FACT)

- Git: `origin/master` = `8d10c9e`(Push 완료). launcher는 commit `afa9fc8`(13:25 기동)이고 그 뒤에 등록한 IDN-000038은 반영 전 코드다(LAUNCHER_STALE).
- 오늘 B_MED·C_TRAVEL 게시 성공: 031·018·019·035·017(피부과), 038(제주). 모두 **수동 게시 경로**(관리자 PowerShell로 Producer→게시)였고 자동 슬롯은 켜지 않았다.
- A_BEAUTY 계정은 `Account_Registry.category = A_BEAUTY`이고 도메인 Gate는 `CATEGORY_DOMAIN_POLICY["A_BEAUTY"] = "PRODUCT"`(키워드 필터)로 이미 연결돼 있다(`modules/sns/content_filter.py`). B_MED용 Gate(허위 의료 표현 차단)는 A_BEAUTY에 적용되지 않는다.
- 041이 자동화되는 구조(Airtable `Crawl_Targets`, 직접 조회): `collection_purpose=production`이고 `publish_account_code=IDN-000041`, `account_ref=k1bto3j4`(AdsPower 프로필)인 Facebook 대상 4개 — A002 `FB_한국화장품`, A003 `FB_뷰티도매2`, A004 `FB_신규1`, A005 `FB_신규2`(Active, max_posts 20). A001은 Hold. 나머지 A0xx 다수는 `training`(자동 게시 안 됨). 크롤은 `launcher/main.py`의 `_job_fb_crawl`, 게시는 5분 폴러 `_job_insta_upload`(PRODUCT Gate 통과 후 `publish_single`).
- A_BEAUTY 계정 `.env` 자격(키 존재·정상 조회만 확인, 값 비공개; 261028 15:35 갱신): IDN-000011·051·052(EAA 정상, Gemini 있음), **IDN-000048**(credential_key `SALE1`: `SALE1_INSTA_*` EAA 정상 + `SALE1_GEMINI_*`를 051과 같은 키로 추가, generateContent 200, IG ID 17841403029540647은 `@ubk_office`로 조회되며 Airtable `account_handle`은 `kbeautiquewholesale`로 불일치 — 확인 필요), **IDN-000007**(공용 EAA·IG ID 추가, `@hsy00718g` 조회 정상, Airtable `account_code`·`api_provider` 입력 완료, `automation_enabled`는 꺼짐). 041은 credential_key `YUNA`(EAA, 전용 Gemini 키 없음). 007·048·051은 모두 같은 공용 EAA 토큰을 쓴다.
- 인스타 토큰: 19개 계정 중 15개가 **같은 EAA 토큰 1개**를 공유(galaxy app instabot). 011·014·017·023은 Threads 토큰(THAA)이 Instagram 칸에 있어 오늘 공용 EAA로 교체했다(ERR-185).

## 2. UNKNOWN (새 세션에서 먼저 확인)

1. 다른 A_BEAUTY 계정에 **전용 AdsPower 프로필·Facebook 로그인 세션**이 있는가 (041은 `k1bto3j4`). AdsPower는 무료 플랜 전환됨.
2. `_job_fb_crawl`·크롤 → `Source_Feeds`/`Instagram_Posts` 변환이 계정별로 일반화돼 있는가(`target_publish_account_code_ref`·`publish_account_code` Fail-closed 규칙은 261022 B2에 설계됨). `source_exporter.py`의 `"IDN-000041"` 하드코딩은 Dome(도매꾹) 카나리 함수에 있고 FB 경로와는 별개로 보인다 — 호출 경로 확인 필요.
3. PRODUCT Gate(`passes_keyword_filter`)와 `Supplier_Blocklist`가 새 계정에도 그대로 적용되는지, 상품 Persona·언어(Persona `language`)가 계정마다 어떻게 설정됐는지.
4. 041의 일일 게시 상한·시간대·`Instagram_Posts` 상태 흐름(draft/ready/posted)의 정확한 값.

## 3. 오늘 얻은 교훈 (반복 금지)

1. **실행 중인 launcher/폴러는 재시작 전 코드를 쓴다.** 새 계정을 코드에 등록해도 폴러가 `UNKNOWN_DOMAIN`으로 `ready` 레코드를 거절한다(ERR-181). 코드 수정 후 관리자 재시작이 필요하고, `tools/check_account_preflight.py`가 `LAUNCHER_STALE` 경고로 알려준다. 폴러 주기는 5분이며 마지막 실행 시각은 `logs/summary/app.log`의 `_job_insta_upload`에서 확인한다.
2. **관리자 PowerShell이 필요한 단계:** Boot Policy(`C:\ProgramData\SNS_24AutoProject\runtime_boot_policy.json`)가 일반 프로세스에는 막혀 있어 Airtable `ready` 등록과 게시는 관리자 문맥에서만 된다. 서비스 재시작은 `Restart-Service SNS_Watchdog`.
3. **토큰 점검은 값이 아니라 호출로:** Preflight는 키 "존재"만 본다. `THAA…`(Threads)와 `EAA…`(Instagram)를 구분하려면 접두사와 `graph.facebook.com/{ig_id}` 조회가 필요하다(FP-120). 출력에 키를 절대 쓰지 않는다 — 이번 세션에서 한 번 노출 사고가 있었다(ERR-179).
4. **Gemini 키 프로젝트별 무료 티어:** 035는 프로젝트에 결제가 없어 403이었다. 모델은 `gemini-3.5-flash-lite`만 쓸 수 있다(2.5는 404).
5. **이미지 생성(Cloudflare Workers AI)은 일일 무료 한도 10,000 neurons**가 있어 아침에 소진될 수 있다(429).
6. **영어 캡션은 357자 상한에 걸려** 영어만 800자로 올렸다(`caption_generator`). Persona 말투가 한국어면 영어 지시에도 한국어가 섞인다.
7. **모델 출력은 사람이 검수한다:** 근거 없는 의료·수치 표현이 나왔고(예: "수백만 년"), 이를 B_MED Gate가 일부 자동 차단한다. A_BEAUTY는 화장품 상품 소개이므로 "효능 보장" 표현 검사가 필요한지 새 세션에서 결정한다.
8. 이미지는 무료 스톡(Pexels 등)을 쓸 수 있고 출처를 캡션과 `.source.txt`에 남긴다(`docs/design/IMAGE_SOURCES_BMED_261028.md`). 단 A_BEAUTY 크롤링 경로는 원본 게시물의 이미지 권리(`Crawl_Targets.sns_reuse_allowed`·`permission_status`)를 따로 확인해야 한다.

## 4. 운영 원칙 (CLAUDE.md 요약)

- **무인 운영 원칙(260907):** 사람 개입은 결함이다. 계정당 1회 프로비저닝(AdsPower/Facebook 최초 로그인)만 허용하고, 반복 개입이 필요하면 자동화 방안을 제시한다. 사람에게 요청할 때는 A(금지)/B(계정당 1회)/C(승인 게이트)를 분류한다.
- Single Canary: 계정 1개 → 게시 1건 → 확인 후 확장. 한 번에 한 가지를 바꾼다.
- Evidence First: Runtime 로그·Airtable·Graph API 조회로 확인하기 전에 완료라고 말하지 않는다. 게시 URL은 Graph API `permalink`로 확인한다.
- 관리자 명령은 항상 명령어만 담은 코드블록으로 준다. 응답 첫 줄은 `(YYMMDD_HH:MMam/pm) (전체단계)번호단계 : 세부단계 시작/종료 — 판정어: 이유`, 마지막 줄은 쉬운 한 줄 요약.
- 문서(`docs/*.md`) 갱신은 승인 없이 바로 가능, Commit·Push는 승인 후.

## 5. 새 세션 작업 순서 (제안)

1. 세션 시작 규칙 4개 읽기(CLAUDE.md의 Session Start Rule) + 이 문서.
2. 읽기 전용 조사: 041 크롤→게시 호출 경로(`_job_fb_crawl` → `Source_Feeds` → `Instagram_Posts` → `_job_insta_upload`)를 import chain으로 확정하고 위 UNKNOWN 1~4를 채운다.
3. 대상 A_BEAUTY 계정 선정: `.env` 자격이 갖춰진 011·051·052(+048은 Gemini 확인) 중 크롤용 AdsPower 프로필·Facebook 세션이 있는 계정부터. 없으면 B(1회 프로비저닝) 항목으로 보고.
4. 설계안 제출(5요소: 문제·증거·BUILD/REUSE/BUY·가장 작은 테스트·원복) → 승인 → 계정 1개로 Crawl_Targets 1행(`publish_account_code` 설정, `production`) → 크롤 1회 → 게시 1건 → URL 확인.
5. 성공하면 자동 잡(스케줄)을 켜기 전 launcher 재시작과 Flag 결정을 별도 승인으로 요청하고, 계정 확장은 1→3으로 단계적으로 진행한다.

## 6. 새 세션 시작 프롬프트

```
너는 SNS_24AutoProject(C:\SNS_24AutoProject_260511)의 Principal Automation Engineer다. 목표는 A_BEAUTY 계정에 IDN-000041(yuna18253)이 이미 자동화된 방식 그대로 "Facebook 크롤링 → Airtable → Instagram 자동 게시"를 확장해 완전 자동 게시를 만드는 것이다.

먼저 docs/SESSION_HANDOFF_ABEAUTY_261028.md 전체를 읽고, CLAUDE.md의 Session Start Rule 4개(CURRENT_RUNTIME_CONTEXT, MERGE_JOURNAL 마지막 20줄, git status, SILICON_VALLEY_EXECUTION_STANDARD)를 읽은 뒤 시작한다.

규칙: ① 041 자동화 경로를 import chain으로 증명하기 전에는 코드를 수정하지 않는다 ② 상태변경(코드·Airtable 쓰기·.env·재시작·Commit·Push)은 각각 승인 후 실행하고 Single Canary(계정 1개·게시 1건)로 검증한다 ③ 키·토큰 값은 절대 출력하지 않는다 ④ 사람 개입이 필요하면 A(금지)/B(계정당 1회)/C(승인) 중 하나로 분류해 보고한다 ⑤ 게시 URL은 Graph API permalink로 확인한다 ⑥ 응답은 헤더 1줄 + 핵심 3~5줄 + 쉬운 한 줄 요약으로 짧게 하고 관리자 명령은 코드블록에 명령만 넣는다.

첫 작업(읽기 전용): 인계 문서의 UNKNOWN 1~4를 채워 "041과 같은 방식으로 확장 가능한 A_BEAUTY 계정과 막힘(AdsPower 프로필·Facebook 세션 등)"을 표로 보고하라. 그 후 승인 요청 형식(문제·증거·직접수정/재사용/외부도구·가장 작은 테스트·원복)으로 첫 계정 Canary 계획을 제출하라.
```
