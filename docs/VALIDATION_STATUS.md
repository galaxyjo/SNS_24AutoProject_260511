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
| inc028_1st_shutdown_root_cause_confirmed | ✅ PASS | 2026-07-10 |
| heartbeat_wake_to_run_applied | 🟡 PARTIAL | 2026-07-10 |
| pending_a_session0_adspower_verified | ✅ PASS | 2026-07-10 |
| testabd_diagnostic_tasks_disabled | ✅ PASS | 2026-07-10 |
| nssm_dual_watchdog_resolved_260711 | ✅ PASS | 2026-07-11 |
| nssm_crash_restart_verified_260711 | ✅ PASS | 2026-07-11 |
| nssm_reboot_proof_260711 | ✅ PASS | 2026-07-11 |
| ngrok_localsystem_fix_260711 | ✅ PASS | 2026-07-11 |
| training_review_grid_50batch_260712 | 🟡 PARTIAL(조건부 종결) | 2026-07-12 |
| training_review_verification_error_fix_260712 | ✅ PASS | 2026-07-12 |

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
| inc028_1st_shutdown_root_cause_confirmed | INC-028 Note 3 / ERR-047 Note 5 — User32 Id=1074(20:09:52, StartMenuExperienceHost.exe 명의 종료 개시) → Kernel-Power/Kernel-General 종료 시퀀스(20:10:53 확정) raw 확인. Modern Standby(Id=506/507 공백 2시간1분 확인)·Windows Update·명시적 로그오프 전부 배제. 사람의 조작 가능성은 Hypothesis(확정 아님)로 남김. |
| heartbeat_wake_to_run_applied | ERR-053/FP-040 — `SNS_HeartbeatMonitor_Independent` Task `WakeToRun=False→True` 변경 적용(Settings 나머지 필드 불변 확인). 실제 Modern Standby 구간에서 heartbeat_monitor.log가 이어지는지 실증은 미완료 — PARTIAL 판정. |
| pending_a_session0_adspower_verified | `docs/PENDING_INVESTIGATIONS.md` PENDING-A — 진단 Task `SNS_DIAG_AdsPowerSession0Test`(LogonType S4U)로 AdsPower Local API 호출, `code=0`+`debug_port` 확인(SUCCESS). Task는 결과 확인 직후 Unregister로 제거, 재조회로 목록에서 사라짐 확인. |
| testabd_diagnostic_tasks_disabled | ERR-051 Note(260710) — `SNS_WatchdogAB_TestA/TestB/TestD` 3개 전부 `Disable-ScheduledTask`로 State: Ready→Disabled 확인(관리자 권한 재시도로 성공). 삭제 아님, 증거 보전 목적 유지. |
| watchdog_wakeup_applied_260710 | ERR-054/FP-040 — `SNS_Watchdog_AutoStart` Task `WakeToRun=False→True` 변경 적용(1차 비관리자 시도 Access denied 실패 → 2차 관리자 권한 성공). XML diff(WakeToRun 라인 1개만 변경)·taskinfo diff(LastRunTime/LastTaskResult 완전 동일)로 다른 필드 리셋 없음과 예약 인스턴스 영향 없음 실증 — PASS(설정 적용 + 무결성 확인 완료 기준). `heartbeat_wake_to_run_applied`와 달리 이 Task는 애초에 반복 트리거 절전 재현 검증 대상이 아니므로(로그온 1회성 트리거 구조), 실제 Modern Standby 상황에서의 효과 검증은 범위 외 — 절전 실증 완료로 과다 해석 금지. |
| backup_15_verified_260711 | ERR-055 — backup(14)(9.14MB, 크기 이상) 재검증 후 launcher/dashboard/n8n 전부 정지 → backup(15) 재생성(174,715KB, backup(13) 172MB와 동일 정상범위) + sha256 해시 생성 확인 — PASS. backup(14).zip은 삭제하지 않고 보존(증거 목적, 삭제 여부 별도 판단). |
| nssm_dual_watchdog_resolved_260711 | ERR-057/FP-042/INC-030 — NSSM 서비스(`SNS_Watchdog`)와 구 Task(`SNS_Watchdog_AutoStart`)가 watchdog.ps1을 이중 실행 중임을 프로세스 부모-자식 체인(PID 13008 vs 27664→28548)으로 확인. 관리자 권한으로 `Disable-ScheduledTask` 실행 → `schtasks /V`로 `Scheduled Task State: Disabled` 확인, 이미 떠 있던 구버전 PID 27664/28548을 `Stop-Process -Force`로 종료 → 재조회로 소멸 확인. NSSM 서비스(PID 13008) 단독 운영 전환, Flask(:5000)/Streamlit(:8501)/ngrok(:4040) 전부 영향 없이 LISTENING 유지 — PASS. |
| nssm_crash_restart_verified_260711 | PENDING-A 크래시 재시작 실증 — 관리자 권한으로 NSSM 관리 watchdog.ps1(PID 13008)을 `Stop-Process -Force`로 강제 종료(11:54:58) → NSSM이 `AppRestartDelay=60000ms` 설정대로 자동 재기동(`watchdog.log` 새 시작 배너 11:56:35 확인, 약 97초 후) → 재기동된 watchdog.ps1이 Streamlit까지 자체 정상화(PID 18048→31652), Flask `/health` HTTP 200 확인. 수동 개입 없이 완전 자동 복구 — PASS. 재부팅 실증은 별도 트랙으로 미실시. |
| nssm_reboot_proof_260711 | PENDING-A 재부팅 실증(잔여 트랙) — 사용자가 실제 재부팅 진행(12:09) 후 `Get-Service SNS_Watchdog` → `Running/Automatic` 자동 기동 확인, `watchdog.log`에 `===== watchdog 시작 =====` 배너가 이번엔 **1번만**(12:08:11) 기록됨(오늘 첫 재부팅 시 09:07:02/09:07:58 2번 기록됐던 것과 대비) — 구 Task 비활성화가 재부팅 전반에 걸쳐 유지됨을 실증. PASS로 PENDING-A(NSSM 서비스 전환) 완전 종결. |
| ngrok_localsystem_fix_260711 | ERR-058/FP-043/INC-031 — NSSM(LocalSystem) 전환으로 드러난 ngrok 이중 실패(MSIX 실행 불가 + authtoken 프로필 분리) 해결. `watchdog.ps1` `$NGROK_EXE` 포터블 경로 도입 + 사용자가 관리자 권한으로 authtoken(`ngrok.yml`)을 LocalSystem 프로필에 복사 → `Restart-Service` 후 12:35:48 `[RECOVER] Ngrok 복구` 확인, `/api/tunnels` 조회로 `public_url=https://danuta-overdramatic-whirly.ngrok-free.dev` 정상 응답 — PASS. |
| training_review_grid_50batch_260712 | ERR-059/INC-032 — 실제 50건 배치 저장이 GET 재검증 오탐으로 "실패" 표시됨. 47/50건 직접 재조회로 42 BLOCK+5 PASS 정확 저장 확인(3건 UNKNOWN). 오류 이후 브라우저 새로고침으로 원본 선택 세션 유실 — Airtable 현재값 역산은 자기 자신과 비교하는 무의미한 검증이라 판단해 완전 재검증 불가. 확보 증거로 **조건부 종결**, 신규 20건 배치부터 수정된 파이프라인으로 재개. |
| training_review_verification_error_fix_260712 | ERR-059/FP-044 — `review_batch_committer.py`에 `VerificationError`(status_code/error_type 보존) 신설, `mismatched_ids`(진짜 값 불일치)와 분리. `repository_interface.py`/`airtable_repository.py`에 status_code/Retry-After/original_error_type 전달 추가. 429는 Retry-After 기반, 5xx·타임아웃은 지수 백오프(최대 3회) 재시도, 403·404·기타는 즉시 처리(재시도 없음). `actual is None`(404 계약)을 `_verify_one()` 공통 헬퍼로 3개 함수(commit/undo/verify_only) 모두 동일하게 verification_errors로 분리(1차 수정 누락분, Codex 재검토로 발견 후 수정). `verify_only(repo, expected)` 신규(PATCH 없음). UI: verification_errors 시 확정 버튼 disabled + 새 배치 시 자동 해제. FakeRepo/mock 테스트 총 191 passed(4 failed는 기존 무관 `test_dm_close.py`) — PASS. |
| nssm_service_rebuild_260712 | ERR-060/FP-045/INC-033 — NSSM 서비스(`SNS_Watchdog`) 본체가 260711 23:08:47 예기치 않게 종료(원인 UNKNOWN), 등록된 `nssm.exe` 실행파일도 디스크에서 소실 확인. 고아 프로세스(3세대) 정리 → `choco install nssm -y --force`로 실행파일 복구했으나 서비스 등록 자체가 손상되어(`nssm get` 조회조차 실패) 재시작 불가 → `nssm remove`+`nssm install`로 서비스 완전 재생성(Application/AppParameters/AppExit/AppRestartDelay 동일 설정 복원) + `sc.exe failure`로 서비스 본체 크래시 복구 옵션 신규 추가 → `Get-Service` Running/Automatic, `sc.exe qfailure` SUCCESS, watchdog.log 새 시작 배너, Flask/Streamlit/ngrok 동일 PID 무중단 유지 확인 — PASS. 원인 규명은 git/chocolatey.log/Defender 탐지 로그 전부 조회했으나 인과관계 있는 흔적 없어 UNKNOWN으로 기록. |
| gate_c_price_safety_260713 | ERR-061/FP-046/INC-034 — `PRICE_AUTO_REPLY_ENABLED` 플래그(기본 `false`) 도입, 상품 미확정 시 가격 대신 상품확인 요청으로 대체, 발송실패·예외 시 `bridge_status` 오갱신·팔로업 오예약 방지, Telegram PII마스킹(신규 `send_telegram_price_pending()` 알림에만 적용 — 기존 `dm_receiver.send_telegram()` 노출은 미해결, P0-1 대상), `(sender_igsid, 정규화된 문의문)` 키 + `threading.Lock` 기반 원자적 임시 중복방지(Airtable 스키마 변경 없음, 3분 TTL, 실패·예외 시 선점 해제). **Claude 로컬 실행: `pytest tests/test_dm_rules.py` 30 passed**(신규 8건: 팔로업오발송방지/발송실패상태보호/Telegram마스킹/dedup 동일문의차단·다른문의허용·실패시해제·예외시해제·동시성 Lock). **Codex는 정적 코드감사로 PASS(테스트 직접 실행 안 함), 4라운드 재검토 거침.** 변경 3파일(`modules/dm/dm_auto_reply.py`/`.env.example`/`tests/test_dm_rules.py`), 432 insertions(+) / 24 deletions(-). **코드 구현·테스트 완료, 커밋 `c1c90b2`.** 260714 10:18 launcher 재시작(watchdog 자동복구 경유) + 10:24:41 통제된 Canary(로컬 웹훅 시뮬레이션)로 **가격 자동발송 차단 PASS 확정**(앱 로그 대조로 팔로업 오예약·bridge_status 오갱신 없음도 확인). **단 Canary가 가짜 IGSID였던 관계로 실제 IG 안내문 발송 성공·신규 `send_telegram_price_pending()` 마스킹은 E2E PARTIAL(미확인)** — 기존 `dm_receiver.send_telegram()` PII 노출(P0-1)은 이번 범위 밖, 계속 OPEN. |
