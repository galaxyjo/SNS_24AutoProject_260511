"""
core/error_handler.py — 공통 예외처리 유틸

사용법:
    from core.error_handler import handle_errors, safe_run

    @handle_errors(task="fb_crawl", reraise=False)
    def crawl():
        ...

    result = safe_run(my_fn, arg1, arg2, task="upload")
"""

import functools
import traceback
from typing import Callable, Any, Optional

from modules.common.logger import get_logger

logger = get_logger(__name__)


def handle_errors(
    task: str = "",
    reraise: bool = False,
    notify_fn: Optional[Callable[[str], None]] = None,
):
    """예외를 잡아 로깅하고 선택적으로 재발생시키는 데코레이터.

    Args:
        task:      태스크 이름 (로그 식별용)
        reraise:   True면 예외 재발생, False면 None 반환
        notify_fn: 예외 발생 시 호출할 알림 함수 (예: Telegram 전송)
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            label = task or fn.__name__
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                tb = traceback.format_exc()
                logger.error(f"[ErrorHandler] {label} 실패 | {exc}\n{tb}")
                if notify_fn:
                    try:
                        notify_fn(f"[{label}] 오류: {exc}")
                    except Exception:
                        pass
                if reraise:
                    raise
                return None
        return wrapper
    return decorator


def safe_run(
    fn: Callable,
    *args,
    task: str = "",
    notify_fn: Optional[Callable[[str], None]] = None,
    **kwargs,
) -> Any:
    """fn(*args, **kwargs)를 실행하고 예외 시 None 반환."""
    label = task or fn.__name__
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.error(f"[ErrorHandler] {label} 실패 | {exc}")
        if notify_fn:
            try:
                notify_fn(f"[{label}] 오류: {exc}")
            except Exception:
                pass
        return None
