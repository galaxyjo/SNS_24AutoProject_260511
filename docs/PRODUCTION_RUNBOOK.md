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

## PRODUCTION RULES
```
1. 운영 중 직접 코드 수정 금지
2. runtime patch 금지
3. 검증 없는 배포 금지
4. evidence 없는 판단 금지
5. rollback 없는 수정 금지
```
