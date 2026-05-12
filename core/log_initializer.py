"""
core/log_initializer.py — 프로세스 시작 시 로거 1회 초기화

사용법:
    from core.log_initializer import init_logging
    init_logging()   # main() 최상단에서 호출
"""

import logging
from modules.common.logger import get_logger, _summary_handler, _error_handler, _console_handler

_initialized = False


def init_logging(level: int = logging.INFO) -> None:
    """루트 로거를 중앙 핸들러로 설정한다. 중복 호출 시 무시."""
    global _initialized
    if _initialized:
        return

    root = logging.getLogger()
    root.setLevel(level)

    existing = {type(h) for h in root.handlers}
    for handler in [_console_handler, _summary_handler, _error_handler]:
        if type(handler) not in existing:
            root.addHandler(handler)

    _initialized = True
    logger = get_logger(__name__)
    logger.info("[LogInitializer] 중앙 로거 초기화 완료")
