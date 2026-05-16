# merge_policy.md
> Generated: 2026-05-16 | Status: ACTIVE | Version: v1.1
> ⚠️ GPT 원본의 저장소 역할 오류 수정됨

---

## REPOSITORY 역할 확정
```
260511 = SOURCE OF TRUTH (운영 실행 기준) ← MASTER
250723 = LEGACY ARCHIVE (발굴 전용, 실행 금지)
```
> ⚠️ GPT가 역할을 반대로 출력함. 위 기준이 확정본.

---

## MERGE 기본 원칙
```
- 250723 → 260511 방향만 허용 (역방향 금지)
- 파일 직접 복사 금지
- adapters/legacy_bridge 경유 필수
- One Module One Commit One Test
- rollback snapshot 없는 merge 금지
```

---

## BEFORE MERGE 체크리스트
```
- [ ] diff review 완료
- [ ] duplicate module 없음 확인
- [ ] runtime validation 완료
- [ ] import validation 완료
- [ ] db schema 충돌 없음 확인
- [ ] rollback snapshot 생성 완료
- [ ] MERGE_JOURNAL.md 기록 준비
```

---

## MERGE EXECUTION ORDER
```
1. 250723 대상 모듈 정적 분석 (실행 금지)
2. import/dependency 수동 확인
3. 260511 Contract 기준 인터페이스 정의
4. adapters/legacy_bridge에 wrapper 작성
5. 독립 테스트 (260511 운영 코드 건드리지 않음)
6. 테스트 통과 후 modules/ 정식 편입
7. bridge 제거 or 유지 결정
8. MERGE_JOURNAL.md 기록
9. VALIDATION_STATUS.md 업데이트
```

---

## FORBIDDEN (절대 금지)
```
1. blind overwrite               → 데이터 손실
2. folder copy merge             → Drift 폭발
3. 테스트 없는 merge             → 운영 붕괴
4. 역방향 merge (260511→250723)  → Source of Truth 오염
5. 운영 중 직접 patch             → runtime 불안정
6. Partial merge (일부만)         → 불완전 상태 누적
```

---

## CONFLICT 우선순위
```
1. Runtime success     (실제 실행 기준)
2. DB consistency      (schema 기준)
3. Import stability    (경로 기준)
4. Documentation       (문서 기준)
```

---

## MERGE JOURNAL 기록 의무
모든 이식 작업은 `porting_logs/MERGE_JOURNAL.md`에 기록:
```
| 날짜 | 모듈 | 출처 | 대상 | 결과 | 커밋 |
```

---

## FINAL POLICY
```
실행 성공 Runtime 기준 우선.
텍스트 기준 merge 금지.
Evidence 없는 merge 금지.
```
