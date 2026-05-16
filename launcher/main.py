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


def _preprocess_image(image_url: str):
    """Instagram 허용 비율(4:5 ~ 1.91:1) 확인 후 필요 시 center-crop.

    Returns:
        (original_url, None)  — 비율 유효 또는 오류 시 → URL 업로드 사용
        (None, local_path)    — 비율 보정 완료 → multipart/form-data 업로드 사용
    """
    try:
        from PIL import Image
        import requests as _req

        resp = _req.get(image_url, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        ratio = w / h

        if _IG_RATIO_MIN <= ratio <= _IG_RATIO_MAX:
            return image_url, None  # 유효 범위 — 전처리 불필요

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

        os.makedirs(os.path.join(str(_ROOT), "data", "temp_images"), exist_ok=True)
        fname = f"ig_{abs(hash(image_url))}.jpg"
        fpath = os.path.join(str(_ROOT), "data", "temp_images", fname)
        img.save(fpath, "JPEG", quality=95)
        logger.info(f"[Preprocess] 비율 보정 완료 | {w}x{h} ratio={ratio:.2f} → {fname}")
        return None, fpath

    except Exception as exc:
        logger.warning(f"[Preprocess] 이미지 전처리 실패 — 원본 URL 사용 | {exc}")
        return image_url, None


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


@handle_errors(task="insta_upload", notify_fn=_slack)
def _job_insta_upload():
    import time, requests as _req
    from modules.common.airtable_bridge import get_table

    token      = os.getenv("INSTA_ACCESS_TOKEN")
    ig_user_id = os.getenv("INSTA_IG_USER_ID", "").strip()
    if not token or not ig_user_id:
        logger.warning("[Main] INSTA 환경변수 미설정 — upload 생략")
        return

    table   = get_table("Instagram_Posts")
    records = table.all(formula="{post_status}='ready'")
    if not records:
        return

    logger.info(f"[Main] insta_upload | {len(records)}건 처리 시작")
    for rec in records:
        rid       = rec["id"]
        fields    = rec["fields"]
        image_url = fields.get("image_url") or fields.get("source_url", "")
        caption   = f"{fields.get('caption','')}\n{fields.get('hashtag','')}".strip()

        if not image_url:
            table.update(rid, {"post_status": "failed", "last_error_msg": "image_url 없음"})
            continue

        # 비율 보정 전처리 (4:5 ~ 1.91:1 범위 벗어나면 center-crop → multipart 업로드)
        upload_url, local_path = _preprocess_image(image_url)

        success, last_err = False, None
        for attempt in range(1, 4):
            try:
                if local_path:
                    # 비율 보정된 로컬 파일 → multipart/form-data 직접 업로드 (ngrok 불필요)
                    with open(local_path, "rb") as img_f:
                        r1 = _req.post(
                            f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
                            data={"caption": caption, "access_token": token},
                            files={"source": ("image.jpg", img_f, "image/jpeg")},
                            timeout=30,
                        )
                else:
                    # 비율 유효한 원본 → image_url 방식
                    r1 = _req.post(
                        f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
                        params={"image_url": upload_url, "caption": caption, "access_token": token},
                        timeout=30,
                    )
                c1 = r1.json()
                if "id" not in c1:
                    raise RuntimeError(f"미디어 생성 실패: {c1}")
                r2 = _req.post(
                    f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish",
                    params={"creation_id": c1["id"], "access_token": token},
                    timeout=30,
                )
                c2 = r2.json()
                if "id" not in c2:
                    raise RuntimeError(f"게시 실패: {c2}")
                table.update(rid, {
                    "post_status":   "posted",
                    "ig_media_id":   c2["id"],
                    "retry_count":   attempt - 1,
                    "last_error_msg": "",
                })
                logger.info(f"[Main] 업로드 성공 | {rid} | post_id={c2['id']}")
                success = True
                break
            except Exception as exc:
                last_err = exc
                if attempt < 3:
                    time.sleep(10)

        if not success:
            table.update(rid, {"post_status": "failed", "retry_count": 3, "last_error_msg": str(last_err)[:500]})
            logger.error(f"[Main] 업로드 최종 실패 | {rid}")


# ── 스케줄러 설정 ─────────────────────────────────────────────────────────────

def _build_scheduler() -> BackgroundScheduler:
    now = datetime.now()
    sched = BackgroundScheduler(timezone="Asia/Seoul")
    sched.add_job(_job_fb_crawl,     "interval", minutes=CRAWL_INTERVAL_MIN,
                  id="fb_crawl",     next_run_time=now)
    sched.add_job(_job_insta_upload, "interval", minutes=UPLOAD_POLL_MIN,
                  id="insta_upload", next_run_time=now + timedelta(seconds=20))
    sched.add_job(_job_kpi_snapshot, "interval", hours=1,
                  id="kpi_snapshot", next_run_time=now + timedelta(seconds=50))
    sched.add_job(_job_engagement_update, "interval", minutes=30,
                  id="engagement_update", next_run_time=now + timedelta(seconds=60))
    sched.add_job(_job_auto_like, "interval", minutes=15,
                  id="auto_like", next_run_time=now + timedelta(seconds=70))
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
