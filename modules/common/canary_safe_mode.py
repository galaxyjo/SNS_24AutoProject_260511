"""Canary Safe Mode와 W1 Runtime Boot Policy 검증.

환경변수 계약은 기존 단위 테스트와 Canary Runner 호환을 위해 유지한다.
실제 Runtime 진입점은 ``require_boot_policy=True``로 이 모듈의 영속
Boot Policy를 반드시 검증해야 한다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CONTEXT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_POLICY_FIELDS = {
    "schema_version",
    "mode",
    "state",
    "purpose",
    "context_id",
    "run_id",
    "expires_at",
}
_MAX_POLICY_BYTES = 16 * 1024
_SAFE_PURPOSE = "approval_r"

DEFAULT_RUNTIME_BOOT_POLICY_PATH = (
    Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    / "SNS_24AutoProject"
    / "runtime_boot_policy.json"
)


class CanarySafeModeError(RuntimeError):
    """Safe Mode 설정이 불완전하거나 만료됨."""


@dataclass(frozen=True)
class CanarySafeModeState:
    enabled: bool
    run_id: str = ""
    expires_at: datetime | None = None
    purpose: str = ""
    context_id: str = ""
    policy_state: str = ""
    source: str = "environment"


@dataclass(frozen=True)
class RuntimeBootPolicy:
    schema_version: int
    mode: str
    state: str
    purpose: str
    context_id: str
    run_id: str
    expires_at: datetime | None
    source_path: Path

    @property
    def safe_mode_enabled(self) -> bool:
        return self.mode == "safe"

    def to_safe_mode_state(self) -> CanarySafeModeState:
        return CanarySafeModeState(
            enabled=self.safe_mode_enabled,
            run_id=self.run_id,
            expires_at=self.expires_at,
            purpose=self.purpose,
            context_id=self.context_id,
            policy_state=self.state,
            source="boot_policy",
        )


def _parse_expiry(raw: str) -> datetime:
    value = (raw or "").strip()
    if not value:
        raise CanarySafeModeError("CANARY_EXPIRES_AT 필수")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CanarySafeModeError(
            "CANARY_EXPIRES_AT은 timezone 포함 ISO-8601 형식이어야 함"
        ) from exc
    if parsed.tzinfo is None:
        raise CanarySafeModeError("CANARY_EXPIRES_AT timezone 필수")
    return parsed.astimezone(timezone.utc)


def mask_canary_run_id(run_id: str) -> str:
    """로그·Health용 Run ID 마스킹."""

    value = (run_id or "").strip()
    if not value:
        return ""
    if len(value) <= 6:
        return f"{value[:1]}***{value[-1:]}"
    return f"{value[:3]}***{value[-3:]}"


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CanarySafeModeError(f"Boot Policy 중복 필드: {key}")
        result[key] = value
    return result


def _read_policy_document(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink():
            raise CanarySafeModeError("Boot Policy symbolic link 금지")
        stat = path.stat()
    except FileNotFoundError as exc:
        raise CanarySafeModeError("Runtime Boot Policy 파일 없음") from exc
    except OSError as exc:
        raise CanarySafeModeError("Runtime Boot Policy 상태 확인 실패") from exc

    if not path.is_file():
        raise CanarySafeModeError("Runtime Boot Policy가 일반 파일이 아님")
    if stat.st_size <= 0 or stat.st_size > _MAX_POLICY_BYTES:
        raise CanarySafeModeError("Runtime Boot Policy 크기 오류")

    try:
        raw_bytes = path.read_bytes()
        if len(raw_bytes) > _MAX_POLICY_BYTES:
            raise CanarySafeModeError("Runtime Boot Policy 크기 오류")
        document = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except UnicodeDecodeError as exc:
        raise CanarySafeModeError("Runtime Boot Policy UTF-8 오류") from exc
    except json.JSONDecodeError as exc:
        raise CanarySafeModeError("Runtime Boot Policy JSON 오류") from exc
    except OSError as exc:
        raise CanarySafeModeError("Runtime Boot Policy 읽기 실패") from exc

    if not isinstance(document, dict):
        raise CanarySafeModeError("Runtime Boot Policy 최상위 객체 필수")
    unknown = set(document) - _POLICY_FIELDS
    missing = _POLICY_FIELDS - set(document)
    if unknown:
        raise CanarySafeModeError(
            f"Runtime Boot Policy 허용되지 않은 필드: {','.join(sorted(unknown))}"
        )
    if missing:
        raise CanarySafeModeError(
            f"Runtime Boot Policy 필수 필드 누락: {','.join(sorted(missing))}"
        )
    for forbidden in ("token", "secret", "password", "credential", "api_key"):
        if any(forbidden in key.lower() for key in document):
            raise CanarySafeModeError("Runtime Boot Policy Credential 필드 금지")
    return document


def load_runtime_boot_policy(
    *,
    now: datetime | None = None,
    policy_path: str | os.PathLike[str] | None = None,
) -> RuntimeBootPolicy:
    """영속 Boot Policy를 읽고 Production/Safe 계약을 엄격 검증한다."""

    path = (
        Path(policy_path)
        if policy_path is not None
        else DEFAULT_RUNTIME_BOOT_POLICY_PATH
    )
    document = _read_policy_document(path)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise CanarySafeModeError("현재 시각 timezone 필수")
    current = current.astimezone(timezone.utc)

    schema_version = document["schema_version"]
    if isinstance(schema_version, bool) or schema_version != 1:
        raise CanarySafeModeError("Runtime Boot Policy schema_version=1 필수")

    string_fields = (
        "mode",
        "state",
        "purpose",
        "context_id",
        "run_id",
        "expires_at",
    )
    if any(not isinstance(document[field], str) for field in string_fields):
        raise CanarySafeModeError("Runtime Boot Policy 문자열 필드 형식 오류")

    mode = document["mode"].strip()
    state = document["state"].strip()
    purpose = document["purpose"].strip()
    context_id = document["context_id"].strip()
    run_id = document["run_id"].strip()
    raw_expiry = document["expires_at"].strip()

    if mode == "production":
        if state != "active":
            raise CanarySafeModeError("Production Boot Policy state=active 필수")
        if purpose != "production":
            raise CanarySafeModeError("Production Boot Policy purpose=production 필수")
        if context_id or run_id or raw_expiry:
            raise CanarySafeModeError(
                "Production Boot Policy Canary Context 공란 필수"
            )
        expires_at = None
    elif mode == "safe":
        if state not in {"armed", "active"}:
            raise CanarySafeModeError(
                "Safe Boot Policy state는 armed 또는 active만 허용"
            )
        if purpose != _SAFE_PURPOSE:
            raise CanarySafeModeError("Safe Boot Policy purpose=approval_r 필수")
        if not _CONTEXT_ID_PATTERN.fullmatch(context_id):
            raise CanarySafeModeError("유효한 Boot context_id 필수")
        if not _RUN_ID_PATTERN.fullmatch(run_id):
            raise CanarySafeModeError("유효한 CANARY_RUN_ID 필수")
        expires_at = _parse_expiry(raw_expiry)
        if current >= expires_at:
            raise CanarySafeModeError("Canary Safe Mode Context 만료")
    else:
        raise CanarySafeModeError(
            "Runtime Boot Policy mode는 production 또는 safe만 허용"
        )

    return RuntimeBootPolicy(
        schema_version=1,
        mode=mode,
        state=state,
        purpose=purpose,
        context_id=context_id,
        run_id=run_id,
        expires_at=expires_at,
        source_path=path,
    )


def _atomic_activate_safe_policy(
    *,
    now: datetime | None = None,
    policy_path: str | os.PathLike[str] | None = None,
) -> RuntimeBootPolicy:
    """armed Safe Policy를 원자적으로 active로 전환한다.

    ``.lock``이 남으면 자동 복구하지 않고 Fail-closed한다. 삭제·복구는 별도
    운영 승인 대상이다. 이미 active인 동일 Policy는 Watchdog 복구를 위해 허용한다.
    """

    path = (
        Path(policy_path)
        if policy_path is not None
        else DEFAULT_RUNTIME_BOOT_POLICY_PATH
    )
    lock_path = path.with_name(f"{path.name}.lock")
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    lock_fd = None
    try:
        try:
            lock_fd = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise CanarySafeModeError(
                "Runtime Boot Policy 활성화 Lock 존재"
            ) from exc

        policy = load_runtime_boot_policy(now=now, policy_path=path)
        if policy.mode == "production" or policy.state == "active":
            return policy

        document = {
            "schema_version": policy.schema_version,
            "mode": policy.mode,
            "state": "active",
            "purpose": policy.purpose,
            "context_id": policy.context_id,
            "run_id": policy.run_id,
            "expires_at": policy.expires_at.isoformat()
            if policy.expires_at
            else "",
        }
        encoded = (
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        temp_fd = os.open(
            temp_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        try:
            with os.fdopen(temp_fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        except Exception:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
            raise
        return load_runtime_boot_policy(now=now, policy_path=path)
    except CanarySafeModeError:
        raise
    except OSError as exc:
        raise CanarySafeModeError(
            "Runtime Boot Policy 원자적 활성화 실패"
        ) from exc
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def get_canary_safe_mode_state(
    *,
    now: datetime | None = None,
    require_boot_policy: bool = False,
    activate_boot_policy: bool = False,
    policy_path: str | os.PathLike[str] | None = None,
) -> CanarySafeModeState:
    """결정론적인 Safe Mode 상태를 반환한다.

    Runtime 진입점은 ``require_boot_policy=True``를 사용한다. 기존 환경변수
    경로는 Boot Policy가 없고 강제가 아닌 격리 테스트·Runner에서만 허용한다.
    """

    selected_path = (
        Path(policy_path)
        if policy_path is not None
        else DEFAULT_RUNTIME_BOOT_POLICY_PATH
    )
    if require_boot_policy or policy_path is not None or selected_path.exists():
        policy = (
            _atomic_activate_safe_policy(now=now, policy_path=selected_path)
            if activate_boot_policy
            else load_runtime_boot_policy(now=now, policy_path=selected_path)
        )
        return policy.to_safe_mode_state()

    raw = os.getenv("CANARY_SAFE_MODE", "").strip().lower()
    if raw in ("", "false"):
        return CanarySafeModeState(enabled=False)
    if raw != "true":
        raise CanarySafeModeError(
            "CANARY_SAFE_MODE는 true 또는 false만 허용"
        )

    run_id = os.getenv("CANARY_RUN_ID", "").strip()
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise CanarySafeModeError("유효한 CANARY_RUN_ID 필수")

    expires_at = _parse_expiry(os.getenv("CANARY_EXPIRES_AT", ""))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise CanarySafeModeError("현재 시각 timezone 필수")
    if current.astimezone(timezone.utc) >= expires_at:
        raise CanarySafeModeError("Canary Safe Mode Context 만료")

    return CanarySafeModeState(
        enabled=True,
        run_id=run_id,
        expires_at=expires_at,
        source="environment",
    )


def safe_mode_health_fields(
    state: CanarySafeModeState,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Safe Mode의 현재 만료 상태를 자동 Production 전환 없이 표시한다."""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    expired = bool(
        state.enabled
        and state.expires_at
        and current.astimezone(timezone.utc) >= state.expires_at
    )
    return {
        "canary_safe_mode": state.enabled,
        "canary_run_id_masked": mask_canary_run_id(state.run_id),
        "canary_purpose": state.purpose,
        "canary_expires_at": state.expires_at.isoformat()
        if state.expires_at
        else "",
        "canary_expired": expired,
        "runtime_boot_policy_state": state.policy_state,
        "runtime_boot_policy_source": state.source,
    }


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--validate-boot-policy",
        action="store_true",
        help="Runtime Boot Policy를 읽기 전용으로 검증",
    )
    parser.add_argument(
        "--policy-path",
        default=str(DEFAULT_RUNTIME_BOOT_POLICY_PATH),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    if not args.validate_boot_policy:
        parser.error("--validate-boot-policy 필수")

    try:
        policy = load_runtime_boot_policy(policy_path=args.policy_path)
    except CanarySafeModeError as exc:
        print(f"BOOT_POLICY_INVALID reason={exc}", file=sys.stderr)
        return 2

    expiry = policy.expires_at.isoformat() if policy.expires_at else ""
    print(
        "BOOT_POLICY_VALID "
        f"mode={policy.mode} state={policy.state} purpose={policy.purpose} "
        f"run_id={mask_canary_run_id(policy.run_id)} expires_at={expiry}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
