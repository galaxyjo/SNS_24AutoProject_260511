# PENDING_INVESTIGATIONS.md

> 아직 결론이 나지 않은 조사/검토 항목을 추적하는 문서. `ERROR_DATABASE.md`/`FAILURE_PATTERN.md`/`INCIDENT_TIMELINE.md`와 달리, 확정된 오류·패턴·사고가 아니라 "결정을 위해 조사 중인 사안"을 다룬다.

---

## PENDING-A | watchdog.ps1 / heartbeat_monitor.py의 NSSM(Windows 서비스) 전환 검토

**상태:** 결론남

**배경:** ERR-053/FP-040(heartbeat_monitor.py가 Task Scheduler 반복 트리거 + `WakeToRun=False`로 인해 Modern Standby 중 71회 미실행)을 계기로, watchdog.ps1/heartbeat_monitor.py를 Task Scheduler 대신 NSSM 기반 Windows 서비스로 전환하는 방안을 검토함.

**조사 근거:**
- `FP-040` Prevention (2)에 "상시 루프 프로세스 방식을 반복 트리거 방식보다 우선 검토"라는 근거가 이미 명시되어 있음을 확인
- WebSearch: Task Scheduler는 시스템이 예정 시각에 사용 불가 상태면 조용히 건너뛰는 사례가 일반적으로 보고됨(ERR-053/FP-040과 일치하는 일반 현상). NSSM은 SCM에 등록되는 실제 서비스로 로그온 여부와 무관하게 지속 실행되고 크래시 시 자동 재시작을 지원 — 단 "Modern Standby 자체를 서비스가 완전히 이겨낸다"는 근거는 검색 결과에서 확인되지 않음
- `modules/sns/facebook_crawler.py` 코드 분석: `start_browser()`/`stop_browser()`는 subprocess/GUI 조작 없이 AdsPower Local API(`http://local.adspower.net:50325`)를 순수 HTTP 호출만 함 — 코드 자체는 Session 0(비대화형)에서도 실행 가능한 구조.

**실증 (2026-07-10, raw):**
1회성 진단 Task `SNS_DIAG_AdsPowerSession0Test`를 `LogonType S4U`(로그온 없이도 실행, Session 0 상당)로 등록해 AdsPower Local API를 호출:
- `Get-ScheduledTaskInfo` → `LastTaskResult: 0`, `LastRunTime: 2026-07-10 17:16:10`
- 로그(`_diag_adspower_session0_260710.log`):
  ```
  [2026-07-10 17:16:11] START_RESPONSE: {"code":0,"msg":"success","data":{"ws":{"puppeteer":"ws://127.0.0.1:51265/devtools/browser/73e398e8-c4dc-4f2b-bf4d-c05e66bb8e2e","selenium":"127.0.0.1:51265"},"debug_port":"51265","webdriver":"C:\\Users\\admin\\AppData\\Roaming\\adspower_global\\cwd_global\\chrome_144\\chromedriver.exe"}}
  [2026-07-10 17:16:11] RESULT: SUCCESS (code=0, debug_port=51265)
  [2026-07-10 17:16:11] STOP_RESPONSE: {"code":0,"msg":"success"}
  ```
- 사전 정의한 판정 기준("HTTP 200 + `code:0` + `debug_port` 값 존재")을 그대로 충족 — **SUCCESS**
- 진단 Task는 결과 확인 직후 `Unregister-ScheduledTask`로 제거, 재조회로 목록에서 사라졌음을 확인(`CONFIRMED REMOVED`)

**결론:** AdsPower Local API는 비대화형(Session 0/S4U) 컨텍스트에서도 정상 응답함이 raw로 확인됨. 이전에 UNKNOWN으로 남겨뒀던 "AdsPower 데몬이 Session 0에서 응답하는가"라는 리스크가 해소됐으므로, **PENDING-A(NSSM/서비스 전환)는 이 축에서는 재상정 가능** — 단, 이번 실증은 "AdsPower Local API 응답성"만 확인한 것이며, watchdog.ps1/heartbeat_monitor.py 전체를 실제 NSSM 서비스로 전환·운영하는 것 자체의 실증(설치, 권한, 로그 리다이렉션, 크래시 재시작 등)은 별도 트랙으로 남음 — 전환 여부 최종 결정과 실제 구현은 사용자 승인 후 별도 진행.

**관련:** ERR-053, FP-040

---

**[2026-07-11 추가 Note — 실제 전환 진행 상태 + 크래시 재시작 실증 완료]:**
세션 재개 중 NSSM 서비스(`SNS_Watchdog`)가 이미 설치되어 `Automatic` 시작으로 Running 상태였음을 발견(설치 시점/주체는 세션 기록에 없어 UNKNOWN) — 단 구 Task(`SNS_Watchdog_AutoStart`) 비활성화가 누락되어 이중 실행 중이던 문제를 ERR-057/FP-042/INC-030으로 별도 등록·해소(관리자 권한으로 `Disable-ScheduledTask` + 구 PID `Stop-Process`).

이어서 **크래시 재시작 실증**을 진행: 관리자 PowerShell에서 NSSM이 띄운 watchdog.ps1(PID 13008)을 `Stop-Process -Force`로 강제 종료 → 11:54:58 종료 확인 → 11:56:35 NSSM이 자동으로 새 watchdog.ps1 인스턴스 기동(`watchdog.log`에 새 시작 배너 확인, `AppRestartDelay=60000ms` 설정과 일치하는 타이밍) → 재기동된 watchdog.ps1이 자체 헬스체크로 Streamlit까지 함께 정상화(PID 18048→31652) → Flask(`/health` HTTP 200)/Streamlit/ngrok/NSSM 서비스 전부 수동 개입 없이 정상 복구 확인 — **PASS**.

**남은 트랙:** 재부팅 실증(실제 OS reboot 후 NSSM 서비스만 단독으로 정상 기동하는지 확인)은 아직 미실시 — 사용자 편한 시점에 별도 진행 예정.

**관련(추가):** ERR-057, FP-042, INC-030

**[2026-07-11 추가 Note 2 — 재부팅 실증 PASS, PENDING-A 완전 종결]:**

사용자가 실제 재부팅 진행(12:09) → `Get-Service SNS_Watchdog` `Running/Automatic` 자동 기동 확인, `watchdog.log` 시작 배너 1번만 기록(12:08:11, 구 Task 재발 없음) — PASS. **PENDING-A 트랙 완전 종결.** 상세는 ERR-057 참조.

부수적으로 실행 계정(admin→LocalSystem) 전환의 부작용으로 ngrok 실행 결함(ERR-058)이 드러나 같은 세션에서 해소 완료 — FP-043 신규 등록.

**관련(추가 2):** ERR-057, ERR-058, FP-043, INC-030, INC-031

---

## PENDING-B | ERR-047/050/051/INC-028 계열 — watchdog NSSM 전환(PENDING-A) 이후 잔여 미해결 항목 재평가

**상태:** 결론남 (재평가 완료, 개별 항목 처리방침 확정)

**배경:** 외부 감사 테이블(사용자 제공, 260711)에 ERR-047/050/051/INC-028 관련 다수 항목이 미완료/보류로 남아있었음. 이 테이블은 PENDING-A(NSSM 전환) 완료 이전 시점 기준이라, 전환 이후에도 여전히 유효한 항목과 더 이상 유효하지 않은(대상 메커니즘 자체가 폐기된) 항목이 섞여 있어 재평가 필요.

**재평가 결과:**

| 항목 | 이전 상태 | 재평가 | 근거 |
|---|---|---|---|
| watchdog Windows Service 등록 | 🔴 미완료 | 🟢 완료 | ERR-057/058, PENDING-A 재부팅 실증 PASS |
| ERR-047 Root Cause(재부팅 후 생존 경로) | 🔴 미완료 | 🟢 구조적 해소(Moot) | ERR-047 Note 6 — 대상 메커니즘(Task Scheduler) 폐기 |
| Streamlit 완전 재시작 Proof | 🔴 미완료 | 🟢 완료 | 크래시 재시작 실증 중 watchdog이 Streamlit도 자동 복구(PID 18048→31652) 직접 관측 |
| INC-028 1차 다운 Root Cause | 🔴 미완료 | 🟢 완료(260710) | INC-028 Note 3 — 실제 OS shutdown 확정(사람 조작 여부만 Hypothesis 잔존). 이 감사 테이블이 260710 이전 시점 기준이라 미반영됐던 것으로 추정 |
| watchdog 2차 다운 복구 증명 | 🟠 진행중 | 🟡 실효성 낮음(재분류) | 대상이 옛 Task 기반 watchdog — 메커니즘 폐기로 이 특정 증거의 추가 조사 실익 낮음. NSSM 기준 신규 증거(크래시+재부팅 실증)로 사실상 대체 |
| ERR-050 Root Cause(silent death) | 🔴 미완료 | 🟢 구조적 해소(Moot) | ERR-050 Note 5 — wrapper 방식 자체 폐기 |
| 운영 Task XML vs 실패 Task XML diff | 🔴 미완료 | 🟡 Moot(낮은 우선순위) | 대상 메커니즘 폐기로 비교 실익 낮음. 완전 폐기 선언은 아니고, 필요시(다른 Task 이슈)엔 재사용 가능한 기법이라 낮은 우선순위로만 하향 |
| Task Scheduler 서비스 재시작(보류) | 🟡 보류 | 🟡 리스크 완화(보류 유지) | watchdog은 더 이상 Task Scheduler 의존 안 함 — "운영 감시 영향" 우려가 watchdog 기준으로는 해소, 단 heartbeat_monitor.py/TestA·B·D 등 다른 Task엔 여전히 해당되어 보류 유지 |
| ERR-051 Root Cause(Queued 고착) | 🔴 미완료 | 🔴 유지 | Test 진단 Task 자체 이슈로 오늘 조치와 무관, 낮은 우선순위로 계속 보류 |
| down/unknown 분기 Runtime Proof | 🔴 미완료 | 🔴 유지 | health_monitor.py 로직 검증 이슈, 오늘 조치와 무관 |
| Bookending 운영 규칙(강제 구조) | 🔴 미완료 | 🔴 유지 | CLAUDE.md에 원칙은 문서화됨(260710), 강제하는 자동화 구조는 없음 — 낮은 우선순위 |
| untracked 파일 정리 | 🔴 미완료 | 🔴 유지 | 사용자 결정 필요, 오늘 미다룸 |
| TestA/B/D 진단 Task 정리 | 🔴 미완료 | 🔴 유지(긴급도 하향) | Disabled 상태로 증거 보존 중, 삭제 여부는 여전히 사용자 결정 필요하나 근본원인(watchdog NSSM화)이 해소돼 긴급도는 낮아짐 |
| 4688 Process Creation 감사 | 🟡 보류 | 🟡 유지 | 오늘 조치와 무관 |
| Windows 업데이트/패치 조사 | 🟡 보류 | 🟡 유지 | 오늘 조치와 무관 |
| 250723 저장소 장기 처리 | 🟡 보류 | 🟡 유지 | 오늘 조치와 무관, 별도 사용자 결정 필요 |

**갱신된 우선순위(260711 기준):**
1. 운영 정리 — untracked 파일/TestA·B·D 삭제 여부/250723 장기 처리 (사용자 결정 필요)
2. heartbeat_monitor.py 실제 Modern Standby 구간 실증 검증 (watchdog.ps1과 별개 트랙, 유일하게 남은 절전 관련 미검증 항목)
3. n8n 반복 실패 알림 정리 (낮은 우선순위, 보류 중)
4. ERR-050/051 등 옛 Task 메커니즘 잔여 조사 — 필요성 낮음, 진행 여부만 판단(권장: 추가 조사 없이 현 상태 유지)

**관련:** PENDING-A, ERR-047(Note 6), ERR-050(Note 5), ERR-057, ERR-058, FP-042, FP-043, INC-028(Note 3), INC-030, INC-031

---
