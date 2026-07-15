# modules/comment/comment_poller.py
# 캠페인 게시물(comment_poll_targets.state=ACTIVE)의 댓글을 5분마다 폴링 — 신규 댓글
# 감지 → comment_auto_reply 처리. 처리 완료된 comment_id는
# data/processed_comment_ids.json에 캐시.
#
# 260715 Package 1 Phase A: "최근 게시물 N개"(get_recent_media_ids) 기반 폴링을
# 폐기하고 캠페인 allowlist 전체(comment_poll_targets 경유)를 감시 대상으로 삼는다 —
# 계정이 게시물을 자주 올리면 캠페인 게시물이 "최근 N개" 밖으로 밀려나 댓글을 통째로
# 놓치는 구조적 버그(260715 실사용자 테스트로 확인)를 근본 수정. get_recent_media_ids()
# 자체는 신규 게시물 탐지 등 다른 용도로 남겨두되, 이 파일의 실시간 처리 루프에서는
# 더 이상 쓰지 않는다.

import os
import json as _json
import logging
import requests
from pathlib import Path

from modules.comment import comment_poll_targets
from modules.comment.comment_auto_reply import process_comment_event, CommentProcessResult
from modules.common.meta_graph import messaging_graph_url

logger = logging.getLogger(__name__)


class CommentFetchIncomplete(Exception):
    """페이지 상한 도달로 댓글 목록을 끝까지 못 읽음 — 부분 결과를 "댓글 없음"으로
    착각해 checkpoint를 전진시키면 안 된다(260715 Codex 3차 리뷰 point 3)."""

# P0(260715 Codex 3·4차 리뷰): 이 결과들만 "확정(durable)"이라 캐시해도 됨.
# IN_PROGRESS(활성 worker만 보유, durable 백업 없음)나 REJECTED_NOT_READY(fail-closed,
# 처리 자체를 안 함/enqueue 실패)는 캐시하면 안 됨 — 캐시해버리면 그 worker가 crash해도
# poller가 다시는 이 comment_id를 안 보게 되어, try_claim()의 stale reclaim(P0-2)이
# 발동할 기회 자체가 영원히 없어짐. RETRY_OWNED는 retry_queue.db가 payload를 durable
# 보유하므로 캐시 가능.
_CACHEABLE_RESULTS = {
    CommentProcessResult.ACCEPTED,
    CommentProcessResult.DUPLICATE_COMPLETED,
    CommentProcessResult.RETRY_OWNED,
    CommentProcessResult.LEGACY,
}

# ── 설정 ─────────────────────────────────────────────────────────────────────

MEDIA_COUNT  = int(os.getenv("COMMENT_POLL_MEDIA_COUNT", "5"))   # get_recent_media_ids() 전용(신규 게시물 탐지 등), 실시간 처리 루프에는 미사용
CACHE_PATH   = Path(__file__).resolve().parents[2] / "data" / "processed_comment_ids.json"
MAX_CACHE    = 2000   # 캐시 최대 항목 수 (오래된 것부터 제거)
MAX_COMMENT_PAGES = int(os.getenv("COMMENT_POLL_MAX_PAGES", "20"))   # fetch_all_comments() 페이지 상한
FAILURE_ALERT_THRESHOLD = int(os.getenv("COMMENT_POLL_FAILURE_ALERT_THRESHOLD", "3"))   # 연속 실패 N회부터 Slack 알림


# ── comment_id 캐시 ───────────────────────────────────────────────────────────

def _load_cache() -> set[str]:
    if CACHE_PATH.exists():
        try:
            return set(_json.loads(CACHE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def _save_cache(ids: set[str]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 캐시 크기 제한 — 초과 시 앞에서 제거 (set이므로 list 변환 후 슬라이싱)
    trimmed = list(ids)[-MAX_CACHE:]
    CACHE_PATH.write_text(_json.dumps(trimmed), encoding="utf-8")


# ── Graph API ─────────────────────────────────────────────────────────────────

def _access_token() -> str:
    return os.getenv("INSTA_ACCESS_TOKEN", "")


def get_recent_media_ids() -> list[str]:
    """IG Graph API에서 최근 게시물 media_id 목록 조회."""
    ig_user_id = os.getenv("INSTA_IG_USER_ID", "")
    try:
        resp = requests.get(
            messaging_graph_url(f"{ig_user_id}/media"),
            params={
                "fields": "id,timestamp",
                "limit":  MEDIA_COUNT,
                "access_token": _access_token(),
            },
            timeout=15,
        )
        data = resp.json()
        if not resp.ok:
            logger.error(f"[CommentPoll] media 조회 실패 | {resp.status_code} {data}")
            return []
        return [item["id"] for item in data.get("data", [])]
    except Exception as exc:
        logger.error(f"[CommentPoll] media 조회 예외 | {exc}")
        return []


def _fetch_comments_page(url: str, params: dict | None = None) -> dict:
    """단일 페이지 원시 조회 — HTTP 실패 시 예외를 던진다(호출부가 부분 결과와
    완전 실패를 구분할 수 있도록, 조용히 빈 리스트로 삼키지 않음)."""
    resp = requests.get(url, params=params, timeout=15)
    if not resp.ok:
        raise RuntimeError(f"comments 조회 실패 | {resp.status_code} {resp.text[:300]}")
    return resp.json()


def get_comments(media_id: str) -> list[dict]:
    """게시물의 댓글 첫 페이지만 조회(하위호환 유지용 — 단독 테스트/디버깅 목적).
    실시간 처리 루프는 fetch_all_comments()를 사용해야 한다(페이지네이션 누락 버그,
    260715 Codex 3차 리뷰 point 3).
    각 항목: {id, text, username, timestamp, from:{id,username}}
    from.id는 계정명 변경에 영향받지 않는 안정적 IG 사용자 ID — 쿨다운 키로 username보다 우선 사용."""
    try:
        data = _fetch_comments_page(
            messaging_graph_url(f"{media_id}/comments"),
            {"fields": "id,text,username,timestamp,from", "access_token": _access_token()},
        )
        return data.get("data", [])
    except Exception as exc:
        logger.warning(f"[CommentPoll] comments 조회 예외 | media={media_id} | {exc}")
        return []


def fetch_all_comments(media_id: str, max_pages: int = MAX_COMMENT_PAGES) -> list[dict]:
    """paging.next를 끝까지 따라가며 전체 댓글을 조회한다. 매 폴링 주기마다 전체
    페이지네이션을 다시 걷는다(paging cursor를 영구 체크포인트로 저장하지 않음 —
    cursor는 만료/URL에 토큰 노출 위험이 있어 업무 watermark로 부적합, 260715 Codex
    3차 리뷰 point 3). 중복 방지는 comment_id 기반 캐시(processed_comment_ids.json)와
    event_store가 담당.
    페이지 상한(max_pages) 도달 시 CommentFetchIncomplete를 던진다 — 부분 결과를
    "이번엔 댓글이 이만큼뿐"이라고 착각해 정상 처리하면 안 되기 때문."""
    comments: list[dict] = []
    url = messaging_graph_url(f"{media_id}/comments")
    params = {"fields": "id,text,username,timestamp,from", "access_token": _access_token()}
    page = 0
    while url:
        page += 1
        if page > max_pages:
            raise CommentFetchIncomplete(f"media={media_id} 페이지 상한({max_pages}) 도달 — 전체 미완주")
        data = _fetch_comments_page(url, params)
        comments.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = None  # next URL엔 access_token 등 필요한 쿼리가 이미 포함됨
    return comments


# ── 폴링 메인 ────────────────────────────────────────────────────────────────

def _alert_consecutive_failures(media_id: str, failures: int) -> None:
    """연속 실패가 임계치를 넘으면 1회만 Slack 알림(이미 알림 보낸 뒤엔 성공할 때까지
    조용히 — record_poll_success()가 last_alerted_at까지 리셋하므로 다음 실패
    스트릭에서 다시 알림 대상이 됨). 260715 Codex 6차 리뷰 P1: notify_error()는
    반환값이 없어(None) 전송 성공 여부를 알 수 없었다 — send_alert()를 직접 호출해
    실제로 전송 성공했을 때만 mark_alerted()한다(실패했는데 "알림 보냄"으로 기록해
    다음 실패 때도 영구히 재시도 안 되는 사고 방지)."""
    if failures < FAILURE_ALERT_THRESHOLD:
        return
    target = comment_poll_targets.get_target(media_id)
    if target and target.get("last_alerted_at"):
        return
    try:
        from services.slack_notifier import send_alert
        sent = send_alert("CommentPoll 연속 실패", f"media={media_id} | 연속 {failures}회 실패", level="error")
    except Exception as exc:
        logger.error(f"[CommentPoll] Slack 알림 예외 | media={media_id} | {exc}")
        sent = False
    if sent:
        comment_poll_targets.mark_alerted(media_id)
    else:
        logger.error(f"[CommentPoll] Slack 알림 전송 실패(다음 실패 시 재시도) | media={media_id}")


def _process_media_comments(media_id: str, comments: list[dict], processed: set[str], new_ids: set[str]) -> int:
    """댓글 목록 1개 media 분을 처리 — legacy/allowlist 두 경로가 공유.
    반환값: 이번 호출에서 신규로 확정 처리된 건수."""
    new_count = 0
    for c in comments:
        cid          = c.get("id", "")
        text         = c.get("text", "").strip()
        username     = c.get("username", "")
        commenter_id = c.get("from", {}).get("id", "") or username

        # P0-5(260715 Codex 6차 리뷰): cid in new_ids 체크 없으면, 페이지 경계에서
        # 같은 댓글이 두 페이지에 겹쳐 나올 때(실시간으로 댓글이 달리며 pagination
        # 커서가 밀리는 경우 등) 같은 주기 안에서 두 번 처리돼 shadow 모드에서
        # Telegram/Private Reply가 중복 발송될 수 있었다.
        if not cid or cid in processed or cid in new_ids:
            continue

        # P0-1(260715 Codex 2·3차 리뷰): 예외가 나면 캐시에 안 남긴다(이전엔 예외
        # 발생 여부와 무관하게 항상 캐시돼 FP-047과 같은 유실 패턴이 재현될 수 있었음).
        # 예외가 없어도 결과가 IN_PROGRESS/REJECTED_NOT_READY면 아직 확정 아니므로
        # 마찬가지로 캐시하지 않는다(_CACHEABLE_RESULTS 참조).
        try:
            result = process_comment_event(cid, username, text, media_id, ingress="poller", commenter_id=commenter_id)
        except Exception as exc:
            logger.error(f"[CommentPoll] process_comment_event 오류(캐시 미기록, 다음 폴링에 재시도) | cid={cid} | {exc}")
            continue
        if result not in _CACHEABLE_RESULTS:
            logger.info(f"[CommentPoll] 미확정 상태(캐시 미기록, 다음 폴링에 재확인) | cid={cid} | result={result.value}")
            continue
        new_ids.add(cid)
        new_count += 1
    return new_count


def _poll_legacy(processed: set[str]) -> tuple[set[str], int]:
    """260715 이전과 완전히 동일한 감시 대상 결정 방식("최근 N개 게시물") —
    COMMENT_POLL_ALLOWLIST_MODE 기본값(legacy)일 때 사용. Phase A 코드가 배포(재시작)
    되어도 이 경로가 기본이므로 실제 운영 동작은 전혀 바뀌지 않는다(260715 Codex
    6차 리뷰 P0-2 — allowlist 경로가 기본이었다면 poll_targets가 아직 비어있어
    ACTIVE media가 0개라 댓글 폴링이 통째로 멈췄을 것).

    260716 Codex 7차 리뷰 P0-2(실제 재현 확인): fetch_all_comments()(전체 페이지네이션)
    를 여기서 쓰면 "기존과 동일"이 아니다 — 이미 감시 중이던 media에 2페이지 이상의
    과거 댓글이 쌓여있었다면, 재시작 한 번으로 그 과거 댓글들이 전부 "신규"로
    오인돼 실제 Telegram/Airtable/Private Reply가 나간다(cutover가 막으려던 바로 그
    사고를 legacy 경로로 재현). 반드시 원래의 get_comments()(첫 페이지만)를 그대로
    써야 한다 — 전체 페이지네이션은 baseline cutover suppression으로 보호되는
    allowlist 경로에서만 안전하다."""
    new_ids: set[str] = set()
    new_count = 0
    media_ids = get_recent_media_ids()
    if not media_ids:
        logger.debug("[CommentPoll] 게시물 없음 또는 API 오류")
        return new_ids, new_count
    for media_id in media_ids:
        comments = get_comments(media_id)
        new_count += _process_media_comments(media_id, comments, processed, new_ids)
    return new_ids, new_count


def _poll_allowlist(processed: set[str]) -> tuple[set[str], int]:
    """260715 Package 1 — comment_poll_targets.state=ACTIVE 전체를 감시 대상으로 삼는다.
    COMMENT_POLL_ALLOWLIST_MODE=allowlist로 명시 전환해야만 사용됨(별도 승인 대상)."""
    new_ids: set[str] = set()
    new_count = 0

    if not comment_poll_targets.sync_from_campaign_json():
        logger.error("[CommentPoll] 캠페인 설정 손상 — 이번 주기 폴링 전체 생략(fail-closed)")
        return new_ids, new_count

    media_ids = comment_poll_targets.get_active_media_ids()
    if not media_ids:
        logger.debug("[CommentPoll] ACTIVE 상태인 캠페인 게시물 없음")
        return new_ids, new_count

    for media_id in media_ids:
        try:
            comments = fetch_all_comments(media_id)
        except CommentFetchIncomplete as exc:
            failures = comment_poll_targets.record_poll_failure(media_id)
            logger.error(f"[CommentPoll] {exc} (연속 실패 {failures}회, 다른 media는 계속 진행)")
            _alert_consecutive_failures(media_id, failures)
            continue
        except Exception as exc:
            failures = comment_poll_targets.record_poll_failure(media_id)
            logger.error(f"[CommentPoll] media 조회 예외(다른 media는 계속 진행) | media={media_id} | {exc} (연속 실패 {failures}회)")
            _alert_consecutive_failures(media_id, failures)
            continue

        comment_poll_targets.record_poll_success(media_id)
        new_count += _process_media_comments(media_id, comments, processed, new_ids)

    return new_ids, new_count


def poll_new_comments() -> None:
    """신규 댓글을 폴링하여 처리한다 (5분 간격 호출).
    COMMENT_POLL_ALLOWLIST_MODE(기본 legacy)로 감시 대상 결정 방식을 전환:
      legacy(기본)  — "최근 N개 게시물". 260715 이전과 완전히 동일.
      allowlist     — comment_poll_targets.state=ACTIVE 전체(Package 1) — 게시
                      빈도 때문에 캠페인 게시물이 "최근 N개"에서 밀려나 댓글을
                      통째로 놓치는 구조적 버그(260715 확인)를 근본 수정하지만,
                      media별 baseline(--apply/--verify/--activate) 완료 후에만
                      켜야 한다."""
    processed = _load_cache()

    if comment_poll_targets.is_allowlist_gating_enabled():
        new_ids, new_count = _poll_allowlist(processed)
    else:
        new_ids, new_count = _poll_legacy(processed)

    if new_count:
        logger.info(f"[CommentPoll] 신규 댓글 {new_count}건 처리 완료")
        _save_cache(processed | new_ids)
    else:
        logger.debug("[CommentPoll] 신규 댓글 없음")
