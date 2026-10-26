# 6개 전문 영역 원천 레지스트리 (261026)

_작성: 2026-10-26 15:15 ICT · Claude Code · 회장 제공 50개 사이트 목록 검증 결과_

## 목적과 범위

- 회장이 정리한 6개 영역 50개 사이트를 **원문 사실 출처(Primary) / 뉴스 발견용(Discovery) / 참고자료(Reference)** 로 분류하고, 실제 접근 여부를 확인한 기록이다.
- 운영 Producer가 자동으로 읽는 곳은 **AI Sourcebook 14.x(뉴스 피드)뿐**이다. 이 문서 자체는 Runtime이 읽지 않는다(참고·배정 기준 문서).
- 검증되지 않은 사이트는 14.x에 넣지 않는다. 14.x에 넣으려면 ①RSS 피드 파싱 성공 ②Gemini url_context로 기사 원문 SUCCESS가 둘 다 확인돼야 한다.

## 검증 방법 (2026-10-26 15:07 ICT)

- 접근: `httpx` GET(브라우저 User-Agent, 리다이렉트 추적, 15초). `403`은 봇 차단일 수 있어 사람·Gemini 접근 불가를 뜻하지는 않는다.
- 피드: 기존 `research_to_topic_adapter.fetch_feed_items()`로 파싱, 72시간 이내·AI 키워드 기사 수 집계.
- 원문 읽기: 036 Producer Dry-run(`analyze_news_url`, url_context) — 게시·Airtable 쓰기 0.
- 원본 결과: 세션 scratchpad `source_check_261026.json`, `dryrun_newfeeds_261026.txt`.

## 분류 결과

판정: PASS=접근 또는 피드 확인 / FAIL=접근 불가·연결 오류 / 중복=기존 등록 또는 다른 항목으로 리다이렉트.

### 1. 미국 AI 웹사이트·앱·AI 툴 뉴스

| # | 사이트 | 분류 | 접근 | 피드(72h AI 기사) | url_context | 운영 상태 |
|---|---|---|---|---|---|---|
| 1 | TechCrunch AI | Primary | 200 | OK (8) | ERROR(261026 2회) | 중복 — 기존 14.1 유지 |
| 2 | The Verge AI | Primary | 200 | OK (8) | PAYWALL | 중복 — 기존 14.2 유지 |
| 3 | There's An AI For That | Discovery | 403 FAIL | 없음 | — | 비활성 |
| 4 | Futurepedia | Discovery | 403 FAIL | 없음 | — | 비활성 |
| 5 | MIT Technology Review AI | Primary | 200 | OK (0) | 미검증 | 중복 — 기존 14.6 유지 |
| 6 | VentureBeat AI | Primary | 429 FAIL | 429 | — | 비활성 |
| 7 | Ars Technica AI | Primary | 405(홈) | OK `arstechnica.com/ai/feed/` (0) | 미검증 | 비활성(후보) |
| 8 | Product Hunt AI | Discovery | 403(홈) | OK `producthunt.com/feed?category=artificial-intelligence` (1) | 미검증 | 비활성(발견용) |
| 9 | AI News | Primary | 202 | 파싱 실패 | — | 비활성 |
| 10 | Tom's Hardware AI | Primary | 404 — 제공 URL 오류 | OK `tomshardware.com/feeds/tag/artificial-intelligence` (6) | **SUCCESS** | **활성 — 14.8 등록** |

### 2. 실리콘밸리·테크 생태계

| # | 사이트 | 분류 | 접근 | 피드 | 운영 상태 |
|---|---|---|---|---|---|
| 11 | The Information | Reference(유료) | 403(홈) | OK (4) | 비활성 |
| 12 | Wired US | Primary | 200 | OK `wired.com/feed/tag/ai/latest/rss` (1) | 비활성(후보, url_context 미검증) |
| 13 | Silicon Valley Business Journal | Reference(유료) | 403 FAIL | 없음 | 비활성 |
| 14 | Crunchbase News | Discovery(투자) | 200 | OK (2) | 비활성 — 투자 뉴스는 관련성 규칙상 제외 |
| 15 | Hacker News | Discovery | 200 | `/rss` 실패 | 비활성 |
| 16 | First Round Review | Reference | 200 | 실패 | 비활성 |
| 17 | Sifted | Reference | 403(홈) | OK (2) | 비활성 |
| 18 | Techmeme | Discovery(집계) | 200 | OK (6) | 비활성 — 링크가 집계 페이지라 원문 출처 아님 |

### 3. 한국 음식 역사·기원·식재료

| # | 사이트 | 분류 | 접근 | 운영 상태 |
|---|---|---|---|---|
| 19 | 한국민족문화대백과사전 | Primary | 200 | 참고(023 Sourcebook 수동 원천 후보) |
| 20 | 한식진흥원 | Primary | 200 | 참고 |
| 21 | 농식품올바로 | Primary | 200 — `nics.go.kr/food/`로 리다이렉트(URL 변경) | 참고 |
| 22 | K-Culture | Reference | 200 — 운영 주체(한국학중앙연구원 여부) 미확인 | 참고 |
| 23 | 국립민속박물관 | Primary | 200 | 참고 |
| 24 | 한국전통음식연구소 | — | 연결 실패 FAIL | 비활성 |
| 25 | 한국식품연구원 | Primary | 200 | 참고 |
| 26 | 국가문화유산포털 | Primary | 200 | 참고 |

### 4. 미용성형·피부과 미용기기

| # | 사이트 | 분류 | 접근 | 운영 상태 |
|---|---|---|---|---|
| 27 | Aesthetic Medical Practitioner | — | 연결 실패 FAIL | 비활성 |
| 28 | Aesthetic Authority | — | `dermatologytimes.com`으로 리다이렉트 | 중복(#44) |
| 29 | Classys | Reference(제조사) | 200 | 참고 |
| 30 | Lutronic | Reference(제조사) | 403 FAIL | 비활성 — #34와 같은 그룹 |
| 31 | InMode | Reference(제조사) | 200 | 참고 |
| 32 | Candela | Reference(제조사) | 200 | 참고 |
| 33 | Jeisys | Reference(제조사) | 200 | 참고 |
| 34 | Cynosure Lutronic | Reference(제조사) | 200 | 참고 |

### 5. 뷰티 트렌드·K-뷰티

| # | 사이트 | 분류 | 접근 | 운영 상태 |
|---|---|---|---|---|
| 35 | WGSN Beauty | Reference(유료) | 403 FAIL | 비활성 |
| 36 | CosmeticsDesign-USA | — | 연결 실패 FAIL | 비활성 |
| 37 | Global Cosmetics News | Primary | 200 | 참고 |
| 38 | Beauty Packaging | — | 403 FAIL | 비활성 |
| 39 | 코스모닝 | Primary | 200 | 참고 |
| 40 | 장업신문 | Primary | 200 | 참고 |
| 41 | Beauty Independent | — | 403 FAIL | 비활성 |
| 42 | KCI | Reference(학술) | 200 — 실제 명칭은 한국학술지인용색인(제공 설명과 다름) | 참고 |

### 6. 피부과 전문의 뉴스·칼럼

| # | 사이트 | 분류 | 접근 | 운영 상태 |
|---|---|---|---|---|
| 43 | JAAD | Reference(학술) | 403 FAIL | 비활성 |
| 44 | Dermatology Times | Primary | 200 | 참고 |
| 45 | Practical Dermatology | Primary | 200 | 참고 |
| 46 | 의사신문 | Primary | 200 | 참고 |
| 47 | 청년의사 | Primary | 200 | 참고 |
| 48 | 의학신문 | Primary | 200(https 리다이렉트) | 참고 |
| 49 | Dermatologic Surgery | Reference(학술) | 403 FAIL | 비활성 |
| 50 | 대한피부과학회 | Reference(학회) | 200 | 참고 |

### 7. 여행 — 베트남 음식·역사·하롱베이·크루즈·여행 안전 (261026 15:30 ICT 추가, 회장 제공 19개)

| # | 사이트 | 분류 | 접근 | 운영 상태 |
|---|---|---|---|---|
| 51 | Vietnam Tourism 공식(한국어) `vietnam.travel/kr` | Primary(관광청 공식) | 200 | 참고 |
| 52 | Taste and Tales of Vietnam | Reference(미식 투어 업체) | 200 | 참고 |
| 53 | Toronto Pho — 베트남 역사·음식 가이드 | Reference(음식점 블로그, 공식 아님) | 200 | 참고 — 사실 인용 시 공식 원천 교차확인 필요 |
| 54 | Skyscanner 베트남 가이드 | Discovery | 200이지만 CAPTCHA 페이지로 이동 FAIL | 비활성 |
| 55 | Halong Bay Cruises 한국어 가이드 | Discovery(예약 플랫폼) | 200 | 참고 |
| 56 | Vietnam Tourism — 하롱베이 크루즈 | Primary(관광청 공식) | 200 | 참고 |
| 57 | 12Go Asia — 공식 `https://12go.asia/ko` (261026 회장 확정, 기존 제공 `12go.kr`은 다른 회사(더원멤버스)로 이동해 폐기) | Discovery(교통 예약 플랫폼) | 405 사람 인증 — 자동 접근 FAIL | 참고(수동 확인용) — 자동 수집 불가 |
| 58 | Ubigi 베트남 여행 앱 가이드 | Reference(eSIM 업체 블로그) | 200 | 참고 |
| 59 | Vinpearl 공식(한국어) | Primary(기업 공식) | 403 FAIL(봇 차단 가능) | 비활성 |
| 60 | Healing Cruise | Reference | 200 | 참고 |
| 61 | VELTRA Cruise | Discovery(예약 플랫폼) | 200 | 참고 |
| 62 | Emperor Cruises | Primary(선사 공식) | 200 | 참고 |
| 63 | Aqua Expeditions | Primary(선사 공식) | 200 | 참고 |
| 64 | UnCruise Adventures | Primary(선사 공식) | 429 FAIL | 비활성 |
| 65 | 외교부 해외안전여행 `0404.go.kr` | Primary(정부 공식) | 200 | 참고 — 안전·경보 정보는 이 원천 우선 |
| 66 | 주베트남 대한민국 대사관 — 공식 `https://overseas.mofa.go.kr/vn-ko/index.do` (261026 회장 확정) | Primary(정부 공식) | 200 | 참고 — 현지 사건·사고·긴급 공지는 0404와 함께 이 원천 우선 |
| 67 | KKday 해외여행 체크리스트 | Reference(여행사 블로그) | 403 FAIL | 비활성 |
| 68 | 트립닷컴 여행 준비물 가이드 | Reference(여행사 가이드) | 432 FAIL | 비활성 |
| 69 | PackPoint (Google Play) | Reference(앱 소개) | 200 | 참고 |

**7번 집계:** 19개 = 접근 PASS 13 + FAIL 6(#54·57·59·64·67·68 — #57은 공식 URL 확정됐으나 사람 인증으로 자동 접근 불가). 운영 Sourcebook 활성 0(여행은 뉴스 피드 경로가 아님).

**집계(1~6번):** 50개 = 접근 PASS 36 + FAIL 14(#3·4·6·9·13·24·27·30·35·36·38·41·43·49). PASS 36 중 중복 4(#1·2·5 기존 14.x, #28→#44). 운영 신규 활성 1(#10 Tom's Hardware → 14.8).

## 계정(Persona) 배정 — Account_Registry `category`·`content_theme` + Persona `content_pillars` 기준

배정은 이 문서에만 기록한다. Airtable에는 원천 배정 필드가 없다(필드 추가는 별도 승인 필요). 기존 Persona·언어·CTA는 변경하지 않았다.

| 원천 영역 | 배정 계정(identity · persona) | 근거 |
|---|---|---|
| 1. AI 툴 뉴스 | 036 PER-002, 025 PER-024, 029 PER-028, 027 PER-026, 026 PER-025, 047 PER-043, 034 PER-033, 033 PER-032, 024 PER-023, 030 PER-029, 021 PER-046, 022 PER-021, 028 PER-027 | category D_AI(023 제외) |
| 2. 실리콘밸리 | 036 PER-002, 022 PER-021 | AI 뉴스·이슈 요약 Pillar |
| 3. 한식 | 023 PER-022, 028 PER-027 | content_theme 한식·식재료 / AI+여행+음식 |
| 4. 미용기기 | 032 PER-031, 031 PER-030, 019 PER-019, 020 PER-020, 035 PER-034, 017 PER-045, 018 PER-018, 014 PER-015, 016 PER-017, 015 PER-016 | B_MED·E_AESTHETIC, secondary_tags MED |
| 5. 뷰티 트렌드 | 041 PER-001, 007 PER-008, 012 PER-013, 052 PER-051, 013 PER-014·PER-048, 011 PER-012, 048 PER-044, 051 PER-050, 044 PER-040, 003 PER-005, 014 PER-015, 016 PER-017, 015 PER-016, 019 PER-019, 018 PER-018, 024 PER-023, 033 PER-032 | A_BEAUTY + AI·뷰티 융합 / 피부과 뷰티 |
| 6. 피부과 칼럼 | 4번과 같은 10계정 | 의료·피부과 계정 |
| 7. 여행(베트남·크루즈·안전) | 038 PER-036, 039 PER-037, 028 PER-027 | 038: C_TRAVEL, Pillar 힐링 여행지·크루즈·역사·지형·여행 코스 / 039: C_TRAVEL, Pillar 문화 비교·베트남 소식·교류 / 028: Pillar AI 여행 코스·맛집 검증 |

- **배정된 Persona: 37 / 51** (261026 15:30 여행 영역 추가로 PER-036·PER-037 2개 추가, PER-027은 기존 배정에 7번 추가).
- **배정 없음 14:** PER-003·004(대표 PR), 006(후기), 007, 009, 010(주식), 011(지식), 035(엔틱), 039(음악), 049(UNCATEGORIZED), 038(책)·041(컬러테라피)·042(다이어트) — A_BEAUTY지만 주제 불일치, 047(헬스운동).
- **Key 완료 23계정 기준:** 원천 영역 배정 23/23(여행 추가로 038·039 해소).
- 023은 Airtable category가 D_AI로 잘못 분류돼 있다(MERGE_JOURNAL 261026 023 항목). 이번 배정은 content_theme 기준(한식)으로 했다.

## 남은 GAP

1. 036 Dry-run(15:10)은 FAIL — 후보 2건이 techcrunch(url_context ERROR)·Tom's Hardware(원문 SUCCESS, 기업 수익 기사라 IRRELEVANT). 관련 있고 읽히는 실무 AI 툴 기사가 아직 72시간 창에 없음.
2. Ars Technica·Wired·Product Hunt는 피드는 되지만 url_context 원문 읽기 미검증 — 확인 후 14.x 등록 가능.
3. 3~6번 영역은 자동 Producer 경로가 없다(뉴스 경로는 036 전용, 계정별 Sourcebook은 수동 큐레이션). 계정별 원천 배정을 Runtime에서 쓰려면 Airtable 필드 또는 계정별 Sourcebook이 필요(별도 승인).
4. ~~여행(C_TRAVEL) 계정용 원천 영역이 50개 목록에 없음.~~ → 261026 15:30 7번 영역(19개)으로 해소. 단 여행 계정(038·039)은 콘텐츠 Producer 미연결이라 Runtime에서 아직 읽지 않음.
5. ~~7번 중 #57 12Go·#66 대사관 URL 회장 확인 필요.~~ → 261026 회장 확정: 12Go `12go.asia/ko`(자동 접근은 사람 인증으로 불가, 수동 참고용), 대사관 `overseas.mofa.go.kr/vn-ko/index.do`(200 확인).
