# PRODUCTION_RUNBOOK.md
> Generated: 2026-05-16 | Status: ACTIVE | Version: v1.1
> Scope: SNS_24AutoProject / 260511

---

## PRE-RUN CHECKLIST
```
- [ ] Git clean (git status)
- [ ] Runtime verified (실행 파일 확인)
- [ ] DB backup complete (db/ 폴더)
- [ ] Airtable accessible
- [ ] AdsPower profile Open 상태
- [ ] Selenium attach 성공 확인
- [ ] .env 로드 확인
- [ ] retry_queue dead = 0 확인
- [ ] Flask :5000 LISTENING 확인 (netstat -ano | findstr ":5000")
- [ ] ngrok :4040 LISTENING 확인 (netstat -ano | findstr ":4040")
- [ ] watchdog.ps1 실행 중 확인
```

## WATCHDOG 기동 (세션 시작 시)
```powershell
# watchdog 미기동 시 실행
Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File C:\SNS_24AutoProject_260511\watchdog.ps1" -WindowStyle Normal
# 자동 시작 등록 (관리자 PowerShell 필요)
# SNS_Watchdog_AutoStart 작업 스케줄러 등록
```

---

## STEP-001 | AdsPower Launch
**대상:** AdsPower Browser
**확인:** profile k1bto3j4 (fb_crawler_01) Open 상태
**실패 시:** AdsPower 재시작 → profile 재Open

---

## STEP-002 | Selenium Attach
**대상:** debug_port CDP attach
**확인:** attach 성공 로그 확인
**실패 시:** ERR-006 참조 / profile 재Open 후 재시도

---

## STEP-003 | Facebook Crawling
**대상:** facebook_crawler.py
**확인:** Airtable Source_Feeds 신규 레코드 생성 확인
**실패 시:** session 상태 확인 / token 유효성 확인

---

## STEP-004 | Airtable Write
**대상:** Source_Feeds 테이블
**확인:** processing_status = gpt_ready 레코드 존재
**실패 시:** ERR-008 참조 / rate limit 확인

---

## STEP-005 | Content Mapping
**대상:** vendor_code / hashtag / caption 매핑
**확인:** Instagram_Posts 레코드 생성 확인
**실패 시:** mapping 스크립트 로그 확인

---

## STEP-006 | Instagram Upload
**대상:** insta_uploader.py (실제 API 구현 필요 — 현재 stub)
**확인:** post_status = published / post_url 존재
**실패 시:** ERR-003 참조 / UI state 재검증

---

## STEP-007 | Status Update
**대상:** Instagram_Posts.post_status 업데이트
**확인:** published_at timestamp 기록 확인
**실패 시:** DB write 경로 확인

---

## STEP-008 | Webhook 수신
**대상:** dm_receiver.py
**확인:** Lead_Interactions 신규 레코드 생성
**실패 시:** webhook endpoint 확인 / n8n 상태 확인

---

## STEP-009 | DM Relay
**대상:** dm_auto_reply.py / dm_router.py
**확인:** replied_at timestamp 기록 / DM 실제 발송 확인
**중복 차단:** `_has_recent_auto_replied()` — CREATED_TIME() 기준 3분 window (2026-05-28 추가)
**중복 확인:** `duplicate skip` 로그 정상 출력 확인
**실패 시:** session 상태 확인 / rate limit 확인

---

## STEP-010 | Retry Queue 확인
**대상:** db/retry_queue.db
**확인:** dead task = 0
**실패 시:** ERR-010 참조 / 원인 제거 후 재시작

---

## STEP-011 | Scheduler 확인
**대상:** dm_followup_scheduler.py
**확인:** duplicate 실행 없음 / lock 정상
**실패 시:** ERR-009 참조 / lock 파일 제거 후 재시작

---

## STEP-012 | E2E 최종 검증
**대상:** 전체 흐름
**확인:**
```
FB Crawl → Airtable ✅
Mapping → Instagram_Posts ✅
Upload → post_url 존재 ✅
Webhook → Lead_Interactions ✅
DM → replied_at 존재 ✅
retry_queue dead = 0 ✅
```
**실패 시:** 실패 단계 특정 후 해당 STEP 재실행

---

## INCIDENT RESPONSE

### Runtime Failure
1. automation 중단
2. 로그 캡처
3. db/ 백업
4. 원인 특정 후 재시작

### DB Failure
1. sqlite backup
2. integrity check
3. schema_governance.md 기준 확인

### Upload Failure
1. UI state 재확인
2. popup state 확인
3. Selenium attach 재시도

---

## 오류 발견 시 의무 처리 규칙

모든 오류/수정 작업 완료 시 반드시:

1. `docs/ERROR_DATABASE.md` 업데이트 (ERR-NNN 추가)
2. `docs/FAILURE_PATTERN.md` 업데이트 (반복 패턴 시 FP-NNN 추가)
3. `docs/INCIDENT_TIMELINE.md` 업데이트 (운영 영향 시 INC-NNN 추가)
4. git commit 필수

수정 전 반드시 실제 entry point 확인:
- import chain 추적 후 실제 실행 파일 특정
- Evidence 없는 완료 선언 금지

완료 후 git commit + `Get-ChildItem` 실존 확인.

---

## CLONE MODE 단발 Runtime Proof 절차 (260602 확정)
```
1. AdsPower k1bto3j4 프로필 Open 확인
2. Facebook 그룹 로그인 상태 + 피드 게시글 육안 확인
3. one-shot crawler 실행 (load_dotenv 필수):
   cd "C:\SNS_24AutoProject_260511"
   .venv\Scripts\python.exe -c "from dotenv import load_dotenv; load_dotenv(override=True); from modules.sns.facebook_crawler import run; result=run('<GROUP_URL>', max_posts=10, adspower_user_id='k1bto3j4'); print('count:', len(result) if result else 0)"
4. [AIRTABLE] 저장 완료 로그 확인
5. Airtable Instagram_Posts 최신 record (post_status=ready) 확인:
   - original_text: 존재
   - converted_text: 존재
   - caption: 원문 기반 (요약 아님)
   - media_type: image
6. 이상 없으면 Runtime Proof PASS
```

## CLONE MODE 운영 안전 원칙 (260602 확정)
```
- COMMENT_AUTO_REPLY_ENABLED=false 유지 (IG 공개 답글 차단)
- git add . 절대 금지 — 파일명 지정 add만 허용
- data/processed_comment_ids.json commit 금지
- Instagram 업로드는 post_status=ready 확인 후 수동 승인
- launcher 장시간 실행 전 Runtime Proof 1건 확보 필수
```

## INSTAGRAM 업로드 단발 테스트 절차 (260602 확정)
```
1. 환경변수 확인:
   - INSTA_ACCESS_TOKEN, INSTA_IG_USER_ID 설정 여부 확인
   - 시스템 환경변수 AIRTABLE_API_KEY 플레이스홀더 없어야 함
   - load_dotenv 절대경로 필수: load_dotenv(dotenv_path=r'..\.env', override=True)

2. Airtable ready 레코드 확인:
   - Instagram_Posts 테이블 post_status='ready' 레코드 존재 확인
   - caption 필드 FB UI 잔여물(작성자명·경과시간··) 없는지 확인

3. 업로드 실행 (max_records=1):
   - _preprocess_image() → imgbb 비율 보정 (IMGBB_API_KEY 설정 시)
   - POST /media → creation_id 획득
   - POST /media_publish → ig_media_id 획득
   - Airtable: post_status=posted / ig_media_id 기록

4. 성공 검증:
   - ig_media_id 출력 확인
   - Airtable post_status=posted 확인
   - Instagram 계정(@yuna18253) 실제 게시 여부 확인

Runtime Proof (2026-06-02):
  recFyw7OUaZ666JDJ → ig_media_id=18101360630320704 → posted ✅
  이미지: 960×1707 → imgbb center-crop → https://i.ibb.co/dwnMVq7Z/2547998023eb.jpg
```

## PRODUCTION RULES
```
1. 운영 중 직접 코드 수정 금지
2. runtime patch 금지
3. 검증 없는 배포 금지
4. evidence 없는 판단 금지
5. rollback 없는 수정 금지
```

## CRAWL_URLS 현황 (260612 기준 — FB_GROUP_POOL_V1)
| 그룹 ID | 상태 | 비고 |
|---------|------|------|
| ~~1676627532598134~~ | ❌ 제거 | 인도 트래픽 비율 높음 — accounts.json + Crawl_Targets 삭제 (c71f2c7) |
| 610113703703488 | ⚠️ Hold | div[role='feed'] 미탐지 — 가입 승인 대기 중 |
| 345179878828208 | ✅ 활성 | Airtable 저장 확인 |
| 755455243345993 | ✅ 활성 | 키워드 매칭 시 수집 |
| 3289570041331131 | ✅ 활성 | FB_신규1 |
| 1827528710833477 | ✅ 활성 | FB_신규2 — caption 저장 확인 (260612 기준)

---

## JSON 설정 파일 저장 규칙 (260602 확정)
```powershell
# ❌ 절대 금지 — BOM 삽입으로 JSON 파싱 실패 유발
Set-Content "경로.json" -Encoding UTF8 -Value $content

# ✅ 필수 사용 — BOM-free UTF-8
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText("경로.json", $content, $utf8NoBom)
```
**근거:** ERR-035 / FP-025 — PowerShell 5.1 Set-Content UTF8 BOM 삽입 버그

---
## 부팅 후 점검 절차 (260603 추가)
1. 작업스케줄러 SNS_Watchdog_AutoStart 실행 확인
2. netstat -ano | findstr ':5000' → LISTENING 확인
3. http://localhost:5000/health → 200 OK 확인
4. watchdog.log 마지막 줄 확인
- 실패 시: Set-ExecutionPolicy RemoteSigned -Scope LocalMachine -Force 후 재시도

## 부팅 후 점검 추가항목 (260603 확정)
- SNS_Watchdog_AutoStart RunLevel=Highest / UserId=admin 확인
- watchdog.ps1 자가치유 블록 관리자 권한 실행 확인
- 명령: (Get-ScheduledTask -TaskName 'SNS_Watchdog_AutoStart').Principal | Select-Object RunLevel, UserId
- 성공기준: RunLevel=Highest

---

## LOST 상태 운영 주의사항 (260612 추가)
```
- LOST 타임아웃: followup3_sent + 72h 경과 → 자동 LOST 전환
- 현재 DRY_RUN 모드: .env LOST_DRY_RUN=true (기본값)
- 실운영 전환: .env LOST_DRY_RUN=false 설정 후 launcher 재시작
- 전환 전 확인: Lead_Interactions lost_reason / lost_at / disqualified 필드 존재 여부 확인
```

## Supplier_Blocklist 운영 (260612 확인)
```
- DRY_RUN 제거 완료 (11fc204) — 실차단 적용 중
- Blocklist 로드: 4건 (로그 확인 가능: [Blocklist] 로드 완료 | 4건)
- 차단 시: [FB Crawler] POST N 필터 제외 로그 출력
```

## Supplier_Blocklist / content_filter 관리 절차 (260616 추가)

### 워터마크 공급자 차단 절차
```python
# 1. Airtable Supplier_Blocklist 등록
requests.post(f'{BASE_URL}/Supplier_Blocklist', json={'records': [{'fields': {
    'author_name': '<FB 작성자명>',
    'page_name': '<브랜드명>',
    'reason_code': 'BLOCK_WATERMARK_SUPPLIER',
    'notes': '워터마크 이미지 공급자'
}}]})

# 2. content_filter.py _IMAGE_BLOCK_KEYWORDS에 패턴 추가
# modules/sns/content_filter.py 내 _IMAGE_BLOCK_KEYWORDS 리스트
# 예: r'm&y\s*global'
```

### 차단 확인
- 다음 크롤링 사이클에서 `[Blocklist] 차단 | author=...` 로그 확인
- 텍스트 필터 테스트: `python -c "from modules.sns.content_filter import passes_keyword_filter; print(passes_keyword_filter('<텍스트>'))"``

### 현재 Blocklist 건수 확인
```python
r = requests.get(f'{BASE_URL}/Supplier_Blocklist', headers=hdrs)
print(len(r.json().get('records', [])), '건')
```

---

## filter_rules.json 운영 금지 사항 (260612 추가)
```
- configs/filter_rules.json: Crawl_Training_Set 기반 분석 전용
- 운영 크롤러(facebook_crawler.py)와 연동 금지
- generate_filter_rules.py: 분석 스크립트, 자동 실행 금지
```

## [260617] PRODUCTION_RUNBOOK - Pilot 3개 운영 절차

### Pilot 계정 (Active)
- IDN-000036: nguyenknv15@gmail.com
- IDN-000038: nhm880808@gmail.com
- IDN-000016: kang88jungmin@gmail.com

### 자동화 실행 조건
- identity_status = Active
- automation_enabled = True
- platform_automation_enabled = True
- adspower_profile_id 존재

### 실행 제외 조건
- identity_status != Active
- automation_enabled = False
- adspower_profile_id 없음

### Rollout 순서
Stage 1: Pilot 3개 -> 7일 안정 확인
Stage 2: 10개 확장
Stage 3: 33개 전체 확장

### 일일 점검 항목
- Instagram_Posts publish_status 확인
- 차단/오류 계정 확인
- Platform_Accounts last_post_success_at 확인
- n8n 실행 로그 확인

### 긴급 중단 방법
Account_Registry -> automation_enabled = False
또는
Platform_Accounts -> platform_automation_enabled = False
