# VALIDATION_STATUS.md

> 기준일: 2026-05-17
> 목적: Phase 1 Runtime Governance 준비 상태 검증 기록

---

| 항목 | 상태 | 확인일 |
|------|------|--------|
| rollback_ready | ✅ PASS | 2026-05-16 |
| schema_locked | ✅ PASS | 2026-05-16 |
| adapter_ready | ✅ PASS | 2026-05-16 |
| merge_journal_ready | ✅ PASS | 2026-05-16 |
| single_account_e2e | ✅ PASS | 2026-05-17 |
| phase2_dup_upload_guard | ✅ PASS | 2026-05-17 |
| phase2_queue_recovery | ✅ PASS | 2026-05-17 |
| phase2_token_expiry | ✅ PASS | 2026-05-17 |
| phase2_multiaccount_race | ✅ PASS | 2026-05-17 |
| phase2_retry_consistency | ✅ PASS | 2026-05-17 |
| watchdog_launcher_recovery | ✅ PASS | 2026-05-17 |
| watchdog_n8n_guard | ✅ PASS | 2026-05-17 |
| watchdog_fail_counter | ✅ PASS | 2026-05-17 |
| watchdog_slack_env_fix | ✅ PASS | 2026-05-17 |
| health_check_tool | ✅ PASS | 2026-05-17 |
| **phase2_runtime_governance_ready** | ✅ **PASS** | **2026-05-17** |

> ⚠️ **scope 한정:** single-account E2E + 운영 안정화 검증 완료. 다계정 실운영 evidence는 Phase 3 대상.

---

## 근거

| 항목 | 근거 |
|------|------|
| rollback_ready | `snapshots/snapshot_260516_project/`, `snapshot_260516_db/`, `snapshot_260516_.env` 생성 완료 |
| schema_locked | `docs/schema_governance.md` 작성 완료 — Migration Forbidden 규칙 명시 |
| adapter_ready | `docs/BRIDGE_SKELETON_POLICY.md` 작성 완료 — bridge contract 정책 확정 |
| merge_journal_ready | `porting_logs/MERGE_JOURNAL.md` 생성 완료 — 이식 기록 체계 수립 |
| single_account_e2e | Pillow crop + imgbb 전처리 후 `ig_media_id=18116524126780958` 생성 확인 (INC-010) |
| phase2_dup_upload_guard | `save_to_airtable()` 동일 image_url 재호출 시 "중복 이미지 - 저장 생략" 반환, 레코드 수 1 유지 확인 |
| phase2_queue_recovery | 재시작(PID 30916→34916) 후 큐 워커가 pending 태스크 픽업·처리 확인 (id=5, status=dead) |
| phase2_token_expiry | OAuthException 190 감지 → Slack 직접 호출 + Airtable failed 마킹 확인 (ERR-017 수정 후 재검증) |
| phase2_multiaccount_race | 코드 분석: race condition 2건(ERR-018) 발견 → uploading 잠금 + max_instances=1 수정 완료 |
| phase2_retry_consistency | Part A: failed→posted 기존 확인 / Part B: ig_media_id 가드로 중복 업로드 차단 확인 (ERR-019) |
| watchdog_launcher_recovery | launcher PID 27104 강제 종료 → watchdog 감지(23:04:23) → 6초 내 재시작 성공(23:04:29) / watchdog.log 직접 확인 |
| watchdog_n8n_guard | n8n 프로세스 전체 강제 종료(포트 5678 CLOSED 확인) → watchdog 감지 → 자동 재시작(23:05:34~23:06:44) / watchdog.log 직접 확인 |
| watchdog_fail_counter | `$failCount` 해시테이블 — 서비스별 연속 실패 카운터, 3회 이상 시 Slack error 알림 |
| watchdog_slack_env_fix | `.env` SLACK_WEBHOOK_URL 자동 로드 추가 — 시스템 환경변수 미설정 시 .env 폴백 (ERR-020) |
| health_check_tool | `tools/check_runtime_health.py` 실행 확인 — launcher PID 27104 / n8n PID 13724 / port 5000·5678 OPEN / Airtable HTTP 200 / posted 97건 정상 출력 |
| **phase2_runtime_governance_ready** | 단일계정 E2E + 운영 안정화(watchdog 자동복구 실증) 완료. 다계정 실운영 evidence는 별도 미보유. Phase 3 진입 가능 상태. |
