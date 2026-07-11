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

---
