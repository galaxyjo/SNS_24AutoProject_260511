# modules/comment/comment_poller.py
# 최근 IG 게시물의 댓글을 5분마다 폴링 — 신규 댓글 감지 → comment_auto_reply 처리
# 처리 완료된 comment_id는 data/processed_comment_ids.json에 캐시

import os
import json as _json
import logging
import requests
from pathlib import Path

from modules.comment.comment_auto_reply import process_comment_event, CommentProcessResult
from modules.common.meta_graph import messaging_graph_url

logger = logging.getLogger(__name__)

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

MEDIA_COUNT  = int(os.getenv("COMMENT_POLL_MEDIA_COUNT", "5"))   # 폴링할 최근 게시물 수
CACHE_PATH   = Path(__file__).resolve().parents[2] / "data" / "processed_comment_ids.json"
MAX_CACHE    = 2000   # 캐시 최대 항목 수 (오래된 것부터 제거)


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


def get_comments(media_id: str) -> list[dict]:
    """게시물의 댓글 목록 조회. 각 항목: {id, text, username, timestamp, from:{id,username}}
    from.id는 계정명 변경에 영향받지 않는 안정적 IG 사용자 ID — 쿨다운 키로 username보다 우선 사용."""
    try:
        resp = requests.get(
            messaging_graph_url(f"{media_id}/comments"),
            params={
                "fields": "id,text,username,timestamp,from",
                "access_token": _access_token(),
            },
            timeout=15,
        )
        if not resp.ok:
            logger.warning(f"[CommentPoll] comments 조회 실패 | media={media_id} | {resp.status_code}")
            return []
        return resp.json().get("data", [])
    except Exception as exc:
        logger.warning(f"[CommentPoll] comments 조회 예외 | media={media_id} | {exc}")
        return []


# ── 폴링 메인 ────────────────────────────────────────────────────────────────

def poll_new_comments() -> None:
    """최근 게시물의 신규 댓글을 폴링하여 처리한다 (5분 간격 호출)."""
    processed = _load_cache()
    media_ids  = get_recent_media_ids()

    if not media_ids:
        logger.debug("[CommentPoll] 게시물 없음 또는 API 오류")
        return

    new_ids: set[str] = set()
    new_count = 0

    for media_id in media_ids:
        comments = get_comments(media_id)
        for c in comments:
            cid          = c.get("id", "")
            text         = c.get("text", "").strip()
            username     = c.get("username", "")
            commenter_id = c.get("from", {}).get("id", "") or username

            if not cid or cid in processed:
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

    if new_count:
        logger.info(f"[CommentPoll] 신규 댓글 {new_count}건 처리 완료")
        _save_cache(processed | new_ids)
    else:
        logger.debug("[CommentPoll] 신규 댓글 없음")
