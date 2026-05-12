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

import os
import sys

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


# ── 잡 함수 ───────────────────────────────────────────────────────────────────

@handle_errors(task="fb_crawl")
def _job_fb_crawl():
    from modules.sns.facebook_crawler import run_all_accounts
    summary = run_all_accounts()
    logger.info(f"[Main] fb_crawl 완료 | {summary}")


@handle_errors(task="kpi_snapshot")
def _job_kpi_snapshot():
    from modules.metrics.kpi_collector import run_hourly_snapshot
    run_hourly_snapshot()


@handle_errors(task="insta_upload")
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

        success, last_err = False, None
        for attempt in range(1, 4):
            try:
                r1 = _req.post(
                    f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
                    data={"image_url": image_url, "caption": caption, "access_token": token},
                    timeout=30,
                )
                c1 = r1.json()
                if "id" not in c1:
                    raise RuntimeError(f"미디어 생성 실패: {c1}")
                r2 = _req.post(
                    f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish",
                    data={"creation_id": c1["id"], "access_token": token},
                    timeout=30,
                )
                c2 = r2.json()
                if "id" not in c2:
                    raise RuntimeError(f"게시 실패: {c2}")
                table.update(rid, {"post_status": "posted", "retry_count": attempt - 1, "last_error_msg": ""})
                logger.info(f"[Main] 업로드 성공 | {rid}")
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
