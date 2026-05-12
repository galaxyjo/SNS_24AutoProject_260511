"""
core/task_router.py — 태스크 이름 → 핸들러 분기

사용법:
    from core.task_router import TaskRouter

    router = TaskRouter()
    router.register("fb_crawl",    crawl_fn)
    router.register("insta_upload", upload_fn)

    router.dispatch("fb_crawl")          # 동기 실행
    router.dispatch("insta_upload", record_id="xxx")
"""

from typing import Callable, Any
from modules.common.logger import get_logger
from core.error_handler import safe_run

logger = get_logger(__name__)


class TaskRouter:
    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register(self, task_name: str, handler: Callable) -> None:
        self._handlers[task_name] = handler
        logger.debug(f"[TaskRouter] 등록: {task_name}")

    def dispatch(self, task_name: str, **kwargs) -> Any:
        """등록된 핸들러를 찾아 실행. 미등록 태스크는 경고 로그."""
        handler = self._handlers.get(task_name)
        if not handler:
            logger.warning(f"[TaskRouter] 미등록 태스크: {task_name}")
            return None
        logger.info(f"[TaskRouter] 실행: {task_name}")
        return safe_run(handler, task=task_name, **kwargs)

    def registered(self) -> list[str]:
        return list(self._handlers.keys())
