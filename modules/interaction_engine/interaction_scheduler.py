"""
modules/interaction_engine/interaction_scheduler.py — interaction 잡 진입점

스케줄러(run_engine / launcher)에서 호출하는 잡 함수를 제공한다.

단독 실행 (1회 즉시 실행):
    python -m modules.interaction_engine.interaction_scheduler
"""

from modules.interaction_engine.engagement_tracker import update_engagement_metrics
from modules.interaction_engine.auto_liker import like_new_comments
from modules.common.logger import get_logger

logger = get_logger(__name__)


def run_engagement_update() -> None:
    """스케줄러 잡: 게시물 engagement 지표 갱신 (like_count / comments_count)."""
    result = update_engagement_metrics()
    logger.info(f"[InteractionScheduler] engagement 갱신 완료 | {result}")


def run_auto_like() -> None:
    """스케줄러 잡: 새 댓글 자동 좋아요."""
    result = like_new_comments()
    logger.info(f"[InteractionScheduler] auto_like 완료 | {result}")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

    from dotenv import load_dotenv
    load_dotenv(override=True)
    from core.log_initializer import init_logging
    init_logging()

    logger.info("[InteractionScheduler] 즉시 실행 모드")
    run_engagement_update()
    run_auto_like()
