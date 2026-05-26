# Progress Log — 2026-05-26

## 작업 목표
Airtable 스키마 정리 + Account_Registry 검증 + Persona_Profile 테이블 신규 구축

---

## Step 1 — 孤兒 필드 삭제 확정 ✅
- `grep` 전수조사 (코드 참조 0건 확인)
- `docs/schema_governance.md` 업데이트: 삭제 확정 필드 목록 + 삭제 금지 필드 명시
- commit: `docs: orphan field cleanup decision 260526`

**삭제 확정 필드:**
| 테이블 | 필드 |
|--------|------|
| Instagram_Posts | `caption copy`, `post_url copy`, `error_message` |
| Source_Feeds | `source_url (URL)` |

**삭제 금지:**
- `processing_status` 값 `gpt_ready` — runtime 상태값
- Source_Feeds `Instagram_Posts` 링크필드 — 테이블 관계 필드

---

## Step 2 — Account_Registry ACC-001 검증 ✅
- `tools/check_account_registry.py` 작성 및 실행
- `rec83rBqrE5ZjYyEm` 레코드 존재 확인
- 3개 필드 모두 PASS:
  - `ig_user_id`: `17841476202821375`
  - `fb_page_id`: `868456346356581`
  - `account_email`: `nhm880808@gmail.com`

---

## Step 3 — .env 단일계정 폴백 구조 확인 ✅
- `accounts.json` 빈 값 유지 확정 — `.env` 폴백 그대로 운영
- `INSTA_ACCESS_TOKEN`, `INSTA_IG_USER_ID`, `FACEBOOK_PAGE_ID`, `AIRTABLE_BASE_ID` 모두 `.env`에 실제 값 존재

---

## Step 4 — Persona_Profile 테이블 생성 ✅
- `tools/create_persona_profile_table.py` 작성 및 실행
- Metadata API로 테이블 + 12개 필드 자동 생성
- **table_id**: `tblbxtUH1K88aomOP`
- **account_code_ref**: `Account_Registry` (`tblPdZz9g9Bz6c4Kt`) 링크 연결

| # | 필드명 | 타입 |
|---|--------|------|
| 1 | persona_code | singleLineText (Primary) |
| 2 | account_code_ref | multipleRecordLinks → Account_Registry |
| 3 | persona_name | singleLineText |
| 4 | persona_role | singleLineText |
| 5 | mbti_type | singleLineText |
| 6 | tone_style | multilineText |
| 7 | greeting_template | multilineText |
| 8 | followup_template | multilineText |
| 9 | language | singleLineText |
| 10 | active | checkbox |
| 11 | created_at | date |
| 12 | last_updated | date |

---

## 잔여 작업
- [x] Airtable UI에서 孤兒 필드 4개 직접 삭제 ✅ 260526
- [x] Persona_Profile PER-001 레코드 데이터 입력 ✅ 260526 (record_id: reck5gPdhpWqgmdKP)
