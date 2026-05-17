# MERGE_JOURNAL

> 생성일: 2026-05-16 20:34
> 목적: 250723 참조 저장소 → 260511 Active 저장소 수동 이식 작업 기록

---

## [260517-2] launcher/main.py 안정화 수정 3건 (PHASE2 검증)

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-05-17 |
| 대상 파일 | `launcher/main.py` |
| 수정 1 | OAuthException 190/104 감지 시 `_slack` 직접 호출 + `raise` (ERR-017) |
| 수정 2 | `post_status='uploading'` 원자적 잠금 + `max_instances=1` (ERR-018) |
| 수정 3 | `ig_media_id` 존재 시 재업로드 차단 — `posted` 복원 후 `continue` (ERR-019) |
| 근거 | PHASE2_CHECKLIST #3/#4/#5 검증 중 GAP 발견 후 즉시 수정 |
| 커밋 | 이번 커밋 포함 |

---

## [260517] imgbb 영구 URL 방식 도입

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-05-17 |
| 대상 파일 | `modules/sns/instagram_uploader.py` |
| 변경 내용 | Facebook CDN URL → imgbb API 재업로드 → 영구 URL 방식으로 전환 |
| 근거 | ERR-013 (aspect ratio / CDN 만료) 반복 해결 불가 → FP-015 등록 |
| 결과 | `ig_media_id=18116524126780958` 실제 업로드 성공 / INC-010 |
| 환경변수 추가 | `IMGBB_API_KEY=702c210583c10ddbeb435751b1b2e5fa` (.env) |
| 커밋 | `0456adb` fix: preprocess image via imgbb upload |

---
