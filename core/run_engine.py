"""
core/run_engine.py — 전체 스케줄 오케스트레이터

launcher/main.py의 스케줄 잡을 TaskRouter + 중앙 로거 기반으로 통합.
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
from modules.common.canary_safe_mode import get_canary_safe_mode_state
from modules.comment.comment_auto_reply import register_retry_handlers as _register_comment_retry_handlers

init_logging()
logger = get_logger(__name__)

CRAWL_INTERVAL_MIN  = int(os.getenv("CRAWL_INTERVAL_MINUTES", "30"))
UPLOAD_POLL_MIN     = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))
FOLLOWUP_POLL_MIN   = 5
PRODUCT_PUBLISH_ACCOUNT_CODE = "IDN-000041"
PRODUCT_DATA_CLASSIFICATION = "production"

# Slack 알림 (SLACK_WEBHOOK_URL 미설정 시 None → 알림 생략)
try:
    from services.slack_notifier import get_notify_fn as _get_notify_fn
    _slack = _get_notify_fn()
except Exception:
    _slack = None


# ── 잡 함수 ──────────────────────────────────────────────────────────────────

@handle_errors(task="fb_crawl", reraise=False, notify_fn=_slack)
def _job_fb_crawl(
    *,
    target_publish_account_code_ref: str,
    data_classification: str,
    canary_run_id: str = "",
):
    from modules.sns.facebook_crawler import run_all_accounts
    summary = run_all_accounts(
        target_publish_account_code_ref=target_publish_account_code_ref,
        data_classification=data_classification,
        canary_run_id=canary_run_id,
    )
    logger.info(f"[RunEngine] fb_crawl 완료 | {summary}")


@handle_errors(task="insta_upload", reraise=False, notify_fn=_slack)
def _job_insta_upload():
    # 독립 실행 경로도 Active launcher의 계정별 Provider 검증을 그대로 사용한다.
    from launcher.main import _job_insta_upload as _active_upload_job
    return _active_upload_job()


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


@handle_errors(task="ngrok_check", reraise=False, notify_fn=_slack)
def _job_ngrok_check():
    from modules.common.ngrok_monitor import check_ngrok_url
    result = check_ngrok_url()
    if result["status"] != "ok":
        logger.warning(f"[RunEngine] ngrok_check | {result}")


@handle_errors(task="crawl_url_check", reraise=False, notify_fn=_slack)
def _job_crawl_url_check():
    from modules.common.crawl_url_checker import check_all
    results = check_all()
    problems = {u: s for u, s in results.items() if s != "ok"}
    if problems:
        logger.warning(f"[RunEngine] crawl_url_check | 이상 URL {len(problems)}건")


@handle_errors(task="airtable_integrity", reraise=False, notify_fn=_slack)
def _job_airtable_integrity():
    from modules.metrics.airtable_integrity import check_ig_media_id
    result = check_ig_media_id()
    if result["missing"]:
        logger.warning(f"[RunEngine] airtable_integrity | ig_media_id 누락 {result['missing']}건")


@handle_errors(task="comment_dead_monitor", reraise=False, notify_fn=_slack)
def _job_comment_dead_monitor():
    """FP-047 — comment_airtable_record retry_queue dead 건 능동 알림(설계문서 §5)."""
    from modules.comment.comment_retry_dead_monitor import check_dead_comment_tasks
    n = check_dead_comment_tasks()
    if n:
        logger.warning(f"[RunEngine] comment_dead_monitor | 신규 dead 알림 {n}건")


# ── RunEngine ─────────────────────────────────────────────────────────────────

class RunEngine:
    def __init__(self):
        # W1: 영속 Boot Policy 누락·손상·만료는 Runtime 객체 생성 전에 차단한다.
        self._safe_mode_state = get_canary_safe_mode_state(
            require_boot_policy=True,
            activate_boot_policy=True,
        )
        self.router    = TaskRouter()
        self.scheduler = BlockingScheduler(timezone="Asia/Seoul")
        self._rq       = None

        if self._safe_mode_state.enabled:
            logger.warning(
                "[CanarySafeMode] core.run_engine RetryQueue·Task·Scheduler Job 0건"
            )
            return

        self._rq       = get_retry_queue()
        # FP-047: comment_airtable_record 핸들러는 rq.start() 이전에 eager 등록해야 함
        # (설계문서 §6 — 지연등록 시 재시작 후 pending task가 dead 처리될 위험)
        _register_comment_retry_handlers(self._rq)
        self._register_tasks()
        self._register_jobs()

    def _register_tasks(self):
        self.router.register(
            "fb_crawl",
            lambda: _job_fb_crawl(
                target_publish_account_code_ref=PRODUCT_PUBLISH_ACCOUNT_CODE,
                data_classification=PRODUCT_DATA_CLASSIFICATION,
            ),
        )
        self.router.register("insta_upload",  _job_insta_upload)
        self.router.register("followup_poll", _job_followup_poll)
        self.router.register("comment_poll",  _job_comment_poll)
        self.router.register("daily_report",  _job_daily_report)
        self.router.register("kpi_snapshot",      _job_kpi_snapshot)
        self.router.register("engagement_update", _job_engagement_update)
        self.router.register("auto_like",         _job_auto_like)
        self.router.register("ngrok_check",       _job_ngrok_check)
        self.router.register("crawl_url_check",    _job_crawl_url_check)
        self.router.register("airtable_integrity", _job_airtable_integrity)
        self.router.register("comment_dead_monitor", _job_comment_dead_monitor)

    def _register_jobs(self):
        now = datetime.now()
        self.scheduler.add_job(
            _job_fb_crawl, "interval", minutes=CRAWL_INTERVAL_MIN,
            id="fb_crawl", next_run_time=now,
            kwargs={
                "target_publish_account_code_ref": PRODUCT_PUBLISH_ACCOUNT_CODE,
                "data_classification": PRODUCT_DATA_CLASSIFICATION,
            },
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
        self.scheduler.add_job(
            _job_ngrok_check, "interval", minutes=5,
            id="ngrok_check", next_run_time=now + timedelta(seconds=80),
        )
        self.scheduler.add_job(
            _job_crawl_url_check, "interval", hours=1,
            id="crawl_url_check", next_run_time=now + timedelta(seconds=90),
        )
        self.scheduler.add_job(
            _job_airtable_integrity, "interval", hours=6,
            id="airtable_integrity", next_run_time=now + timedelta(seconds=100),
        )
        self.scheduler.add_job(
            _job_comment_dead_monitor, "interval", minutes=15,
            id="comment_dead_monitor", next_run_time=now + timedelta(seconds=110),
            max_instances=1, coalesce=True,
        )

    def start(self):
        if self._safe_mode_state.enabled:
            logger.warning(
                "[CanarySafeMode] core.run_engine 자동 Side Effect 시작 차단"
            )
            return

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
