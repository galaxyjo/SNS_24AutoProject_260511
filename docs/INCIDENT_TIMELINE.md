# INCIDENT_TIMELINE.md
> Generated: 2026-05-16 | Status: ACTIVE | Version: v1.1
> Scope: SNS_24AutoProject

---

## PURPOSE
프로젝트 전체 운영 중 발생한 주요 Incident 기록.
목적: 원인 추적 / 구조 Drift 추적 / 재발 방지

---

## INC-001 | Disk Loss / Environment Migration
**발생:** 2025-05
**요약:** 기존 개발 노트북 환경 손실. 신규 환경 복구 시작.
**영향:** 환경 초기화 / Runtime mismatch / package drift
**해결:** 신규 환경 구축 / PowerShell 기준 통합 / Python 3.10.11 고정
**재발 방지:** 환경 snapshot 정책 도입

---

## INC-002 | Duplicate Module Drift
**발생:** 2025-07
**요약:** 실행되는 account_runner.py와 수정한 파일이 서로 달랐음
**영향:** 수정이 반영 안 됨 / 디버깅 시간 낭비
**해결:** sys.path.insert 적용 / __pycache__ 제거 / absolute path 고정
**재발 방지:** FP-010 등록 / Source of Truth 1개 원칙

---

## INC-003 | Coverage Illusion
**발생:** 2025-08
**요약:** Coverage PASS인데 실제 Runtime 불안정
**영향:** 테스트 신뢰도 하락
**해결:** Runtime-first 기준 적용 / 실제 flow 검증 강화
**재발 방지:** FP-003 Ghost Success 등록

---

## INC-004 | Instagram Runtime Instability
**발생:** 2025-10
**요약:** Instagram Upload 단계 반복 실패
**근본 원인:** UI State mismatch / Selenium attach instability / popup state mismatch
**해결:** UI state validation 도입 / sequential load 적용 / nav existence check 추가
**재발 방지:** FP-008 UI State Assumption 등록

---

## INC-005 | sys.path 오염 누적
**발생:** 2025-11
**요약:** sys.path.insert 임시패치 누적으로 import 경로 불확정
**영향:** 어느 파일이 실행되는지 모르는 상태
**해결:** absolute path 전환 / sys.path 패치 제거
**재발 방지:** FP-006 등록 / ARCHITECTURE_LOCK sys.path 금지 추가

---

## INC-006 | DB Schema Mismatch
**발생:** 2025-12
**요약:** post_id 컬럼 없음 오류 / OperationalError 반복
**근본 원인:** schema 변경 후 migration 미적용
**해결:** ALTER TABLE / init_db sync
**재발 방지:** FP-009 등록 / schema_governance.md 작성

---

## INC-007 | Multi-Repo Structure Confusion
**발생:** 2026-05-11 ~ 2026-05-16
**요약:** 250723 / 260511 두 저장소 역할 미확정으로 동시 수정 발생
**영향:** Drift 폭발 위험 / import 혼재
**해결:** ARCHITECTURE_LOCK.md 선언 / 260511 = SOURCE OF TRUTH 확정
**재발 방지:** merge_policy.md / MASTERTREE_CONTRACT.md 작성

---

## INC-008 | Documentation Hallucination
**발생:** 2026-05-16
**요약:** 완료 선언된 문서 7개가 실제 filesystem에 존재하지 않음 발견
**영향:** 운영 혼선 / Phase 1 완료 조건 미충족
**근본 원인:** AI 텍스트 출력 = 실제 파일 생성으로 오인
**해결:** Evidence-based verification 의무화 / 실제 파일 생성 후 Get-ChildItem 확인
**재발 방지:** FP-001 / FP-005 / FP-013 등록 / 완료 선언 기준 고정

---

## INC-009 | Launcher 2일 중단
**발생:** 2026-05-15 ~ 2026-05-17
**요약:** `main.py` 미실행으로 크롤링/업로드 전면 중단. `crawl_stats.db` 마지막 기록 2026-05-15 15:24 확인으로 발견.
**영향:** FB 크롤링 / Instagram 업로드 / KPI 수집 / engagement 업데이트 전면 중단
**해결:** launcher 재기동 (`python launcher/main.py`) 후 크롤→Airtable 저장 확인
**재발 방지:** watchdog.ps1 상시 실행 / FP-014 등록

---

## LESSONS LEARNED
```
1. 텍스트는 증거가 아니다
2. Runtime만 신뢰
3. Git 없는 완료는 완료 아님
4. Evidence 없는 PASS 금지
5. AI 출력 = 실제 실행 아님
```
