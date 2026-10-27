"""온보딩 Preflight(modules/common/account_preflight.py) Target Test + 공유 캡션 상한(357) 영향 확인 1건.

Airtable·네트워크 없이 Fake repo와 env dict로만 검증한다. Secret 값은 사용하지 않는다(존재 여부 문자열만).
"""
from pathlib import Path
from types import SimpleNamespace

from modules.common.account_preflight import run_account_preflight
from modules.sns import caption_generator as cg

_ROOT = Path(__file__).resolve().parents[1]
_PERSONA_OK = {
    "persona_code": "PER-023", "tone_style": "t", "language": "ko",
    "content_pillars": "beauty", "seo_keywords": "k", "conversion_cta": "c",
}


class _Repo:
    def __init__(self, persona=_PERSONA_OK, account=None):
        self._persona = persona
        self._account = {"automation_enabled": True} if account is None else account

    def get_active_persona_by_account_code_v2(self, code):
        return self._persona

    def get_publish_account(self, code):
        return self._account


def _acct(**kw):
    base = dict(account_code="IDN-000024", credential_key="IDN_000024", env_prefix="IDN_000024",
                vault_root=_ROOT / "vault" / "accounts" / "IDN-000024", brand_handle="@x", sourcebook_path=None)
    base.update(kw)
    return SimpleNamespace(**base)


_ENV_OK = {
    "IDN_000024_INSTA_ACCESS_TOKEN": "x", "IDN_000024_INSTA_IG_USER_ID": "1",
    "IDN_000024_GEMINI_API_KEY": "x", "IDN_000024_SLOT_SCHEDULE_ENABLED": "true",
    "IDN_000024_CONTENT_PRODUCER_ENABLED": "true", "PUBLISH_TEXT_GATE_ENABLED": "true",
}


def _run(**kw):
    args = dict(content_accounts={"IDN-000024": _acct()}, repo=_Repo(), stage="publish", env=_ENV_OK)
    args.update(kw)
    return run_account_preflight("IDN-000024", **args)


def test_publish_stage_ready_when_everything_registered():
    result = _run()
    assert result["status"] == "READY", result["not_ready"]


def test_unregistered_account_is_not_ready():
    result = _run(content_accounts={})
    assert result["status"] == "NOT_READY" and result["not_ready"] == ["NOT_IN_CONTENT_ACCOUNTS"]


def test_each_missing_piece_reports_its_own_reason():
    assert "ENV_INSTAGRAM_CREDENTIAL_MISSING" in _run(env={**_ENV_OK, "IDN_000024_INSTA_ACCESS_TOKEN": ""})["not_ready"]
    assert "ENV_GEMINI_KEY_MISSING" in _run(env={**_ENV_OK, "IDN_000024_GEMINI_API_KEY": ""})["not_ready"]
    assert "KILL_SWITCH_OFF" in _run(repo=_Repo(account={"automation_enabled": False}))["not_ready"]
    assert "PERSONA_NOT_ACTIVE" in _run(repo=_Repo(persona=None))["not_ready"]
    assert "PERSONA_CODE_MISMATCH_WITH_MAP" in _run(repo=_Repo(persona={**_PERSONA_OK, "persona_code": "PER-999"}))["not_ready"]
    assert "FLAG_SLOT_SCHEDULE_OFF" in _run(env={**_ENV_OK, "IDN_000024_SLOT_SCHEDULE_ENABLED": "false"})["not_ready"]


def test_unknown_domain_account_is_not_ready():
    result = run_account_preflight(
        "IDN-000099", content_accounts={"IDN-000099": _acct(account_code="IDN-000099", credential_key="IDN_000099",
                                                              env_prefix="IDN_000099")},
        repo=_Repo(), stage="publish", env={})
    assert result["status"] == "NOT_READY"
    assert "NOT_IN_ACCOUNT_DOMAIN_POLICY" in result["not_ready"]
    assert "ENV_GEMINI_KEY_MISSING" in result["not_ready"]


def test_produce_stage_reports_brand_handle_and_persona_fields():
    result = run_account_preflight(
        "IDN-000024", content_accounts={"IDN-000024": _acct(brand_handle="")}, repo=_Repo(), stage="produce",
        env=_ENV_OK, persona_loader=lambda repo, acct: None)
    assert result["status"] == "NOT_READY"
    assert "BRAND_HANDLE_EMPTY" in result["not_ready"]
    assert "PERSONA_FIELDS_MISSING_OR_INACTIVE" in result["not_ready"]


def test_result_never_contains_env_values():
    secret_env = {**_ENV_OK, "IDN_000024_INSTA_ACCESS_TOKEN": "SECRET-TOKEN-VALUE"}
    assert "SECRET-TOKEN-VALUE" not in repr(_run(env=secret_env))


# ── 공유 캡션 상한 357(해시태그 제외) 영향 — 기존 성공 계정 캡션 길이(110·147·357자)로 확인 ──
def _fields_with_total(total: int) -> dict:
    """고정 템플릿 오버헤드를 런타임에 재서 캡션 길이가 정확히 total이 되도록 한 필드를 채운다."""
    base = {k: "가" for k in cg._REQUIRED_ELEMENT_LABELS}
    caption, _, reason = cg._assemble_structured_caption(base, "")
    assert reason == "" and len(caption) <= total
    base["DETAIL_BODY"] = "가" * (1 + total - len(caption))
    return base


def test_shared_caption_cap_357_keeps_existing_success_lengths_and_excludes_hashtags():
    for total in (110, 147, 357):  # 261028 기존 성공 계정(023·029·022) 캡션 길이
        caption, _, reason = cg._assemble_structured_caption(_fields_with_total(total), "#" + "나" * 400)
        assert reason == "" and len(caption) == total, (total, reason)
    _, _, reason = cg._assemble_structured_caption(_fields_with_total(358), "")
    assert reason == "PAYLOAD_TOO_LONG:358"
