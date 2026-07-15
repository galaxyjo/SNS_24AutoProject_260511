# tools/comment_campaign_baseline_cli.py
# 캠페인 게시물 media별 수동 cutover baseline 도구 — FP-047 Package 1 Phase A (260715)
#
# 목적: comment_poll_targets.state를 PENDING_BASELINE → ACTIVE로 옮기는 유일한 합법
# 경로. poller 최초 실행에 자동으로 넣지 않는다(260715 Codex 5차 리뷰 point 1) —
# 정상 첫 배포/DB 삭제 후 재시작/서버 이전/설정 손상 복구/media 추가를 구분할 수
# 없어서, 사람이 media 하나씩 확인하고 명시적으로 실행해야 한다.
#
# 사용법(media_id 1개씩, 안전한 순서 — 260716 Codex 8차 리뷰로 확정):
#   0) 모든 media가 아직 PENDING인 상태에서 COMMENT_POLL_ALLOWLIST_MODE=allowlist로
#      먼저 전환(이 시점엔 ACTIVE media가 0개라 poller가 아무것도 안 함, no-op).
#      캠페인 댓글 실시간 처리가 이 순간부터 잠시 멈춘다는 것을 인지할 것.
#   1) python -m tools.comment_campaign_baseline_cli --media-id <ID> --dry-run
#      → config_hash 출력됨, 이 값을 다음 단계에 그대로 사용
#   2) python -m tools.comment_campaign_baseline_cli --media-id <ID> --apply \
#        --cutover-at 2026-07-16T00:00:00+00:00 --expected-config-hash <dry-run이 출력한 값>
#   3) python -m tools.comment_campaign_baseline_cli --media-id <ID> --verify
#   4) launcher 로그에서 "comment_airtable_record retry handler 등록 완료 →
#      RetryQueue 워커 시작 → 서버 시작 배너" 순서를 직접 확인 후, COMMENT_EVENT_STORE_MODE=
#      enforce로 전환
#   5) python -m tools.comment_campaign_baseline_cli --media-id <ID> --activate \
#        --acknowledge-runtime-proof
#
# 어느 단계든 하나라도 실패하면 다음 단계로 진행하지 않는다(exit code != 0).
# --activate는 COMMENT_POLL_ALLOWLIST_MODE=allowlist AND COMMENT_EVENT_STORE_MODE=
# enforce AND --acknowledge-runtime-proof AND config hash 일치를 전부 만족하지
# 못하면 하드 블록한다(260716 Codex 8차 리뷰 — "두 모드가 켜지기 전엔 ACTIVE가
# 실효과 없다"는 이전 판단이 틀렸음: allowlist+shadow 조합에서 ACTIVE media는
# 다음 폴링 주기부터 바로 실제 발송으로 이어질 수 있다).
#
# 260716 Codex 9차 리뷰 — --acknowledge-runtime-proof는 "증명(proof)"이 아니라
# 운영자의 자기선언(acknowledgement)이다(그래서 플래그명을 confirm→acknowledge로
# 바꿈). 이 CLI 프로세스는 comment_poller→comment_auto_reply→airtable_repository의
# import 체인을 통해 실제로 .env를 load_dotenv(override=True)로 읽어 os.getenv()
# 검사는 그 시점의 .env 내용을 정확히 반영한다(Codex 9차 리뷰가 "CLI는 .env를 안
# 읽는다"고 한 부분은 사실과 다름 — 실제로 읽음, 직접 재현 확인).
# 그러나 이것으로 안전이 "증명"된다고 주장할 수 없는 진짜 이유는 따로 있다: 이미
# 오래전에 기동된 launcher 프로세스는 자기 기동 시점에 읽은 .env 값을 그 프로세스
# 메모리에 그대로 들고 있다 — 그 이후 .env가 바뀌어도 이미 떠 있는 launcher는
# 재시작 전까지 옛 값으로 계속 돈다. 이 CLI가 "지금 .env를 다시 읽어서 맞다"고
# 확인해도, 그게 "이미 떠 있는 launcher가 같은 값으로 돌고 있다"를 보장하진
# 않는다 — PID/기동 세대까지 교차 확인하는 자동 검증(launcher가 시작 시 PID·
# boot_id·event_mode·poll_mode·handler_ready를 DB에 남기고 이 CLI가 그 신선도까지
# 검증)은 Phase C/D 하드닝 과제로 남겨두고, 지금은 운영자가 수동으로 두 프로세스의
# 실제 상태 일치를 확인했다는 선언만 강제한다(그 이상을 주장하지 않음).
# baseline 처리 중에는 Airtable/Telegram/Private Reply를 절대 호출하지 않는다 —
# event_store.suppress_pre_cutover()로 "완료됨"만 직접 기록할 뿐, comment_auto_reply의
# 어떤 함수도 import하지 않는다(설계 불변식, Codex 검증 point 8).

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# 260716 Codex 9차 리뷰 P1 — 이전엔 comment_poller→comment_auto_reply→
# airtable_repository의 import 체인이 우연히 .env를 로드해줬다(그 자체는 사실로
# 확인됐지만, 이 CLI가 정말 os.getenv()로 안전하게 모드를 판단하는지는 이 CLI가
# "명시적으로" 읽는지에 달려있어야지 다른 모듈의 import 순서에 우연히 의존하면
# 안 된다 — 나중에 그 import chain이 리팩터링되며 조용히 깨질 수 있음). 프로젝트
# 관례(modules/infra/airtable_repository.py와 동일 패턴)대로 이 파일도 직접 호출한다.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

from modules.comment import comment_event_store as event_store
from modules.comment import comment_poll_targets as poll_targets
from modules.comment.comment_campaign_config import CampaignConfigError, load_campaign_media_ids
from modules.comment.comment_poller import CommentFetchIncomplete, fetch_all_comments

_EVENT_SOURCE = "instagram_comment"


class BaselineError(Exception):
    """CLI 단계 실패 — 호출부가 exit code 1로 종료해야 함."""


def _parse_created_time(raw: str | None, comment_id: str) -> datetime:
    """Meta Graph API 댓글 timestamp는 '+0000'(콜론 없는 offset) 형식이라
    Python 3.10의 datetime.fromisoformat()이 못 읽는다(3.11+에서야 지원됨) —
    strptime의 %z가 두 형식(+0000/+00:00) 모두 받아들이므로 이걸 우선 사용."""
    if not raw:
        raise BaselineError(f"comment_id={comment_id} timestamp 없음 — baseline 실패(수동 검토 필요)")
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BaselineError(f"comment_id={comment_id} timestamp 파싱 실패({raw!r}) — baseline 실패(수동 검토 필요)") from exc


def _require_campaign_media(media_id: str) -> None:
    try:
        media_ids = load_campaign_media_ids()
    except CampaignConfigError as exc:
        raise BaselineError(f"캠페인 설정 손상: {exc}") from exc
    if media_id not in media_ids:
        raise BaselineError(f"media_id={media_id}는 캠페인 allowlist에 없음 — baseline 대상 아님")


def _hash_ids(ids: list[str]) -> str:
    return hashlib.sha256(",".join(sorted(ids)).encode("utf-8")).hexdigest()


def _classify_existing(status: dict | None) -> str:
    """260715 Codex 6차 리뷰 P0-4 — apply 시점에 comment_events 행이 이미 있을 수
    있다(오늘 세션 내내 shadow 모드로 실사용자 댓글을 관측해왔으므로, 실제 운영
    DB에는 cutover 이전 댓글 다수가 이미 SHADOW_SEEN으로 남아있다). suppress_pre_
    cutover()의 INSERT OR IGNORE는 이런 기존 행을 그냥 건너뛰기만 하고, verify가
    "전부 PRE_CUTOVER_SUPPRESSED여야 한다"고 요구하면 실제 운영에서는 절대 통과할
    수 없다 — 기존 행의 안전성을 먼저 분류해야 한다.
    반환값: 'NEW'(행 없음, suppress 대상) / 'SAFE'(이미 안전하게 처리 완료로 간주
    가능 — SHADOW_SEEN 또는 COMPLETED/PRE_CUTOVER_SUPPRESSED) / 'NEEDS_REVIEW'
    (PROCESSING 중이거나 RETRY_PENDING/UNKNOWN effect 상태 — 자동 처리 금지) /
    'UNSAFE'(위 어느 것도 아닌 인식 못 하는 상태 — fail-closed)."""
    if status is None:
        return "NEW"
    if status.get("migration_tag") in ("SHADOW_SEEN", "PRE_CUTOVER_SUPPRESSED"):
        return "SAFE"
    if status.get("status") == "COMPLETED":
        return "SAFE"
    if status.get("status") == "PROCESSING":
        return "NEEDS_REVIEW"
    if status.get("airtable_status") == "RETRY_PENDING":
        return "NEEDS_REVIEW"
    if status.get("private_reply_status") == "UNKNOWN" or status.get("telegram_status") == "UNKNOWN":
        return "NEEDS_REVIEW"
    return "UNSAFE"


def _current_campaign_config_hash() -> str:
    """poll_targets DB를 건드리지 않고 현재 캠페인 JSON 내용만으로 해시를 계산
    (dry-run이 읽기 전용을 유지하면서도 apply와 비교할 기준값을 낼 수 있게)."""
    return _hash_ids(load_campaign_media_ids())


def _fetch_and_split(media_id: str, cutover_at: datetime) -> tuple[list[dict], list[dict]]:
    """전체 댓글을 조회해 (cutover 이전, cutover 이후)로 분리. 페이지 미완주/조회 실패/
    timestamp 파싱 실패 시 예외를 던져 전체를 실패 처리한다(부분 적용 금지).
    260716 Codex 7차 리뷰 P1: 빈 comment_id는 거부(수동검토), 같은 id가 두 번
    나오면 첫 번째만 채택(페이지 경계 중복으로 건수가 부풀려지는 것 방지)."""
    try:
        comments = fetch_all_comments(media_id)
    except CommentFetchIncomplete as exc:
        raise BaselineError(str(exc)) from exc
    before, after = [], []
    seen_ids: set[str] = set()
    for c in comments:
        cid = c.get("id", "")
        if not cid:
            raise BaselineError(f"media={media_id}: 빈 comment_id를 가진 댓글 발견 — baseline 실패(수동 검토 필요)")
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        created = _parse_created_time(c.get("timestamp"), cid)
        (before if created < cutover_at else after).append(c)
    return before, after


# ── 단계별 커맨드 ────────────────────────────────────────────────────────────

def cmd_dry_run(media_id: str) -> None:
    """260715 Codex 6차 리뷰 P0-3: dry-run은 정말로 읽기 전용이어야 한다 — 이전엔
    sync_from_campaign_json()을 호출해 poll_targets에 PENDING_BASELINE 행을 실제로
    INSERT했다(dry-run 계약 위반). 여기서는 어떤 쓰기 함수도 호출하지 않는다.
    260716 Codex 7차 리뷰 P1: config_hash를 출력 — 운영자가 이 값을 --apply의
    --expected-config-hash로 넘기면, dry-run으로 눈으로 확인한 시점과 실제 apply
    실행 시점 사이에 캠페인 JSON이 바뀌지 않았음을 보장할 수 있다."""
    _require_campaign_media(media_id)
    comments = fetch_all_comments(media_id)
    config_hash = _current_campaign_config_hash()
    print(f"[dry-run] media={media_id} 총 댓글 {len(comments)}건 조회됨(페이지네이션 완주). "
          f"실제 쓰기 없음 — config_hash={config_hash[:12]}... "
          f"(--apply --expected-config-hash {config_hash} 로 드리프트 검증 가능)")


def cmd_apply(media_id: str, cutover_at_str: str, expected_config_hash: str) -> None:
    _require_campaign_media(media_id)
    # 260716 Codex 8차 리뷰 P1: "안전한 실제 순서"는 allowlist 모드를 먼저 켜고(이
    # 시점엔 아직 ACTIVE media가 없어 poller가 아무것도 안 함, no-op) 그 다음
    # baseline을 진행하는 것 — apply 자체를 이 순서 밖에서 실행하지 못하게 막는다.
    # (PENDING media 보호 자체는 이제 flag와 무관하게 항상 걸리지만, 이건 운영
    # 절차를 강제하는 별개의 방어선)
    if not poll_targets.is_allowlist_gating_enabled():
        raise BaselineError(
            "COMMENT_POLL_ALLOWLIST_MODE=allowlist로 먼저 전환한 뒤 apply를 진행하십시오 "
            "(모든 media가 아직 PENDING인 상태에서 켜면 poller는 아무 media도 폴링하지 않아 안전함)"
        )
    if not poll_targets.sync_from_campaign_json():
        raise BaselineError("캠페인 설정 손상 — apply 중단")

    # 260716 Codex 8차 리뷰 P1: --expected-config-hash를 선택 인자로 두면 운영자가
    # 생략할 수 있어 dry-run~apply 드리프트 방어가 무력화된다 — 필수로 강제.
    current_hash = _current_campaign_config_hash()
    if current_hash != expected_config_hash:
        raise BaselineError(
            f"media={media_id}: dry-run 이후 캠페인 설정이 바뀜(dry-run 해시={expected_config_hash[:12]}... "
            f"vs 현재={current_hash[:12]}...) — dry-run부터 재확인 필요"
        )

    try:
        cutover_at = datetime.fromisoformat(cutover_at_str.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BaselineError(f"--cutover-at 파싱 실패: {cutover_at_str!r}") from exc
    if cutover_at.tzinfo is None:
        raise BaselineError("--cutover-at은 timezone-aware UTC 값이어야 함(예: 2026-07-16T00:00:00+00:00)")

    target = poll_targets.get_target(media_id)
    if not target or target["state"] != "PENDING_BASELINE":
        raise BaselineError(f"media={media_id} 상태가 PENDING_BASELINE이 아님(현재={target['state'] if target else 'NONE'}) — apply 불가")

    before, after = _fetch_and_split(media_id, cutover_at)

    # P0-4(260715 Codex 6차 리뷰): 쓰기를 시작하기 전에 전체를 먼저 분류한다 —
    # 하나라도 NEEDS_REVIEW/UNSAFE면 apply 자체를 시작하지 않는다(부분 suppress 후
    # 중단되는 것보다, 아예 시작 안 하는 게 상태를 더 예측 가능하게 만든다).
    classifications = {c.get("id", ""): _classify_existing(event_store.get_status(_EVENT_SOURCE, c.get("id", ""))) for c in before}
    needs_review = [cid for cid, cls in classifications.items() if cls in ("NEEDS_REVIEW", "UNSAFE")]
    if needs_review:
        raise BaselineError(
            f"media={media_id}: 자동 처리 불가능한 기존 상태 {len(needs_review)}건 발견(수동 검토 필요) — "
            f"comment_id 예시: {needs_review[:5]}"
        )

    suppressed_new = 0
    # 260716 Codex 7차 리뷰 P1: SHADOW_SEEN은 "처리 완료 증거"가 아니다 — shadow claim
    # 직후 크래시했다면 실제로는 손님이 응답을 못 받았을 수도 있다. COMPLETED/기존
    # PRE_CUTOVER_SUPPRESSED(확정 종결)와는 신뢰도가 다르므로 카운트를 분리해서
    # 운영자가 apply 결과를 볼 때 "이만큼은 검증 안 된 채로 넘어갔다"를 알 수 있게 한다.
    suppressed_confirmed_safe = 0
    suppressed_shadow_unverified = 0
    for c in before:
        cid = c.get("id", "")
        cls = classifications[cid]
        if cls == "SAFE":
            status = event_store.get_status(_EVENT_SOURCE, cid)
            if status and status.get("migration_tag") == "SHADOW_SEEN":
                suppressed_shadow_unverified += 1
            else:
                suppressed_confirmed_safe += 1
            continue
        if event_store.suppress_pre_cutover(_EVENT_SOURCE, cid, claimed_by="baseline_cli"):
            suppressed_new += 1
        else:
            # 분류 시점 이후 다른 worker가 막 처리를 시작한 경우(드묾) — 재분류해 안전한지 재확인
            reclassified = _classify_existing(event_store.get_status(_EVENT_SOURCE, cid))
            if reclassified != "SAFE":
                raise BaselineError(f"media={media_id}: comment_id={cid} apply 도중 상태가 바뀜(재분류={reclassified}) — 재시도 필요")
            suppressed_confirmed_safe += 1

    source_hash = _hash_ids([c.get("id", "") for c in before])
    ok = poll_targets.apply_baseline(media_id, cutover_at.isoformat(), len(before), source_hash)
    if not ok:
        raise BaselineError(f"media={media_id} apply_baseline 기록 실패(state가 도중에 바뀜) — 처음부터 재시도 필요")

    print(f"[apply] media={media_id} cutover_at={cutover_at.isoformat()} | "
          f"suppressed 신규={suppressed_new} 기존 확정완료={suppressed_confirmed_safe} "
          f"기존 shadow-미검증={suppressed_shadow_unverified} | "
          f"cutover 이후(처리 대상 유지)={len(after)}건 | source_hash={source_hash[:12]}...")
    if suppressed_shadow_unverified:
        print(f"[apply] 경고: {suppressed_shadow_unverified}건은 과거 shadow 관측 기록만 있고 실제 발송 성공 여부가 "
              f"확인되지 않음(크래시 시나리오 가능) — 필요시 표본 확인 권장.")


def cmd_verify(media_id: str) -> None:
    _require_campaign_media(media_id)
    target = poll_targets.get_target(media_id)
    if not target or target["state"] != "PENDING_BASELINE" or not target.get("baseline_applied_at"):
        raise BaselineError(f"media={media_id}: apply가 먼저 필요(현재 상태={target['state'] if target else 'NONE'})")

    cutover_at = datetime.fromisoformat(target["cutover_at"])
    before, after = _fetch_and_split(media_id, cutover_at)

    # point 3: 재조회한 cutover 이전 건수 == baseline 기록 건수
    if len(before) != target["baseline_comment_count"]:
        raise BaselineError(
            f"건수 불일치: 재조회={len(before)} vs baseline 기록={target['baseline_comment_count']} "
            f"— 재-apply 필요(댓글이 삭제/추가됐을 수 있음)"
        )

    # point 4: 재조회 해시 == baseline 기록 해시
    recomputed_hash = _hash_ids([c.get("id", "") for c in before])
    if recomputed_hash != target["baseline_source_hash"]:
        raise BaselineError("해시 불일치: 동일 개수여도 실제 댓글 집합이 다름 — 재-apply 필요")

    # point 3(보완) + P0-4(260715 Codex 6차 리뷰): DB에 실제로 "안전 처리됨"으로
    # 분류되는 행 수와 대조 — literal PRE_CUTOVER_SUPPRESSED만 세면 SHADOW_SEEN으로
    # 이미 안전하게 처리된 기존 행(오늘 세션 내내 shadow로 관측된 실사용자 댓글들)
    # 때문에 실제 운영 DB에서는 절대 통과 못 하는 검증이 됨.
    unsafe_before = []
    for c in before:
        cls = _classify_existing(event_store.get_status(_EVENT_SOURCE, c.get("id", "")))
        if cls not in ("SAFE",):
            unsafe_before.append((c.get("id", ""), cls))
    if unsafe_before:
        raise BaselineError(f"DB 안전성 재검증 실패: {len(unsafe_before)}건이 SAFE 분류 아님(예: {unsafe_before[:5]}) — 재-apply 또는 수동검토 필요")

    # point 5: cutover 이후 댓글은 절대 suppress 안 돼 있어야 함
    for c in after:
        status = event_store.get_status(_EVENT_SOURCE, c.get("id", ""))
        if status and status.get("migration_tag") == "PRE_CUTOVER_SUPPRESSED":
            raise BaselineError(f"cutover 이후 댓글이 suppress되어 있음(comment_id={c.get('id')}) — 심각한 버그, activate 금지")

    # point 6: apply와 verify 사이 캠페인 JSON/상태 드리프트 감지(media 자체 상태 +
    # 캠페인 목록 전체 내용 해시 둘 다 — 260715 Codex 6차 리뷰 P0-3)
    if not poll_targets.sync_from_campaign_json():
        raise BaselineError("캠페인 설정 손상 — verify 중단")
    target_now = poll_targets.get_target(media_id)
    if not target_now or target_now["state"] != "PENDING_BASELINE" or target_now["baseline_applied_at"] != target["baseline_applied_at"]:
        raise BaselineError("apply~verify 사이 상태가 바뀜(캠페인 목록 변경 등) — 재-apply 필요")
    if target_now["campaign_config_hash"] != target_now["baseline_config_hash"]:
        raise BaselineError("apply~verify 사이 캠페인 설정 파일 내용이 바뀜(이 media 자체는 안 바뀌었어도) — 재-apply 필요")

    # P1(260716 Codex 7차 리뷰): verify_baseline()의 반환값을 반드시 확인해야 한다 —
    # 안 그러면 이 DB 갱신이 실패해도(예: 그 찰나에 다른 CLI가 상태를 바꿈) "통과"라고
    # 출력해버린다.
    if not poll_targets.verify_baseline(media_id):
        raise BaselineError(f"media={media_id}: 모든 검증은 통과했으나 DB 기록(verify_baseline) 자체가 실패함 — 재시도 필요")

    print(f"[verify] media={media_id} 통과 — cutover 이전 {len(before)}건 suppress 확인, "
          f"cutover 이후 {len(after)}건 정상 유지. --activate로 진행 가능.")


def cmd_activate(media_id: str, acknowledge_runtime_proof: bool = False) -> None:
    """260716 Codex 8차 리뷰 P0(실제 재현 확인) — "enforce/allowlist가 모두 켜지기
    전까진 ACTIVE가 실효과 없다"는 이전 판단은 틀렸다: allowlist+shadow 조합에서
    ACTIVE media는 다음 poll_new_comments() 주기부터 전체 페이지네이션으로 조회되고,
    shadow는 claim 결과와 무관하게 handle_comment()를 무조건 실행하므로 그 자리에서
    바로 실제 Telegram/Airtable/Private Reply가 나간다. ACTIVE는 이름 그대로 운영
    개시 상태여야 하므로, 아래 4가지를 전부 만족하지 못하면 activate 자체를 거부한다
    (경고만 하고 통과시키지 않음).

    260716 Codex 9차 리뷰 — acknowledge_runtime_proof(구 confirm_runtime_proof)는
    "증명"이 아니라 운영자의 자기선언이다. 이 CLI 프로세스 자체는 os.getenv() 검사
    직전에 실제로 .env를 다시 읽지만(import 체인을 통해, 직접 재현 확인함), 그게
    "이미 떠 있는 launcher 프로세스도 같은 값으로 돌고 있다"까지 보장하지는
    않는다 — launcher는 자기 기동 시점에 읽은 값을 재시작 전까지 그대로 들고
    있으므로, 이 CLI가 방금 읽은 .env와 다를 수 있다(PID/기동 세대 교차검증 없이는
    구조적으로 못 막는 gap). 이 함수는 그 gap을 자동으로 닫지 않는다 — 운영자가
    launcher 로그를 직접 보고 같은 기동 세대에서 두 모드가 실제로 일치함을
    확인했다는 선언만 강제한다."""
    _require_campaign_media(media_id)

    if os.getenv("COMMENT_POLL_ALLOWLIST_MODE", "legacy").strip().lower() != "allowlist":
        raise BaselineError("COMMENT_POLL_ALLOWLIST_MODE=allowlist가 아님 — activate 거부(허위 ACTIVE 방지)")
    if os.getenv("COMMENT_EVENT_STORE_MODE", "disabled").strip().lower() != "enforce":
        raise BaselineError("COMMENT_EVENT_STORE_MODE=enforce가 아님 — activate 거부(허위 ACTIVE 방지)")
    if not acknowledge_runtime_proof:
        # 260716: CLI는 별도 프로세스라 launcher의 _retry_handlers_registered를
        # 이 자리에서 신뢰성 있게 확인할 방법이 없다(교차 프로세스 상태, PID/기동
        # 세대 불일치 가능성 포함) — 그래서 자동 검사 대신, 운영자가 launcher
        # 로그(순서: "comment_airtable_record retry handler 등록 완료 → RetryQueue
        # 워커 시작 → 서버 시작 배너")에서 "같은 기동 세대"의 실제 상태를 직접
        # 확인했다는 것을 이 플래그로 명시적으로 선언하게 강제한다.
        raise BaselineError(
            "--acknowledge-runtime-proof 필요 — launcher 로그에서 'comment_airtable_record retry "
            "handler 등록 완료 → RetryQueue 워커 시작 → 서버 시작 배너' 순서를, 지금 이 activate와 "
            "같은 launcher 기동 세대에서 직접 확인한 뒤에만 지정할 것(이 플래그는 자동 검증이 아니라 "
            "운영자의 수동 확인 선언임)"
        )

    # verify 이후 activate 전 사이에 캠페인 JSON이 바뀌었을 수 있으므로, activate
    # 직전에 최신 상태로 한 번 더 동기화한 뒤 판단한다(260716 Codex 7차 리뷰 P1).
    if not poll_targets.sync_from_campaign_json():
        raise BaselineError("캠페인 설정 손상 — activate 중단")

    target = poll_targets.get_target(media_id)
    if target and target.get("baseline_verified_at") and target.get("campaign_config_hash") != target.get("baseline_config_hash"):
        raise BaselineError(f"media={media_id}: verify 이후 캠페인 설정이 바뀜 — 재-verify 필요(activate 거부)")

    if not poll_targets.activate(media_id):
        raise BaselineError(f"media={media_id}: verify 통과 기록이 없어 activate 불가")

    print(f"[activate] media={media_id} → ACTIVE. 다음 poll_new_comments() 주기부터 실시간 처리 대상.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-id", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    group.add_argument("--verify", action="store_true")
    group.add_argument("--activate", action="store_true")
    parser.add_argument("--cutover-at", help="--apply 필수, UTC ISO8601 (예: 2026-07-16T00:00:00+00:00)")
    parser.add_argument("--expected-config-hash", help="--apply 필수, --dry-run이 출력한 config_hash — dry-run~apply 사이 드리프트 검증용")
    parser.add_argument(
        "--acknowledge-runtime-proof", action="store_true",
        help="--activate 필수 — 자동 검증 아님. launcher 로그에서 같은 기동 세대의 retry handler "
             "등록 순서를 직접 확인했다는 운영자 선언(구 --confirm-runtime-proof)",
    )
    args = parser.parse_args(argv)

    try:
        if args.dry_run:
            cmd_dry_run(args.media_id)
        elif args.apply:
            if not args.cutover_at:
                raise BaselineError("--apply는 --cutover-at이 필수")
            if not args.expected_config_hash:
                raise BaselineError("--apply는 --expected-config-hash가 필수(먼저 --dry-run으로 값을 확인할 것)")
            cmd_apply(args.media_id, args.cutover_at, args.expected_config_hash)
        elif args.verify:
            cmd_verify(args.media_id)
        elif args.activate:
            cmd_activate(args.media_id, args.acknowledge_runtime_proof)
    except BaselineError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
