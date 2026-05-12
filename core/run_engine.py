"""
core/run_engine.py — 전체 스케줄 오케스트레이터

기존 insta_scheduler.py의 스케줄 잡을 TaskRouter + 중앙 로거 기반으로 통합.
단독 실행 시 모든 잡을 APScheduler로 구동.

사용법:
    python -m core.run_engine          # 직접 실행
    from core.run_engine import RunEngine
    engine = RunEngine()
    engine.start()
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)

from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler

from core.log_initializer import init_logging
from core.task_router import TaskRouter
from core.error_handler import handle_errors
from modules.common.logger import get_logger
from modules.common.retry_queue import get_retry_queue

init_logging()
logger = get_logger(__name__)

CRAWL_INTERVAL_MIN  = int(os.getenv("CRAWL_INTERVAL_MINUTES", "30"))
UPLOAD_POLL_MIN     = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))
FOLLOWUP_POLL_MIN   = 5

# Slack 알림 (SLACK_WEBHOOK_URL 미설정 시 None → 알림 생략)
try:
    from services.slack_notifier import get_notify_fn as _get_notify_fn
    _slack = _get_notify_fn()
except Exception:
    _slack = None


# ── 잡 함수 ──────────────────────────────────────────────────────────────────

@handle_errors(task="fb_crawl", reraise=False, notify_fn=_slack)
def _job_fb_crawl():
    from modules.sns.facebook_crawler import run_all_accounts
    summary = run_all_accounts()
    logger.info(f"[RunEngine] fb_crawl 완료 | {summary}")


@handle_errors(task="insta_upload", reraise=False, notify_fn=_slack)
def _job_insta_upload():
    import time, requests
    from modules.common.airtable_bridge import get_table

    page_token = os.getenv("INSTA_ACCESS_TOKEN")
    ig_user_id = os.getenv("INSTA_IG_USER_ID", "").strip()
    if not page_token or not ig_user_id:
        logger.warning("[RunEngine] INSTA 환경변수 미설정 — upload 생략")
        return

    table   = get_table("Instagram_Posts")
    records = table.all(formula="{post_status}='ready'")

    if not records:
        logger.info("[RunEngine] insta_upload | ready 레코드 없음")
        return

    logger.info(f"[RunEngine] insta_upload | {len(records)}건 처리 시작")
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
                r1 = requests.post(
                    f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
                    data={"image_url": image_url, "caption": caption, "access_token": page_token},
                    timeout=30,
                )
                c1 = r1.json()
                if "id" not in c1:
                    raise RuntimeError(f"미디어 생성 실패: {c1}")
                r2 = requests.post(
                    f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish",
                    data={"creation_id": c1["id"], "access_token": page_token},
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
                logger.info(f"[RunEngine] 업로드 성공 | {rid} | post_id={c2['id']}")
                success = True
                break
            except Exception as exc:
                last_err = exc
                logger.warning(f"[RunEngine] 업로드 시도 {attempt}/3 실패 | {rid} | {exc}")
                if attempt < 3:
                    time.sleep(10)

        if not success:
            table.update(rid, {"post_status": "failed", "retry_count": 3, "last_error_msg": str(last_err)[:500]})
            logger.error(f"[RunEngine] 업로드 최종 실패 | {rid}")


@handle_errors(task="followup_poll", reraise=False, notify_fn=_slack)
def _job_followup_poll():
    from modules.dm.dm_followup_scheduler import process_due_followups
    process_due_followups()


@handle_errors(task="comment_poll", reraise=False, notify_fn=_slack)
def _job_comment_poll():
    from modules.comment.comment_poller import poll_new_comments
    poll_new_comments()


@handle_errors(task="daily_report", reraise=False, notify_fn=_slack)
def _job_daily_report():
    from modules.crm.daily_report import send_daily_report
    send_daily_report()


@handle_errors(task="kpi_snapshot", reraise=False, notify_fn=_slack)
def _job_kpi_snapshot():
    from modules.metrics.kpi_collector import run_hourly_snapshot
    run_hourly_snapshot()


@handle_errors(task="engagement_update", reraise=False, notify_fn=_slack)
def _job_engagement_update():
    from modules.interaction_engine.interaction_scheduler import run_engagement_update
    run_engagement_update()


@handle_errors(task="auto_like", reraise=False, notify_fn=_slack)
def _job_auto_like():
    from modules.interaction_engine.interaction_scheduler import run_auto_like
    run_auto_like()


# ── RunEngine ─────────────────────────────────────────────────────────────────

class RunEngine:
    def __init__(self):
        self.router    = TaskRouter()
        self.scheduler = BlockingScheduler(timezone="Asia/Seoul")
        self._rq       = get_retry_queue()
        self._register_tasks()
        self._register_jobs()

    def _register_tasks(self):
        self.router.register("fb_crawl",      _job_fb_crawl)
        self.router.register("insta_upload",  _job_insta_upload)
        self.router.register("followup_poll", _job_followup_poll)
        self.router.register("comment_poll",  _job_comment_poll)
        self.router.register("daily_report",  _job_daily_report)
        self.router.register("kpi_snapshot",      _job_kpi_snapshot)
        self.router.register("engagement_update", _job_engagement_update)
        self.router.register("auto_like",         _job_auto_like)

    def _register_jobs(self):
        now = datetime.now()
        self.scheduler.add_job(
            _job_fb_crawl, "interval", minutes=CRAWL_INTERVAL_MIN,
            id="fb_crawl", next_run_time=now,
        )
        self.scheduler.add_job(
            _job_insta_upload, "interval", minutes=UPLOAD_POLL_MIN,
            id="insta_upload", next_run_time=now + timedelta(seconds=20),
        )
        self.scheduler.add_job(
            _job_followup_poll, "interval", minutes=FOLLOWUP_POLL_MIN,
            id="followup_poll", next_run_time=now + timedelta(seconds=30),
        )
        self.scheduler.add_job(
            _job_comment_poll, "interval", minutes=FOLLOWUP_POLL_MIN,
            id="comment_poll", next_run_time=now + timedelta(seconds=40),
        )
        self.scheduler.add_job(
            _job_daily_report, "cron", hour=9, minute=0,
            id="daily_report",
        )
        self.scheduler.add_job(
            _job_kpi_snapshot, "interval", hours=1,
            id="kpi_snapshot", next_run_time=now + timedelta(seconds=50),
        )
        self.scheduler.add_job(
            _job_engagement_update, "interval", minutes=30,
            id="engagement_update", next_run_time=now + timedelta(seconds=60),
        )
        self.scheduler.add_job(
            _job_auto_like, "interval", minutes=15,
            id="auto_like", next_run_time=now + timedelta(seconds=70),
        )

    def start(self):
        self._rq.start()
        logger.info(
            f"[RunEngine] 시작 | 크롤링={CRAWL_INTERVAL_MIN}분 | "
            f"업로드={UPLOAD_POLL_MIN}분 | 팔로업/댓글={FOLLOWUP_POLL_MIN}분"
        )
        logger.info(f"[RunEngine] 등록 태스크: {self.router.registered()}")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("[RunEngine] 종료")
            self._rq.stop()


if __name__ == "__main__":
    RunEngine().start()
