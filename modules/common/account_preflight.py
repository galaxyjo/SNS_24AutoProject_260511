"""
modules/common/account_preflight.py — 신규 계정 온보딩 Preflight (261028 STEP 3)

계정별 등록이 코드·Airtable·.env 여러 곳에 흩어져 있어, 하나라도 비면 Fail-closed가 한 겹씩
게시를 막는다(261028 4계정 온보딩 사고). 이 모듈은 그 등록 여부를 한 번에 점검해
READY / NOT_READY(사유코드)로 돌려준다.

- Secret 값은 읽거나 반환하지 않는다. 환경변수는 "존재 여부"만 확인한다.
- 네트워크·Airtable 쓰기 없음. repo는 이미 게시 경로가 쓰는 읽기 메서드만 호출한다.
- stage="publish": 게시 직전에 필요한 항목만 (게시 경로 Fail-closed 연결용)
  stage="produce": 콘텐츠 생성에 필요한 항목만
  stage="all": 둘 다 (CLI 점검용)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from modules.common.logger import get_logger

logger = get_logger(__name__)

_PUBLISH = "publish"
_PRODUCE = "produce"


def _item(name: str, stage: str, ok: bool, reason: str = "") -> dict:
    return {"name": name, "stage": stage, "ok": bool(ok), "reason": "" if ok else reason}


def _env_present(env, key: str) -> bool:
    return bool(str(env.get(key, "")).strip())


def run_account_preflight(
    account_code: str,
    *,
    content_accounts: dict,
    repo=None,
    stage: str = "all",
    env=None,
    persona_loader: "Optional[Callable]" = None,
    publish_account: "dict | None" = None,
    check_persona: bool = True,
) -> dict:
    """계정 1개의 온보딩 준비 상태를 점검한다.

    persona_loader(repo, acct): launcher의 `_content_persona_kwargs`처럼 필수 Persona 설정을
    dict로 돌려주고 부족하면 None을 돌려주는 함수(생성 단계 점검용). 없으면 그 항목은 건너뛴다.
    publish_account: 호출부가 이미 조회한 `repo.get_publish_account()` 결과(중복 조회 방지).
    반환: {"account_code", "stage", "status": "READY"|"NOT_READY", "checks": [...], "not_ready": [사유코드...]}
    """
    env = os.environ if env is None else env
    want_publish = stage in ("all", _PUBLISH)
    want_produce = stage in ("all", _PRODUCE)
    checks: list = []

    acct = content_accounts.get(account_code)
    if acct is None:
        checks.append(_item("CONTENT_ACCOUNTS", "all", False, "NOT_IN_CONTENT_ACCOUNTS"))
        return _finish(account_code, stage, checks)
    checks.append(_item("CONTENT_ACCOUNTS", "all", True))

    # 1) Credential 매핑 — 값은 읽지 않고 존재 여부만 확인
    key = acct.credential_key
    if want_publish:
        ok = _env_present(env, f"{key}_INSTA_ACCESS_TOKEN") and _env_present(env, f"{key}_INSTA_IG_USER_ID")
        checks.append(_item("INSTAGRAM_CREDENTIAL", _PUBLISH, ok, "ENV_INSTAGRAM_CREDENTIAL_MISSING"))
    from modules.common.credential_resolver import _GEMINI_ENV_PREFIX_BY_CREDENTIAL_KEY
    # 예외 이름 표 또는 규칙 `{credential_key}_GEMINI_API_KEY` 중 하나로 해석된다(261028 — 신규 계정은 표 수정 불필요).
    prefix = _GEMINI_ENV_PREFIX_BY_CREDENTIAL_KEY.get(key) or key
    checks.append(_item("GEMINI_CREDENTIAL", "all", _env_present(env, f"{prefix}_GEMINI_API_KEY"),
                        "ENV_GEMINI_KEY_MISSING"))

    # 2) 도메인 정책 + Persona 매핑 (게시 직전 Gate가 쓰는 하드코딩 표)
    persona = None
    if repo is not None and want_publish and check_persona:
        try:
            persona = repo.get_active_persona_by_account_code_v2(account_code)
        except Exception:
            persona = None
    if want_publish:
        from modules.sns import content_filter
        domain_ok = content_filter.ACCOUNT_DOMAIN_POLICY.get(account_code) == "AI_CONTENT"
        checks.append(_item("DOMAIN_POLICY", _PUBLISH, domain_ok, "NOT_IN_ACCOUNT_DOMAIN_POLICY"))
        expected = content_filter._AI_CONTENT_PERSONA_BY_ACCOUNT.get(account_code)
        checks.append(_item("PERSONA_DOMAIN_MAP", _PUBLISH, bool(expected), "NOT_IN_AI_CONTENT_PERSONA_MAP"))
        if repo is not None and check_persona:
            if not persona:
                checks.append(_item("PERSONA_ACTIVE", _PUBLISH, False, "PERSONA_NOT_ACTIVE"))
            elif expected and str(persona.get("persona_code", "")).strip() != expected:
                checks.append(_item("PERSONA_ACTIVE", _PUBLISH, False, "PERSONA_CODE_MISMATCH_WITH_MAP"))
            else:
                checks.append(_item("PERSONA_ACTIVE", _PUBLISH, True))

    # 3) Kill Switch (Airtable automation_enabled)
    if want_publish and repo is not None:
        account = publish_account
        if account is None:
            try:
                account = repo.get_publish_account(account_code)
            except Exception:
                account = None
        if account is None:
            checks.append(_item("KILL_SWITCH", _PUBLISH, False, "ACCOUNT_LOOKUP_FAILED"))
        else:
            checks.append(_item("KILL_SWITCH", _PUBLISH, bool(account.get("automation_enabled", False)),
                                "KILL_SWITCH_OFF"))

    # 4) 생성 단계: Persona 필수설정·brand_handle·Sourcebook 주제 매칭
    if want_produce:
        persona_kwargs = None
        if persona_loader is not None and repo is not None:
            try:
                persona_kwargs = persona_loader(repo, acct)
            except Exception:
                persona_kwargs = None
            checks.append(_item("PERSONA_REQUIRED_FIELDS", _PRODUCE, persona_kwargs is not None,
                                "PERSONA_FIELDS_MISSING_OR_INACTIVE"))
        if acct.vault_root is not None:
            checks.append(_item("BRAND_HANDLE", _PRODUCE, bool(acct.brand_handle), "BRAND_HANDLE_EMPTY"))
        if persona_kwargs:
            checks.append(_sourcebook_check(acct, persona_kwargs))

    # 5) 실행 Flag (프로세스 환경값만 — 값 자체는 Secret이 아니다)
    flag_prefix = acct.env_prefix
    if want_publish:
        checks.append(_item("FLAG_SLOT_SCHEDULE", _PUBLISH,
                            str(env.get(f"{flag_prefix}_SLOT_SCHEDULE_ENABLED", "")).strip().lower() == "true",
                            "FLAG_SLOT_SCHEDULE_OFF"))
        checks.append(_item("FLAG_PUBLISH_TEXT_GATE", _PUBLISH,
                            str(env.get("PUBLISH_TEXT_GATE_ENABLED", "")).strip().lower() == "true",
                            "FLAG_PUBLISH_TEXT_GATE_OFF"))
    if want_produce:
        checks.append(_item("FLAG_CONTENT_PRODUCER", _PRODUCE,
                            str(env.get(f"{flag_prefix}_CONTENT_PRODUCER_ENABLED", "")).strip().lower() == "true",
                            "FLAG_CONTENT_PRODUCER_OFF"))

    return _finish(account_code, stage, checks)


def _sourcebook_check(acct, persona_kwargs: dict) -> dict:
    try:
        from modules.sns import source_selector
        topics = source_selector.parse_sourcebook(acct.sourcebook_path) if acct.sourcebook_path \
            else source_selector.parse_sourcebook()
        selectable = source_selector.list_selectable_topics(topics)
        pillars = persona_kwargs.get("content_pillars", "")
        matched = [t for t in selectable if source_selector.topic_matches_content_pillars(t, pillars)]
        return _item("SOURCEBOOK_TOPIC_MATCH", _PRODUCE, bool(matched), "NO_SOURCEBOOK_TOPIC_MATCHES_PERSONA")
    except Exception:
        return _item("SOURCEBOOK_TOPIC_MATCH", _PRODUCE, False, "SOURCEBOOK_UNREADABLE")


_BOOT_STATE_PATH = Path(__file__).resolve().parents[2] / "db" / "launcher_boot_state.json"
_STALE_WATCH_FILES = ("launcher/main.py", "modules/sns/content_filter.py", "modules/sns/caption_generator.py")


def launcher_stale_warnings(boot_state_path=None, root=None) -> list:
    """261028 GPT 검수 D — 실행 중 launcher가 코드 수정 전 버전이면(감시 파일 수정시각 > launcher 기동시각) 경고 코드를 돌려준다.
    읽기 전용·경고 전용이다(NOT_READY로 만들지 않는다). 기동 기록이 없거나 읽을 수 없으면 빈 목록."""
    try:
        state = json.loads(Path(boot_state_path or _BOOT_STATE_PATH).read_text(encoding="utf-8"))
        started = datetime.strptime(str(state["started_at"]), "%Y-%m-%d %H:%M:%S").timestamp()
        base = Path(root) if root else Path(__file__).resolve().parents[2]
        newer = [name for name in _STALE_WATCH_FILES if (base / name).stat().st_mtime > started + 1]
        return [f"LAUNCHER_STALE:{','.join(newer)}"] if newer else []
    except Exception:
        return []


def _finish(account_code: str, stage: str, checks: list) -> dict:
    not_ready = [c["reason"] for c in checks if not c["ok"]]
    return {
        "warnings": launcher_stale_warnings(),
        "account_code": account_code,
        "stage": stage,
        "status": "READY" if not not_ready else "NOT_READY",
        "checks": checks,
        "not_ready": not_ready,
    }
