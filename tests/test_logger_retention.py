"""261012 — app.log 보존 backup 5→12만 변경, 나머지 핸들러는 기존 값 유지 확인.
파일 기록·로테이션 실행 없음(핸들러 설정값만 검사).
"""

from logging.handlers import RotatingFileHandler

from modules.common import logger as central

_5MB = 5 * 1024 * 1024
_2MB = 2 * 1024 * 1024


def test_app_log_backup_is_12_and_max_bytes_unchanged():
    h = central._summary_handler
    assert isinstance(h, RotatingFileHandler)
    assert h.baseFilename.endswith("app.log")
    assert h.backupCount == 12
    assert h.maxBytes == _5MB


def test_error_log_unchanged():
    h = central._error_handler
    assert h.baseFilename.endswith("error.log")
    assert h.backupCount == 5
    assert h.maxBytes == _5MB


def test_function_log_handler_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(central, "_FUNC_DIR", tmp_path)  # 실제 logs/ 아래 파일 생성 방지
    lg = central.get_logger("tests.retention_probe")
    func = [h for h in lg.handlers
            if isinstance(h, RotatingFileHandler) and h.baseFilename.endswith("tests_retention_probe.log")]
    try:
        assert func
        assert func[0].backupCount == 3
        assert func[0].maxBytes == _2MB
    finally:
        for h in func:
            lg.removeHandler(h)
            h.close()
