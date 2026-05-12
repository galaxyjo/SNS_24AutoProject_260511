"""
modules/interaction_engine/auto_liker.py — 자신의 게시물 댓글 자동 좋아요

자신의 Instagram 게시물에 달린 새 댓글을 자동으로 좋아요 처리한다.
중복 방지: db/liked_comments.db 에 처리된 comment_id 저장.

Graph API 엔드포인트:
  GET  /{ig-media-id}/comments?fields=id,username,text,timestamp
  POST /{ig-comment-id}/likes   (권한: instagram_manage_comments)
"""

import os
import sqlite3
import requests
from datetime import datetime, timezone
from pathlib import Path

from modules.common.airtable_bridge import get_table
from modules.common.logger import get_logger

logger = get_logger(__name__)

IG_API  = "https://graph.facebook.com/v21.0"
DB_PATH = Path(__file__).resolve().parents[2] / "db" / "liked_comments.db"
MAX_POSTS = int(os.getenv("AUTO_LIKE_MAX_POSTS", "10"))


# ── SQLite 중복 방지 ──────────────────────────────────────────────────────────

def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS liked_comments (
            comment_id TEXT PRIMARY KEY,
            liked_at   TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()


def _is_liked(comment_id: str) -> bool:
    _ensure_db()
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT 1 FROM liked_comments WHERE comment_id=?", (comment_id,)
    ).fetchone()
    con.close()
    return row is not None


def _mark_liked(comment_id: str) -> None:
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR IGNORE INTO liked_comments (comment_id, liked_at) VALUES (?, ?)",
        (comment_id, datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


# ── Graph API 호출 ────────────────────────────────────────────────────────────

def _get_comments(media_id: str, token: str) -> list[dict]:
    try:
        resp = requests.get(
            f"{IG_API}/{media_id}/comments",
            params={"fields": "id,username,text,timestamp", "access_token": token},
            timeout=10,
        )
        data = resp.json()
        if "error" in data:
            logger.warning(f"[AutoLiker] 댓글 조회 오류 | {media_id} | {data['error'].get('message','')}")
            return []
        return data.get("data", [])
    except Exception as exc:
        logger.warning(f"[AutoLiker] 댓글 조회 실패 | {media_id} | {exc}")
        return []


def _like_comment(comment_id: str, token: str) -> bool:
    try:
        resp = requests.post(
            f"{IG_API}/{comment_id}/likes",
            params={"access_token": token},
            timeout=10,
        )
        result = resp.json()
        if "error" in result:
            logger.warning(f"[AutoLiker] 좋아요 API 오류 | {comment_id} | {result['error'].get('message','')}")
            return False
        return result.get("success", False)
    except Exception as exc:
        logger.warning(f"[AutoLiker] 좋아요 실패 | {comment_id} | {exc}")
        return False


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────

def like_new_comments(max_posts: int = MAX_POSTS) -> dict:
    """
    최근 posted 게시물(ig_media_id 있음)의 새 댓글에 좋아요.
    - liked_comments.db로 중복 방지
    - max_posts: 처리할 최대 게시물 수
    """
    token = os.getenv("INSTA_ACCESS_TOKEN") or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    if not token:
        logger.warning("[AutoLiker] INSTA_ACCESS_TOKEN 미설정 — 생략")
        return {"liked": 0, "skipped": 0}

    table   = get_table("Instagram_Posts")
    records = table.all(formula="AND({post_status}='posted', {ig_media_id}!='')")
    records = sorted(
        records,
        key=lambda r: r.get("createdTime", r["fields"].get("createdTime", "")),
        reverse=True,
    )[:max_posts]

    liked = skipped = 0
    for rec in records:
        media_id = rec["fields"].get("ig_media_id", "")
        if not media_id:
            continue

        comments = _get_comments(media_id, token)
        for comment in comments:
            cid = comment.get("id", "")
            if not cid:
                continue
            if _is_liked(cid):
                skipped += 1
                continue
            if _like_comment(cid, token):
                _mark_liked(cid)
                liked += 1
                logger.debug(f"[AutoLiker] 좋아요 완료 | comment={cid} user={comment.get('username','')}")
            else:
                skipped += 1

    logger.info(f"[AutoLiker] 완료 | liked={liked} skipped={skipped}")
    return {"liked": liked, "skipped": skipped}
