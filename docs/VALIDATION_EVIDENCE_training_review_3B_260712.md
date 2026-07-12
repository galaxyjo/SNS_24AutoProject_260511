# 학습 리뷰 그리드 3B 단계 — 실제 Airtable 실증 증거 (260712)

## 범위

`Training_Review_Queue` 테이블에 전용 TEST 레코드 5건만 생성해서, 실제 Airtable에 대해
`commit_batch_with_verification()` / `undo_batch_with_verification()` (3A/3B에서 구현,
FakeRepo로 사전 검증 완료)가 진짜로 저장·GET 재검증·실행취소까지 정확히 동작하는지 확인.
운영 레코드는 전혀 대상에 포함하지 않음. 토큰/API 키는 이 문서에 포함하지 않음.

## 사전 확인 (읽기 전용)

- `candidate_id`/`search_query`/`source_platform`/`other_note`/`target_id_ref`에 "TEST"가
  포함된 기존 레코드 조회 → **0건** (전용 테스트 레코드 없음 확인 후 생성 진행)

## 테스트 레코드 5건

| candidate_id | record_id |
|---|---|
| TEST_VALIDATION_260712_1 | reccbyZKW4NfpYtyg |
| TEST_VALIDATION_260712_2 | recdGsj6uVwBcnplH |
| TEST_VALIDATION_260712_3 | rec02wUrurAyILANM |
| TEST_VALIDATION_260712_4 | recGoULtDO7sdIZxD |
| TEST_VALIDATION_260712_5 | reckmiewyfSXdgqiW |

`search_query="TEST_3B_VALIDATION_260712"`, `image_url="https://via.placeholder.com/300"`,
`source_platform`/`target_id_ref` 미설정. `review_status` 기본값 PENDING.

## 단계별 실행 결과 (raw)

### 1. 생성 (POST × 5)
전부 성공. record_id 5건 확보 (위 표).

### 2. 사전 GET × 5 (PENDING 확인)
```
reccbyZKW4NfpYtyg -> PENDING
recdGsj6uVwBcnplH -> PENDING
rec02wUrurAyILANM -> PENDING
recGoULtDO7sdIZxD -> PENDING
reckmiewyfSXdgqiW -> PENDING
```

### 3. 저장 — `commit_batch_with_verification(repo, batch_ids=[5건], block_ids=[앞 2건])`
```
committed: True
saved_ids: [reccbyZKW4NfpYtyg, recdGsj6uVwBcnplH, rec02wUrurAyILANM, recGoULtDO7sdIZxD, reckmiewyfSXdgqiW]
failed_id: None
verified: True
mismatched_ids: []
```

### 4. GET × 5 재검증
```
reccbyZKW4NfpYtyg -> BLOCK (기대값 BLOCK)
recdGsj6uVwBcnplH -> BLOCK (기대값 BLOCK)
rec02wUrurAyILANM -> PASS (기대값 PASS)
recGoULtDO7sdIZxD -> PASS (기대값 PASS)
reckmiewyfSXdgqiW -> PASS (기대값 PASS)
```
전부 기대값과 일치.

### 5. 실행취소 — `undo_batch_with_verification(repo, record_ids=[5건])`
```
committed: True
reverted_ids: [reccbyZKW4NfpYtyg, recdGsj6uVwBcnplH, rec02wUrurAyILANM, recGoULtDO7sdIZxD, reckmiewyfSXdgqiW]
failed_id: None
verified: True
mismatched_ids: []
```

### 6. GET × 5 재검증 (PENDING 복원 확인)
```
reccbyZKW4NfpYtyg -> PENDING
recdGsj6uVwBcnplH -> PENDING
rec02wUrurAyILANM -> PENDING
recGoULtDO7sdIZxD -> PENDING
reckmiewyfSXdgqiW -> PENDING
```

### 7. 삭제 (DELETE × 5)
```
DELETE reccbyZKW4NfpYtyg -> HTTP 200
DELETE recdGsj6uVwBcnplH -> HTTP 200
DELETE rec02wUrurAyILANM -> HTTP 200
DELETE recGoULtDO7sdIZxD -> HTTP 200
DELETE reckmiewyfSXdgqiW -> HTTP 200
```

### 8. 삭제 후 GET × 5
```
GET reccbyZKW4NfpYtyg -> HTTP 403 INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND
GET recdGsj6uVwBcnplH -> HTTP 403 INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND
GET rec02wUrurAyILANM -> HTTP 403 INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND
GET recGoULtDO7sdIZxD -> HTTP 403 INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND
GET reckmiewyfSXdgqiW -> HTTP 403 INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND
```

**403 원인: UNKNOWN.** 최초 보고에서 "Airtable이 삭제된 레코드에 대해 보안상 의도적으로 403을
반환한다"고 단정했으나, Airtable 공식 문서(403 = "권한 없음 또는 리소스를 찾지 못함")에서
"삭제된 레코드는 반드시 403을 반환한다"는 구체적 근거를 확인할 수 없어 Codex 검토에서
과도한 단정으로 지적받고 정정함. 403 자체가 삭제의 직접 증거는 아니며, 아래 재조회 결과가
삭제의 실질 증거임.

### 사후 확인 (읽기 전용) — TEST 표시 레코드 재조회
"TEST" 포함 레코드 재조회 → **0건**. DELETE 응답 HTTP 200 5건 + 이 재조회 결과를 근거로
5건 전부 삭제됨으로 판정.

## 최종 판정

| 항목 | 판정 |
|---|---|
| 저장(commit) + GET 검증 | PASS |
| 실행취소(undo) + GET 검증 | PASS |
| 삭제(DELETE) + 재조회 확인 | PASS (DELETE 200 + TEST 재조회 0건 근거) |
| 403 원인 설명 | UNKNOWN (최초 단정 정정) |
| 전체 3B 실증 | 조건부 PASS |

운영 레코드는 이 실증 과정에서 전혀 조회·수정·삭제되지 않음. 실제 50건 배치 연결은
별도 승인 전까지 보류.
