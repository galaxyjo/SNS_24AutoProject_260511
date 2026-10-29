"""261029 승인 B2 — 크롤 대상 사용권 미확인 차단(CRAWL_RIGHTS_REQUIRED_ACCOUNTS) Target Test.

계약: 환경변수 CRAWL_RIGHTS_REQUIRED_ACCOUNTS(기본 비어 있음=OFF)에 든 게시 계정의 크롤 대상은
permission_status=="allowed" 이고 sns_reuse_allowed가 True일 때만 크롤한다. 그 외(공란·unknown·
blocked·미체크)는 그 대상만 CRAWL_TARGET_RIGHTS_UNCONFIRMED로 건너뛴다. 목록 밖 계정(041 포함)과
플래그 OFF는 기존 라우팅 결과와 같다. 이 값은 사람이 입력한 선언이며 권리 증빙이 아니다.

실제 Airtable·Facebook·AdsPower 호출과 Runtime 상태변경 없음.
"""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from modules.common import account_manager as am
from modules.sns import facebook_crawler as fc

ACCOUNTS = {
    "IDN-000041": {"account_code": "IDN-000041", "category": ""},
    "IDN-000051": {"account_code": "IDN-000051", "category": "A_BEAUTY"},
    "IDN-000048": {"account_code": "IDN-000048", "category": "A_BEAUTY"},
}


def _t(tid, code="IDN-000051", status=None, reuse=None, purpose="production", max_posts=1):
    target = {
        "target_url": f"https://www.facebook.com/groups/{tid}", "target_id": tid,
        "publish_account_code": code, "collection_purpose": purpose, "max_posts": max_posts,
    }
    if status is not None:
        target["permission_status"] = status
    if reuse is not None:
        target["sns_reuse_allowed"] = reuse
    return target


@pytest.fixture(autouse=True)
def _clean_flag(monkeypatch):
    monkeypatch.delenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", raising=False)


@pytest.fixture
def validate(monkeypatch):
    def _fake(code, data_classification, canary_run_id=""):
        if code not in ACCOUNTS:
            raise RuntimeError("account_code_ref가 Account_Registry의 단일 계정과 연결되지 않음")
        return dict(ACCOUNTS[code])
    monkeypatch.setattr(fc, "_validate_publish_context", _fake)


def _route(targets, max_posts=20):
    return fc._route_crawl_targets(targets, max_posts, "production", "")


def _codes(routes):
    return [(url.rsplit("/", 1)[-1], code) for url, _, code in routes]


# ── 플래그 OFF / 목록 밖 계정: 기존 동작 불변 ───────────────────────────────────────

def test_flag_unset_routes_blank_rights_exactly_like_before(validate):
    targets = [_t("A005"), _t("A002", code="IDN-000041")]
    assert _codes(_route(targets)) == [("A005", "IDN-000051"), ("A002", "IDN-000041")]


def test_flag_empty_or_whitespace_is_off(validate, monkeypatch):
    for raw in ("", "   ", " , ,"):
        monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", raw)
        assert _codes(_route([_t("A005")])) == [("A005", "IDN-000051")]


def test_account_outside_flag_list_is_unchanged_even_with_blank_rights(validate, monkeypatch):
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "IDN-000051")
    targets = [_t("A002", code="IDN-000041"), _t("A003", code="IDN-000041"), _t("A004", code="IDN-000041")]
    assert [c for _, c in _codes(_route(targets, max_posts=20))] == ["IDN-000041"] * 3


def test_removing_flag_restores_blank_rights_routing(validate, monkeypatch):
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "IDN-000051")
    assert _route([_t("A005")]) == []
    monkeypatch.delenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS")
    assert _codes(_route([_t("A005")])) == [("A005", "IDN-000051")]


# ── 플래그 ON: 사용권 미확인 차단 ───────────────────────────────────────────────────

@pytest.mark.parametrize("target", [
    _t("blank"),                                              # 두 필드 모두 공란(현재 A005 상태)
    _t("unknown", status="unknown", reuse=True),
    _t("blocked", status="blocked", reuse=True),
    _t("allowed_unchecked", status="allowed", reuse=False),
    _t("allowed_missing_checkbox", status="allowed"),
    _t("checked_only", status="", reuse=True),
    _t("checked_unknown", status="unknown", reuse=False),
    _t("string_true_is_not_true", status="allowed", reuse="true"),
])
def test_unconfirmed_rights_are_skipped_with_reason(validate, monkeypatch, caplog, target):
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "IDN-000051")
    with caplog.at_level(logging.WARNING):
        routes = _route([target])
    assert routes == []
    assert "CRAWL_TARGET_RIGHTS_UNCONFIRMED" in caplog.text
    assert target["target_id"] in caplog.text


def test_allowed_and_reuse_true_is_routed(validate, monkeypatch):
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "IDN-000051")
    routes = _route([_t("A005", status="allowed", reuse=True)])
    assert routes == [("https://www.facebook.com/groups/A005", 1, "IDN-000051")]


def test_status_is_case_and_space_tolerant_but_value_must_be_allowed(validate, monkeypatch):
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "IDN-000051")
    assert len(_route([_t("ok", status=" Allowed ", reuse=True)])) == 1
    assert _route([_t("no", status="allowed_maybe", reuse=True)]) == []


def test_flag_list_parses_commas_and_spaces(validate, monkeypatch):
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", " IDN-000048 , IDN-000051 ")
    targets = [_t("a", code="IDN-000048"), _t("b", code="IDN-000051"), _t("c", code="IDN-000041")]
    assert _codes(_route(targets)) == [("c", "IDN-000041")]


def test_targets_are_judged_independently(validate, monkeypatch):
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "IDN-000051")
    targets = [_t("ok1", status="allowed", reuse=True), _t("blank"), _t("ok2", status="allowed", reuse=True)]
    assert _codes(_route(targets)) == [("ok1", "IDN-000051"), ("ok2", "IDN-000051")]


def test_rights_gate_runs_after_existing_validations(validate, monkeypatch, caplog):
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "IDN-000051")
    with caplog.at_level(logging.WARNING):
        routes = _route([_t("blank_code", code=""), _t("training", purpose="training"), _t("zero", max_posts=0)])
    assert routes == []
    assert "CRAWL_TARGET_BLANK" in caplog.text
    assert "CRAWL_TARGET_NOT_OPERATIONAL" in caplog.text
    assert "CRAWL_TARGET_INVALID_MAX_POSTS" in caplog.text
    assert "CRAWL_TARGET_RIGHTS_UNCONFIRMED" not in caplog.text


# ── run_all_accounts: 차단된 대상은 크롤·저장 호출 0회 ──────────────────────────────

def _acct(targets):
    return SimpleNamespace(name="account1", adspower_user_id="k1bto3j4", crawl_urls=[t["target_url"] for t in targets],
                           crawl_targets=targets, selenium_proxy_options=lambda: {})


def test_blocked_target_is_never_crawled(validate, monkeypatch):
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "IDN-000051")
    targets = [_t("A005"), _t("A002", code="IDN-000041", max_posts=20)]
    monkeypatch.setattr(am, "get_active_accounts", lambda: [_acct(targets)])
    calls = []

    def _run(url, max_posts, adspower_user_id, proxy_opts, *, target_publish_account_code_ref, **kw):
        calls.append((url, target_publish_account_code_ref))
        return [{"ok": 1}]

    monkeypatch.setattr(fc, "run", _run)
    fc.run_all_accounts(20, target_publish_account_code_ref="IDN-000041", data_classification="production")
    assert calls == [("https://www.facebook.com/groups/A002", "IDN-000041")]


# ── loader / account_manager: 두 필드 전달, 없으면 미확인 ─────────────────────────────

def test_loader_returns_rights_fields_and_defaults(monkeypatch):
    from modules.infra.airtable_repository import AirtableRepository
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"records": [
        {"fields": {"target_url": "u1", "platform": "facebook", "publish_account_code": "IDN-000051",
                    "collection_purpose": "production", "max_posts": 1,
                    "permission_status": "allowed", "sns_reuse_allowed": True}},
        {"fields": {"target_url": "u2", "platform": "facebook"}},
    ]}
    with patch("modules.infra.airtable_repository.requests.get", return_value=resp) as g, \
         patch("modules.infra.airtable_repository.log_api_call"):
        out = AirtableRepository().fetch_active_crawl_targets()
    params = g.call_args.kwargs["params"]
    assert {"permission_status", "sns_reuse_allowed"} <= set(params.values())
    assert params["filterByFormula"] == "AND({status}='Active', NOT({collection_purpose}='training'))"
    assert (out[0]["permission_status"], out[0]["sns_reuse_allowed"]) == ("allowed", True)
    assert (out[1]["permission_status"], out[1]["sns_reuse_allowed"]) == ("", False)


def test_account_manager_keeps_rights_fields_and_tolerates_missing_keys():
    repo = MagicMock()
    repo.fetch_active_crawl_targets.return_value = [
        {"target_url": "f1", "platform": "facebook", "target_id": "A005", "publish_account_code": "IDN-000051",
         "collection_purpose": "production", "max_posts": 1, "permission_status": "allowed", "sns_reuse_allowed": True},
        {"target_url": "f2", "platform": "facebook", "target_id": "A002", "publish_account_code": "IDN-000041",
         "collection_purpose": "production", "max_posts": 20},
    ]
    with patch("modules.infra.airtable_repository.AirtableRepository", return_value=repo):
        routes = am._load_crawl_targets_from_airtable()
    assert (routes[0]["permission_status"], routes[0]["sns_reuse_allowed"]) == ("allowed", True)
    assert (routes[1]["permission_status"], routes[1]["sns_reuse_allowed"]) == ("", False)


def test_flag_default_is_off_in_source():
    from pathlib import Path
    env_text = (Path(__file__).resolve().parents[1] / ".env.example")
    if env_text.exists():
        assert "CRAWL_RIGHTS_REQUIRED_ACCOUNTS=IDN" not in env_text.read_text(encoding="utf-8", errors="ignore")
    assert fc._rights_required_accounts() == set()
