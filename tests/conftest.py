"""
tests/conftest.py — 테스트가 운영 logs/·db/에 기록하지 않게 격리한다 (ERR-131).

운영 코드는 바꾸지 않는다. 테스트 실행 중에만 경로를 임시 폴더로 돌린다.

1) 세션 시작(테스트 모듈 import 전): 중앙 로거(modules.common.logger)의
   app.log / error.log 핸들러와 logs/function 폴더를 세션 임시 폴더로 옮긴다.
   logger.py는 import 시 .env를 읽지 않으므로 여기서 import해도 환경변수가 바뀌지 않는다.
2) 테스트마다: 이미 로드된 프로젝트 모듈의 모듈 상수 중 운영 db/ 또는 logs/ 아래를
   가리키는 Path를 임시 폴더로 monkeypatch한다(테스트 종료 시 자동 원복).
   새 모듈은 import하지 않는다 — airtable_usage_logger 등은 import 시 .env를 override로 읽기 때문.
3) 세션 전체: 루프백(localhost / 127.x / ::1) 외의 DNS 조회와 소켓 연결을 차단한다.
   운영 .env에 실제 Slack·Telegram·Airtable 인증값이 있으므로, Mock이 빠진 테스트가
   실제 발송하지 않게 한다(측정: 5개 파일 13건). 차단은 OSError로 나타난다.
"""
import errno
import shutil
import socket
import sys
import tempfile
from pathlib import Path

import pytest

# ── 3) 외부 네트워크 차단 ─────────────────────────────────────────────────────
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_real_getaddrinfo = socket.getaddrinfo
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


class ExternalNetworkBlockedError(OSError):
    """테스트 중 외부 네트워크 접근 시도."""


def _is_loopback(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    text = str(host).strip("[]").lower()
    return text in _LOOPBACK_HOSTS or text.startswith("127.")


def _guarded_getaddrinfo(host, port, *args, **kwargs):
    # host None/""는 로컬 바인드 조회라 외부 접근이 아니다
    if host not in (None, "", b"") and not _is_loopback(host):
        raise ExternalNetworkBlockedError(f"[tests/conftest] external DNS lookup blocked: {host}")
    return _real_getaddrinfo(host, port, *args, **kwargs)


def _target_host(address):
    if isinstance(address, tuple) and address:
        return address[0]
    return None


def _guarded_connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_loopback(_target_host(address)):
        raise ExternalNetworkBlockedError(f"[tests/conftest] external connection blocked: {address}")
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_loopback(_target_host(address)):
        return errno.EACCES
    return _real_connect_ex(self, address)


socket.getaddrinfo = _guarded_getaddrinfo
socket.socket.connect = _guarded_connect
socket.socket.connect_ex = _guarded_connect_ex

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROD_LOGS = _PROJECT_ROOT / "logs"
_PROD_DB = _PROJECT_ROOT / "db"
_PROJECT_PACKAGES = ("launcher", "modules", "core", "services", "adapters")
_CENTRAL_LOGGER_MODULE = "modules.common.logger"

_SESSION_TMP = Path(tempfile.mkdtemp(prefix="sns_pytest_isolation_"))


# ── 4) Boot Policy 테스트 전용 주입 (261029) ────────────────────────────────────────
# 운영 Boot Policy(C:\ProgramData\SNS_24AutoProject\runtime_boot_policy.json)는 SYSTEM·Administrators
# 전용이라 일반 셸의 pytest는 modules.dm(dm_receiver) import에서 PermissionError로 죽는다. 테스트가
# 운영 파일을 읽거나 쓰지 않도록, 프로젝트 운영 모듈이 부르는 인자 없는 기본 호출(policy_path=None,
# require_boot_policy=False — dm_receiver의 import 시점 호출이 이 형태다)에만 세션 임시 폴더의 production 모드
# 정책을 대신 쓴다. 테스트 코드가 직접 부르는 호출은 바꾸지 않는다.
# 상수 DEFAULT_RUNTIME_BOOT_POLICY_PATH는 바꾸지 않는다(경로 계약을 검사하는 테스트 보존).
# 명시적 policy_path를 넘기거나 require_boot_policy=True로 부르는 호출(운영 진입점 검증 테스트)은
# 그대로 통과시킨다. 운영 정책을 실제로 읽어야 하는 환경(CI 등)은 SNS_TEST_REAL_BOOT_POLICY=1.
_ORIG_GET_CANARY_STATE = None
_csm = None


def _install_test_boot_policy():
    global _ORIG_GET_CANARY_STATE, _csm
    import json
    import os

    if os.environ.get("SNS_TEST_REAL_BOOT_POLICY") == "1":
        return
    try:
        from modules.common import canary_safe_mode as csm
    except Exception:
        return
    if _relative_to(Path(csm.__file__), _PROJECT_ROOT) is None:
        return   # 다른 저장소의 모듈이면 건드리지 않는다

    policy = _SESSION_TMP / "test_boot_policy" / "runtime_boot_policy.json"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(json.dumps({
        "schema_version": 1, "mode": "production", "state": "active", "purpose": "production",
        "context_id": "", "run_id": "", "expires_at": "",
    }), encoding="utf-8")

    original = csm.get_canary_safe_mode_state

    def _get_state_with_test_policy(*, now=None, require_boot_policy=False,
                                    activate_boot_policy=False, policy_path=None):
        if policy_path is None and not require_boot_policy and not activate_boot_policy:
            # 프로젝트 운영 모듈(modules.dm.dm_receiver 등)의 인자 없는 호출만 대체한다. 테스트가 직접
            # 부르는 호출(환경변수 모드·경로 probe 오류 등을 검증)은 원래 동작 그대로 둔다.
            caller = sys._getframe(1).f_globals.get("__name__", "")
            if caller.split(".")[0] in _PROJECT_PACKAGES:
                policy_path = policy
        return original(now=now, require_boot_policy=require_boot_policy,
                        activate_boot_policy=activate_boot_policy, policy_path=policy_path)

    _get_state_with_test_policy.__wrapped__ = original
    csm.get_canary_safe_mode_state = _get_state_with_test_policy
    _ORIG_GET_CANARY_STATE, _csm = original, csm


def _relative_to(path: Path, base: Path):
    try:
        return path.resolve().relative_to(base)
    except (ValueError, OSError):
        return None


def _redirect_central_logger():
    try:
        from modules.common import logger as central_logger
    except Exception:
        return None
    # 다른 저장소(예: PYTHONPATH 누수)의 logger라면 건드리지 않는다
    if _relative_to(Path(central_logger.__file__), _PROJECT_ROOT) is None:
        return None

    log_dir = _SESSION_TMP / "logs"
    for sub in ("summary", "error", "function"):
        (log_dir / sub).mkdir(parents=True, exist_ok=True)

    targets = (
        (central_logger._summary_handler, log_dir / "summary" / "app.log"),
        (central_logger._error_handler, log_dir / "error" / "error.log"),
    )
    for handler, target in targets:
        handler.acquire()
        try:
            if handler.stream is not None:
                handler.stream.close()
                handler.stream = None
            handler.baseFilename = str(target)
        finally:
            handler.release()
    central_logger._FUNC_DIR = log_dir / "function"
    return central_logger


_central_logger = _redirect_central_logger()
_install_test_boot_policy()   # _relative_to 정의 이후에 호출해야 한다


def pytest_unconfigure(config):
    if _csm is not None and _ORIG_GET_CANARY_STATE is not None:
        _csm.get_canary_safe_mode_state = _ORIG_GET_CANARY_STATE
    socket.getaddrinfo = _real_getaddrinfo
    socket.socket.connect = _real_connect
    socket.socket.connect_ex = _real_connect_ex
    if _central_logger is not None:
        for handler in (_central_logger._summary_handler, _central_logger._error_handler):
            handler.acquire()
            try:
                if handler.stream is not None:
                    handler.stream.close()
                    handler.stream = None
            finally:
                handler.release()
    shutil.rmtree(_SESSION_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def _isolate_production_state_paths(monkeypatch, tmp_path_factory):
    isolated = tmp_path_factory.mktemp("isolated_state")
    bases = ((_PROD_DB, isolated / "db"), (_PROD_LOGS, isolated / "logs"))
    for _, target_base in bases:
        target_base.mkdir(parents=True, exist_ok=True)

    for name, module in list(sys.modules.items()):
        if module is None or name == _CENTRAL_LOGGER_MODULE:
            continue
        if name.split(".")[0] not in _PROJECT_PACKAGES:
            continue
        module_file = getattr(module, "__file__", None)
        if not module_file or _relative_to(Path(module_file), _PROJECT_ROOT) is None:
            continue
        for attr, value in list(vars(module).items()):
            if not isinstance(value, Path):
                continue
            for prod_base, target_base in bases:
                rel = _relative_to(value, prod_base)
                if rel is None:
                    continue
                target = target_base / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                monkeypatch.setattr(module, attr, target)
                break
    yield
