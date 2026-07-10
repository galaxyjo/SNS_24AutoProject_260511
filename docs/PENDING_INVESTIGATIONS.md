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
