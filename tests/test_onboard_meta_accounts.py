"""261015 tools/onboard_meta_accounts.py — 50계정 연결 도구(순수 계획·실행 함수) Target Test.

네트워크·Airtable·.env 실파일은 쓰지 않는다(전부 가짜 데이터·주입 함수).
"""

import tools.onboard_meta_accounts as ob

TOKEN = "EAAMfakeSystemUserToken000000000000"


def ar(rid, idn, **f):
    return {"id": rid, "fields": {"identity_id": idn, **f}}


def pa(idn, platform, username):
    return {"id": f"p_{idn}_{platform}", "fields": {"identity_id": idn, "platform": platform, "username": username}}


def page(pid, ig_id=None, ig_user=None, assigned=True, name="Pg"):
    return {"page_id": pid, "page_name": name, "assigned": assigned, "ig_id": ig_id, "ig_username": ig_user}


BASE_AR = [
    ar("r41", "IDN-000041", account_code="IDN-000041", ig_user_id="178YUNA", credential_key="YUNA", account_handle="yuna18253"),
    ar("r36", "IDN-000036", account_code="IDN-000036", ig_user_id="178AI", credential_key="AI"),
    ar("r48", "IDN-000048", account_code="IDN-000048", ig_user_id="178KB", fb_page_id="117", credential_key="SALE1",
       api_provider="facebook_login", account_handle="kbeautiquewholesale"),
    ar("r17", "IDN-000017", account_handle="Petit Phẫu Thuật"),
]
BASE_PA = [pa("IDN-000017", "Instagram", "Petit Phẫu Thuật"), pa("IDN-000014", "Instagram", "medspa")]
ENV = "SALE1_INSTA_IG_USER_ID=178KB\nSALE1_INSTA_ACCESS_TOKEN=x\n"


def by_page(plan):
    return {p["page_id"]: p for p in plan}


def test_new_account_ready_fills_only_empty_fields_and_env():
    plan = by_page(ob.build_plan([page("P17", "178PETIT", "petit phẫu thuật")], BASE_AR, BASE_PA, ENV))
    p = plan["P17"]
    assert p["status"] == "ready" and p["identity_id"] == "IDN-000017"
    assert p["airtable"] == {"account_code": "IDN-000017", "ig_user_id": "178PETIT", "fb_page_id": "P17",
                             "credential_key": "IDN_000017", "api_provider": "facebook_login"}
    assert p["env"] == ["IDN_000017_INSTA_IG_USER_ID", "IDN_000017_INSTA_ACCESS_TOKEN"]


def test_already_connected_sale1_is_no_change():
    p = by_page(ob.build_plan([page("117", "178KB", "kbeautiquewholesale")], BASE_AR, BASE_PA, ENV))["117"]
    assert p["status"] == "no_change" and p["airtable"] == {} and p["env"] == []


def test_protected_accounts_skipped():
    p = by_page(ob.build_plan([page("PY", "178YUNA", "yuna18253")], BASE_AR, BASE_PA, ENV))["PY"]
    assert p["status"] == "skip" and "보호" in p["reason"]


def test_zero_or_multiple_matches_skipped():
    ar2 = BASE_AR + [ar("rX", "IDN-000099", account_handle="dupname"), ar("rY", "IDN-000098", account_handle="dupname")]
    plan = by_page(ob.build_plan([page("PA", "178A", "nobody"), page("PB", "178B", "dupname")], ar2, BASE_PA, ENV))
    assert plan["PA"]["status"] == "skip" and "0건" in plan["PA"]["reason"]
    assert plan["PB"]["status"] == "skip" and "2건" in plan["PB"]["reason"]


def test_existing_different_value_is_conflict_not_overwrite():
    ar2 = [r for r in BASE_AR if r["id"] != "r17"] + [ar("r17", "IDN-000017", account_handle="petitx", ig_user_id="178OTHER")]
    p = by_page(ob.build_plan([page("P17", "178PETIT", "petitx")], ar2, [], ENV))["P17"]
    assert p["status"] == "skip" and "충돌" in p["reason"] and p["airtable"] == {}


def test_ig_id_used_by_other_record_blocked():
    ar2 = BASE_AR + [ar("r20", "IDN-000020", account_handle="hoa")]
    p = by_page(ob.build_plan([page("P20", "178KB", "hoa")], ar2, [], ENV))["P20"]   # 178KB 는 048 소유
    assert p["status"] == "skip" and "IDN-000048" in p["reason"]


def test_env_ig_mismatch_blocked():
    ar2 = BASE_AR + [ar("r20", "IDN-000020", account_handle="hoa", credential_key="HOA")]
    env = ENV + "HOA_INSTA_IG_USER_ID=178WRONG\n"
    p = by_page(ob.build_plan([page("P20", "178HOA", "hoa")], ar2, [], env))["P20"]
    assert p["status"] == "skip" and ".env" in p["reason"]


def test_unassigned_page_unknown_identity_is_skipped_not_assigned():
    p = by_page(ob.build_plan([page("PN", assigned=False, name="mystery")], BASE_AR, BASE_PA, ENV))["PN"]
    assert p["status"] == "skip" and "0건" in p["reason"]


def test_unassigned_page_identified_by_facebookpage_row_is_assign_only():
    pa2 = BASE_PA + [pa("IDN-000017", "FacebookPAGE", "petit")]
    p = by_page(ob.build_plan([page("PN", assigned=False, name="petit")], BASE_AR, pa2, ENV))["PN"]
    assert p["status"] == "ready" and p["assign"] and p["identity_id"] == "IDN-000017"
    assert p["airtable"] == {} and p["env"] == []


def test_only_filter_includes_unassigned_identified_page():
    pa2 = BASE_PA + [pa("IDN-000017", "FacebookPAGE", "petit"), pa("IDN-000014", "FacebookPAGE", "galaxylab")]
    plan = ob.build_plan([page("PN", assigned=False, name="petit"), page("PM", assigned=False, name="galaxylab")],
                         BASE_AR + [ar("r14", "IDN-000014")], pa2, ENV, only={"IDN-000017"})
    assert [(p["identity_id"], p["status"]) for p in plan] == [("IDN-000017", "ready")]


def test_only_filter_limits_to_identity():
    plan = ob.build_plan([page("P17", "178PETIT", "Petit Phẫu Thuật"), page("PN", assigned=False, name="zz")],
                         BASE_AR, BASE_PA, ENV, only={"IDN-000017"})
    assert [p["identity_id"] for p in plan] == ["IDN-000017"]


def test_protected_by_page_or_ig_id_even_if_handle_points_elsewhere():
    ar2 = [r for r in BASE_AR if r["id"] != "r41"] + [ar("r41", "IDN-000041", account_code="IDN-000041",
           ig_user_id="178YUNA", fb_page_id="PY", credential_key="YUNA")]
    plan = by_page(ob.build_plan([page("PY", assigned=False, name="AI+24autoprogram"),
                                  page("PZ", "178YUNA", "Petit Phẫu Thuật")], ar2, BASE_PA, ENV))
    assert plan["PY"]["status"] == "skip" and "보호" in plan["PY"]["reason"]
    assert plan["PZ"]["status"] == "skip" and "보호" in plan["PZ"]["reason"]


def test_duplicate_ig_in_airtable_fail_closed_any_order():
    for order in (0, 1):
        dup = [ar("rA", "IDN-000017", account_handle="petitx"), ar("rB", "IDN-000099", ig_user_id="178P")]
        if order:
            dup.reverse()
        ar2 = BASE_AR[:3] + dup + [ar("rC", "IDN-000098", ig_user_id="178P")]
        p = by_page(ob.build_plan([page("P17", "178P", "petitx")], ar2, [], ENV))["P17"]
        assert p["status"] == "skip" and "IDN-000098" in p["reason"] and "IDN-000099" in p["reason"]


def test_duplicate_identity_records_fail_closed():
    ar2 = BASE_AR + [ar("r17b", "IDN-000017", account_handle="other")]
    p = by_page(ob.build_plan([page("P17", "178PETIT", "Petit Phẫu Thuật")], ar2, BASE_PA, ENV))["P17"]
    assert p["status"] == "skip" and "2건" in p["reason"]


def test_in_plan_duplicates_skip_all_involved_order_independent():
    pa2 = BASE_PA + [pa("IDN-000017", "Instagram", "petit2")]
    for pages in ([page("P1", "178A", "Petit Phẫu Thuật"), page("P2", "178B", "petit2")],
                  [page("P2", "178B", "petit2"), page("P1", "178A", "Petit Phẫu Thuật")]):
        plan = by_page(ob.build_plan(pages, BASE_AR, pa2, ENV))
        assert plan["P1"]["status"] == plan["P2"]["status"] == "skip"
        assert "계획 내 중복" in plan["P1"]["reason"]


def test_env_duplicate_key_fail_closed():
    ar2 = BASE_AR + [ar("r20", "IDN-000020", account_handle="hoa", credential_key="HOA")]
    env = ENV + "HOA_INSTA_ACCESS_TOKEN=a\nHOA_INSTA_ACCESS_TOKEN=b\n"
    p = by_page(ob.build_plan([page("P20", "178HOA", "hoa")], ar2, [], env))["P20"]
    assert p["status"] == "skip" and "중복" in p["reason"]


def _ready_two():
    pa2 = BASE_PA + [pa("IDN-000014", "FacebookPAGE", "galaxylab")]
    return ob.build_plan([page("P17", "178PETIT", "Petit Phẫu Thuật"), page("P14", assigned=False, name="galaxylab")],
                         BASE_AR + [ar("r14", "IDN-000014")], pa2, ENV)


def test_partial_apply_airtable_failure_reports_without_secret():
    import pytest
    def bad_patch(rid, f):
        raise RuntimeError(f"boom with {TOKEN}")
    with pytest.raises(ob.PartialApplyError) as ei:
        ob.apply_plan(_ready_two(), assign_page=lambda pid: None, patch_airtable=bad_patch,
                      append_env=lambda t: None, token=TOKEN, today="261015")
    rep = ei.value.report
    assert rep["failed_step"] == "airtable_patch" and rep["failed_identity"] == "IDN-000017"
    assert not any(w["op"] == "env_append" for w in rep["writes"]) and TOKEN not in str(rep)


def test_partial_apply_after_assign_lists_assigned_page():
    import pytest
    plan = _ready_two()
    order = [p["identity_id"] for p in plan if p["status"] == "ready"]
    assigned = []
    def patch(rid, f):
        raise RuntimeError("airtable down")
    with pytest.raises(ob.PartialApplyError) as ei:
        ob.apply_plan(list(reversed(plan)), assign_page=assigned.append, patch_airtable=patch,
                      append_env=lambda t: None, token=TOKEN, today="261015")
    rep = ei.value.report
    assert assigned == ["P14"] and any(w["op"] == "meta_assign" and w["target"] == "P14" and w["outcome"] == "applied"
                                       for w in rep["manual_rollback"])
    assert set(order) >= {"IDN-000017", "IDN-000014"}


def test_partial_apply_env_failure_reports_airtable_done():
    import pytest
    def bad_env(t):
        raise OSError("disk full")
    with pytest.raises(ob.PartialApplyError) as ei:
        ob.apply_plan(_ready_two(), assign_page=lambda pid: None, patch_airtable=lambda r, f: None,
                      append_env=bad_env, token=TOKEN, today="261015")
    rep = ei.value.report
    assert rep["failed_step"] == "env_append"
    assert any(w["op"] == "airtable_patch" and w["target"] == "r17" and "ig_user_id" in w["fields"]
               and w["outcome"] == "applied" for w in rep["manual_rollback"])


def test_apply_calls_only_injected_io_and_renders_env():
    plan = ob.build_plan([page("P17", "178PETIT", "Petit Phẫu Thuật"), page("117", "178KB", "kbeautiquewholesale"),
                          page("PY", "178YUNA", "yuna18253")], BASE_AR, BASE_PA, ENV)
    calls = {"assign": [], "patch": [], "env": []}
    done = ob.apply_plan(plan, assign_page=calls["assign"].append,
                         patch_airtable=lambda rid, f: calls["patch"].append((rid, f)),
                         append_env=calls["env"].append, token=TOKEN, today="261015")
    assert done == {"assigned": 0, "airtable": 1, "env_lines": 2}
    assert [rid for rid, _ in calls["patch"]] == ["r17"]          # 048·041 은 쓰지 않음
    text = calls["env"][0]
    assert "IDN_000017_INSTA_IG_USER_ID=178PETIT" in text and f"IDN_000017_INSTA_ACCESS_TOKEN={TOKEN}" in text
    assert "YUNA" not in text and "SALE1" not in text


def test_print_plan_never_shows_token(capsys):
    plan = ob.build_plan([page("P17", "178PETIT", "Petit Phẫu Thuật")], BASE_AR, BASE_PA, ENV + f"X={TOKEN}\n")
    ob.print_plan(plan)
    assert TOKEN not in capsys.readouterr().out


def test_dry_run_main_writes_nothing(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(f"YUNA_INSTA_ACCESS_TOKEN={TOKEN}\n", encoding="utf-8")
    monkeypatch.setenv("YUNA_INSTA_ACCESS_TOKEN", TOKEN)   # load_dotenv 가 바꾼 값을 테스트 후 원복
    monkeypatch.setattr(ob, "ROOT", tmp_path)
    monkeypatch.setattr(ob, "fetch_pages", lambda t: [page("P17", "178PETIT", "Petit Phẫu Thuật")])
    monkeypatch.setattr(ob, "fetch_airtable", lambda table: BASE_AR if table == "Account_Registry" else BASE_PA)
    def no_write(*a, **k):
        raise AssertionError("dry-run 에서 쓰기 호출")
    monkeypatch.setattr(ob.requests, "post", no_write)
    monkeypatch.setattr(ob.requests, "patch", no_write)
    before = env_file.read_bytes()
    assert ob.main([]) == 0
    assert env_file.read_bytes() == before
    assert not (tmp_path / "backup").exists()


# ── 261015 ID 우선 매칭 ─────────────────────────────────────────────────────

def test_id_match_wins_even_if_names_changed():
    p = by_page(ob.build_plan([page("117", "178KB", "renamed_ig", name="renamed_page")], BASE_AR, [], ENV))["117"]
    assert p["identity_id"] == "IDN-000048" and p["status"] == "no_change"


def test_same_page_id_on_two_records_is_id_conflict():
    ar2 = BASE_AR + [ar("r12", "IDN-000012", fb_page_id="117", account_handle="K cosmetics")]
    p = by_page(ob.build_plan([page("117", "178KB", "kbeautiquewholesale", name="k.beautymcn")], ar2, [], ENV))["117"]
    assert p["status"] == "skip" and "ID 충돌" in p["reason"]


def test_sale1_scenario_before_and_after_isolation():
    pa_rows = [pa("IDN-000048", "FacebookPAGE", "k.beautymcn"), pa("IDN-000012", "FacebookPAGE", "k.beautymcn")]
    pg_ = [page("117", "178KB", "kbeautiquewholesale", name="k.beautymcn")]
    before = BASE_AR + [ar("r12", "IDN-000012", fb_page_id="117")]
    after = BASE_AR + [ar("r12", "IDN-000012")]
    assert by_page(ob.build_plan(pg_, before, pa_rows, ENV))["117"]["status"] == "skip"
    p = by_page(ob.build_plan(pg_, after, pa_rows, ENV))["117"]
    assert p["status"] == "no_change" and p["identity_id"] == "IDN-000048"


def test_name_pointing_only_elsewhere_contradicts_id():
    ar2 = BASE_AR + [ar("r12", "IDN-000012", account_handle="kbeautiquewholesale2")]
    p = by_page(ob.build_plan([page("117", "178KB", "kbeautiquewholesale2")], ar2, [], ENV))["117"]
    assert p["status"] == "skip" and "이름 매칭" in p["reason"]


def test_protected_by_id_still_skipped_when_name_points_elsewhere():
    p = by_page(ob.build_plan([page("PX", "178AI", "Petit Phẫu Thuật")], BASE_AR, BASE_PA, ENV))["PX"]
    assert p["status"] == "skip" and "보호" in p["reason"]


# ── 261015 원격 성공 후 Timeout(결과 불명) ──────────────────────────────────

class _Timeout(Exception):
    pass


def _assign_only_plan():
    pa2 = BASE_PA + [pa("IDN-000014", "FacebookPAGE", "galaxylab")]
    return ob.build_plan([page("P14", assigned=False, name="galaxylab")], BASE_AR + [ar("r14", "IDN-000014")], pa2, ENV)


def _run(plan, **kw):
    import pytest
    base = dict(assign_page=lambda pid: None, patch_airtable=lambda r, f: None, append_env=lambda t: None,
                token=TOKEN, today="261015")
    base.update(kw)
    with pytest.raises(ob.PartialApplyError) as ei:
        ob.apply_plan(plan, **base)
    return ei.value.report


def test_timeout_after_remote_success_is_recorded_as_applied():
    calls = []
    def assign(pid):
        calls.append(pid)
        raise _Timeout("read timed out")
    rep = _run(_assign_only_plan(), assign_page=assign, verify_assign=lambda pid: True)
    assert calls == ["P14"]                                    # 재시도 없음
    assert rep["failed_outcome"] == "applied"
    assert rep["manual_rollback"] == [{"op": "meta_assign", "identity_id": "IDN-000014", "target": "P14",
                                       "fields": [], "outcome": "applied"}]


def test_timeout_unverifiable_is_unknown_and_listed_for_manual_check():
    def assign(pid):
        raise _Timeout("t")
    rep = _run(_assign_only_plan(), assign_page=assign, verify_assign=lambda pid: None)
    assert rep["failed_outcome"] == "UNKNOWN" and rep["manual_rollback"][0]["outcome"] == "UNKNOWN"


def test_verify_exception_or_missing_verifier_is_unknown():
    def assign(pid):
        raise _Timeout("t")
    def boom(pid):
        raise RuntimeError("verify down")
    assert _run(_assign_only_plan(), assign_page=assign, verify_assign=boom)["failed_outcome"] == "UNKNOWN"
    assert _run(_assign_only_plan(), assign_page=assign)["failed_outcome"] == "UNKNOWN"


def test_airtable_timeout_not_applied_is_excluded_from_rollback():
    plan = _ready_two()
    def patch(rid, f):
        raise _Timeout("t")
    rep = _run(list(reversed(plan)), patch_airtable=patch, verify_airtable=lambda rid, f: False)
    assert rep["failed_outcome"] == "not_applied"
    assert [w["op"] for w in rep["manual_rollback"]] == ["meta_assign"]    # 앞서 성공한 배정만
    assert "IDN-000017" not in rep["not_started"]


def test_intent_recorded_before_write():
    seen = []
    def patch(rid, f):
        seen.append("patch")
        raise _Timeout("t")
    rep = _run(_ready_two(), patch_airtable=patch, verify_airtable=lambda rid, f: True)
    w = [x for x in rep["writes"] if x["op"] == "airtable_patch"][0]
    assert seen == ["patch"] and w["outcome"] == "applied" and w["target"] == "r17"


def test_env_timeout_verified_applied_and_no_token_in_report():
    def bad_env(t):
        raise _Timeout(f"slow {TOKEN}")
    rep = _run(_ready_two(), append_env=bad_env, verify_env=lambda t: True)
    assert rep["failed_step"] == "env_append" and rep["failed_outcome"] == "applied"
    assert TOKEN not in str(rep)
