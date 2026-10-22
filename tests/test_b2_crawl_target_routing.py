"""261022 B2 — Crawl_Target별 게시 계정 라우팅 + URL별 max_posts 전달 Target Test.

계약: production + facebook 대상만, publish_account_code가 형식·Registry·도메인 검증을
통과할 때만 그 계정으로 크롤한다. 공란·오류는 그 대상만 Skip하고 IDN-000041로 대신 보내지
않는다. URL별 max_posts는 min(대상 값, 전역 상한). 실제 Airtable·Facebook·AdsPower 호출 없음.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from modules.common import account_manager as am
from modules.sns import facebook_crawler as fc

ACCOUNTS = {
    "IDN-000041": {"account_code": "IDN-000041", "category": ""},
    "IDN-000048": {"account_code": "IDN-000048", "category": "A_BEAUTY"},
    "IDN-000036": {"account_code": "IDN-000036", "category": "A_BEAUTY"},
    "IDN-000027": {"account_code": "IDN-000027", "category": "D_AI"},
}


def _t(tid, code="IDN-000041", purpose="production", max_posts=20, url=None):
    return {"target_url": url or f"https://www.facebook.com/groups/{tid}", "target_id": tid,
            "publish_account_code": code, "collection_purpose": purpose, "max_posts": max_posts}


@pytest.fixture
def validate(monkeypatch):
    calls = []

    def _fake(code, data_classification, canary_run_id=""):
        calls.append(code)
        if code not in ACCOUNTS:
            raise RuntimeError("account_code_ref가 Account_Registry의 단일 계정과 연결되지 않음")
        return dict(ACCOUNTS[code])
    monkeypatch.setattr(fc, "_validate_publish_context", _fake)
    return calls


def _route(targets, max_posts=20):
    return fc._route_crawl_targets(targets, max_posts, "production", "")


# ── 라우팅 계약 ──────────────────────────────────────────────────────────────
def test_operating_yuna_targets_route_to_041_with_same_volume(validate):
    targets = [_t(f"A00{i}") for i in (2, 3, 4, 5)]
    routes = _route(targets)
    assert [(code, mp) for _, mp, code in routes] == [("IDN-000041", 20)] * 4
    assert validate == ["IDN-000041"]                      # 계정당 1회 검증(캐시)


@pytest.mark.parametrize("target,reason", [
    (_t("x", code=""), "CRAWL_TARGET_BLANK"),
    (_t("x", code="   "), "CRAWL_TARGET_BLANK"),
    (_t("x", code="IDN-41"), "CRAWL_TARGET_INVALID"),
    (_t("x", code="IDN-000041,IDN-000048"), "CRAWL_TARGET_INVALID"),
    (_t("x", code="IDN-000041 IDN-000048"), "CRAWL_TARGET_INVALID"),
    (_t("x", purpose="training"), "CRAWL_TARGET_NOT_OPERATIONAL"),
    (_t("x", purpose=""), "CRAWL_TARGET_NOT_OPERATIONAL"),
    (_t("x", max_posts=0), "CRAWL_TARGET_INVALID_MAX_POSTS"),
    (_t("x", max_posts=None), "CRAWL_TARGET_INVALID_MAX_POSTS"),
    (_t("x", max_posts="abc"), "CRAWL_TARGET_INVALID_MAX_POSTS"),
    (_t("x", code="IDN-999999"), "CRAWL_TARGET_NOT_FOUND"),
    (_t("x", code="IDN-000036"), "CRAWL_TARGET_DOMAIN_MISMATCH"),    # dict=AI_CONTENT가 category보다 우선
    (_t("x", code="IDN-000027"), "CRAWL_TARGET_DOMAIN_MISMATCH"),    # D_AI는 PRODUCT 아님
])
def test_fail_closed_skips_without_fallback(validate, caplog, target, reason):
    import logging
    with caplog.at_level(logging.WARNING):
        routes = _route([target, _t("A002")])
    assert [code for _, _, code in routes] == ["IDN-000041"]     # 다른 대상만 남고, 041로 대체되지 않음
    assert all(url != target["target_url"] for url, _, _ in routes)
    assert reason in caplog.text


def test_a_beauty_account_routes_by_category(validate):
    routes = _route([_t("C1", code="IDN-000048", max_posts=1)])
    assert routes == [("https://www.facebook.com/groups/C1", 1, "IDN-000048")]


def test_max_posts_capped_by_global(validate):
    assert _route([_t("A", max_posts=50)], max_posts=20)[0][1] == 20
    assert _route([_t("B", max_posts=1)], max_posts=20)[0][1] == 1


def test_many_targets_same_account_validated_once(validate):
    routes = _route([_t("a", code="IDN-000048"), _t("b", code="IDN-000048"), _t("c", code="IDN-000048")])
    assert len(routes) == 3 and validate == ["IDN-000048"]


# ── run_all_accounts: URL별 계정·max_posts 전달 ─────────────────────────────
def _acct(**kw):
    base = dict(name="account1", adspower_user_id="k1bto3j4", crawl_urls=[], crawl_targets=[],
                selenium_proxy_options=lambda: {})
    base.update(kw)
    return SimpleNamespace(**base)


def _spy_run(monkeypatch):
    calls = []

    def _run(url, max_posts, adspower_user_id, proxy_opts, *, target_publish_account_code_ref, **kw):
        calls.append((url, max_posts, target_publish_account_code_ref))
        return [{"ok": 1}]
    monkeypatch.setattr(fc, "run", _run)
    return calls


def test_routing_mode_passes_per_url_account_and_max_posts(monkeypatch, validate):
    targets = [_t("A002"), _t("CANARY", code="IDN-000048", max_posts=1), _t("BAD", code="")]
    monkeypatch.setattr(am, "get_active_accounts",
                        lambda: [_acct(crawl_urls=[t["target_url"] for t in targets], crawl_targets=targets)])
    calls = _spy_run(monkeypatch)
    fc.run_all_accounts(20, target_publish_account_code_ref="IDN-000041", data_classification="production")
    assert calls == [
        ("https://www.facebook.com/groups/A002", 20, "IDN-000041"),
        ("https://www.facebook.com/groups/CANARY", 1, "IDN-000048"),
    ]


def test_routing_mode_all_skipped_does_not_raise_or_crawl(monkeypatch, validate):
    monkeypatch.setattr(am, "get_active_accounts", lambda: [_acct(crawl_targets=[_t("x", code="")])])
    calls = _spy_run(monkeypatch)
    assert fc.run_all_accounts(20, target_publish_account_code_ref="IDN-000041",
                               data_classification="production") == {"account1": 0}
    assert calls == []


def test_legacy_mode_unchanged_when_no_crawl_targets(monkeypatch, validate):
    monkeypatch.setattr(am, "get_active_accounts", lambda: [_acct(crawl_urls=["u1", "u2"])])
    calls = _spy_run(monkeypatch)
    fc.run_all_accounts(20, target_publish_account_code_ref="IDN-000041", data_classification="production")
    assert calls == [("u1", 20, "IDN-000041"), ("u2", 20, "IDN-000041")]
    assert validate == ["IDN-000041"]                    # 기존 전역 검증 1회 유지


def test_legacy_object_without_crawl_targets_attribute(monkeypatch, validate):
    acct = SimpleNamespace(name="old", adspower_user_id="k", crawl_urls=["u"], selenium_proxy_options=lambda: {})
    monkeypatch.setattr(am, "get_active_accounts", lambda: [acct])
    calls = _spy_run(monkeypatch)
    fc.run_all_accounts(20, target_publish_account_code_ref="IDN-000041", data_classification="production")
    assert calls == [("u", 20, "IDN-000041")]


def _real_run_boundaries(monkeypatch, n_posts=5):
    """run()의 처리 루프는 실제 코드 그대로 두고, 브라우저·저장 경계만 기록용으로 바꾼다."""
    state = SimpleNamespace(extract=[], saved=[], quit=0)
    posts = [SimpleNamespace(text=f"author {i}\nK-beauty serum wholesale {i}") for i in range(n_posts)]

    class _Feed:
        def find_elements(self, by, xpath):
            return list(posts)

    class _Driver:
        def get(self, url): pass
        def execute_script(self, *a): pass
        def find_element(self, by, sel): return _Feed()
        def quit(self): state.quit += 1

    def _extract(post, driver):
        state.extract.append(post)
        return f"https://scontent.example/{posts.index(post)}.jpg"

    def _save(image_url, target_url, converted_text, **kw):
        state.saved.append((image_url, kw["target_publish_account_code_ref"]))
        return True

    monkeypatch.delenv("FB_PROGRESSIVE_CRAWL_ENABLED", raising=False)
    monkeypatch.setattr(fc, "_focus_emulation_enabled", lambda: False)
    monkeypatch.setattr(fc, "_stage_log", lambda *a, **k: None)
    monkeypatch.setattr(fc, "load_supplier_blocklist", lambda: [])
    monkeypatch.setattr(fc, "is_blocked_supplier", lambda *a, **k: None)
    monkeypatch.setattr(fc, "get_driver", lambda *a, **k: _Driver())
    monkeypatch.setattr(fc, "stop_browser", lambda *a, **k: None)
    monkeypatch.setattr(fc, "extract_image_url", _extract)
    monkeypatch.setattr(fc, "expand_see_more", lambda *a, **k: None)
    monkeypatch.setattr(fc, "passes_keyword_filter", lambda t: True)
    monkeypatch.setattr(fc, "passes_image_filter", lambda url: True)
    monkeypatch.setattr(fc, "generate_sku", lambda url: "SKU")
    monkeypatch.setattr(fc, "save_to_airtable", _save)
    monkeypatch.setattr(fc.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr("modules.metrics.crawl_monitor.record_crawl", lambda *a, **k: None)
    return state


@pytest.mark.parametrize("max_posts,expected", [(1, 1), (5, 5)])
def test_run_processes_at_most_max_posts(monkeypatch, validate, max_posts, expected):
    """게시물 5개 입력 → max_posts=1이면 추출·저장 각 1회. 대조군 max_posts=5이면 5회
    (Mock이 처리 건수를 스스로 줄이는 것이 아님을 확인)."""
    state = _real_run_boundaries(monkeypatch, n_posts=5)
    results = fc.run("https://www.facebook.com/groups/C1", max_posts, "k1bto3j4", {},
                     target_publish_account_code_ref="IDN-000048", data_classification="production")
    assert len(state.extract) == expected
    assert len(state.saved) == expected
    assert len(results) == expected
    assert state.quit == 1


def test_canary_target_end_to_end_saves_one_post_to_its_account(monkeypatch, validate):
    """Canary Crawl_Target(max_posts=1, IDN-000048) → run_all_accounts → 실제 run() → 저장 1건."""
    state = _real_run_boundaries(monkeypatch, n_posts=5)
    targets = [_t("CANARY", code="IDN-000048", max_posts=1)]
    monkeypatch.setattr(am, "get_active_accounts", lambda: [_acct(crawl_targets=targets)])
    summary = fc.run_all_accounts(20, target_publish_account_code_ref="IDN-000041",
                                  data_classification="production")
    assert summary == {"account1": 1}
    assert len(state.extract) == 1
    assert state.saved == [("https://scontent.example/0.jpg", "IDN-000048")]


# ── account_manager / loader ─────────────────────────────────────────────────
def test_account_manager_keeps_route_fields_and_facebook_only(monkeypatch):
    repo = MagicMock()
    repo.fetch_active_crawl_targets.return_value = [
        {"target_url": "f1", "platform": "facebook", "target_id": "A002", "publish_account_code": "IDN-000041",
         "collection_purpose": "production", "max_posts": 20},
        {"target_url": "d1", "platform": "domeggook", "target_id": "D001"},
        {"target_url": "n1", "platform": "", "target_id": "X"},
    ]
    with patch("modules.infra.airtable_repository.AirtableRepository", return_value=repo):
        routes = am._load_crawl_targets_from_airtable()
        urls = am._load_crawl_urls_from_airtable()
    assert [r["target_id"] for r in routes] == ["A002"]
    assert routes[0]["publish_account_code"] == "IDN-000041" and routes[0]["max_posts"] == 20
    assert urls == ["f1"]


def test_airtable_mode_sets_crawl_targets(monkeypatch):
    monkeypatch.setenv("CRAWL_TARGET_SOURCE", "airtable")
    monkeypatch.setattr(am, "_cache", None)
    monkeypatch.setattr(am, "_load_from_json", lambda: [am.Account("account1", True, "k1bto3j4", "", "", "", "")])
    route = {"target_url": "f1", "target_id": "A002", "publish_account_code": "IDN-000041",
             "collection_purpose": "production", "max_posts": 20}
    monkeypatch.setattr(am, "_load_crawl_targets_from_airtable", lambda: [route])
    accts = am.get_active_accounts()
    assert accts[0].crawl_urls == ["f1"] and accts[0].crawl_targets == [route]
    monkeypatch.setattr(am, "_cache", None)


def test_loader_returns_new_fields_and_blank_platform(monkeypatch):
    from modules.infra.airtable_repository import AirtableRepository
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"records": [
        {"fields": {"target_url": "u1", "platform": "facebook", "publish_account_code": "IDN-000041",
                    "collection_purpose": "production", "max_posts": 20}},
        {"fields": {"target_url": "u2"}},
    ]}
    with patch("modules.infra.airtable_repository.requests.get", return_value=resp) as g, \
         patch("modules.infra.airtable_repository.log_api_call"):
        out = AirtableRepository().fetch_active_crawl_targets()
    params = g.call_args.kwargs["params"]
    assert params["filterByFormula"] == "AND({status}='Active', NOT({collection_purpose}='training'))"
    assert {"publish_account_code", "collection_purpose"} <= set(params.values())
    assert out[0]["publish_account_code"] == "IDN-000041" and out[0]["collection_purpose"] == "production"
    assert out[1]["platform"] == "" and out[1]["publish_account_code"] == ""


def test_global_image_hash_dedupe_has_no_account_filter():
    from modules.infra.airtable_repository import AirtableRepository
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"records": []}
    with patch("modules.infra.airtable_repository.requests.get", return_value=resp) as g, \
         patch("modules.infra.airtable_repository.log_api_call"):
        AirtableRepository().exists_post_by_image_url("http://img")
    formula = g.call_args.kwargs["params"]["filterByFormula"]
    assert formula.startswith("{image_url_hash}='") and "account" not in formula
