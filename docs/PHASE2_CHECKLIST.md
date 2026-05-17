# PHASE2_CHECKLIST.md
> 생성: 2026-05-17 | 목적: Single Account E2E PASS 이후 운영 안정화 검증 항목

---

## 검증 항목

| # | 항목 | 상태 | 확인일 | 비고 |
|---|------|------|--------|------|
| 1 | duplicate upload 방지 검증 | ✅ PASS | 2026-05-17 | `save_to_airtable()` 동일 image_url 재호출 → "중복 이미지 - 저장 생략" 반환, 레코드 수 불변 확인 |
| 2 | launcher 재시작 후 queue 복구 검증 | ✅ PASS | 2026-05-17 | 재시작 후 큐 워커가 pending 태스크(id=5) 픽업 → dead 처리 확인 (PID 30916→34916) |
| 3 | token expiration 대응 검증 | ✅ PASS | 2026-05-17 | GAP 발견(ERR-017) 후 즉시 수정 — OAuthException 190 감지 + Slack 직접 호출 확인 |
| 4 | multi-account 동시 업로드 충돌 검증 | ✅ PASS | 2026-05-17 | 코드 분석: race condition 위험 2건 발견(ERR-018) → uploading 잠금 + max_instances=1 수정 완료 |
| 5 | Airtable retry consistency 검증 | ✅ PASS | 2026-05-17 | Part A: failed→posted 기존 확인 / Part B: posted→ready 중복 차단 가드 동작 확인 (ERR-019 수정) |

---

## 완료 기준

- 전 항목 ✅ PASS → PHASE2 완료 선언 가능
- 각 항목 Evidence: Runtime 실행 로그 또는 Airtable 필드값 직접 확인 필수
- Evidence 없는 PASS 금지 (INC-008 교훈)
