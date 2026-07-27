# CURRENT_RUNTIME_CONTEXT.md
_마지막 업데이트: 260726_ERR-082(Webhook서명검증부재)_FAILED확정+CLAUDE.md↔SVES_중복정리(D2)+Meta_App_Topology_B_확정_(⚠️ 260706~260709 구간 여전히 별도 미반영, 아래 [260710] 섹션 Backlog #5 참조 — 이번 갱신 범위 밖, 그대로 승계)

## 현재 단계
**260726: CLAUDE.md 거버넌스 대량 확장 + Bundle B(DM 계정 태깅) 구현·테스트 완료(킬스위치 OFF, 미배포) + ERR-082(Webhook 서명검증 부재) FAILED 확정 + CLAUDE.md↔SVES 문서 중복 정리(D2) + Meta App Topology B 확정. 세션 종료, 다음 세션으로 인계.**

- **CLAUDE.md 거버넌스 추가(전부 uncommitted)**: "수정 승인 5요소 원칙"(회장 확정) + Codex 작성 26개 섹션 "SILICON VALLEY ENGINEERING OPERATING MANUAL" 원문 그대로 append(603줄) + "완료된 단계" 표(라인110 하단) 오독방지 각주 1줄(B안, 표 문구는 무변경).
- **Bundle B(DM `account_code_ref` 태깅, 260726)**: `modules/dm/dm_receiver.py`+`modules/infra/airtable_repository.py`+`modules/infra/repository_interface.py` 수정 + 신규 테스트 3파일(23 tests). `DM_ACCOUNT_ROUTING_ENABLED`(기본 false) 킬스위치로 기존 동작 무변화, fail-open 설계. 댓글·크롤러 경로는 이번 Bundle에서 제외(Codex 승인 조건). **미배포 상태로 uncommitted 유지** — ERR-082(아래) 해결 전까지 프로덕션 전환 HOLD.
- **ERR-082(Webhook `X-Hub-Signature-256` 서명검증 부재) — FAILED 확정**: `/webhook` POST(DM·댓글 공용, `receive_webhook()`)에 서명검증 코드·App Secret 저장소·HMAC 계산 로직이 전부 없음을 코드 전수확인(Grep 2회, 백그라운드 전체탐색 포함)으로 확정. 위조 Payload가 Airtable Write·자동응답·댓글처리까지 무방비 도달 가능(Blast Radius 확인) — **이 노출은 Bundle B 이전부터 있던 기존 운영 DM 경로의 위험**. Build·Buy·Reuse 비교 결과 Python 표준 `hmac`/`hashlib`로 Meta 공식 스펙 충족 가능(신규 OSS/SaaS 불필요, 유력후보). **구현 자체는 미착수, 회장 승인 대기.** `docs/ERROR_DATABASE.md` ERR-082 / `docs/WORKFLOW_ARCHITECTURE_STATUS.md` §10-9 참조.
- **Meta App Topology 조사 — Topology B 확정**: Account_Registry 실측(`yuna18253`=IDN-000041/`facebook_login`/App ID `860604299884476`"Galaxy International", `aijomoojin`=IDN-000036/`instagram_login`/App ID `4522543077982497`"AI Strategist") — 회장이 Meta Dashboard 스크린샷으로 두 계정이 **서로 다른 Meta App**임을 직접 확인. 이어서 Callback→Runtime→Route 매핑 조사: **yuna18253은 이 260511 Runtime과의 연결이 Runtime Evidence로 CONFIRMED**(과거 `recipient.id` 실측 수신 기록), **aijomoojin은 이 Runtime 연결 여부 UNKNOWN**(인바운드 웹훅 수신 증거 0건, 발신 `publish_single()` 증거만 존재). `credential_resolver.py`에 App Secret 개념 자체가 코드에 없음도 확인. 복수 App Secret Keyring 설계는 aijomoojin 쪽 Mapping 미확정이라 **HOLD**(추측으로 만들지 않음).
- **CLAUDE.md↔`docs/SILICON_VALLEY_EXECUTION_STANDARD.md` 문서 중복 정리(D2 완료)**: CLAUDE.md 신규 매뉴얼과 SVES.md가 Evidence 우선순위·보고형식·Stage/Gate 절차를 서로 다르게 중복 규정하고 있던 것을 Claude Code가 Read-only로 전수조사 → GPT [260726_D2_EXECUTION] 지시서에 따라 **SVES.md 1개 파일만** 편집: §1에 7-Stage×12-Gate 매핑 신설, §3 Canonical Reporting Format, §5 Canonical Evidence Priority(9단계 단일화), §10~12 승인순서/Atomic Commit/Read-only Batch 규칙 신설, 구 원문 512줄은 §13으로 이동(비규범 표시, 내용 무손상). 15/15 성공기준 충족, 다른 파일 무변경.

## 260721 마일스톤(이전 기록, 그대로 유효)
- **배경**: Codex가 "AdsPower 시작프로그램 바로가기 대상 오류 수정 / n8n watchdog 무한재시도 원인 확정+비활성화 / Airtable Engagement 무효 ID 6개 정리"를 수행하며 git commit(`5165b8e`)까지 직접 실행 — CLAUDE.md "승인 범위 명시 원칙"·"git add/commit 선행 금지" 위반. 회장이 결과 재검토 및 이후 실행 주체 인계를 Claude Code에 지시.
- **Claude Code 독립 재검증(전부 read-only)**: commit `5165b8e` 실존·파일범위(`git show --stat`) 일치 확인 / AdsPower 바로가기 TargetPath·`TargetExists=True`·포트 50325 LISTENING 직접 재확인 / `SNS_Watchdog` 서비스 Running·Automatic 확인 / `watchdog.ps1` UTF-8 BOM(`EF BB BF`) 직접 hex 확인 / `tests/test_watchdog_encoding.py` 직접 재실행 3 passed 재현 / `watchdog.log` 원본에서 n8n 마지막 실패(12:16:37)→비활성화 로그(12:16:54) 이후 재시도 0건 확인 / Airtable MCP로 Codex가 명시한 6개 record ID의 `ig_media_id` 공란 직접 재조회 + `posted+ig_media_id 있음` 카운트 재집계 = **289 정확히 일치**. **결론: 절차 위반(권한 범위 초과)은 사실이나 보고 내용 자체의 허위·과장 없음, 6건 전부 CONFIRMED.**
- **AdsPower 재부팅 자동기동 실증(회장 명시 승인 후 실행, `AskUserQuestion`으로 영향 고지 후 진행)**: `Restart-Computer -Force` 실행(13:13) → `watchdog.log` 원본: `13:14:41 FATAL 종료` → `13:15:13 SNS_Watchdog 자동 재기동` → `13:15:18~37 Streamlit/ngrok/launcher 자동 복구` → `13:17:32~40 AdsPower Global 프로세스 8개 자동 실행`(수정된 바로가기 경로로 정상 작동). 재부팅 후 50325/5000/8501/4040 전부 LISTENING 재확인. **ERR-073/FP-054/INC-040의 "재부팅 자동기동 미검증(PENDING)"이 실증 PASS로 완전 종결.**
- **기록·커밋·push**: `docs/ERROR_DATABASE.md`(ERR-073)/`docs/FAILURE_PATTERN.md`(FP-054)/`docs/INCIDENT_TIMELINE.md`(INC-040)/`docs/VALIDATION_STATUS.md`/`porting_logs/MERGE_JOURNAL.md` 갱신, commit `2d57648`, `origin/master`에 push 완료(`1ebdc95..2d57648`). 커밋 시 기존 미커밋 상태였던 `docs/ERROR_DATABASE.md`의 ERR-068 부분은 blob 재구성 방식으로 정확히 제외하고 보존(git working tree에는 여전히 미커밋 상태로 남아있음, 의도된 상태).
- **여전히 보존·미커밋 상태(건드리지 않음)**: `configs/comment_campaign_posts.json`, `docs/ERROR_DATABASE.md`의 ERR-068 섹션, `docs/design/MANYCHAT_ACCOUNT_ROUTING_260715.md`(untracked).
- **여전히 미구현**: n8n 기능 자체(감시만 임시 중지, 워크플로우 WF-01~05는 미착수).
- 이전 마일스톤 — **FP-047 enforce 전제조건 A+B 완료(260716) → ManyChat kbeautiquewholesale Canary 성공 → RFC 웜핸드오프 설계변경(260717, 파일 미반영)은 이번 세션과 무관하게 그대로 유효**, 상세는 아래 "260717 마일스톤(이전 기록)" 참조.
- **[신규 백로그, 260721 13:51 회장 지정] 옴니채널 메시징(Omnichannel Messaging)**: 카카오톡/WhatsApp/Messenger 등 여러 채널로 들어오는 DM을 하나로 맵핑해 통합 대화 스레드로 응대하는 기능(에어비앤비 호스트-게스트 메시징 방식 참고). **현재 미구현 확인**(코드 전수조사 결과 — `modules/sns/content_filter.py`의 kakao/whatsapp/zalo/line 관련 코드는 FB 크롤링 중 판매자 연락처 노출을 걸러내는 스팸필터일 뿐, 실제 그 채널의 DM을 수신·통합하는 기능이 아님. 현재 실제로 살아있는 채널은 Instagram DM 1개뿐). 회장이 작업 착수를 지시했으나, 채널별로 각각 별도 Business API 심사(WhatsApp Business Platform/Kakao 비즈니스 채널/Messenger Platform)가 필요해 지금 진행 중인 Meta App Review(6일째 대기)와 유사한 규모의 대기시간이 각 채널마다 추가로 발생할 가능성이 높음 — 착수 전 회장과 범위·우선순위 재확인 필요(다음 세션 시작 시 first-touch 대상).

## 260717 마일스톤(이전 기록, 그대로 유효)
- **FP-047 enforce 전제조건 A**(커밋 `ab3c25d`, 260716): 댓글 원문이 로그/Telegram/retry payload 3곳에 평문으로 남던 문제(ERR-066과 같은 클래스) 해소. 공용 마스킹 유틸 `modules/common/pii_mask.py`(신규, ERR-070/FP-051 순환임포트 해결 겸용) + Fernet 암호화(retry payload, `enc_version` 엄격검증, fail-closed). enforce 모드 키검증 실패 시 launcher 전체가 아니라 댓글 처리만 거부(blast radius 한정 원칙 확립).
- **FP-047 enforce 전제조건 B**(커밋 `d456102`, 260716): `repository_interface.py`에 `verify_field_exists()` 추가, Airtable `Lead_Interactions.source_event_id` 필드 존재를 launcher 시작 시 Metadata API로 확인(startup preflight). A-2와 동일한 blast-radius 원칙 재사용.
- **부수 발견 — ERR-071/FP-052**(커밋 `e70f733`): B단계 신규 테스트 파일 추가로 pytest 수집 순서가 바뀌며 무관 테스트 2건이 일시 실패 — 근본원인은 `comment_safety_guard.COOLDOWN_HOURS`가 모듈 import 시점에 실제 `.env`(현재 0) 값으로 고정되는 구조였음. 테스트에 명시적 override 추가로 해결, 전체 회귀 원래 베이스라인(4 failed, `test_dm_close.py`만 무관)으로 복귀 확인.
- **ManyChat 전략 확정**: 자체 시스템과 ManyChat **병행 사용**(양자택일 아님) — 계정 1개(kbeautiquewholesale)는 ManyChat "Auto-DM links from comments"로 실운영 Canary 성공(실제 테스트 계정 댓글→Contact 등록→Inbox DM 확인). 도매/소매 qualifying 문구 반영("Wholesale"/"Retail" 표준 용어, "웜 핸드오프" 대화패턴 적용), FREE 플랜은 버튼 1개만 지원함을 확인(2버튼+태그 분기는 정식 Flow Builder 필요, 이번엔 버튼 1개+텍스트질문으로 타협). **남은 미완료: `View Details` 링크가 아직 `ubk.com` 플레이스홀더 — Shopify 결제 연동 완료 후 회장 직접 교체 예정.**
- **ManyChat 1000계정 확장 비용조사**: FREE는 활성 contact 25개로 제한(2026-03 정책변경), 유료 최저 $14/월(워크스페이스=계정당 별도과금) — 1000계정이면 월 $14,000+로 "마중물" 전략에 경제적으로 불가능함을 확정. **결론: 소수 대표계정(kbeautiquewholesale 등)=ManyChat, 대량 확장(1000계정 목표)=자체 시스템 필수. 단, 자체 시스템으로 1000계정을 실제로 뒷받침하는 인프라 설계는 "지금 필요 없음"으로 판단(회장 260717 확정) — 계정 1~2개조차 아직 매출 전환 증거가 없어 ROI-Gated Rollout 원칙상 시기상조.**
- **DM_RELAY_COMMERCE_RFC 설계 변경(260717, 파일 미반영 — 메모리만)**: 불변조건 #7("Supplier 답변 매번 회장님 수동승인") 폐기 → **"웜 핸드오프(Warm Handoff)"** 방식 확정 — Buyer 정보 확인 버튼 클릭이 트리거가 되어 실Supplier에게 DM 발송, 이후 Buyer↔Supplier 직접 소통. 불변조건 #1("Buyer에게 나가는 메시지는 항상 회장님 계정에서 발송")과 충돌 가능성 있어 재검토 필요. **다음 세션 최우선 작업: RFC 파일(`docs/design/DM_RELAY_COMMERCE_RFC.md`) 본문에 이 변경 정식 반영** — 세션 시작 프롬프트 이미 작성돼 회장님이 다음 세션 첫 메시지로 사용 예정.
- Meta App Review(4개 권한 신청 — `instagram_manage_comments`/`instagram_content_publish`/`instagram_manage_messages`/`instagram_basic`, 260715 00:35 제출)는 **260721 13:45 회장 직접 재확인(스크린샷) 기준으로도 여전히 "검토 진행 중"(상태: 정상, 대부분 20일 이내 소요 예상)** — 이용 사례별로 제출한 동영상 검수도 아직 안 끝남. 260716 최초 확인 이후 6일째 미결론, 다음 세션에도 재확인 필요.
- Gate C~G(260713~715, 이전 요약 그대로 유효) + 이전 마일스톤(260711 NSSM 전환, 260624 Repository Interface 전체 작업)은 그대로 유효.

## 최종 확인 커밋
2d57648 (docs(runtime): Codex 260721 작업 재검증 + AdsPower 재부팅 자동기동 실증 [260721], push 완료) — 직전 5165b8e(Codex: AdsPower/n8n/Engagement, 재검증 완료), 7f72976(watchdog UTF-8 BOM), 1ebdc95(FP-047 A+B/ManyChat/RFC 요약) 순으로 이어짐

## Source of Truth
- Runtime: C:\SNS_24AutoProject_260511
- Archive: C:\SNS_24AutoProject_250723 (삭제/dead 판정 금지)

## 마지막 확인 커밋 체인
- 9cc4ee9 (feat: CRAWL_TARGET_SOURCE Feature Flag — Airtable crawl_urls 동적 로드 [260619])
- 9d65cb4 (refactor: publish_single() 분리 — APScheduler/n8n 공용 게시 함수 [260617])
- 20bef95 (fix: last_error_msg L191 잔존 참조 제거 [260616])
- 463c350 (fix: retry_count/last_error_msg 필드 제거 + Graph API 실패 로깅 보강 [260616])
- 25c6779 (fix: image_url_hash FB CDN 중복 감지 개선 — URL 전체 대신 미디어ID 추출 [260616])
- 366c617 (fix: facebook_crawler import re 누락 추가 [260616])
- a126754 (fix: IMAGE_BLOCK_KEYWORDS에 M&Y GLOBAL 워터마크 패턴 추가 [260616])
- 0688849 (fix: clean_fb_metadata 호출 추가 — FB UI 잔여물 제거 [260616])

## Runtime 상태 (260622 기준)
| 구간 | 상태 | 근거 |
|---|---|---|
| Flask (dm_receiver) | ✅ LIVE | :5000 확인 |
| launcher/main.py | ✅ LIVE | watchdog.ps1 기동 중 |
| ngrok | ✅ LIVE | :4040 확인 |
| Streamlit | ✅ LIVE | :8501 확인 |
| n8n | ⚠️ 미구현(설계만, WF-01~05) | watchdog이 계속 재시작 시도하나 260711(LocalSystem 전환) 이후 성공 0건·실패 5,298건+ 누적 중(ERR-065, OPEN) — 실사용 대상 아님, 안정화 우선 후 진행+설계 재검토 예정(260715 회장 방침) |

## Dual Scheduler 해소 (260527)
| 항목 | Before | After |
|---|---|---|
| process_due_followups 실행 횟수/5분 | 2회 (27초 간격) | 1회 |
| :5000 바인딩 수 | 2 (watchdog Start-Flask + launcher) | 1 (launcher만) |
| watchdog.ps1 Start-Flask | ACTIVE | 주석 처리 완료 |
| 근거 | app.log 22:00:34 / 22:05:34 단일 실행 2사이클 확인 | ERR-021 / FP-017 / INC-011 |

## E2E AutoReply 증거
| 증거 | 상태 | 내용 |
|---|---|---|
| 화면 증거 | ✅ CONFIRMED | "단가 기준가는 11,000원" (5/12) |
| 로그 증거 | ❌ LOST | overwrite 구조로 소멸 |
| 코드 경로 | ✅ CONFIRMED | get_base_price() → Airtable → 응답 정상 |

## 250723 스캔 결과
- 전체 스캔 완료
- 이식 대상 없음 확정
- pytest: 613 passed / 17 failed / 6 errors — Green Build 아님
- 역할: Archive / Evidence 참고용만

## Known Fact
- DEFAULT_BASE_PRICE=50000 .env 설정 확인
- dual scheduler 중복 발송 → **260527 해소 완료** (watchdog.ps1 Start-Flask 주석 처리)
- webhook_stderr.log overwrite 구조 확인됨
- Windows venv shim: .venv\Scripts\python.exe(268KB) → Python310\python.exe(103KB) 자식 프로세스 — 2 PID 정상 (1 논리 인스턴스)
- 중복 발송 버그 → **260528 해소 완료** (_has_recent_auto_replied() CREATED_TIME() 기준 3분 window)
- _rule.reason AttributeError → **260528 해소 완료** (getattr fallback)
- SNS_Watchdog_AutoStart 작업 스케줄러 등록 → ✅ **등록 완료** (260529 관리자 권한으로 등록) → ⚠️ **260705 정정: "등록 완료"≠"실제 재기동 보장" 확인** — 06-29 이후 실제 재부팅 9회에도 Last Run Time 갱신 없음, watchdog.log 07-01 23:36 이후 4일+ 무기록. 상세: ERR-047 / FP-035 / INC-025 (미해결, OPEN)
- accounts.json 빈 배열 → crawl_urls skip → **260529 해소 완료** (account1 + crawl_url 등록)
- Airtable caption 필드 없음 → 422 UNKNOWN_FIELD_NAME → **260529 해소** → **260612 재발 → 재해소** (API로 multilineText 필드 추가, field_id=fldcxTzLzYCzD9aYe)
- FB 크롤러 2회 연속 정상 완료 → **260529 19:43 / 20:13 확인**
- crawl_urls 4개 그룹 확장 → **260602 완료** (3dbe72a)
- accounts.json BOM 제거 → **260602 완료** (c6a30d1) — PowerShell Set-Content UTF8 금지
- facebook_crawler.py load_dotenv 추가 → **260602 완료** (f5d59f2)
- pytest 104 passed / 1 xfailed / 2 xpassed 확인 (260602)
- deep-translator 1.11.4 설치 완료 (260602)
- 시스템 환경변수 AIRTABLE_API_KEY 플레이스홀더(`pat여기에전체토큰`) → **260602 제거 완료** (User scope + 세션 제거)
- bot_uploader.py → insta_uploader.py 체인: **dead stub 확인** — 실제 Graph API 호출 없음, launcher/main.py가 실제 업로더
- caption clean_fb_metadata() → **260602 완료** (349fedf) — 작성자명·경과시간·구분점(·) 제거
- Airtable ready 레코드 caption 오염 일괄 정정 → **260602 완료** (2건: recKLX1OsOvfRu5k1, recsmA4WIlrur1wHO)
- Instagram 업로드 Runtime Proof → **260602 완료** — recFyw7OUaZ666JDJ / ig_media_id=18101360630320704 / post_status=posted ✅
- 백업 완료: C:\backup_(12)_260602_2207_SNS_24AutoProject_260511.zip
- 최종 commit: 2695d87
- Supplier_Blocklist 실제 차단 적용 → **260611 완료** (11fc204) — DRY_RUN 제거, continue 적용
- LOST 72h 타임아웃 구현 → **260611 완료** (0e5133b) — DRY_RUN 모드, 실운영은 LOST_DRY_RUN=false 설정 후 활성화
- Lead_Interactions lost_reason / lost_at / disqualified 필드 추가 → **260611 완료** (Airtable UI)
- filter_rules.json + generate_filter_rules.py 추가 → **260611 완료** (3840a6a) — 운영 연동 금지, 분석용 전용
- FB그룹 1676627532598134 제거 → **260612 완료** (c71f2c7) — 인도 비율 높음, accounts.json + Crawl_Targets 동시 삭제
- ig_media_id 17863634121631171 클리어 → **260612 완료** — rectwruMD3uua54sv, engagement_tracker 반복 오류 해소
- crawl_urls 현재 5개 운영 중 (FB_GROUP_POOL_V1): 610113703703488(Hold) / 345179878828208 / 755455243345993 / 3289570041331131 / 1827528710833477
- upload_rate 6.2% → caption 필드 복구로 다음 크롤링부터 회복 예상 (260612)
- post_status ready/uploading 옵션 소실 → **260616 해소** (typecast 더미 레코드 방식으로 강제 복구)
- uploading 고착 28건 (Regine Kim 포스트 동일 이미지) → **260616 failed 일괄 마킹** (200 OK 전부)
- retry_count/last_error_msg UNKNOWN_FIELD_NAME → **260616 해소** (463c350 — 두 필드 코드에서 제거)
- image_url_hash URL 전체 해시 → CDN 노드 달라 중복 미탐지 → **260616 해소** (25c6779 — FB 미디어 ID 추출로 변경)
- import re 누락 → [FB Crawler] 크롤링 실패 | name 're' is not defined → **260616 해소** (366c617)
- Instagram 업로드 성공 → **260616 02:07 KST 확인** | recw3EHD8d9uiP2FX | post_id=18122871268709171 ✅
- M&Y GLOBAL / Mooncher Kim Supplier_Blocklist 등록 → **260616 완료** | recEDhkour93vZR74 | reason_code=BLOCK_WATERMARK_SUPPLIER
- _IMAGE_BLOCK_KEYWORDS에 `r'm&y\s*global'` 추가 → **260616 완료** (a126754)
- `clean_fb_metadata()` facebook_crawler.py L202 호출 추가 → **260616 완료** (0688849) — raw_text 추출 직후 작성자명·경과시간 제거
- `modules/sns/image_hosting.py` 신규 추가 → **260616 완료** — imgbb 업로드 유틸 (다운로드→MIME검증→SHA256→업로드→URL검증)
- `publish_single()` 분리 → **260617 완료** (9d65cb4) — launcher/main.py 게시 로직 독립 함수화, APScheduler + n8n Endpoint 공용 호출 가능
- `last_error_msg` L191 잔존 참조 제거 → **260616/17 완료** (20bef95)
- n8n Architecture 설계 → **260617 확정** (DESIGN_COMPLETE) — WF-01 Posting Scheduler / WF-02 DM Webhook / WF-03 Credential Health / WF-04 Failure Recovery / WF-05 Runtime Alert
- Credential 구조 Option B 확정 — Python이 Graph API Token 소유 (.env CRED_{ref}_TOKEN), n8n Token 비보유
- Canonical Status: post_status 단일 사용 (publish_status 미사용)
- `execution_owner` 필드 — **미구현 (P0 Backlog)**
- FB_MAX_POSTS=20 .env 설정 완료 (260619)
- Crawl_Targets 스키마 확장: platform/max_posts/account_ref/last_run_at/last_result 필드 추가 (260619)
- account_manager.py _load_crawl_urls_from_airtable() + _shadow_compare() 추가 (260619) — 9cc4ee9
- CRAWL_TARGET_SOURCE Feature Flag 구현 (260619): accounts_json(기본)/shadow(비교 로그)/airtable(URL 교체)
- Shadow 모드 검증 완료 (260619): accounts.json=5건 vs Airtable=4건, 누락 그룹 610113703703488 감지
- CRAWL_TARGET_SOURCE=airtable 전환 → Airtable 4건 URL 기반 크롤링 Runtime Proof 완료 (260619)
- accounts.json: 계정/세션 정보 전용 유지 / crawl_urls: Airtable Crawl_Targets 단일 소스 (260619)
- heartbeat_monitor.py 신규 추가 (b2aa30d) — watchdog.ps1과 독립된 Task Scheduler 기반(5분 주기) heartbeat 정지 감지 + Slack 알림
- ERR-052/FP-039/INC-029: 250723 참조 활성 Task 2건(SNS_AUTO_PRODUCTION/SNS_Auto_Run) 발견 → Disable-ScheduledTask로 비활성화 완료
- ERR-053/FP-040: heartbeat_monitor.py 예약 작업이 WakeToRun=False로 Modern Standby 중 71회(5시간47분) 미실행 근본원인 확정 → WakeToRun=True로 변경 완료(260710), 실제 절전 구간 재현 검증은 다음 세션 대기
- INC-028 Note 3: 1차 다운(20:09:40)의 실제 원인 확정 — Modern Standby 아님, 실제 OS shutdown(StartMenuExperienceHost.exe 명의, 20:09:52 개시). 사람의 조작 가능성 Hypothesis(확정 아님)
- PENDING-A(docs/PENDING_INVESTIGATIONS.md 신규): watchdog/heartbeat_monitor NSSM 전환 검토 — AdsPower Local API의 Session 0(S4U) 응답성 실증 SUCCESS 확인, 실제 전환 여부는 별도 결정 대기
- CLAUDE.md governance 2건 추가: "승인 범위 명시 원칙"(read-only 조사 승인이 문서기록/commit까지 자동 포함하지 않음), "단계별 Bookending 원칙"(작업 전/후 상태 한 줄 확인)

## 미해결 항목 (Phase 후순위)
- **[P0 — 다음 세션]** Instagram_Posts.execution_owner 필드 Airtable 추가
- **[P0 — 다음 세션]** APScheduler 조회 조건 수정: post_status=ready AND execution_owner 없음
- **[P0 — 다음 세션]** /api/v1/instagram/publish Endpoint 구현 (modules/sns/instagram_publish_api.py)
- **[P0 — 다음 세션]** DRY_RUN 검증 (PUBLISH_API_DRY_RUN=true → false 전환)
- **[P0 — 다음 세션]** 테스트용 Record 1건 생성 후 실제 게시 Runtime Proof
- 그룹 610113703703488: div[role='feed'] 미탐지 — 가입 승인 대기 중 (코드 문제 아님)
- LOST_DRY_RUN=false 전환 대기 — 실운영 전 Airtable 필드 확인 후 적용
- 워터마크 제외 로직 — **260616 부분 구현** (_IMAGE_BLOCK_KEYWORDS + Supplier_Blocklist 등록), passes_image_filter 이미지 픽셀 분석 미구현
- data/processed_comment_ids.json untracked 유지 (정상 — gitignore 대상)
- 백업 필요 시점 도달 (마지막 백업: backup_(12)_260602_2207)
- ~~**[P1 — 다음 세션]** 도매꾹(domeggook) 크롤러 추가~~ → **완료**(260619 세션2~8, D001/D002 Active 실운영 중, dome_crawl/dome_export APScheduler 잡 정상 — 이 목록 자체가 오래 미정리된 상태였음)
- **[P1 — 다음 세션]** heartbeat_monitor.py WakeToRun=True 변경 후 실제 Modern Standby 구간에서 로그가 이어지는지 실증 검증 대기 (유일하게 남은 절전 관련 미검증 항목)
- ~~**[P1 — 다음 세션]** watchdog.ps1 자체의 절전/1차다운 근본 메커니즘 여전히 UNKNOWN~~ → **260711 구조적 해소**: watchdog.ps1을 Task Scheduler 기반에서 NSSM Windows 서비스로 전환, 크래시 재시작+재부팅 실증 PASS(ERR-057/058, PENDING-A 종결) — Task Scheduler 고유 결함(WakeToRun 등) 자체가 더 이상 해당 없음
- ~~**[P1]** ERR-047 핵심 증상(재부팅 후 SNS_Watchdog_AutoStart 무재실행) 자체는 여전히 미해결(OPEN)~~ → **260711 해소**(위와 동일 사유, 구조 자체 교체)
- **[P2]** ERR-051/FP-038 Task Scheduler launch-only 실패 근본원인 미확정 (watchdog.ps1은 더 이상 Task Scheduler 아니므로 영향 범위 축소, 다른 Task 대상 잔존 여부만 저위험으로 남음)
- ~~**[P2]** PENDING-A(NSSM 전환) 최종 결정 — 사용자 승인 필요~~ → **260711 완전 종결**(ERR-057/058 참조)
- ~~**[P2 — 신규]** n8n(PID 10248 등) watchdog.ps1이 계속 재시작 시도·실패하며 알림만 반복 발생~~ → **260715 근본원인 확인**(ERR-065/FP-049/INC-037): LocalSystem 전환 후 npx 대화형 설치 프롬프트에서 좀비 프로세스 발생 가설(미확정), 성공 0건·실패 5,298건+ 누적. **Fix 미적용** — 회장 방침: 안정화 우선, n8n은 나중에 진행+설계(WF-01~05) 재검토 예정
- ~~**[P0-1 → ERR-066, OPEN]** `dm_receiver.send_telegram()` IGSID·원문 무마스킹~~ → **260715 RESOLVED**(패키지 A1): `_mask_igsid()`/`_telegram_preview()` 재사용 적용 + DM 수신 로그 원문 완전 제거, Runtime Proof로 마스킹 확인, pytest 30 passed
- ~~**[FP-047, OPEN, 재확인 260715]** 댓글 Airtable 기록(`_record_comment()`) 실패 시 예외를 삼키고 무조건 캐시에 처리완료로 남겨 재시도 없이 영구 유실~~ → **260715~716 코드 구현 완료**(커밋 `00466a3`): `comment_event_store.py` fencing claim + retry_queue 위임으로 근본 수정. `COMMENT_EVENT_STORE_MODE=disabled`(기본값)로 커밋 — enforce 전환 전 필수 항목이던 원문 평문 저장/Airtable preflight는 **260716~17 A+B로 완료**(아래 항목).
- ~~**[enforce 전환 전 필수 A+B, OPEN]** 댓글 원문 평문 저장(ERR-066과 같은 클래스), Airtable 필드 존재 startup preflight 미구현~~ → **260716~17 코드 구현 완료**: A(커밋 `ab3c25d`, PII 마스킹+retry payload 암호화), B(커밋 `d456102`, `verify_field_exists()` startup preflight). **`COMMENT_EVENT_STORE_MODE`/`COMMENT_POLL_ALLOWLIST_MODE` 운영 모드 전환(enforce/allowlist)은 여전히 미실행 — 별도 승인 대상으로 남음.**
- **[ERR-069/FP-050/INC-038, 코드 구현 완료·운영 미전환]** "최근 게시물 N개" 폴링 한도로 캠페인 댓글이 시스템 진입 자체를 못 하던 결함(실사용자 테스트로 발견) — Package 1(Phase A, 커밋 `eb98741`)로 근본 수정. `COMMENT_POLL_ALLOWLIST_MODE=legacy`(기본값)로 커밋 — **이 결함을 만든 "최근 N개" 방식이 여전히 운영 중**이라, allowlist 모드 전환 전까지는 동일 누락이 재발할 수 있음을 인지할 것. **Phase B(allowlist 전환·6개 media 순차 baseline) 자체는 아직 착수 안 함 — 별도 세션·별도 승인 대상.**
- ~~**[신규, 미커밋]** `modules/comment/comment_auto_reply.py`의 가격 키워드 확대(스팸/부정 제외 전부 응답 대상, 260715 회장 지시) + 쿨다운 0h·일일예산 사실상 무제한~~ → **260716 커밋 완료**(`210f72b`, 스팸/부정 필터 강화와 함께 커밋됨).
- **[ERR-064/FP-048/INC-036, OPEN — 부분 완화]** 앱 테스터 미등록 실계정과의 DM 왕복 시 손님 답장 웹훅 미도착(Standard Access 의심, 미확정) — Meta App Review 4개 권한 신청 260716 재확인 기준 "검토 진행 중"(최대 20일 소요, 여전히 미결론). **ManyChat 병행 전략 확정 + kbeautiquewholesale 1개 계정 실운영 Canary 성공**(Advanced Access라 이 문제 자체가 없음) — 완전한 대체는 아니지만 리스크 완화 경로 확보됨. Meta 심사 결과는 **다음 세션 시작 시에도 계속 확인 필요**.
- ~~**[ERR-063]** `test_dm_rules.py` hang, 원인 UNKNOWN~~ → **260715 RESOLVED**: 실제 Gemini API 호출(`generate_reply()`)을 mock하지 않은 테스트 설계 누락 확인, 7.48초 재현 실증. 테스트에 mock 추가하는 실제 수정은 미착수(기록만)
- ~~**[ERR-071/FP-052, OPEN]** 신규~~ → **260716 RESOLVED**: `comment_safety_guard.COOLDOWN_HOURS` 모듈 상수가 실제 `.env` 값에 고정되던 테스트 격리 버그, 커밋 `e70f733`로 해결.
- **[신규, 260717]** DM_RELAY_COMMERCE_RFC 설계 변경(불변조건 #7 폐기→웜 핸드오프) — **파일 본문 미반영, 다음 세션 최우선 작업**. 불변조건 #1과의 충돌 가능성 재검토 필요.
- **[신규, 260717]** ManyChat kbeautiquewholesale `View Details` 링크 — 아직 `ubk.com` 플레이스홀더, Shopify 결제 연동 완료 후 회장 직접 교체 예정(코드/승인 불필요, 순수 운영 작업).

## 절대 금지
- 250723 삭제/dead 판정
- 폴더 merge/전체 복사
- Evidence 없는 완료 선언
- 코드 수정 (승인 전)
- git add/commit 선행
- PowerShell Set-Content -Encoding UTF8 로 JSON 파일 저장 (BOM 삽입됨 — [System.IO.File]::WriteAllText + UTF8Encoding(false) 사용)

## [260528_Virtual_AutoReply_Proof] — 2026-05-28 13:27 KST
- Infra: Flask :5000 PID 14256 + ngrok :4040 PID 8956 LISTENING 확인
- Webhook: 로컬 POST 200 OK 확인
- Parser: 단가 얼마예요? detect_price_inquiry=True 확인
- AutoReply: DEFAULT_BASE_PRICE=50000 적용, handle_price_inquiry 완료
- Airtable: LI-2B0A72F7 생성, recXgM9FlDo9EEikr qualified/auto_replied
- IG 발송 실패: TEST_SENDER_004 가상 ID 정상 예상 결과
- 백업: backup_(7)_260528_1338 완료

## [260528_Real_DM_AutoReply_Proof] — 2026-05-28 20:14 KST
- 실계정 IGSID: 1792783944739953
- IG DM 발송 완료: 20:14:37 msg_id 확인 (recKh3tm6R5foxjjv)
- Lead 상태: qualified / auto_replied
- Telegram 알림: 성공 (1회 ConnectionReset 후 복구)

## [260528_Duplicate_Bug_Fix] — 2026-05-28 21:42 KST
- 버그1: _rule.reason AttributeError → getattr(_rule, "reason", "unknown") 수정
- 버그2: 중복 발송 → _has_recent_auto_replied() 추가 (CREATED_TIME() 기준 3분 window)
- 검증: 21:42:15 duplicate skip recvpUz9Q6YW4EsPv ✅
- 검증: 21:50:03 duplicate skip recKeIWfh5YtBLhzo ✅
- 수정 파일: modules/dm/dm_auto_reply.py ✅ 72e0e1a 커밋 완료

## [260529_Crawler_Normalization] — 2026-05-29 KST
- ERR-027: accounts.json `[]` → crawl_urls skip → account1 등록으로 해소 (7ce335e)
- ERR-028: Airtable caption 필드 없음 → 422 → UI에서 Long text 필드 추가로 해소
- 검증: 19:43:40 `계정 완료 | account=account1 | 3개` ✅
- 검증: 20:13:41 `계정 완료 | account=account1 | 3개` ✅

## [260601~260602_Clone_Mode_Proof] — 2026-06-02 01:08 KST
- Phase 1: replace_contacts() 매핑 추가 (c8000ee)
- Phase 2: generate_caption_clone() 추가 (3ed3b45)
- Phase 3: facebook_crawler clone 경로 연결 (b059740)
- Phase 4: keyword filter 확장 + BRAND_ALLOWLIST (25c3f13)
- Phase 5: comment auto-reply 안전장치 COMMENT_AUTO_REPLY_ENABLED=false (a64b0ff)
- Phase 6: expand_see_more() 추가 + Runtime Proof (deec24c)
- Runtime Proof: recsmA4WIlrur1wHO — original_text / converted_text / caption / media_type=image 전부 저장 확인 ✅
- 백업: C:\backup_(11)_260602_0108_SNS_24AutoProject_260511.zip

## [260602_섹션19_Instagram_Upload_Runtime_Proof] — 2026-06-02 16:20 KST
- 업로드 체인 분석: bot_uploader→insta_uploader dead stub 확인, 실제 업로더=launcher/main.py:159
- 환경변수 이슈: 시스템 AIRTABLE_API_KEY 플레이스홀더 → latin-1 UnicodeEncodeError → User scope 삭제 해소
- find_dotenv() 탐색 실패 원인 확인: temp 경로 실행 시 발생 — 절대경로 load_dotenv 사용으로 우회
- ERR-037 해소: caption Facebook UI 잔여물(작성자명·경과시간··) → clean_fb_metadata() 추가 (349fedf)
- Airtable ready 레코드 2건 caption 일괄 정정 완료
- **Graph API 업로드 성공 증거:**
  - 대상: recFyw7OUaZ666JDJ
  - 이미지: 960×1707 ratio=0.56 → imgbb center-crop → https://i.ibb.co/dwnMVq7Z/2547998023eb.jpg
  - /media id: 17889472404540095
  - /media_publish id (ig_media_id): **18101360630320704** ✅
  - Airtable post_status: ready → uploading → **posted** ✅

## [260602_섹션19_Clone_Mode_그룹URL_다중화] — 2026-06-02 13:40 KST
- crawl_urls 1개 → 4개 그룹 확장 (3dbe72a)
  - 1676627532598134 (K-beauty 필리핀 중고 그룹)
  - 610113703703488 (feed 셀렉터 실패 — 가입 승인 대기)
  - 345179878828208 (기존 그룹, Airtable 저장 확인 ✅)
  - 755455243345993 (신규 그룹)
- accounts.json BOM 제거 (c6a30d1) — PowerShell Set-Content UTF8 BOM 삽입 버그 수정
- facebook_crawler.py load_dotenv(override=True) 추가 (f5d59f2) — 모듈 직접 실행 시 .env 로드 보장
- Airtable 저장 성공 재확인: 그룹 345179878828208 → [AIRTABLE] 저장 완료 ✅
- pytest 104 passed / 1 xfailed / 2 xpassed ✅
- deep-translator 1.11.4 pip install 완료
- 백업 필요 시점 도달 (다음 세션 초반 백업 권장)

## [260612_운영정비] — 2026-06-12 00:26 KST
- Supplier_Blocklist 실차단 적용 (11fc204) — DRY_RUN 로그 제거, 매칭 시 continue로 실제 skip
- LOST 72h 타임아웃 구현 (0e5133b) — followup3_sent + 72h 경과 → LOST 자동 전환, DRY_RUN 모드
  - 실운영 전환 조건: .env LOST_DRY_RUN=false 설정
- Lead_Interactions 필드 추가: lost_reason(Single line) / lost_at(Date) / disqualified(Checkbox)
- filter_rules.json + generate_filter_rules.py (3840a6a) — Crawl_Training_Set 기반 분석 전용, 운영 연동 금지
- FB그룹 1676627532598134 제거 (c71f2c7) — Crawl_Targets 레코드 삭제 + accounts.json crawl_urls 제거
  - 사유: 인도 트래픽 비율 높음, K-beauty 타겟 부적합
  - crawl_urls 5개 → 5개 유지 (610113703703488 Hold 포함)
- Instagram_Posts.caption 필드 재추가 — API로 multilineText 추가 (fldcxTzLzYCzD9aYe), 422 오류 해소
  - 원인: 260529 UI 추가 후 어느 시점 삭제됨
- ig_media_id 17863634121631171 클리어 (rectwruMD3uua54sv) — engagement_tracker 30분 간격 반복 오류 해소
- launcher/main.py 기동 확인 (00:26 KST) — Flask :5000 / APScheduler 8잡 / RetryQueue 정상
  - AdsPower 미실행으로 FB 크롤링 WinError 10061 (AdsPower 기동 후 자동 복구)
- upload_rate 6.2% — caption 필드 복구로 다음 크롤링부터 ready 레코드 누적 회복 예상
- 최신 커밋: 0688849 / GitHub push 완료

## [260616_운영정비_2차] — 2026-06-16 23:00 KST
- M&Y GLOBAL 워터마크 공급자 차단:
  - Supplier_Blocklist 등록: author_name=Mooncher Kim / page_name=M&Y GLOBAL / reason_code=BLOCK_WATERMARK_SUPPLIER (recEDhkour93vZR74)
  - content_filter._IMAGE_BLOCK_KEYWORDS에 `r'm&y\s*global'` 추가 (a126754)
- `facebook_crawler.py`에 `clean_fb_metadata()` 호출 추가 (0688849):
  - raw_text 추출 직후 L202에서 clean_fb_metadata(raw_text) 호출
  - 작성자명·경과시간·구분점(·) 제거 후 필터링 → 오탐 방지
  - import L14에 clean_fb_metadata 추가
- `modules/sns/image_hosting.py` 신규 생성 (BOM없음, 54줄):
  - upload_to_imgbb(source_url) — imgbb API 래퍼
  - MIME 검증 / 32MB 제한 / SHA256 content_hash / HEAD 공개 URL 검증
  - 향후 launcher/main.py _preprocess_image() 대체 후보
- Blocklist 로드 완료: 5건 (M&Y GLOBAL 추가 후 확인)
- Regine Kim 포스트 A-F3-260616-001 업로드 성공 → posted 확인 ✅
- 런처 재기동: 23:00 KST (clean_fb_metadata 적용 버전)

## [260616_버그수정] — 2026-06-16 02:07 KST
- post_status 옵션 소실 (ready/uploading 없음) → Airtable Meta API PATCH 422 → typecast:True 더미 레코드 방식으로 강제 복구
  - 복구 후 옵션 목록: ['draft', 'scheduled', 'posted', 'failed', 'ready', 'uploading'] ✅
- uploading 고착 28건 일괄 마킹:
  - 원인①: FB CDN 동일 이미지를 다른 노드(fhan15-2, fdad3-8, fhan5-6)로 서빙 → URL 해시 달라 중복 28건 저장
  - 원인②: Graph API 업로드 실패 후 retry_count UNKNOWN_FIELD_NAME 예외 → uploading 고착
  - 조치: 28건 전체 post_status=failed PATCH 완료 (200 OK)
- retry_count/last_error_msg 필드 제거 (463c350):
  - launcher/main.py 성공/실패 경로 양쪽에서 두 필드 참조 제거
  - 실패 에러 내용은 logger.error로 직접 출력으로 대체
- image_url_hash 개선 (25c6779):
  - Before: `hashlib.sha256(image_url.encode())` — CDN 노드 다르면 다른 해시
  - After: `re.search(r"/(\d+_\d+(?:_\d+)*)[_.]", image_url)` → FB 미디어 ID 추출 후 해시
  - 검증: 3개 CDN URL → 동일 미디어 ID → 동일 해시 ✅
- import re 추가 (366c617): facebook_crawler.py 상단 `import re` 누락 수정
- Instagram 업로드 성공 증거:
  - 대상: recw3EHD8d9uiP2FX
  - /media_publish id (ig_media_id): **18122871268709171** ✅
  - Airtable post_status: ready → uploading → **posted** ✅
- 최신 커밋: 366c617 / GitHub push 완료
## [260617] Airtable Account DB 구축 완료

### 변경사항
- Account_Registry 필드 추가: identity_id / category / automation_enabled / pilot_wave / identity_status / adspower_profile_id
- 유효 계정 33개 확정 (중복/빈행 정리 완료)
- Platform_Accounts 테이블 신규 생성 (tblkdk5dEagfQvUMp)
- Instagram 19개 + Facebook 12개 = 31개 입력
- Instagram_Posts 라우팅 필드 추가: target_identity_id / target_platform_account_id / publish_status / run_id / scheduled_at
- Account_Registry <-> Platform_Accounts Linked Record 연결 (fldcRdC6XdGnMILqI)
- Pilot 3개 Active: IDN-000036(nguyenknv15) / IDN-000038(nhm880808) / IDN-000016(kang88jungmin)

### Airtable 현재 상태
- Base ID: apphJNTHWNoFcVb1D
- Account_Registry: 33개 (Active 3 / Ready 30)
- Platform_Accounts: 31개

### 다음 단계
- n8n 워크플로우 설계 (별도 세션)
- Pilot 3개 Runtime 포스팅 검증
- 3 -> 10 -> 33개 확장


## [260617] ImgBB 연동 + 데이터 정합성 복구 세션

### 완료 작업
1. Dashboard 복구 — Flask :5000 / Streamlit :8501 / watchdog 정상 기동
2. Instagram 업로드 실패 원인 확정 — Facebook CDN URL -> Instagram Graph API error_subcode 2207052
3. imgbb 연동 (Phase 1~4)
   - original_image_url 필드 추가 (fldEpMV0uFiWR7OmB)
   - IMGBB_API_KEY .env 추가
   - modules/sns/image_hosting.py 신규 생성
   - tools/backfill_failed_images.py 신규 생성 (DRY_RUN=true 기본값)
4. Backfill 1건 End-to-End 실증 — rec2v96YaBLQJvLyl: failed->ready->posted (ig_media_id: 18071004683495931)
5. 데이터 정합성 복구
   - ig_media_id 있는 failed 78건 Graph API 검증
   - VERIFIED_POSTED 3건 -> posted 복구
   - INVALID 75건 -> ig_media_id 클리어
6. 버그 수정 — launcher/main.py: unverified ig_media_id -> posted 강제전환 제거 (commit e33cf37)
7. Phase 4 — facebook_crawler.py save_to_airtable()에 imgbb 업로드 연동 (commit af85d3a)

### 현재 Airtable 상태
- failed: 145건 / posted: 14건 / ready: 0건
- 성공률: 6.2% -> 8.2% 개선

### Git 커밋 (260617 세션)
- e33cf37: fix: prevent unverified ig_media_id from forcing posted status
- 3b3fedf: feat: add ImgBB image hosting adapter
- 6ab2ff0: feat: add guarded failed-image backfill utility
- af85d3a: feat: integrate ImgBB upload in save_to_airtable (Phase4)

### 미완료
- Runtime Proof: 신규 크롤링 1건 ImgBB 성공 로그 확인 (진행 중)
- failed 145건 backfill (Phase 3 보류)
- push 미실행 (별도 승인 필요)
- 안정화 후 API 키 재발급 필요 (AIRTABLE/INSTA/GEMINI/TELEGRAM/SLACK/IMGBB)

## [260617_n8n설계_publish_single분리] — 2026-06-17 KST

### publish_single() 분리 (9d65cb4)
- launcher/main.py 게시 로직을 publish_single() 독립 함수로 분리
- _job_insta_upload(): uploading 마킹 후 publish_single() 1줄 위임
- n8n Endpoint와 APScheduler 공통 호출 가능 구조 확보
- Token/ig_user_id 호출자 주입, 함수 내 저장소 참조 없음, 로그 access_token 출력 금지
- Runtime Proof: NOT_EXECUTED (260617 기준 ready 레코드 0건)

### last_error_msg L191 잔존 참조 제거 (20bef95)
- launcher/main.py L191 image_url 없음 조기 실패 경로에서 last_error_msg 제거
- ERR-041 완전 해소

### n8n Architecture 설계 확정 (DESIGN_COMPLETE)
- WF-01: Posting Scheduler — Airtable ready 레코드 폴링 → /api/v1/instagram/publish 호출
- WF-02: Real-time DM Webhook — Meta Webhook → Python dm_receiver 처리
- WF-03: Credential Health Check — 계정 토큰 주기적 검증
- WF-04: Failure/Recovery Watchdog — failed 레코드 재시도 조율
- WF-05: Runtime Alert — 오류/비정상 감지 → Slack 알림
- Credential 구조 Option B 확정: Python Graph API Token 소유 (.env CRED_{ref}_TOKEN), n8n Token 비보유
- Canonical Status: post_status 단일 (publish_status 신규 필드 미사용)

### P0 Backlog (다음 세션)
1. Instagram_Posts.execution_owner 필드 Airtable 추가
2. APScheduler _job_insta_upload() 조회 조건 수정
3. modules/sns/instagram_publish_api.py — /api/v1/instagram/publish Blueprint 구현
4. dm_receiver.py Blueprint 등록
5. PUBLISH_API_DRY_RUN=true 검증 → false 전환
6. 테스트용 Record 1건 생성 → 실제 게시 Runtime Proof

## [260619_Airtable_crawl_urls_전환] — 2026-06-19 KST

### 완료 작업
1. FB_MAX_POSTS=20 .env 설정 완료
2. Crawl_Targets 스키마 확장: platform(singleSelect)/max_posts(number)/account_ref(singleLineText)/last_run_at(dateTime)/last_result(singleLineText) 필드 추가 (Airtable Metadata API)
3. account_manager.py _load_crawl_urls_from_airtable() + _shadow_compare() 추가
4. CRAWL_TARGET_SOURCE Feature Flag 구현: accounts_json(기본) / shadow(비교 로그) / airtable(URL 교체)
5. Shadow 모드 검증: accounts.json=5건 / Airtable=4건 / 누락 그룹(610113703703488 Hold) 정상 감지
6. CRAWL_TARGET_SOURCE=airtable 전환 — Airtable 4건 URL 기반 크롤링 Runtime Proof 완료
   - groups/1827528710833477 → 1건 수집 (720×1280, imgbb 중복 skip 정상)
7. accounts.json → 계정/세션 정보 전용 유지 / crawl_urls → Airtable Crawl_Targets 단일 소스

### Git
- 커밋: 9cc4ee9 (feat: CRAWL_TARGET_SOURCE Feature Flag — Airtable crawl_urls 동적 로드 [260619])
- push: origin/master 완료

### 다음 세션 예정
- 도매꾹(domeggook) 크롤러 추가 — Crawl_Targets platform=domeggook 지원

## [260619_도매꾹크롤러] — 2026-06-19 KST (세션2)

### 완료 작업
1. 도매꾹 Open API 개통 확인 (ver=4.1, aid=DOMEGGOOK_API_KEY, om=json)
2. modules/crawlers/ 패키지 신설
   - base_connector.py — BaseCrawlConnector ABC + ConnectorError
   - domeggook_api_connector.py — DomeggookApiConnector (health_check/fetch/normalize)
   - quality_gate.py — READY/ERROR/FILTERED 판정 (fixture 5/5 PASS)
3. Crawl_Targets keyword 필드 추가 (fldNhkqfOJvkCZZnp)
4. D001 레코드 Hold 등록 (recg8JU3eqL9BkMgf) — category_code 제외 (singleSelect 선택지 미등록)
5. commit 2112739 push 완료

### Known Facts
- DomeggookApiConnector.fetch(kw=화장품, max_posts=10) = 10건 정규화 성공
- NormalizedItem Contract v1.0 확정
- Crawl_Targets category_code 선택지: A/B/C/D (BEAUTY 추가 시 Airtable UI에서 직접)
- API 키 파라미터: aid= (key= 아님), mode=getItemList, ver=4.1

### P0 Backlog (다음 세션)
1. Dispatcher 연결 — APScheduler에 domeggook job 추가
2. platform=domeggook 레코드 조회 → fetch() → Gate → Source_Items 저장
3. D001 Hold → Active 전환 전 Runtime Proof 필수
4. Source_Items Airtable 테이블 설계 및 생성

### 절대 금지 (다음 세션 전)
- D001 Active 전환 금지 (Runtime Proof 전)
- 전체 2,743건 수집 금지
- FB/Instagram 코드 수정 금지

## [260619_세션3_Source_Items] — 2026-06-19 KST

### 완료 작업
1. adultOnly 파싱 버그 수정 (str->bool, f6bef6a)
2. Source_Items 테이블 생성 (tblMWJaInVHS7YfY6, 17개 필드)
3. STAGING WRITE TEST 4/4 PASS
   - 1차: INSERT=10 / 2차: SKIP=10 / 3차: UPDATE=1 / 4차: SKIP=10(복구확인)
4. D001 Hold 유지 확인
5. 절차 위반 기록: STAGING WRITE TEST 전 BOM/diff 5개 조건 Claude Code 자체 진행

### Known Facts
- Source_Items 10건 저장 (화장품 키워드, READY)
- pipeline_status=NEW, quality_status=READY 정상
- FILTERED/ERROR 항목 pipeline_status 비움 확인
- D001 recoNRhWSKTiwNeuv Hold 유지
- tools/ 임시 스크립트 untracked (commit 대상 아님)

### P0 Backlog (다음 세션)
1. _job_dome_crawl() 구현 — launcher/main.py APScheduler 등록
2. Dispatcher read-only 재확인 후 DRY_RUN
3. Scheduler 수동 1회 실행
4. D001 Hold 상태 Runtime Proof 후 Active 전환 검토
5. C003 platform=daisomall 수정 (Dispatcher 확대 전 필수)

### 절대 금지 (다음 세션 전)
- D001 Active 전환 금지
- Instagram_Posts 저장 금지
- 전체 2,743건 수집 금지
- FB/Instagram 코드 수정 금지
- Dispatcher 미승인 연결 금지

## [260619_세션4_Dispatcher] — 2026-06-19 KST

### 완료 작업
1. _job_dome_crawl() 구현 + APScheduler 등록 (d1ca290)
2. DRY_RUN: D001 Hold → Active 타겟 없음 스킵 확인
3. D001 Active 전환 → fetch=10 ready=10 Runtime Proof
4. Source_Items Upsert 정상 (중복 없음)
5. max_posts 상한 min(value, 10) 강제 적용
6. D001 Hold 복구 확인

### Known Facts
- dome_crawl job: interval 60분, next_run offset 80초
- D001 Hold 상태 — 실운영 전 별도 Active 전환 승인 필요
- Source_Items 11건 (STAGING + Runtime Proof 누적)
- C003 platform=daisomall 수정 미완료 — 다음 세션

### P0 Backlog (다음 세션)
1. C003 platform=daisomall 수정
2. D001 실운영 Active 전환 승인 후 24시간 모니터링
3. Source_Items → Instagram_Posts Export 파이프라인 설계
4. 건강식품 등 카테고리 확장 (D002 추가)

## [260619_세션5_실운영전환] — 2026-06-19 KST

### 완료 작업
1. C003 platform=daisomall 수정 완료
2. D001 Active 전환
3. launcher 재시작 → dome_crawl job 등록 확인
4. 16:47:28 자동 실행 → fetch=10 ready=10 Upsert 성공
5. 다음 실행 17:47:28 (60분 interval) 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중
- D001 Active (recoNRhWSKTiwNeuv)
- C003 platform=daisomall (Hold 유지)
- Source_Items 누적 중 (11건+)
- watchdog.ps1 백그라운드 유지

### P0 Backlog (다음 세션)
1. Source_Items → Instagram_Posts Export 파이프라인 설계
2. 건강식품 D002 추가
3. 24시간 후 Source_Items 누적 건수 확인

## [260619_세션6_ExportPipeline] — 2026-06-19 KST

### 완료 작업
1. Source_Items 필드 4개 추가 (export_retry_count/last_error/next_retry_at/started_at)
2. Instagram_Posts source_item_id 필드 추가
3. source_exporter.py 구현 + Runtime Proof (d3b6003)
   - DRY_RUN 3건 확인
   - Export 1건 성공 (domeggook:55808288)
   - 중복 재실행 exported=0 확인
4. _job_dome_export() + APScheduler 10분 interval 등록 (4bf6e74)
   - Runtime Proof exported=2 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중
- dome_export: 10분 interval 실운영 중
- D001 Active
- Source_Items → Instagram_Posts 파이프라인 완성
- STALE_QUEUED 30분 복구 로직 포함
- retry/backoff: 10분/60분/300분

### P0 Backlog (다음 세션)
1. 건강식품 D002 추가
2. 24시간 후 Source_Items/Instagram_Posts 누적 확인
3. launcher 재시작 (watchdog 통해 dome_export job 자동 등록 확인)
## [260619_세션7_실운영확인] — 2026-06-19 KST

### 완료 작업
1. launcher 재시작 → dome_crawl + dome_export 자동 등록 확인
2. D002 건강식품 Hold 등록 (recuRdoKY0KDiV7Ci)
3. 24시간 누적 확인:
   - Source_Items 21건 (EXPORTED=4 / NEW=17)
   - Instagram_Posts 도매꾹 출처 3건
   - dome_crawl 60분 / dome_export 10분 자동 실행 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중 (D001 Active)
- dome_export: 10분 interval 실운영 중
- D002 Hold (건강식품) — 다음 세션 Active 전환 검토
- Source_Items 누적 중 (10건/회)

### P0 Backlog (다음 세션)
1. D002 건강식품 Active 전환 → Runtime Proof
2. source_item_id 기준 export_to_instagram_posts target_id 확장
3. Instagram_Posts 도매꾹 출처 게시물 품질 확인

## [260622_API_Usage_Logging] — 2026-06-22 KST

### 완료 작업
1. Airtable Team 플랜 업그레이드 완료
2. Lily Yoon Supplier_Blocklist 등록 (recTMGb5XHgT8qjKJ)
   - author_name: Lily Yoon / reason_code: WATERMARK_TAG_OVERLAY
   - 근거: Crawl_Training_Set 3건 decision=BLOCK / has_watermark=True 확인
3. Instagram_Posts 160번 레코드 rejected 처리
4. modules/infra/ 패키지 신설
   - airtable_usage_logger.py — API 호출 카운트 / logs/airtable_usage.jsonl 날짜별 누적 / get_monthly_count() / 100,000회 초과 Telegram 경고
5. log_api_call() 12개 포인트 연결
   - airtable_bridge.py: fetch_ready_one(GET) / update_record(PATCH)
   - facebook_crawler.py: Supplier_Blocklist(GET) / Instagram_Posts(GET·POST)
   - launcher/main.py: Crawl_Targets(GET) / Source_Items(GET·PATCH·POST) / Instagram_Posts(GET·PATCH×3)

### Known Facts
- Airtable Usage 월 누적: 3회 (2026-06 기준, 테스트 포함)
- logs/airtable_usage.jsonl 정상 생성 확인
- content_filter.py: Airtable 직접 호출 없음 (연결 대상 아님)

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 안정성 모니터링

## [260619_세션8_D002확장] — 2026-06-19 KST

### 완료 작업
1. D002 건강식품 Active 전환
2. dome_crawl D001+D002 동시 fetch=10+10 Runtime Proof
3. _job_dome_export() target_id=None / batch_size=5 확장 (7fdd9d1)
4. exported=3 (D001+D002 혼합) Gemini caption 3건 성공

### Known Facts
- dome_crawl: D001(화장품)+D002(건강식품) Active 실운영
- dome_export: target_id=None 전체 대상 / batch_size=5
- Source_Items 누적 중
- Instagram_Posts 도매꾹 출처 증가 중

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 안정성 모니터링

## [260623_FB_Crawler_HUNG_해소] — 2026-06-23 14:17 KST

### Root Cause 4개 해소

| 커밋 | 분류 | 내용 |
|---|---|---|
| e648ce3 | feat | Stage Log (JOB_START/ADSPOWER/DRIVER/PAGE_GET/CRAWL/CLEANUP) + timeout hardening |
| f9b9483 | fix | SSL handshake timeout: socket.setdefaulttimeout + urllib3 adapter (효과 없음 → 다음 커밋으로 대체) |
| 1082d11 | fix | daemon thread + join(timeout=12): Windows SSL hang 포함 wall-clock 강제 종료 |
| 0878c68 | fix | **threading.Lock → RLock** — log_api_call()→get_monthly_count() 중첩 획득 deadlock 해소 (핵심 원인) |
| 56b09d1 | fix | RemoteConnection.set_timeout() 제거 — _client_config AttributeError (_job_fb_crawl 크롤링 실패) |

### Stage Log 전구간 확인 (Scheduler 자동 실행 14:17 KST)
```
JOB_START  elapsed=0.0s
Blocklist  6건 로드 완료
ADSPOWER   elapsed=1.3~1.4s
DRIVER     elapsed=2.5~4.0s  (WebDriver 연결 완료)
PAGE_GET   elapsed=16~24s
CRAWL      posts=2~3
CLEANUP    elapsed=25~32s
AdsPower Stop API 완료
→ 다음 URL 반복 (4개 URL 전체)
```

### Repository Interface (260622~260623)
- modules/infra/repository_interface.py — ABC (fetch_one/fetch_all/update/insert/delete)
- modules/infra/airtable_repository.py — AirtableRepository 구현체 (offset 페이지네이션, log_api_call 내장)
- 기존 airtable_bridge.py 수정 금지 (호환성 유지)
- **연결 0% — 기존 코드 수정 없음, Phase 2 대기**

### Known Facts
- airtable_usage_logger._lock: RLock으로 교체 완료 (재진입 안전)
- _job_fb_crawl 스케줄러 자동 실행: 14:17:51 KST (interval 30분)
- 다음 정기 실행: 16:47 KST
- scheduler_err.log에 STAGE 로그 기록됨 (app.log 동일 핸들러)
- fb_crawl 완료: {'account1': 1} — 1건 처리 (중복 이미지 skip 정상)
- pytesseract 없음 경고: 비치명적, 통과 처리

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 FB Crawler 안정성 모니터링
4. Repository Interface Phase 2 연결 계획 수립

## [260623_Repository_Interface_1차_연결] — 2026-06-23 KST

### 완료 작업

#### Phase 1 — Interface 설계 (758d29d)
- `modules/infra/repository_interface.py` 전면 교체
  - Enum: SourceItemStatus / InstagramPostStatus
  - TypedDict 6개: SupplierBlockEntry / SourceItemRef / SourceItem / InstagramPost / CrawlTarget / PostPublishResult
  - 예외 4개: RepositoryError / Unavailable / NotFound / Validation
  - ABC 메서드 10개: list_blocked_suppliers / exists_post_by_image_url / save_instagram_post / fetch_active_crawl_targets / find_source_item_by_hash / save_source_item / update_source_item_status / fetch_pending_posts / claim_post_for_upload / mark_post_result
- `modules/infra/airtable_repository.py` 전면 교체
  - 10개 메서드 Airtable HTTP 구현체
  - fields 언패킹 → TypedDict 변환
  - _raise() → RepositoryError 계층 변환
  - claim_post_for_upload: WARNING non-atomic, single-worker only
  - fetch_active_crawl_targets: filterByFormula `{status}='Active'` 단독 (platform 제한 제거)

#### Phase 2 — 직접 호출 교체 (c52e00b)
| 파일 | 교체 내용 |
|------|----------|
| `airtable_bridge.py` | fetch_ready_one / update_record dead code 제거 / import requests 제거 |
| `launcher/main.py` | _job_dome_crawl: Crawl_Targets GET → repo.fetch_active_crawl_targets() |
| `launcher/main.py` | _job_dome_crawl: Source_Items upsert → find_source_item_by_hash / save_source_item / update_source_item_status |
| `launcher/main.py` | _job_insta_upload: fetch_pending_posts / claim_post_for_upload / mark_post_result 연결 |
| `launcher/main.py` | publish_single: table.update 3개 제거, 순수 반환값 함수로 전환 |
| `facebook_crawler.py` | Instagram_Posts 중복체크 직접호출 → repo.exists_post_by_image_url() |

### Known Facts
- import 검증: AirtableRepository 10개 추상 메서드 전부 구현 확인 (python -c 검증)
- airtable_bridge.py: get_table() 유지 (Function Signature Lock) / fetch_ready_one, update_record 제거
- launcher/main.py: _req, BASE_ID, API_KEY 잔재 _job_dome_crawl 내부 전부 제거
- facebook_crawler.py: _api_key, _base_id, image_url_hash 계산 로직 Repository 내부로 이동
- 잔존 직접 호출: dm/, crm/, comment/, crawlers/source_exporter.py 등 16개 파일 — 다음 세션

### P0 Backlog (다음 세션)
1. DM 모듈 (dm_auto_reply / dm_followup_scheduler / dm_receiver) Repository 연결
2. CRM 모듈 (lead_scorer / lead_closer / order_detector / daily_report) Repository 연결
3. Comment 모듈 (comment_auto_reply / comment_poller) Repository 연결
4. source_exporter.py Repository 연결 (호출 11개 — 최대 규모)

## [260624_DM_CRM_Comment_Repository_연결] — 2026-06-24 KST

### 완료 작업

#### Interface 확장 (repository_interface.py)
- Enum 추가: LeadBridgeStatus (dm_received / auto_replied / followup1~3_sent / lost / closed / converted)
- TypedDict 추가: LeadInteraction (id / igsid / bridge_status / lead_status / lead_grade / relay_scheduled_at) / LeadInteractionCreate (igsid / source / interaction_type / occurred_at)
- 추상 메서드 12개 추가 (#11~#22): get_base_price / has_recent_auto_reply / create_lead_interaction / is_repeat_inquiry / fetch_leads_due / fetch_today_lead_stats / update_lead_replied / update_lead_score / update_followup_status / mark_lead_lost / mark_lead_closed / mark_lead_converted

#### AirtableRepository 구현 (airtable_repository.py)
- 12개 메서드 Airtable HTTP 구현 + _patch_lead_interaction() private helper
- fetch_today_lead_stats: lead_grade 필드 반환 추가

#### 직접 호출 교체 (10개 파일)
| 파일 | 교체 내용 | 직접 호출 |
|------|----------|----------|
| dm_auto_reply.py | _at_headers/_at_patch 제거 → has_recent_auto_reply / get_base_price / update_lead_replied | 3→0 |
| dm_receiver.py | _at_post/_gen_code 제거 → create_lead_interaction | 1→0 |
| dm_followup_scheduler.py | _at_get_due/lost/_at_patch 제거 → fetch_leads_due / update_followup_status / mark_lead_lost | 3→0 |
| comment_auto_reply.py | _record_comment 직접 POST → create_lead_interaction | 1→0 |
| lead_scorer.py | 직접 GET/PATCH → is_repeat_inquiry / update_lead_score | 2→0 |
| lead_closer.py | 직접 PATCH 2건 → mark_lead_closed | 2→0 |
| order_detector.py | 직접 PATCH 2건 → mark_lead_converted | 2→0 |
| daily_report.py | 직접 GET → fetch_today_lead_stats | 1→0 |
| repository_interface.py | LeadInteraction lead_grade 필드 추가 | — |
| airtable_repository.py | fetch_today_lead_stats lead_grade 반환 추가 | — |

### Known Facts
- DM/CRM/Comment 영역 Airtable 직접 호출 0건 검증 완료 (Grep 확인)
- "followup_error" 비표준 상태: LeadBridgeStatus 외부 → _patch_lead_interaction() private 직접 사용
- inquiry_message / comment_id / media_id: LeadInteractionCreate 미포함 데이터 갭 (허용)
- lead_grade (hot/warm/cold): LeadInteraction TypedDict 추가 후 fetch_today_lead_stats 반환에 포함
- BOM 체크 10개 파일 전부 OK

### 잔존 직접 호출 (다음 세션 대상)
| 파일 | 라인 | 테이블 |
|------|------|--------|
| modules/common/account_manager.py | L114 | Crawl_Targets GET |
| modules/common/airtable_autorun_engine.py | L19 | BASE_URL 상수 |
| modules/crawlers/source_exporter.py | L9 | BASE_URL 상수 (다수 호출) |
| modules/ingest/domeggook_ingest.py | L33 | TRAINING_TABLE POST |
| modules/sns/facebook_crawler.py | L44 | Supplier_Blocklist GET |

### P0 Backlog (다음 세션)
1. account_manager / airtable_autorun_engine / source_exporter / domeggook_ingest / facebook_crawler Repository 연결

## [260624_직접호출_완전교체] — 2026-06-24 KST

### 완료 작업

#### 잔존 4파일 Repository 교체 (df9df6b)
| 파일 | 변경 내용 |
|------|-----------|
| `account_manager.py` | `_load_crawl_urls_from_airtable()` — requests 제거 → `repo.fetch_active_crawl_targets()` + platform 필터 list comprehension |
| `facebook_crawler.py` | `load_supplier_blocklist()` — requests+threading+socket 제거 → `repo.list_blocked_suppliers()` / `socket` top-level import 제거 |
| `source_exporter.py` | 직접 호출 11건 전체 → Repository 교체. `BASE_URL/_headers()/_base()` 제거. 신규 메서드 4개(fetch_source_items_for_export / recover_stale_queued / claim_source_item_for_export / update_source_item_retry) 추가 |
| `domeggook_ingest.py` | Training 직접 호출 → `TrainingRepository.upsert_training_record()` |
| `training_repository.py` | 신규 생성 — Product_Training_Set 전용 (GET 중복확인 → PATCH/POST upsert) |
| `repository_interface.py` | `SourceItemStatus.QUEUED` 추가 / `SourceItem` 필드 확장 / 추상 메서드 4개 추가 (#23~#26) |
| `airtable_repository.py` | 메서드 23~26 구현 (서버사이드 filterByFormula 적용) |

#### save_to_airtable NameError 수정 (4502e65)
- `facebook_crawler.py` `save_to_airtable()` — `_req/_url/_hdrs/image_url_hash` 미정의 변수 NameError 수정
- `_req.post()` + `log_api_call()` → `repo.save_instagram_post(payload)` 교체
- `hashlib.sha256` 인라인 계산 추가
- `import logging` 인라인 3개 → `logger` 통일

#### airtable_bridge dead import 제거 (e0bcff6)
- `airtable_bridge.py` — `log_api_call` import 제거 (호출 없는 dead import)

#### inquiry_message 데이터 갭 해소 (36cbf05)
- `LeadInteractionCreate` — `inquiry_message: str` 필드 추가
- `create_lead_interaction()` — `fields["inquiry_message"]` Airtable 저장 추가
- `dm_receiver.py` — `record_interaction()` 호출 시 `inquiry_message=message_text` 전달
- `comment_auto_reply.py` — `_record_comment()` 호출 시 `inquiry_message=text` 전달
- 효과: dashboard.py 메시지 표시 / kpi_collector price/neg 집계 실데이터 기반 동작

### Infrastructure 외부 직접 호출 최종 검증
- `Select-String api.airtable.com` grep 결과 운영 코드 내 잔존:
  - `airtable_autorun_engine.py` 1건 — **dead 파일 확정** (import 없음, 250723 복사 산물)
  - `airtable_repository.py` / `training_repository.py` — infra 계층 허용
- **실질적 직접 호출 0건 확정**

### Known Facts
- `airtable_autorun_engine.py`: 250723 복사 파일, 어디서도 import 없음, dead 판정 (삭제 불필요)
- `domeggook_ingest.py` 중복 반환값 변경: duplicate → upsert 내부 처리 (PATCH), 카운터 집계 방식 변경
- `SourceItemStatus.QUEUED` 추가: source_exporter 내부 상태 전용

### P0 Backlog (다음 세션)
1. ~~Failure Injection Test~~ ✅ PASS (260624)
2. ~~Runtime Proof 5회 연속 정상~~ ✅ PASS (260624 19:50~21:50)

## [260624_검증완료] — 2026-06-24 KST

### Failure Injection Test
- 스크립트: `tools/_test_failure_injection.py`
- 주입 방식: `get_driver()` 몽키패치 → `page_load_timeout=3s` 강제 오버라이드
- 결과:
  - **finally cleanup PASS** — `[STAGE:CLEANUP]` 정상 실행 / `[AdsPower] Stop API 완료` 확인
  - **AdsPower Pre/Post=False** — Stop API 정상 호출 후 Inactive 확인
  - TimeoutException 미발생 — CDP-attach 모드(debuggerAddress)에서 `page_load_timeout` 미작동 (Facebook 초기 DOM 3초 내 complete 도달)
  - finally 경로 자체는 정상 보장 확인
- STAGE Log 전구간:
  ```
  JOB_START → ADSPOWER → DRIVER(timeout 3s 적용) → PAGE_GET(15.4s) → CRAWL(posts=2) → CLEANUP → AdsPower Stop API 완료
  ```

### Runtime Proof 5회 연속 정상 (19:50~21:50 KST)
- DM/댓글 수신 정상
- inquiry_message Airtable 저장 확인
- Repository Interface 전 계층 정상 동작

### Repository Interface 전체 작업 완료 요약
| 단계 | 커밋 | 내용 |
|------|------|------|
| DM/CRM/Comment 연결 | 18aa3a7 | 10개 파일 직접 호출 → Repository |
| 잔존 4파일 교체 | df9df6b | account_manager / facebook_crawler / source_exporter / domeggook_ingest |
| NameError 수정 | 4502e65 | facebook_crawler save_to_airtable |
| dead import 제거 | e0bcff6 | airtable_bridge log_api_call |
| inquiry_message 갭 | 36cbf05 | LeadInteractionCreate + dm/comment caller |
| docs 업데이트 | 90c971d | CURRENT_RUNTIME_CONTEXT |

### Known Facts
- Infrastructure 외부 직접 호출 실질적 0건 (airtable_autorun_engine.py dead 파일 제외)
- CDP-attach 모드 page_load_timeout 제한: debuggerAddress 연결 시 timeout 미작동 — 알려진 Selenium 제약
- TrainingRepository: Product_Training_Set 전용 분리 클래스 (RepositoryInterface 미상속)

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. D003 카테고리 추가 검토
3. 48시간 안정성 모니터링

---

## [260629] 워터마크/필터 수정 + Caption 교체

_업데이트: 260629 21:34 KST_

### 변경 내용

| 항목 | Before | After | 커밋 |
|------|--------|-------|------|
| COSLIFE·Lily 차단 | ImageFilter OCR (pytesseract 미설치로 무력화) | CAPTION_BLOCKLIST 텍스트 매칭 | d79a3b3 |
| FB UI 잔여물 제거 | 경과시간·댓글달기만 제거 | 원본보기·번역평가·좋아요·공유하기·저장 추가(_ui_pat) | 998215e |
| Caption 생성 | generate_caption_clone() — 텍스트 원본 보존 | generate_caption() — Gemini 재생성 | 998215e |
| 해시태그 필터 | 국가명 제한 없음 | Korea-related tags only (Myanmar·Vietnam 등 제외 명시) | 998215e |
| DOME_EXPORT_ENABLED | true (260619 활성화 완료) | 유지 | — |

### CAPTION_BLOCKLIST (content_filter.py)
`python
CAPTION_BLOCKLIST = ["coslife", "lily"]
`
- passes_keyword_filter() 선두에서 번역 캡션 체크 → 매칭 시 즉시 False 반환
- pytesseract 미설치 상태에서 텍스트 레벨 대체 차단 (ERR-044)

### 48시간 모니터링
- 시작: 2026-06-29 21:34 KST
- 종료: 2026-07-01 21:34 KST
- 확인 항목: [CaptionBlocklist] 차단 감지 로그 / lily 오탐 여부 / Gemini caption 품질

### P0 Backlog (갱신)
1. lily 오탐 모니터링 → 오탐 발생 시 "lily cosmetics"로 구체화
2. pytesseract 설치 여부 검토 (ERR-044 근본 해소)
3. Instagram_Posts 도매꾹 품질 육안 확인
4. D003 카테고리 추가 검토

## [260703~260705] DI Canary #2/#3 + Supplier_Blocklist 회귀 수정

### 260703 — Supplier_Blocklist 필드 매핑 회귀 수정 (ERR-046/FP-034/INC-024)
- repository_interface.py / airtable_repository.py / facebook_crawler.py 3파일 supplier_name→author_name+page_name 매핑 수정
- Gate 6 ISOLATED INTEGRATION PROOF 통과 + 운영 Supplier_Blocklist 5건 대상 Runtime Proof 6/6 매칭 성공
- pytest 100 passed, pre-existing 4 failed는 stash 비교로 무관 확인

### 260704 — DI Canary #2 (airtable_integrity.py)
- 신규 메서드 fetch_posted_missing_media_id() 추가 (repository_interface.py + airtable_repository.py)
- airtable_integrity.py get_table() 직접호출 → AirtableRepository 치환
- 타겟 3건 PASSED, 전체 100 passed·4 failed(pre-existing)·3 xfailed
- 커밋: 코드 f6194ac / 문서 57b5c00

### 260705 — DI Canary #3 (kpi_collector.py)
- 신규 메서드 2개 추가: fetch_all_instagram_posts() / fetch_all_lead_interactions(since_utc)
- kpi_collector.py _fetch_leads()/_fetch_posts() get_table() 직접호출 2곳 → AirtableRepository 치환
- 신규 테스트 4건 추가 (tests/test_smoke_metrics.py)
- 타겟 17/17 PASSED, 전체 104 passed·4 failed(pre-existing, test_dm_close.py)·3 xfailed
- 신규 HOLD: airtable_repository.py 전체 GET 메서드 offset 페이지네이션 미구현
- 커밋: 코드 f21e4b8 / 문서 a24d318

## [260710] heartbeat_monitor 절전 대응 + Governance 강화

### 완료 작업
1. heartbeat_monitor.py 신규 (b2aa30d) — watchdog.ps1과 독립된 heartbeat 정지 감지, Task Scheduler 5분 주기(`SNS_HeartbeatMonitor_Independent`)
2. ERR-052/FP-039/INC-029 (fe37ed4) — 250723 참조 활성 Task 2건(`SNS_AUTO_PRODUCTION`/`SNS_Auto_Run`) 발견, `Disable-ScheduledTask`로 즉시 비활성화
3. ERR-047/050 INC-028 Modern Standby 상관관계 조사 (fdd1333) — 1차/2차 다운 메커니즘이 서로 다를 수 있음을 최초 제기
4. ERR-049 증거 파일 정식 편입 + 스크래치 파일 gitignore 정리 (e8583ba)
5. ERR-053/FP-040 (d49ab61) — heartbeat_monitor.py 예약 작업이 `WakeToRun=False`로 Modern Standby 중 71회(약 5시간47분) 미실행 근본원인 확정
6. CLAUDE.md 승인 범위 명시 원칙 (3ab2e49) — read-only 조사 승인이 문서기록/commit까지 자동 포함하지 않음 (ERR-053 절차위반을 계기로 등록)
7. INC-028 Note 3 (422f9bd) — 1차 다운(20:09:40) 실제 원인 확정: Modern Standby 아님, 실제 OS shutdown(`StartMenuExperienceHost.exe`, 20:09:52 개시). Update/로그오프 배제, 사람의 조작 Hypothesis(확정 아님)
8. `docs/PENDING_INVESTIGATIONS.md` 신규 (b89e213) — PENDING-A(NSSM 전환 검토): AdsPower Local API가 Session 0(S4U)에서도 정상 응답함을 진단 Task로 실증 SUCCESS 확인
9. CLAUDE.md 단계별 Bookending 원칙 (e09fae5) — 작업 전/후 상태를 한 줄로 확인하는 습관 등록
10. `SNS_HeartbeatMonitor_Independent` Task `WakeToRun=True`로 변경 적용 — 실제 절전 구간 재현 검증은 다음 세션 대기

### Known Facts
- Flask(:5000)/Streamlit(:8501)/ngrok(:4040) 3개 포트 LISTENING 확인(260710 세션 중 재확인)
- `SNS_HeartbeatMonitor_Independent` 최근 상태: `WakeToRun=True`, 나머지 Settings 필드 변경 없음
- AdsPower Local API(`http://local.adspower.net:50325`)는 Session 0/S4U 비대화형 컨텍스트에서도 정상 응답(raw 실증 완료) — `facebook_crawler.py` 자체는 subprocess/GUI 의존 없음, 순수 HTTP 클라이언트

### P0/P1 Backlog (다음 세션)
1. WakeToRun=True 적용 후 실제 Modern Standby 구간 1~2회 확보해 heartbeat_monitor.log 기록 대조 검증
2. watchdog.ps1 자체의 1차다운 근본 메커니즘(여전히 UNKNOWN) 별도 조사
3. ERR-047 핵심 증상(재부팅 후 SNS_Watchdog_AutoStart 무재실행) 자체 해결책 검토
4. PENDING-A(NSSM/서비스 전환) 최종 결정 — 사용자 승인 필요
5. ⚠️ 260706~260709 커밋(ERR-048/050/051, INC-023/025/026/028, quality gate 재설계 등)은 이번 갱신에 미포함 — 필요 시 별도 backfill

### 관련 문서
- ERR-052/053, FP-039/040, INC-028(Note1~3)/029, PENDING-A — 전체 raw 근거는 각 문서 참조(중복 서술 최소화)

---

## [260711] NSSM 전환 완료 + ngrok LocalSystem 결함 발견·해소

### 완료 작업
1. 전날 노트북 종료로 자동화 전체 중단 → 재부팅 후 세션 재개, `SNS_Watchdog_AutoStart`(당시 아직 미비활성) 자동 재기동으로 1차 복구 확인
2. AdsPower 미기동으로 FB 크롤링 전량 실패(WinError 10061) → 사용자 직접 재기동, 정상화 확인
3. `.claude/settings.json` 신규 — PowerShell 도구 읽기 전용 명령 20개 자동 허용(권한 팝업 감소), git commit/push·프로세스 제어는 의도적으로 제외
4. **ERR-057** — NSSM 서비스(`SNS_Watchdog`)와 구 Task(`SNS_Watchdog_AutoStart`)가 watchdog.ps1을 동시 이중 실행 중이던 것 발견(PENDING-A 전환의 Phase 3 누락) → 관리자 권한으로 `Disable-ScheduledTask` + 중복 프로세스 `Stop-Process` 정리
5. **크래시 재시작 실증 PASS** — NSSM 관리 watchdog.ps1 강제 종료 → `AppRestartDelay` 경과 후 자동 재기동, 수동 개입 없이 전체 복구 확인
6. **재부팅 실증 PASS** — 실제 재부팅 후 watchdog.log 시작 배너 1번만 기록(구 Task 재발 없음) → **PENDING-A(NSSM 서비스 전환) 완전 종결**
7. **ERR-058** — 재부팅 실증 중 ngrok 실행 실패 신규 발견: (1) Microsoft Store(MSIX) 설치라 LocalSystem(비대화형) 컨텍스트에서 Execution Alias 실행 불가 (2) authtoken이 admin 사용자 프로필 전용이라 LocalSystem이 인증정보 미발견 — 오늘 아침엔 구 Task(admin 계정)가 우연히 가려온 잠복 결함. `watchdog.ps1` 포터블 exe 경로 지정 + authtoken을 LocalSystem 프로필에 복사로 해소, Runtime Proof 완료(`public_url` 정상 응답)
8. FP-042(전환 중간상태 방치 패턴)/FP-043(서비스 계정 전환 시 의존 도구 전수점검 필요) 신규 등록

### Known Facts
- `SNS_Watchdog` NSSM 서비스: `LocalSystem` 계정, `AppExit Default=Restart`, `AppRestartDelay=60000ms`
- `SNS_Watchdog_AutoStart` Task: `Disabled` 유지(삭제 아님, 증거 보존), 재부팅 실증으로 재발 없음 확인
- ngrok: `C:\ngrok\ngrok-v3-stable-windows-amd64\ngrok.exe`(포터블, 실사용) vs `WindowsApps\ngrok.exe`(MSIX 심볼릭 링크, LocalSystem에서 사용 불가 — 더 이상 참조 안 함)
- ngrok authtoken 이중 보관: `C:\Users\admin\AppData\Local\ngrok\ngrok.yml`(admin) + `C:\Windows\System32\config\systemprofile\AppData\Local\ngrok\ngrok.yml`(LocalSystem, 260711 신규 복사)
- AdsPower Global: 260711 재부팅 시 Windows 시작 시 자동 기동 확인(12:10:33~40) — 오늘 아침 첫 재부팅 때만 예외적으로 꺼져있었음(원인 미상)
- FB 크롤링: 재부팅 이후에도 정상 수집 지속 확인(12:34:07 1건 등)

### P1/P2 Backlog (다음 세션)
1. heartbeat_monitor.py 실제 Modern Standby 구간에서 로그가 이어지는지 실증 검증(유일하게 남은 절전 관련 미검증 항목, watchdog.ps1과 별개)
2. n8n(PID 10248 등) watchdog.ps1의 반복 재시작 시도·알림 잡음 — 우선순위 낮음으로 보류
3. ⚠️ 260706~260709 구간 여전히 별도 미반영(과거 Backlog #5 그대로 승계)

### 관련 문서
- ERR-057/058, FP-042/043, INC-030/031, PENDING-A(완전 종결) — 전체 raw 근거는 각 문서 참조

---

## [260713~260715] Gate C~G DM/댓글 안전장치 시리즈 + n8n/P0-1/FP-047/ERR-063 재조사

⚠️ 260706~260709 구간은 이번 갱신에도 여전히 미반영(과거 Backlog #5 그대로 승계, 필요 시 별도 backfill).

### 완료 작업

1. **Gate C — 가격 자동응답 안전차단**(ERR-061/FP-046/INC-034): `docs/design/DM_RELAY_COMMERCE_RFC.md` 설계검토 중 `get_base_price()`가 문의 상품을 특정하지 않고 최신 등록가를 그대로 자동발송하는 구조적 결함 발견. `PRICE_AUTO_REPLY_ENABLED`(기본 `false`) 도입, 비활성 시 상품확인 요청 템플릿으로 대체. Codex 4라운드 교차검증으로 발송실패 시 `bridge_status` 오갱신 방지, Telegram PII 마스킹(`_mask_igsid`/`_telegram_preview`, 단 신규 함수에만 적용), `(sender, 문의문)` 키 원자적 중복방지 동반 수정. 커밋 `c1c90b2`(260713) → 260714 10:18 launcher 재시작 + 10:24:41 Canary로 **가격 자동발송 차단 PASS 확정**. 안내문 실발송·신규 마스킹 E2E는 PARTIAL(미확인).
2. **Gate E-A/E-B — Graph API 버전 중앙화**: `modules/common/meta_graph.py` 신규(v19.0→v25.0 URL 중앙화), DM/댓글 4파일 8곳 적용. 라이브 Canary 4경로 중 3경로(dm_auto_reply/dm_followup_scheduler/comment_poller) PASS.
3. **ERR-062/FP-047/INC-035 — 댓글 리드 Airtable 기록 실패**(RESOLVED, 이번 2건): `Lead_Interactions.conversation_channel`에 `instagram_comment` 선택지 없어 댓글 리드 2건 기록 실패 + 재시도 없이 캐시에 완료 처리되어 유실. Airtable 선택지 추가로 이번 유형 해소, 저장 Canary PASS. **단 예외를 삼키고 무조건 캐시하는 근본 패턴(FP-047) 자체는 미해결로 계속 OPEN.**
4. **Gate G — 댓글 자동응답 Private Reply 전환**(ERR-064/FP-048/INC-036): 공개 답글 대신 비공개 Private Reply로 전면 전환. `modules/comment/comment_safety_guard.py` 신설(캠페인 게시물 allowlist/24h 쿨다운/일일예산/circuit breaker/fail-closed/REPLY_LOCK 동시성). Codex 4라운드 리뷰로 엔드포인트 계약(`POST /{page-id}/messages`, `recipient.comment_id`) 확정. 실계정(tgbtgbnate) 라이브 테스트로 댓글→Private Reply 수신까지 회장 육안 확인.
5. **Gate G 라이브 테스트 중 신규 발견(OPEN)**: tgbtgbnate(앱 테스터 미등록)의 Private Reply 답장이 45분+ 웹훅 미도착. 웹훅 구독(`messages`/`messaging_postbacks`)·토큰 스코프 전부 정상 확인됐으나, Meta 앱 대시보드에서 테스트 계정(채솔)만 테스터 등록·tgbtgbnate 미등록임을 확인 — Standard Access(App Review 미통과) 상태에서 앱 역할 없는 일반 사용자와의 메시징(인바운드 웹훅)이 제한될 수 있다는 가설과 정황 일치, 단 실제 Access Level은 미확인(CONFIRMED 아님).
6. **Meta App Review 제출**: 260715 00:35, `instagram_manage_comments`/`instagram_content_publish`/`instagram_manage_messages`/`instagram_basic` 4개 권한 Advanced Access 신청 제출(검토 중, 대본 `docs/design/META_APP_REVIEW_SCRIPT_260714.md`). **ManyChat**(이미 Meta 공식 Business Partner로 Advanced Access 보유, Pro $29~/월) 우회 전환도 검토 후보로 부상 — App Review 대기 vs ManyChat 전환 최종 방향 미결정.
7. **260715 재조사(전부 read-only, 회장 지시로 기록만 — 코드/프로세스 변경 없음):**
   - **ERR-065/FP-049/INC-037(n8n)**: watchdog.log 전체(260517~260715) n8n 재시작 실패 5,298건/성공 8건, 마지막 성공 260624 23:56:09 — **260711 NSSM/LocalSystem 전환 이후 성공 0건**. `logs/n8n.log`가 npx 대화형 설치 프롬프트("Ok to proceed? (y)")에서 멈춰 있고, 그 원인으로 보이는 좀비 프로세스(cmd.exe 16948→node.exe 21620, 260714 22:25 생성)가 10시간+ 생존 확인. 전역 npm 경로(admin 프로필 전용)와 LocalSystem 실행 계정 불일치가 원인으로 의심(ERR-058과 동일 클래스, 미확정).
   - **P0-1 → ERR-066 승격**: `dm_receiver.py:54-71`/`:147`이 여전히 IGSID 전체·원문 200자를 무마스킹 전송 확인. Gate C 때 만든 마스킹 유틸(`dm_auto_reply._mask_igsid()`/`_telegram_preview()`/`_PII_PATTERNS`)이 이미 있어 재사용만 하면 됨. 부수로 `dm_receiver.py:143` 로그도 원문 무마스킹 노출 확인(문서에 없던 추가 지점).
   - **FP-047 재확인**: Gate G 이후 줄 번호만 이동(`comment_poller.py:116`/`:123-125`, `comment_auto_reply.py:146-157`), 로직(예외를 삼키는 `_record_comment()` + 무조건 캐시) 그대로 — 부정 댓글·일반/가격 댓글 두 경로 모두 동일하게 취약함을 추가 확인.
   - **ERR-063 원인 확정(RESOLVED)**: `test_send_failure_does_not_mark_replied_or_schedule_followup`만 유일하게 `PRICE_AUTO_REPLY_ENABLED=True`+`get_base_price` non-None이라 `dm_auto_reply.py:289`의 실제 Gemini `generate_reply()` 호출까지 도달하는데 이게 mock되어 있지 않음 확인. `.venv` python으로 직접 재실행 → Gemini 200 OK, 7.48초 만에 PASSED — 무한 hang이 아니라 실제 API 상태(quota/rate-limit)에 좌우되는 테스트임을 실증. 260714 최초 발견 당시 Gemini 무료 쿼터 소진 상태였다는 기록과 대조하면 429 재시도 지연(`_RETRY_DELAYS=[20,40,60]`, 누적 최대 120초+)이 25초 격리 타임아웃을 넘겨 "hang"으로 보였던 것으로 설명됨.

### Known Facts
- `.env`: `COMMENT_AUTO_REPLY_ENABLED=false`, `PRICE_AUTO_REPLY_ENABLED=false` 둘 다 안전 상태 확인(260715).
- `configs/comment_campaign_posts.json`: `media_ids=["18116772601675773"]`(Gate G 라이브 테스트 값 유지, 커밋 완료) — `.env` 플래그 false라 즉시 실행 위험 없음.
- Gate C~G 전체 origin 동기화 완료(커밋 4f3f38e까지 push), 260715 문서 커밋 2건(`a0d5207`, `f511447`)도 push 완료.
- Gemini API 쿼터 상태는 시점에 따라 변동(260714 소진 확인 → 260715 재실행 시 200 OK 정상) — 매 세션 재확인 필요, 고정 사실 아님.

### P0/P1 Backlog (다음 세션)
1. **[최우선]** Meta App Review 결과 확인 + ManyChat 전환 여부 최종 결정(ERR-064/FP-048/INC-036) — 실제 손님 대상 자동화 핵심 전제에 직접 영향
2. FP-047(댓글 Airtable 기록 실패 시 유실) 코드 수정 — 재시도 큐 적용 또는 실패 ID 캐시 제외
3. ERR-066(P0-1, Telegram PII 노출) 코드 수정 — 기존 마스킹 유틸 재사용, 신규 개발 불필요
4. ERR-063 테스트에 `ai_reply_generator.generate_reply` mock 추가(회귀 아님, 테스트 안정성 개선)
5. n8n(ERR-065) 좀비 프로세스 정리 + watchdog.ps1 n8n 감시 블록 처리 방향 결정 — 단 회장 방침(안정화 우선)에 따라 n8n 재설계와 함께 후순위
6. ⚠️ 260706~260709 구간 여전히 별도 미반영 — 과거 Backlog 그대로 승계

### 관련 문서
- ERR-061~066, FP-046~049, INC-034~037, `docs/design/DM_RELAY_COMMERCE_RFC.md`, `docs/design/META_APP_REVIEW_SCRIPT_260714.md` — 전체 raw 근거는 각 문서 참조

---

## [260715~260716] FP-047 구현 + shadow 실계정 라이브 테스트 + Package 1(Phase A) 캠페인 allowlist 폴링

### 완료 작업

1. **FP-047(댓글 이벤트 idempotency) 실제 구현**(커밋 `00466a3`) — GPT/Codex 12라운드 교차검토(설계 8라운드 + 구현 후 코드리뷰 4라운드). 신규 `comment_event_store.py`(fencing token 원자적 claim, stale lease 자동 회수 내장), `comment_retry_dead_monitor.py`(retry_queue dead 태스크 Slack 알림). 단일 진입점 `process_comment_event()` — `COMMENT_EVENT_STORE_MODE`(disabled/shadow/enforce) 킬스위치, `CommentProcessResult` 구조화 반환값. Airtable `Lead_Interactions.source_event_id` 필드 신규 추가. 신규 테스트 65개, `COMMENT_EVENT_STORE_MODE=disabled`(기본값)로 커밋 — 운영 동작 무변화.

2. **shadow 모드 실계정 라이브 테스트(260715)** — `.env`를 `COMMENT_EVENT_STORE_MODE=shadow` + `COMMENT_AUTO_REPLY_ENABLED=true`로 전환(관리자 권한 서비스 재시작 반복 경유). 실제 테스트 계정(hsy00718g/jiho2987/petit__phau_thuat/kbeautymcn/reviewasiamarket 등)이 캠페인 게시물에 댓글 → **실제 Private Reply DM 수신까지 회장 육안 스크린샷 확인**(E2E PASS, 복수 계정·복수 라운드).
   - 이 과정에서 회장이 직접 내린 비즈니스 정책 변경 3건: (1) 가격 키워드(`단가`/`가격`/`price` 등)로 좁혀서 걸러내지 않고 스팸/부정 댓글 외 전부 Private Reply 대상으로 확대("재고있나요"/"연락주세요" 등 키워드 목록에 없던 실제 구매의사 표현을 놓치던 jiho2987 사례로 발견) (2) 사용자별 재응답 쿨다운 24h→0h (3) 일일 발송 예산 30→100000(사실상 무제한, circuit breaker는 버그 방지용으로 유지).
   - **이 정책 변경(`comment_auto_reply.py` 일부 + `tests/test_comment_auto_reply.py`)은 `.env`에는 반영·라이브 테스트까지 마쳤으나, 코드 자체는 아직 미커밋** — Package 1 커밋(`eb98741`)에서 관련 무관 변경으로 의도적으로 제외했고, 워킹트리에 그대로 남아있음. 다음 세션에서 별도 커밋 여부 결정 필요.

3. **ERR-069/FP-050/INC-038 발견** — 라이브 테스트 중 회장이 30초 간격으로 서로 다른 상품 게시물 2곳에 댓글을 남겼는데 1곳만 응답이 옴을 보고. 조사 결과 `comment_poller.py`가 `COMMENT_POLL_MEDIA_COUNT=5`(기본값) "최근 게시물 5개"만 폴링 중이었고, 캠페인 게시물(총 6개 등록)이 계정의 잦은 게시 빈도로 그중 3개가 감시 범위 밖에 밀려나 있었음. 밀려난 게시물의 댓글은 `db/comment_events.db`에 기록 자체가 없어(웹훅도 이 계정에서 안정적으로 안 들어와 보완 안 됨) 이벤트가 시스템에 아예 진입 못 한 것으로 raw 확인 — 실제 잠재고객 문의 1건("MOV 어떻게되나요")이 완전히 유실됨.

4. **Package 1(Phase A) 구현**(커밋 `eb98741`, push 완료) — GPT 전략자문 1라운드("최근 N개" 폐기, 캠페인 목록 직접 폴링으로 전환 확정, ManyChat 등 상용 서비스 사례 근거 제시) + Codex 코드검수 9라운드(설계가 아니라 구현 완료 후 실제 코드 재현 기반 리뷰, 라운드마다 실제 버그 발견).
   - 신규 `modules/comment/comment_campaign_config.py` — 캠페인 allowlist 공용 loader(`comment_safety_guard`/`comment_poll_targets` 공유, 스키마 검증/중복제거/공백 정규화, 파일 없음도 fail-closed).
   - 신규 `modules/comment/comment_poll_targets.py` — media별 `PENDING_BASELINE→ACTIVE→PAUSED` 상태머신(`comment_events.db` 별도 테이블), `campaign_config_hash`/`baseline_config_hash`로 설정 드리프트 감지, `COMMENT_POLL_ALLOWLIST_MODE`(기본 legacy) 킬스위치.
   - 신규 `tools/comment_campaign_baseline_cli.py` — media당 1개씩 수동 cutover(`--dry-run` → `--apply --cutover-at --expected-config-hash`(필수) → `--verify`(8개 계약) → `--activate --acknowledge-runtime-proof`(4가지 하드 조건: allowlist 모드+enforce 모드+운영자 확인 선언+설정 해시 일치)).
   - `comment_poller.py` — `_poll_legacy()`(기존 "최근 N개", 무변경)/`_poll_allowlist()`(신규, 전체 페이지네이션)로 분리.
   - `comment_auto_reply.py` — `process_comment_event()` 최상단에 `_blocked_by_allowlist_gating()` 게이트 신설(event-store 모드·mode 분기보다 먼저, event_store 행 생성 전 검사).
   - **9라운드 중 재현·수정된 핵심 버그(전부 실제 코드 재현으로 확인 후 수정, 상세는 ERR-069/`porting_logs/MERGE_JOURNAL.md` 참조):** PENDING media 새 댓글이 SHADOW_SEEN 태그로 영구 고착돼 나중에 ACTIVE 전환 후에도 처리 못 하는 버그(가장 심각 — 응답 영구 유실 시나리오), legacy 모드가 실수로 전체 페이지네이션을 써서 배포만으로 과거 댓글 대량발송 위험 재현, disabled 모드가 게이트 우회, PENDING 보호가 allowlist 플래그에만 종속돼 baseline 준비 작업(Phase B) 도중 무방비, JSON에서 방금 제거된 ACTIVE media가 DB 동기화 전까지 통과되는 경쟁 구간, `--activate` "경고만"이 위험함(allowlist+shadow+ACTIVE 조합이 다음 폴링 주기부터 실발송으로 이어짐 재현) → 하드 블록으로 변경, `--confirm-runtime-proof`가 증명이 아니라 자기선언임을 인정해 `--acknowledge-runtime-proof`로 개명 + CLI가 명시적으로 `.env` 로드하도록 수정.
   - 신규 테스트 87개, 전체 회귀 **424 total / 416 passed / 5 failed(무관 기존 `test_dm_close.py` 4건 + flaky 후보 `test_review_grid_ui.py` 1건, 반복 실행 중 재현 여부가 갈려 환경 타이밍 의존으로 추정되나 원인조사 전이라 공식 UNCLASSIFIED 유지) / 3 xfailed**.
   - 커밋 스테이징을 hunk 단위로 정밀 분리(`comment_auto_reply.py`의 게이트 부분만 스테이징, 가격 키워드 확대 부분은 워킹트리에 남기고 제외) — Codex가 최종 `git diff --cached --stat`/`--check` 재검수 후 승인.
   - 의무기록 5종(`ERROR_DATABASE.md` ERR-069 / `FAILURE_PATTERN.md` FP-050 / `INCIDENT_TIMELINE.md` INC-038 / `VALIDATION_STATUS.md` / `porting_logs/MERGE_JOURNAL.md`) 작성, `.env.example`에 신규 킬스위치 3종(`COMMENT_POLL_ALLOWLIST_MODE`/`COMMENT_POLL_MAX_PAGES`/`COMMENT_POLL_FAILURE_ALERT_THRESHOLD`) 등록 — 전부 이번 커밋에 포함.

5. **커밋+push 완료** — `eb98741`(Package 1 Phase A) push 시 그 이전 로컬 전용 커밋 2개(`00466a3` FP-047, `07e6521` ERR-066 PII 마스킹 — 둘 다 이 세션 내 이미 승인·커밋됐던 것)도 함께 origin에 반영됨(fast-forward, 선택적 push 불가능한 git 특성).

### Known Facts
- `COMMENT_EVENT_STORE_MODE=shadow`(FP-047), `COMMENT_POLL_ALLOWLIST_MODE=legacy`(Package 1), `COMMENT_AUTO_REPLY_ENABLED=true`, `COMMENT_REPLY_COOLDOWN_HOURS=0`, `COMMENT_REPLY_DAILY_BUDGET=100000` — 260716 기준 실제 `.env` 상태(라이브 테스트 이후 유지 중).
- `configs/comment_campaign_posts.json`: media_ids 6개로 확장된 상태(이전 세션 회장 직접 편집분, Package 1과 무관하게 이미 반영됨, 미커밋 상태로 워킹트리에 남음).
- `comment_poll_targets`/`comment_campaign_config`/baseline CLI는 전부 코드만 존재 — 실제 `--apply`/`--activate` 한 번도 미실행, `COMMENT_POLL_ALLOWLIST_MODE=allowlist`/`COMMENT_EVENT_STORE_MODE=enforce` 전환도 미실행.
- shadow 모드 라이브 테스트로 인해 `db/comment_events.db`에 실계정 댓글 다수가 `SHADOW_SEEN` 태그로 이미 존재 — 향후 baseline `--apply` 실행 시 이 행들을 "확정완료 아님"으로 분류해 정상 처리하도록 이미 코드 반영됨(P0-4).

### P0 Backlog (다음 세션)
1. **[최우선]** Meta App Review 결과 확인 + ManyChat 전환 여부 최종 결정(ERR-064/FP-048/INC-036) — 이전 세션부터 이어지는 미결 사안, 여전히 미확인
2. 가격 키워드 확대 정책 변경(`comment_auto_reply.py`)의 별도 커밋 여부 결정
3. Package 1 Phase B 착수 여부 결정 — allowlist 모드 전환 → 6개 media 순차 baseline(`--dry-run`/`--apply`/`--verify`) → enforce 전제조건(원문 평문 저장/Airtable preflight) 해소 → 자동 Runtime Proof 시스템 → 1개 media Canary → 전체 활성화, 각 단계 별도 승인
4. FP-047 enforce 진입 전제조건(원문 평문 저장, Airtable 필드 preflight) 착수 여부
5. ⚠️ 260706~260709 구간 여전히 별도 미반영 — 과거 Backlog 그대로 승계

### 관련 문서
- ERR-067~069, FP-047/050, INC-035/038, `docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md`, `porting_logs/MERGE_JOURNAL.md`(상세 구현 로그·9라운드 버그 목록) — 전체 raw 근거는 각 문서 참조

---
