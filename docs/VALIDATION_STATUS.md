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
| schema_orphan_cleanup_260526 | ✅ PASS | 2026-05-26 |
| persona_profile_per001_created_260526 | ✅ PASS | 2026-05-26 |
| backup_3_confirmed_260526 | ✅ PASS | 2026-05-26 |
| watchdog_flask_dual_fixed_260527 | ✅ PASS | 2026-05-27 |
| dual_scheduler_resolved_260527 | ✅ PASS | 2026-05-27 |
| virtual_autoreply_proof_260528 | ✅ PASS | 2026-05-28 |
| supplier_blocklist_fieldmap_fix_260703 | ✅ PASS | 2026-07-03 |
| watchdog_task_wrapper_260708 | 🟡 PARTIAL | 2026-07-09 |
| quality_gate_relevance_filter_canary_260706 | 🔴 FAILED → ROLLED_BACK | 2026-07-06 |
| quality_gate_relevance_filter_redesign_260707 | 🟡 PARTIAL | 2026-07-07 |
| di_canary2_airtable_integrity_260704 | ✅ PASS | 2026-07-04 |
| di_canary3_kpi_collector_260705 | ✅ PASS | 2026-07-05 |
| launcher_duplicate_instance_cleanup_260706 | 🟡 PARTIAL | 2026-07-06 |

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
| caption_blocklist_260629 | content_filter.py CAPTION_BLOCKLIST 추가(coslife, lily) — passes_keyword_filter() 선행 차단. OCR 없이 caption 텍스트 레벨 차단 적용. ERR-044 MITIGATED. |
| schema_orphan_cleanup_260526 | 孤兒 필드 4개 삭제 확인 — `caption copy`, `post_url copy`, `error_message` (Instagram_Posts), `source_url (URL)` (Source_Feeds). grep 코드 참조 0건 확인 후 Airtable UI 직접 삭제. |
| persona_profile_per001_created_260526 | Persona_Profile 테이블 신규 생성 (tblbxtUH1K88aomOP, 12개 필드) + PER-001 레코드 생성 완료. record_id: reck5gPdhpWqgmdKP, persona_name: 엔틱, account_code_ref: ACC-001 연결. |
| backup_3_confirmed_260526 | `C:\backup_(3)_260526 1350_SNS_24AutoProject_260511.zip` 백업 완료 확인. |
| virtual_autoreply_proof_260528 | Flask :5000 PID 14256 + ngrok :4040 PID 8956 LISTENING 확인. 로컬 POST 200 OK. detect_price_inquiry=True. DEFAULT_BASE_PRICE=50000 적용. Airtable LI-2B0A72F7 생성·qualified/auto_replied 확인. IG 발송 실패는 TEST_SENDER_004 가상 ID 정상 예상 결과. backup_(7)_260528_1338 완료. |

| repository_interface_260624 | AirtableRepository 22개 메서드 전면 교체 완료 — Infrastructure 외부 직접 호출 0건 확정. Failure Injection Test PASS (finally/AdsPower Stop 정상). Runtime Proof 5회 연속 정상 (19:50~21:50 KST). 커밋 체인: 18aa3a7→df9df6b→4502e65→e0bcff6→36cbf05. |
| caption_generate_260629 | generate_caption_clone → generate_caption 교체 완료. clean_fb_metadata _ui_pat 추가(원본보기·번역평가·좋아요·공유하기·저장). 해시태그 Korea-related only 프롬프트 규칙 추가. 커밋 998215e. |
| supplier_blocklist_fieldmap_fix_260703 | ERR-046/FP-034/INC-024 해결. `repository_interface.py`/`airtable_repository.py`/`facebook_crawler.py` 3파일 `supplier_name`→`author_name`+`page_name` 매핑 수정. Gate 6 ISOLATED INTEGRATION PROOF(격리 테스트 테이블 `Supplier_Blocklist_Test`, 실 HTTP 왕복) 사전 통과 + 운영 `Supplier_Blocklist` 5건 대상 Runtime Proof 6/6 매칭 성공. pytest 100 passed, pre-existing 4 failed는 stash 비교로 무관 확인. |
| di_canary2_airtable_integrity_260704 | Canary #2 — modules/metrics/airtable_integrity.py의 airtable_bridge.get_table() 직접 호출을 AirtableRepository.fetch_posted_missing_media_id()로 치환. repository_interface.py(ABC 계약 추가) + airtable_repository.py(구현, AND({post_status}='posted', {ig_media_id}='') 필터) + tests/test_smoke_metrics.py(mock 대상 갱신) 동시 수정. Runtime Proof: 타겟 테스트 13/13 passed, 전체 suite 100 passed / 4 failed(pre-existing, test_dm_close.py 무관) / 3 xfailed — 260703 baseline과 정확히 일치. BOM 확인 — airtable_integrity.py / test_smoke_metrics.py 2개 파일 BOM 없음 확인(repository_interface.py / airtable_repository.py는 BOM 미검증). commit f6194ac, push 436bdf7..f6194ac 완료. |
| di_canary3_kpi_collector_260705 | ERR/FP 없음. repository_interface.py/airtable_repository.py 신규 메서드 2개(fetch_all_instagram_posts/fetch_all_lead_interactions) 추가, kpi_collector.py get_table 직접호출 2곳 Repository 치환, test_smoke_metrics.py 신규 테스트 4건 추가. 타겟 4건 PASS + 전체 104 passed·4 failed(pre-existing)·3 xfailed(baseline 일치). BOM 4개 파일 전부 확인. HOLD 신규: offset 페이지네이션 전체 미구현. |
| quality_gate_relevance_filter_canary_260706 | ERR-049/FP-037/INC-027 working tree 문서화 완료, commit 전. `quality_gate.py`에 relevance filter canary 편집(5번째 규칙) 추가 시 dry-run 검증을 영문 `caption` 필드 20건 기준으로 수행해 20/20 MATCH를 확인했으나, 실제 runtime 입력 필드(`title`, 한국어)와 불일치 — 영어-only 키워드가 한국어 title에 매칭 안 되어 D001/D002 `fetch=10 ready=0`(100% 차단) 발생. `git checkout HEAD -- modules\crawlers\quality_gate.py`로 원본 4규칙 rollback, launcher/main.py PID 지정 재시작으로 반영 확인. 재설계 미착수 — 한국어+영어 이중언어 키워드 기준 dry-run 후 재설계 필요. |
| quality_gate_relevance_filter_redesign_260707 | ERR-049/FP-037/INC-027(260706 canary 실패) 이후 재설계. 정책: category_code='Healthy'→무조건 READY, category_code='BEAUTY'→한국어+영어 COSMETIC_KEYWORDS/IRRELEVANT_HINTS 매칭(미매칭 시 기본 FILTERED). 30건 dry-run 기준 사용자 승인 라벨과 대체로 일치. 단, 상품유형 키워드가 없는 BEAUTY title edge case 1건은 기본 FILTERED 정책상 known limitation으로 승인됨. Canary 편집 후 launcher 재시작 중 중복 이슈 발생/정리 완료. Runtime Proof: D001(BEAUTY) fetch=10 ready=2, D002(Healthy) fetch=10 ready=10 — 정책대로 정상 동작 확인. DEFER: 키워드 보강(팩/패치/시트/수분/진정/미백/주름/피부 등), UNKNOWN 3단계 상태 도입 검토(READY/FILTERED만 저장하는 현 구조 제약), FILTERED 로그 별도 저장. commit/push 별도 승인 필요. |
| launcher_duplicate_instance_cleanup_260706 | ERR-048/FP-036/INC-026 등록. 세션 중 수동 반복 기동으로 launcher/main.py 5세대(10프로세스) 동시 생존 발견 → 8개 `Stop-Process -Force` 정리 + 단일 인스턴스(PID 33148/6140) 재기동, app.log상 스케줄러 1세트 정상 등록 확인. PID 20448/5284(전날 기동, Access denied)와 `:5000` 유령 LISTENING PID 32944(프로세스 열거 도구에 미포착)는 비관리자 권한으로 종료/식별 불가하여 미해결 — PARTIAL. |
| watchdog_task_wrapper_260708 | wrapper 경유 Task 트리거 시 direct(60초 내 사망)보다 오래 생존(1h46m, 정상 heartbeat 지속) — 이중 감시 정리 위해 의도적 종료(크래시 아님). 재부팅 자동 트리거 실증 완료(260709) — Task Action 발동 확인되나 wrapper 4분 24초 만에 silent death, 근본원인 UNKNOWN(ERR-047 Note 2 / ERR-050 Note 3 / INC-025 Note 교차참조) |
