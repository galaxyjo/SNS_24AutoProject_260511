# 재사용 보충 잡(Reuse Replenisher) 설계 — 261103

작성: Claude Code (설계만, 코드·설정 변경 없음). 상태: 승인 대기.

## 1. 문제
041(YURA) posted 158건을 폴러 4계정(007·014·039·048)이 재사용하기로 확정(261103 "전부 재사용").
지금은 `tools/reassign_041_assets.py --apply`를 사람이 실행해야 `ready`가 채워진다 → 무인 운영 원칙상 A(반복 개입, 결함).
계정당 최대 158건 = 하루 3건 기준 약 52일치이므로, 자동 보충이 있어야 한다.

## 2. 증거
- 폴러 조회 `fetch_pending_posts(limit=50)`는 계정 구분 없이 `ready` 전체에서 50건만 읽는다(`airtable_repository.py:440-452`, `launcher/main.py:810`). 한 번에 `ready`를 많이 넣으면 일부 계정이 앞 50건에 못 들어가 굶는다.
- 폴러 슬롯 Gate는 폴링당 계정 1건, 하루 `min(post_hours 개수, daily_post_limit)`건만 허용한다(`_poller_slot_allowed`).
- 첫 배치 24건 생성에서 이미지 복구(Graph `ig_media_id` → ImgBB)가 실제 동작함(reupload_graph 성공 다수).
- 기존 잡은 `*_ENABLED=false` 기본 플래그 + `sched.add_job` 패턴이다(`launcher/main.py:2977` 등).

## 3. 선택지 (Build / Reuse / Buy)
- **Reuse:** `tools/reassign_041_assets.py`의 후보 선정·이미지 복구·행 생성 로직을 모듈로 옮겨 그대로 쓴다. APScheduler·`handle_errors`·Slack 알림·`retry` 패턴 재사용.
- **Build(작게):** `modules/sns/reuse_replenisher.py`(로직) + launcher에 잡 1개(`_job_reuse_replenish`). 외부도구 불필요.
- **Buy:** 해당 없음(표준 인프라 기능이 아니라 우리 고유 공급 규칙).

## 4. 설계
- **플래그:** `REUSE_REPLENISH_ENABLED`(기본 false), `REUSE_REPLENISH_ACCOUNTS`(쉼표 목록, 초기값 IDN-000007).
- **주기:** 30분마다 1회. `max_instances=1`, `coalesce=True`.
- **목표량:** 계정당 `ready`를 `READY_TARGET=2`건으로 유지한다(부족분만 생성). 전체 `ready`가 `READY_GLOBAL_CAP=40` 이상이면 이번 회차는 생성하지 않는다(50건 조회 한계 방어).
- **후보 선정(무상태):** 원본 = 041 posted 전부, 정렬 = `insta_post_code`. 대상 계정 Airtable 행의 `image_url_hash`에 없는 첫 후보를 쓴다. 별도 커서 불필요.
- **행 규칙:** `account_code_ref`=대상, `post_status=ready`, `data_classification=production`, `canary_run_id` 빈 값, `run_id=R041-AUTO-<yymmdd>`, `insta_post_code=<run_id>-<seq>`. 캡션·해시태그는 041 그대로. Gate 없음.
- **이미지:** `image_url` 정상 → 그대로 / 원본 정상 → ImgBB 재업로드 / 둘 다 불가 → Graph `ig_media_id`로 복구. 복구 실패 후보는 건너뛰고 다음 후보.
- **안전장치(Fail-closed):** 계정 `automation_enabled`가 true가 아니면 생성하지 않는다. 대상은 허용 목록의 계정뿐(041 자신 제외, 슬롯 계정 제외). Graph 토큰 오류(190/459)는 그 회차를 중단하고 Slack 1회 알림.
- **소진:** 어떤 계정에서 후보가 0이 되면 생성을 멈추고 Slack 1회 알림("재사용 자산 소진, 새 크롤 필요").
- **관측:** 회차마다 계정별 `ready 수 / 생성 수 / 복구 실패 수`를 INFO 로그 + `db/reuse_replenish_state.json`(마지막 실행 시각·결과). 이상(연속 실패)은 Slack.

## 4-B. Codex 리뷰 반영 (261103, 1차 조건부 → 수정)
1. **저장소 경계:** 보충기는 Airtable REST를 직접 부르지 않고 `RepositoryInterface`에 추가한 도메인 메서드만 쓴다.
   `count_ready_posts_by_account`, `fetch_reuse_source_posts`, `fetch_image_hashes_for_account`,
   `count_recent_failed_posts_by_run_prefix`(비추상 — 기존 구현체·Fake 무영향, `AirtableRepository`에만 구현).
   게시물 생성은 기존 `save_instagram_post`(계정·분류 검증, API 호출 기록 포함)를 그대로 쓰며 `InstagramPostCreate`에 선택 키 `run_id`만 추가했다.
   계정 Kill Switch는 기존 `get_publish_account().automation_enabled`를 쓴다.
2. **상한의 의미:** `READY_GLOBAL_CAP=40`은 "이 잡이 새로 만드는 양"에 대한 가드다. 기존 backlog나 다른 생산자의 ready를 정리하지 않는다.
   같은 호스트의 중복 실행(수동 실행·이중 launcher)은 OS 파일 잠금(`db/reuse_replenish.lock`, Windows msvcrt / POSIX fcntl)으로 막는다.
   프로세스가 죽으면 OS가 잠금을 자동으로 풀고, 시간 기준 stale 회수와 잠금 파일 삭제는 없다 → 오래 걸리는 살아 있는 실행을 다른 실행이 빼앗지 않는다
   (Codex 2차 지적: 20분 stale 회수 결함 → 수정). 다른 호스트에서 동시에 도는 경우는 범위 밖(단일 호스트 운영 전제).
   Windows 는 비정상 종료된 프로세스의 잠금을 "시스템 자원에 따라 지연되어" 푼다(LockFile 문서). 그래서 비정상 종료 직후 한 회차는 `LOCKED`로 건너뛸 수 있으나
   30분 뒤 회차에서 다시 획득된다(교차 프로세스 테스트로 확인 — 소유 프로세스 강제 종료 후 재획득).
   선택 Repository 메서드를 구현하지 않은 구현체에 연결되면 `NotImplementedError`를 받아 `REPO_UNSUPPORTED`로 중단하고 로그에 남긴다(조용히 넘기지 않음).
3. **게시 실패 반복 시 중단(회로 차단):** 최근 24시간 안에 이 잡이 만든 행(`run_id` 접두 `R041-AUTO`) 중 `failed`가 3건 이상이면 새 글을 만들지 않고 Slack을 하루 1회 보낸다.
   ImgBB 간헐 장애(Meta 9004/2207052)로 자산을 연달아 소모하는 것을 막는다. 근본 원인(호스트 접근성)은 UNKNOWN이며 이 장치는 확산 방지용이다.
   실패한 행은 보존하고 자동 재시도하지 않는다(기존 게시 경로 동작 유지).
   **정확한 의미(Codex 2차 확인):** 집계 기준은 "최근 24시간 안에 *생성된* `R041-AUTO` 행 중 *현재* failed" 건수다 — 실패가 발생한 시각이 아니고,
   오류 코드를 구분하지 않아 ImgBB 외 실패도 합산하며, Meta 9004/2207052 전용이 아니다(오류 코드는 저장소에 보존되지 않는다).
   차단되어도 이미 ready 인 행의 게시 시도는 멈추지 않고 새 행 생성만 중단한다. 실패 시각 기준이 필요해지면 실패 시각 필드를 별도 승인으로 추가한다.

## 5. 가장 작은 테스트 (Single Canary)
1. 단위 테스트: 보충량 계산, 전체 상한, 소진, 이미지 복구 순서, `automation_enabled` 차단 — Airtable·HTTP는 가짜로.
2. Runtime: `REUSE_REPLENISH_ACCOUNTS=IDN-000007` 한 계정만 켜고 하루 관찰(ready가 2로 유지, 슬롯대로 게시, 신규 ERROR 0).
3. 통과 시 4계정 → 이후 신규 폴러 계정 추가는 목록에만 추가.

## 6. 원복
`REUSE_REPLENISH_ENABLED=false` 후 launcher 재시작. 이미 만든 행은 `run_id`가 `R041-AUTO-`로 시작하는 `ready` 행을 `rejected`로 변경. 코드는 커밋 단위 `git revert`.

## 7. 리뷰·승인 경로
Runtime/스케줄러 변경이라 High-Risk: Claude 구현 → Codex 리뷰 → GPT 구조 점검 → Runtime 검증. 코드 수정·`.env` 플래그 변경·launcher 재시작(관리자)은 각각 별도 승인.

## 8. 회장 결정 필요
1. `READY_TARGET=2`, `READY_GLOBAL_CAP=40`으로 시작해도 되는가.
2. 자산 소진 시 "정지 + Slack 알림"으로 충분한가(같은 계정 내 중복 금지라 재순환 불가).
3. 초기 대상 계정은 007 한 개로 시작해도 되는가.
