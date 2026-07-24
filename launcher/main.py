"""
launcher/main.py — SNS_24AutoProject 통합 실행 진입점

단일 프로세스로 전체 서비스를 구동한다:
  - Flask Webhook 서버 (port 5000)          ← 메인 스레드
  - APScheduler: FB 크롤링 / Instagram 업로드 ← 백그라운드 스레드
  - APScheduler: 팔로업·댓글·일일 리포트     ← 백그라운드 스레드 (dm_receiver 내)
  - RetryQueue 워커                          ← 백그라운드 데몬 스레드

사용법:
    python launcher/main.py
    python -m launcher.main

Streamlit 대시보드는 별도 프로세스:
    streamlit run dashboard.py
"""

import io
import os
import sys

# 백그라운드 프로세스에서 stdout/stderr 인코딩을 UTF-8로 강제 설정
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 프로젝트 루트를 sys.path에 추가 (launcher/ 하위에서 실행 시 필요)
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from core.log_initializer import init_logging
from core.error_handler import handle_errors
from modules.common.logger import get_logger
from modules.common.retry_queue import get_retry_queue
from modules.common.health_monitor import get_health, print_health
from modules.comment.comment_auto_reply import register_retry_handlers as _register_comment_retry_handlers
from modules.infra.airtable_usage_logger import log_api_call
from modules.common.log_sanitizer import redact_sensitive
from modules.sns.content_filter import passes_keyword_filter

init_logging()
logger = get_logger(__name__)

CRAWL_INTERVAL_MIN = int(os.getenv("CRAWL_INTERVAL_MINUTES", "30"))
UPLOAD_POLL_MIN    = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))
WEBHOOK_PORT       = int(os.getenv("WEBHOOK_PORT", "5000"))

# Slack 알림 (SLACK_WEBHOOK_URL 미설정 시 None → 알림 생략)
try:
    from services.slack_notifier import get_notify_fn as _get_notify_fn
    _slack = _get_notify_fn()
except Exception:
    _slack = None


# ── 이미지 전처리 ─────────────────────────────────────────────────────────────

_IG_RATIO_MIN = 0.8    # 4:5  (세로형 최대)
_IG_RATIO_MAX = 1.91   # 1.91:1 (가로형 최대)


def _preprocess_image(image_url: str) -> str:
    """Instagram 허용 비율(4:5 ~ 1.91:1) 확인 후 필요 시 center-crop → imgbb 업로드.

    Returns:
        imgbb 영구 URL  — 비율 보정 후 업로드 성공 시
        original URL   — 비율 유효하거나 오류 시 (폴백)
    IMGBB_API_KEY 미설정 시 원본 URL 그대로 반환.
    """
    imgbb_key = os.getenv("IMGBB_API_KEY", "").strip()
    if not imgbb_key:
        logger.warning("[Preprocess] IMGBB_API_KEY 미설정 — 전처리 생략")
        return image_url

    try:
        import base64
        from PIL import Image
        import requests as _req

        resp = _req.get(image_url, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        ratio = w / h

        if _IG_RATIO_MIN <= ratio <= _IG_RATIO_MAX:
            return image_url  # 유효 범위 — 전처리 불필요

        if ratio > _IG_RATIO_MAX:
            # 너무 넓음 → 너비 크롭 (center)
            new_w = int(h * _IG_RATIO_MAX)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            # 너무 길음 → 높이 크롭 (center)
            new_h = int(w / _IG_RATIO_MIN)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

        logger.info(f"[Preprocess] 비율 보정 완료 | {w}x{h} ratio={ratio:.2f} → crop 후 imgbb 업로드")

        # 크롭 이미지를 메모리에서 base64 인코딩 후 imgbb 업로드
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        upload_resp = _req.post(
            "https://api.imgbb.com/1/upload",
            data={"key": imgbb_key, "image": b64},
            timeout=30,
        )
        upload_data = upload_resp.json()
        if not upload_data.get("success"):
            raise RuntimeError(f"imgbb 업로드 실패: {upload_data}")

        imgbb_url = upload_data["data"]["url"]
        logger.info(f"[Preprocess] imgbb 업로드 완료 | {imgbb_url}")
        return imgbb_url

    except Exception as exc:
        logger.warning(f"[Preprocess] 이미지 전처리 실패 — 원본 URL 사용 | {exc}")
        return image_url


# ── 잡 함수 ───────────────────────────────────────────────────────────────────

@handle_errors(task="fb_crawl", notify_fn=_slack)
def _job_fb_crawl():
    from modules.sns.facebook_crawler import run_all_accounts
    summary = run_all_accounts()
    logger.info(f"[Main] fb_crawl 완료 | {summary}")


@handle_errors(task="kpi_snapshot", notify_fn=_slack)
def _job_kpi_snapshot():
    from modules.metrics.kpi_collector import run_hourly_snapshot
    run_hourly_snapshot()


@handle_errors(task="engagement_update", notify_fn=_slack)
def _job_engagement_update():
    from modules.interaction_engine.interaction_scheduler import run_engagement_update
    run_engagement_update()


@handle_errors(task="auto_like", notify_fn=_slack)
def _job_auto_like():
    from modules.interaction_engine.interaction_scheduler import run_auto_like
    run_auto_like()


@handle_errors(task="dome_crawl", notify_fn=_slack)
def _job_dome_crawl():
    import os as _os
    from modules.crawlers.domeggook_api_connector import DomeggookApiConnector
    from modules.crawlers.quality_gate import run_gate
    from dotenv import load_dotenv
    from modules.infra.airtable_repository import AirtableRepository
    from modules.infra.repository_interface import SourceItem, SourceItemStatus
    load_dotenv()

    repo = AirtableRepository()

    raw_targets = repo.fetch_active_crawl_targets()
    targets = [t for t in raw_targets if t.get("platform") == "domeggook"]
    if not targets:
        logger.info("[dome_crawl] Active 타겟 없음 — 스킵")
        return

    conn = DomeggookApiConnector()
    for rec in targets:
        f = rec
        target = {
            "target_id":     f.get("target_id", ""),
            "kw":            f.get("keyword", ""),
            "category_code": f.get("category_code", ""),
            "max_posts":     min(int(f.get("max_posts", 10)), 10),
        }
        items = conn.fetch(target)
        gated = run_gate(items)
        ready = [i for i in gated if i["quality_status"] == "READY"]
        logger.info(f"[dome_crawl] {target['target_id']} fetch={len(items)} ready={len(ready)}")

        for item in ready:
            payload = {k: v for k, v in {
                "source_item_id":  item["source_item_id"],
                "target_id":       target["target_id"],
                "source_platform": item["source_platform"],
                "source_url":      item.get("source_url") or None,
                "title":           item["title"],
                "unit_price":      item.get("unit_price"),
                "currency":        item["currency"],
                "min_order_qty":   item.get("min_order_qty"),
                "image_url":       item.get("image_url") or None,
                "seller_id":       item.get("seller_id") or None,
                "category_code":   item.get("category_code") or None,
                "keyword":         item.get("keyword") or None,
                "content_hash":    item["content_hash"],
                "quality_status":  item["quality_status"],
                "filter_reason":   item.get("filter_reason", ""),
                "collected_at":    item["collected_at"],
                "pipeline_status": "NEW",
            }.items() if v is not None}

            # Upsert: content_hash 기준 중복 확인 → 신규/변경 분기
            existing_ref = repo.find_source_item_by_hash(item["content_hash"])
            if existing_ref:
                continue  # 동일 hash 존재 → SKIP

            source_item = SourceItem(**{k: v for k, v in payload.items() if v is not None})
            saved_id = repo.save_source_item(source_item)
            if saved_id:
                repo.update_source_item_status(
                    saved_id,
                    SourceItemStatus.NEW,
                )


@handle_errors(task="dome_export", notify_fn=_slack)
def _job_dome_export():
    if os.getenv('DOME_EXPORT_ENABLED', 'true').lower() == 'false':
        logger.info('[dome_export] DISABLED by feature flag')
        return
    from modules.crawlers.source_exporter import export_to_instagram_posts
    result = export_to_instagram_posts(target_id=None, batch_size=5, dry_run=False)
    logger.info(f"[dome_export] {result}")


@handle_errors(task="comment_dead_monitor", notify_fn=_slack)
def _job_comment_dead_monitor():
    """FP-047 — comment_airtable_record retry_queue dead 건 능동 알림(설계문서 §5)."""
    from modules.comment.comment_retry_dead_monitor import check_dead_comment_tasks
    n = check_dead_comment_tasks()
    if n:
        logger.warning(f"[comment_dead_monitor] 신규 dead 알림 {n}건")


def publish_single(rid, image_url, caption, access_token, ig_user_id):
    """
    단일 Record 게시 실행 함수.
    APScheduler와 n8n Endpoint가 공통으로 호출한다.
    Token/ig_user_id는 호출자가 주입 — 이 함수는 저장소를 모른다.
    로그에 access_token 출력 금지.
    """
    import requests as _req

    if not image_url:
        logger.error(f"[publish_single] image_url 없음 | rid={rid}")
        return {"ok": False, "error": "image_url_missing"}

    image_url = _preprocess_image(image_url)

    for attempt in range(1, 4):
        try:
            r1 = _req.post(
                f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
                params={"image_url": image_url, "caption": caption,
                        "access_token": access_token},
                timeout=30,
            )
            r1.raise_for_status()
            c1 = r1.json()

            r2 = _req.post(
                f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish",
                params={"creation_id": c1["id"], "access_token": access_token},
                timeout=30,
            )
            r2.raise_for_status()
            c2 = r2.json()

            ig_media_id = c2.get("id", "")
            logger.info(f"[publish_single] 성공 | rid={rid} | ig_media_id={ig_media_id}")
            return {"ok": True, "ig_media_id": ig_media_id}

        except Exception as e:
            logger.warning(f"[publish_single] 시도 {attempt}/3 실패 | rid={rid} | {redact_sensitive(str(e))}")
            if attempt == 3:
                logger.error(f"[publish_single] 3회 실패 최종 | rid={rid}")
                return {"ok": False, "error": str(e)}


@handle_errors(task="insta_upload", notify_fn=_slack)
def _job_insta_upload():
    from modules.infra.airtable_repository import AirtableRepository
    from modules.infra.repository_interface import PostPublishResult

    token      = os.getenv("INSTA_ACCESS_TOKEN")
    ig_user_id = os.getenv("INSTA_IG_USER_ID", "").strip()
    if not token or not ig_user_id:
        logger.warning("[Main] INSTA 환경변수 미설정 — upload 생략")
        return

    repo  = AirtableRepository()
    posts = repo.fetch_pending_posts(limit=50)
    if not posts:
        return

    logger.info(f"[Main] insta_upload | {len(posts)}건 처리 시작")
    for post in posts:
        post_id   = post["post_id"]
        logger.info(f"[Approval] ready 레코드 처리 시작 | rid={post_id}")
        image_url = post.get("image_url", "")
        caption   = f"{post.get('caption','')}\n{post.get('hashtag','')}".strip()

        # ig_media_id 있으면 이미 업로드된 레코드 — 재업로드 차단
        if post.get("ig_media_id"):
            logger.warning("[Main] unverified ig_media_id detected — skip | post_id=%s", post_id)
            continue

        # 발행 직전 텍스트 Quality Gate (기본 비활성 — PUBLISH_TEXT_GATE_ENABLED=true 시에만 적용)
        if os.getenv("PUBLISH_TEXT_GATE_ENABLED", "false").lower() == "true":
            if not passes_keyword_filter(caption):
                logger.info(f"[PublishGate] 텍스트 차단 | rid={post_id}")
                from modules.infra.repository_interface import PostPublishResult as _PPR
                repo.mark_post_result(post_id, _PPR(status="rejected", platform_post_id="", error_code=""))
                continue

        # claim: uploading 마킹 (non-atomic, single-worker only)
        if not repo.claim_post_for_upload(post_id):
            continue

        raw = publish_single(post_id, image_url, caption, token, ig_user_id)

        pub_result = PostPublishResult(
            status="posted" if raw.get("ok") else "failed",
            platform_post_id=raw.get("ig_media_id", ""),
            error_code=raw.get("error", ""),
        )
        repo.mark_post_result(post_id, pub_result)


# ── 스케줄러 설정 ─────────────────────────────────────────────────────────────

def _build_scheduler() -> BackgroundScheduler:
    now = datetime.now()
    sched = BackgroundScheduler(timezone="Asia/Seoul")
    sched.add_job(_job_fb_crawl,     "interval", minutes=CRAWL_INTERVAL_MIN,
                  id="fb_crawl",     next_run_time=now + timedelta(seconds=60))
    sched.add_job(_job_insta_upload, "interval", minutes=UPLOAD_POLL_MIN,
                  id="insta_upload", next_run_time=now + timedelta(seconds=120),
                  max_instances=1)
    sched.add_job(_job_kpi_snapshot, "interval", hours=1,
                  id="kpi_snapshot", next_run_time=now + timedelta(seconds=180))
    sched.add_job(_job_engagement_update, "interval", minutes=30,
                  id="engagement_update", next_run_time=now + timedelta(seconds=240))
    #DISABLED_260603 sched.add_job(_job_auto_like, "interval", minutes=15,
    #DISABLED_260603               id="auto_like", next_run_time=now + timedelta(seconds=70))
    sched.add_job(_job_dome_crawl, "interval", minutes=60,
                  id="dome_crawl", next_run_time=now + timedelta(seconds=300))
    sched.add_job(_job_dome_export, "interval", minutes=10,
                  id="dome_export", next_run_time=now + timedelta(seconds=360),
                  max_instances=1, coalesce=True)
    sched.add_job(_job_comment_dead_monitor, "interval", minutes=15,
                  id="comment_dead_monitor", next_run_time=now + timedelta(seconds=420),
                  max_instances=1, coalesce=True)
    return sched


# ── 시작 배너 ────────────────────────────────────────────────────────────────

def _print_banner():
    logger.info("=" * 60)
    logger.info("  SNS_24AutoProject — 통합 서버 시작")
    logger.info(f"  Flask Webhook   : http://localhost:{WEBHOOK_PORT}")
    logger.info(f"  FB 크롤링       : {CRAWL_INTERVAL_MIN}분 간격")
    logger.info(f"  Instagram 업로드: {UPLOAD_POLL_MIN}분 간격")
    logger.info(f"  Streamlit       : python -m streamlit run dashboard.py")
    logger.info("=" * 60)


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main():
    # 1. retry_queue 워커 시작
    rq = get_retry_queue()
    # FP-047: comment_airtable_record 핸들러는 반드시 rq.start() 이전에 eager 등록해야
    # 함 — 기존 ig_auto_reply/ig_followup처럼 실패 시점에 지연등록하면 재시작 후 pending
    # task가 handler를 못 찾고 dead 처리될 위험이 있음(설계문서 §6).
    _register_comment_retry_handlers(rq)
    logger.info("[Main] comment_airtable_record retry handler 등록 완료")
    rq.start()

    # 2. 크롤링·업로드 스케줄러 시작 (백그라운드)
    scheduler = _build_scheduler()
    scheduler.start()
    logger.info("[Main] 스케줄러 시작")

    # 3. Flask + 팔로업·댓글·리포트 스케줄러 (dm_receiver 내부에서 start_scheduler 호출)
    from modules.dm.dm_receiver import app, start_scheduler
    start_scheduler()

    _print_banner()

    # 4. 시작 시 헬스체크
    try:
        h = get_health()
        logger.info(f"[Main] 시작 헬스체크 | overall={h['overall']} | services={h['services']}")
    except Exception:
        pass

    # 5. Flask 메인 스레드 실행 (블로킹)
    try:
        app.run(host="0.0.0.0", port=WEBHOOK_PORT, debug=False, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Main] 종료 신호 수신")
    finally:
        scheduler.shutdown(wait=False)
        rq.stop()
        logger.info("[Main] 종료 완료")


if __name__ == "__main__":
    main()
