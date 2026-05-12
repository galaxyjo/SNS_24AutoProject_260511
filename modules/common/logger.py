"""
중앙 로거 (modules/common/logger.py)

사용법:
    from modules.common.logger import get_logger
    logger = get_logger(__name__)
    logger.info("메시지")

로그 라우팅:
    - 콘솔              : INFO+
    - logs/summary/app.log  : INFO+  (RotatingFileHandler, 5MB × 5)
    - logs/error/error.log  : ERROR+ (RotatingFileHandler, 5MB × 5)
    - logs/function/{name}.log : DEBUG+ (모듈별, RotatingFileHandler, 2MB × 3)
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parents[2]   # 프로젝트 루트
_LOG_ROOT    = _BASE / "logs"
_SUMMARY_DIR = _LOG_ROOT / "summary"
_ERROR_DIR   = _LOG_ROOT / "error"
_FUNC_DIR    = _LOG_ROOT / "function"

for _d in (_SUMMARY_DIR, _ERROR_DIR, _FUNC_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── 포맷 ──────────────────────────────────────────────────────────────────────
_FMT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

# ── 공유 핸들러 (프로세스당 1회만 생성) ─────────────────────────────────────────
def _make_handler(path: Path, level: int, max_bytes: int = 5 * 1024 * 1024, backup: int = 5):
    h = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup, encoding="utf-8")
    h.setLevel(level)
    h.setFormatter(_formatter)
    return h

_summary_handler = _make_handler(_SUMMARY_DIR / "app.log", logging.INFO)
_error_handler   = _make_handler(_ERROR_DIR   / "error.log", logging.ERROR)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_formatter)

# ── 루트 로거 기본 설정 ───────────────────────────────────────────────────────
_root = logging.getLogger()
if not _root.handlers:
    _root.setLevel(logging.DEBUG)
    _root.addHandler(_console_handler)
    _root.addHandler(_summary_handler)
    _root.addHandler(_error_handler)

# ── 공개 API ──────────────────────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    """모듈별 로거 반환. logs/function/{name}.log 에도 기록."""
    logger = logging.getLogger(name)

    # 모듈별 function 로그 (중복 추가 방지)
    safe_name = name.replace(".", "_")
    func_path = _FUNC_DIR / f"{safe_name}.log"
    if not any(
        isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == func_path.resolve()
        for h in logger.handlers
    ):
        func_handler = _make_handler(func_path, logging.DEBUG, max_bytes=2 * 1024 * 1024, backup=3)
        logger.addHandler(func_handler)

    return logger
