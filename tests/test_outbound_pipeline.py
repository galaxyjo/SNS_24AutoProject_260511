"""STEP 3-D1 (260901) — outbound_pipeline.crawl_group_prospects (source='members').
실 브라우저/Airtable 미접촉."""

import pytest

from modules.interaction_engine import outbound_pipeline as pl


class _Box:
    def __init__(self, text):
        self.text = text


class _MemberLink:
    """/members 페이지의 회원 프로필 링크 <a>."""
    def __init__(self, href, name, card_text=""):
        self._href = href
        self.text = name
        self._card = card_text or name

    def get_attribute(self, k):
        if k == "href":
            return self._href
        if k == "aria-label":
            return self.text
        return None

    def find_element(self, by, xpath):
        return _Box(self._card)


class _MembersDriver:
    def __init__(self, links, body_text="Members"):
        self._links = links
        self._body = body_text
        self.current_url = "https://www.facebook.com/groups/1/members"
        self.gets = []
        self.quit_called = False

    def get(self, url):
        self.gets.append(url)
        self.current_url = url

    def find_elements(self, by, sel):
        if "/user/" in sel:
            return self._links
        return []

    def find_element(self, by, sel):
        return _Box(self._body)

    def execute_script(self, *a, **k):
        return None

    def quit(self):
        self.quit_called = True


class _Repo:
    def __init__(self, existing_prospects=None, existing_actions=None,
                 automation_enabled=True, limits=None, used_today=0):
        self._p = set(existing_prospects or [])
        self._a = set(existing_actions or [])
        self._auto = automation_enabled
        self._limits = dict(limits) if limits is not None else {
            "follow": 20, "friend": 10, "comment": 0}
        self._used = used_today
        self.created = []

    def find_prospect_by_target(self, ident, action_type):
        return "recP" if ident in self._p else None

    def find_outbound_action(self, account, ident, action_type):
        return "recA" if ident in self._a else None

    def create_prospect(self, data):
        self.created.append(data)
        return "recNEW"

    def get_publish_account(self, account_code):
        return {"account_code": account_code, "automation_enabled": self._auto}

    def get_account_outbound_limits(self, account_code):
        return dict(self._limits)

    def count_outbound_actions_today(self, account_code, action_type):
        return self._used


_GROUP = {"group_code": "PG-017", "group_url": "https://www.facebook.com/groups/610113703703488",
          "prospecting_status": "active"}

_REAL_RESOLVE_GROUP = pl._resolve_group   # autouse _fast 가 교체하기 전 원본 캡처


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(pl.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr("modules.sns.facebook_crawler.load_supplier_blocklist", lambda: [])
    monkeypatch.setattr(pl, "_resolve_group", lambda repo, q: dict(_GROUP))


def _links(n, prefix="Seller"):
    out = []
    for i in range(n):
        out.append(_MemberLink(
            f"https://www.facebook.com/groups/610113703703488/user/{1000 + i}/",
            f"{prefix} {i}",
            card_text=f"{prefix} {i}\nKorean cosmetics wholesale · Vietnam"))
    return out


def test_group_not_found(monkeypatch):
    monkeypatch.setattr(pl, "_resolve_group", lambda repo, q: None)
    out = pl.crawl_group_prospects("PG-999", dry_run=False, repo=_Repo())
    assert out["status"] == "error" and out["reason"] == "group_not_in_prospect_groups"


def test_dry_run_returns_plan():
    out = pl.crawl_group_prospects("PG-017", dry_run=True, repo=_Repo())
    assert out["status"] == "dry_run"
    assert out["source"] == "members"
    assert out["crawled"] == 0


def test_members_page_url_used():
    d = _MembersDriver(_links(3))
    pl.crawl_group_prospects("PG-017", dry_run=False, repo=_Repo(),
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    assert d.gets[0].endswith("/members")


def test_checkpoint_aborts():
    d = _MembersDriver([], body_text="Please complete this security check")
    out = pl.crawl_group_prospects("PG-017", dry_run=False, repo=_Repo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["status"] == "aborted"
    assert out["reason"].startswith("checkpoint:")
    assert d.quit_called is True


def test_members_extracted_filtered_and_written():
    d = _MembersDriver(_links(5))
    repo = _Repo()
    out = pl.crawl_group_prospects("PG-017", source="members", max_authors=15,
                                   dry_run=False, repo=repo,
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["status"] == "done"
    assert out["crawled"] == 5
    assert out["created"] == 5           # write=True 기본
    assert len(repo.created) == 5
    assert out["scored"] >= 1            # "Korean cosmetics wholesale · Vietnam" → scored
    rec = repo.created[0]
    assert rec["source_group_code_ref"] == "PG-017"
    assert rec["target_identifier"] == "1000"
    assert rec["action_type"] == "follow"


def test_no_write_returns_samples_only():
    d = _MembersDriver(_links(4))
    repo = _Repo()
    out = pl.crawl_group_prospects("PG-017", write=False, dry_run=False, repo=repo,
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["status"] == "done"
    assert out["crawled"] == 4
    assert out["created"] == 0
    assert repo.created == []
    assert len(out["samples"]) == 4
    assert all("decision" in s and "url" in s for s in out["samples"])


def test_dedup_skips_existing():
    d = _MembersDriver(_links(3))
    repo = _Repo(existing_prospects={"1000"}, existing_actions={"1001"})
    out = pl.crawl_group_prospects("PG-017", dry_run=False, repo=repo,
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["crawled"] == 3
    assert out["skipped_dup"] == 2
    assert out["created"] == 1


def test_dedup_by_identifier_not_url():
    # 회원 링크에 trailing slash 유무가 달라도 identifier(uid)로 중복 잡힌다
    d = _MembersDriver(_links(2))
    repo = _Repo(existing_prospects={"1000", "1001"})
    out = pl.crawl_group_prospects("PG-017", dry_run=False, repo=repo,
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["skipped_dup"] == 2 and out["created"] == 0


def test_bad_source_rejected():
    with pytest.raises(ValueError):
        pl.crawl_group_prospects("PG-017", source="nope", repo=_Repo())


# ── STEP 3-E: enrich_one_prospect (Friend Canary Ready) ───────────────────

TGT = "https://www.facebook.com/groups/192853047958638/user/100095633377091/"


class _Btn:
    def __init__(self, label):
        self._label = label
    def get_attribute(self, k):
        return self._label if k == "aria-label" else None
    @property
    def text(self):
        return self._label


class _ProfileDriver:
    def __init__(self, h1="", body="normal profile page", friend_button=True):
        self._h1 = h1
        self._body = body
        self._btns = [_Btn("친구 추가"), _Btn("메시지")] if friend_button else [_Btn("메시지")]
        self.gets = []
        self.quit_called = False

    def get(self, url):
        self.gets.append(url)

    def find_element(self, by, sel):
        if "h1" in sel:
            if not self._h1:
                raise Exception("no h1")
            return _Box(self._h1)
        return _Box(self._body)

    def find_elements(self, by, sel):
        if "button" in sel or "role='button'" in sel:
            return self._btns
        return []

    def execute_script(self, *a, **k):
        return None

    def quit(self):
        self.quit_called = True


def test_enrich_dedup_no_browser():
    repo = _Repo(existing_prospects={"100095633377091"})
    out = pl.enrich_one_prospect(TGT, group_code="PG-009", dry_run=False, repo=repo,
                                 driver_factory=lambda: (_ for _ in ()).throw(AssertionError("no browser")))
    assert out["status"] == "dedup"
    assert out["duplicate"] is True
    assert repo.created == []


def test_enrich_dry_run():
    out = pl.enrich_one_prospect(TGT, group_code="PG-009", repo=_Repo())
    assert out["status"] == "dry_run"
    assert out["target_identifier"] == "100095633377091"
    assert out["action_type"] == "friend_request"


def test_enrich_checkpoint_aborts():
    d = _ProfileDriver(body="please complete this security check")
    repo = _Repo()
    out = pl.enrich_one_prospect(TGT, group_code="PG-009", dry_run=False, repo=repo,
                                 driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["status"] == "aborted"
    assert out["reason"].startswith("checkpoint:")
    assert repo.created == []


def test_enrich_canary_ready_when_all_pass():
    d = _ProfileDriver(
        h1="Anna Beauty Shop",
        body="Anna Beauty Shop\nLives in Ho Chi Minh City, Vietnam\nKorean cosmetics wholesale",
        friend_button=True)
    repo = _Repo()
    out = pl.enrich_one_prospect(TGT, group_code="PG-009", dry_run=False, repo=repo,
                                 driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["status"] == "written"
    assert out["queue_status"] == "CANARY_TARGET_READY"
    assert out["friend_button"] == "found"
    assert out["korean_exclusion"] is False
    assert out["profile_normal"] is True
    assert out["kill_switch"] == "on"
    assert out["daily_limit"].startswith("ok:")
    rec = repo.created[0]
    assert rec["status"] == "CANARY_TARGET_READY"
    assert rec["action_type"] == "friend_request"
    assert rec["source_group_code_ref"] == "PG-009"


def test_enrich_no_friend_button_filtered():
    d = _ProfileDriver(h1="Some Shop", body="Some Shop\nVietnam\ncosmetics", friend_button=False)
    repo = _Repo()
    out = pl.enrich_one_prospect(TGT, group_code="PG-009", dry_run=False, repo=repo,
                                 driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["queue_status"] == "filtered_out"
    assert repo.created[0]["filter_reason"] == "friend_button_not_found"


def test_enrich_korea_based_filtered():
    d = _ProfileDriver(h1="박지민", body="박지민\n서울특별시 거주\n일상 계정", friend_button=True)
    repo = _Repo()
    out = pl.enrich_one_prospect(TGT, group_code="PG-009", dry_run=False, repo=repo,
                                 driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["queue_status"] == "filtered_out"
    assert out["korean_exclusion"] is True
    assert repo.created[0]["filter_reason"] in ("korean_based", "korean_national")


def test_enrich_unavailable_profile_filtered():
    d = _ProfileDriver(body="This content isn't available right now", friend_button=False)
    repo = _Repo()
    out = pl.enrich_one_prospect(TGT, group_code="PG-009", dry_run=False, repo=repo,
                                 driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["queue_status"] == "filtered_out"
    assert repo.created[0]["filter_reason"] == "abnormal_profile"


def test_enrich_reports_kill_switch_off():
    d = _ProfileDriver(h1="Anna", body="Anna\nVietnam\ncosmetics wholesale", friend_button=True)
    repo = _Repo(automation_enabled=False)
    out = pl.enrich_one_prospect(TGT, group_code="PG-009", dry_run=False, repo=repo,
                                 driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["kill_switch"] == "off"
    # 타겟 자체는 조건 충족 → 레코드는 CANARY_TARGET_READY, 시스템 게이트는 RESULT 로만
    assert out["queue_status"] == "CANARY_TARGET_READY"


def test_enrich_reports_daily_limit_exceeded():
    d = _ProfileDriver(h1="Anna", body="Anna\nVietnam\ncosmetics wholesale", friend_button=True)
    repo = _Repo(limits={"follow": 20, "friend": 10, "comment": 0}, used_today=10)
    out = pl.enrich_one_prospect(TGT, group_code="PG-009", dry_run=False, repo=repo,
                                 driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["daily_limit"] == "exceeded:10/10"


# ── STEP 3-F: friend_canary_from_group (카드 기반 위임 + Daily KPI) ────────

def test_friend_canary_group_not_found(monkeypatch):
    monkeypatch.setattr(pl, "_resolve_group", lambda repo, q: None)
    out = pl.friend_canary_from_group("PG-999", dry_run=False, repo=_Repo())
    assert out["status"] == "error"


def test_resolve_group_adhoc_preserves_members_subview(monkeypatch):
    # Prospect_Groups 에 없는 raw URL → ad-hoc, /members/things_in_common 하위뷰 보존
    class _R:
        def raise_for_status(self): pass
        def json(self): return {"records": []}
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: _R())

    g = _REAL_RESOLVE_GROUP(None,
        "https://www.facebook.com/groups/755455243345993/members/things_in_common")
    assert g["group_url"].endswith("/members/things_in_common")
    assert g["prospecting_status"] == "adhoc"

    g2 = _REAL_RESOLVE_GROUP(None, "https://www.facebook.com/groups/755455243345993")
    assert g2["group_url"] == "https://www.facebook.com/groups/755455243345993"


def test_friend_canary_delegates_to_friend_request_canary(monkeypatch):
    monkeypatch.setattr(pl, "_resolve_group", lambda repo, q: dict(_GROUP))
    calls = {}

    def _fake(group_url, **kw):
        calls.update(kw)
        calls["group_url"] = group_url
        return {"result": "success", "reason": "", "action_type": "friend_request",
                "target_identifier": "555", "daily_count": 3}

    monkeypatch.setattr(pl.oc, "friend_request_canary", _fake)
    out = pl.friend_canary_from_group("PG-009", dry_run=False, repo=_Repo())
    assert out["status"] == "done"
    assert calls["group_url"] == _GROUP["group_url"]
    assert calls["dry_run"] is False
    assert out["friend"]["result"] == "success"
    # STEP 3-G: 개인별 KPI 조회 없음 — canary 가 반환한 로컬 집계만 동봉
    assert out["daily_count"] == 3


def test_friend_canary_dry_run_no_kpi(monkeypatch):
    monkeypatch.setattr(pl, "_resolve_group", lambda repo, q: dict(_GROUP))
    monkeypatch.setattr(pl.oc, "friend_request_canary",
                        lambda *a, **k: {"result": "skipped", "reason": "dry_run"})
    out = pl.friend_canary_from_group("PG-009", dry_run=True, repo=_Repo())
    assert out["friend"]["reason"] == "dry_run"
    assert "daily_kpi" not in out


class _KpiRepo:
    def __init__(self, rows, friend_limit=10):
        self._rows = rows
        self._lim = friend_limit

    def list_outbound_actions_since(self, account, action, since):
        return [r for r in self._rows if r["occurred_at"].startswith(since)]

    def get_account_outbound_limits(self, account):
        return {"follow": 20, "friend": self._lim, "comment": 0}


def test_daily_friend_kpi():
    today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
    rows = [
        {"occurred_at": f"{today}T01:00:00Z", "result": "success", "relationship_status": "requested"},
        {"occurred_at": f"{today}T02:00:00Z", "result": "failed", "relationship_status": ""},
        {"occurred_at": f"{today}T03:00:00Z", "result": "success", "relationship_status": "requested"},
        {"occurred_at": "2020-01-01T00:00:00Z", "result": "success", "relationship_status": "requested"},
    ]
    k = pl.daily_friend_kpi("IDN-000041", repo=_KpiRepo(rows))
    assert k["friend_requests_attempted_today"] == 3
    assert k["friend_requests_success_today"] == 2
    assert k["friend_requests_failed_today"] == 1
    assert k["daily_limit"] == 10
    assert k["remaining_today"] == 8   # 10 - 2 sent(requested)


def test_monthly_friend_kpi():
    mon = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m")
    rows = [
        {"occurred_at": f"{mon}-02T00:00:00Z", "relationship_status": "requested"},
        {"occurred_at": f"{mon}-05T00:00:00Z", "relationship_status": "accepted"},
        {"occurred_at": f"{mon}-06T00:00:00Z", "relationship_status": "requested"},
        {"occurred_at": f"{mon}-07T00:00:00Z", "relationship_status": ""},
    ]
    k = pl.monthly_friend_kpi("IDN-000041", repo=_KpiRepo(rows))
    assert k["friend_requests_sent_this_month"] == 3   # requested + accepted
    assert k["friends_accepted_this_month"] == 1
    assert k["acceptance_rate"] == round(1 / 3, 4)


def test_monthly_friend_kpi_zero():
    k = pl.monthly_friend_kpi("IDN-000041", repo=_KpiRepo([]))
    assert k == {"friend_requests_sent_this_month": 0, "friends_accepted_this_month": 0,
                 "acceptance_rate": 0.0}


# ── STEP 3-G HUMAN SOP (260903): friend_daily_run — Airtable 그룹 순회 ───────────
import re as _re

from modules.interaction_engine import outbound_connector as _oc


class _SopRepo:
    """Kill-switch ON + friend 한도 지정."""
    def __init__(self, friend_cap=10):
        self._cap = friend_cap

    def get_publish_account(self, code):
        return {"account_code": code, "automation_enabled": True}

    def get_account_outbound_limits(self, code):
        return {"follow": 20, "friend": self._cap, "comment": 0}


class _SopBtn:
    def __init__(self, aria, text="친구 추가", on_click=None, visible=True):
        self._aria, self._text, self._on_click, self._visible = aria, text, on_click, visible
        self._container = None

    def get_attribute(self, k):
        return self._aria if k == "aria-label" else None

    @property
    def text(self):
        return self._text

    def is_displayed(self):
        return self._visible

    @property
    def rect(self):
        return ({"x": 5, "y": 5, "width": 100, "height": 30} if self._visible
                else {"x": 0, "y": 0, "width": 0, "height": 0})

    def click(self):
        if self._on_click:
            self._on_click()

    def find_elements(self, by, xpath):
        return [self._container] if ("ancestor" in xpath and self._container) else []


class _SopBox:
    def __init__(self, uid, text):
        self._uid, self.text = uid, text

    def find_elements(self, by, sel):
        class _A:
            def __init__(self, u):
                self._u = u
            def get_attribute(self, k):
                return f"https://www.facebook.com/groups/1/user/{self._u}/" if k == "href" else None
            @property
            def text(self):
                return ""
        return [_A(self._uid)] if "/user/" in sel else []


class _MultiGroupDriver:
    """그룹 URL 별로 다른 회원 목록을 돌려주는 fake. members = {group_substr: [(uid, name)]}"""
    def __init__(self, members_by_group, body="Members"):
        self._by_group = members_by_group
        self._body = body
        self._cur_group = None
        self._clicked = set()
        self.current_url = ""
        self.gets = []
        self.quit_called = False

    def get(self, url):
        self.gets.append(url)
        self.current_url = url
        for key in self._by_group:
            if key in url:
                self._cur_group = key
                break

    def _members(self):
        return self._by_group.get(self._cur_group, [])

    def find_elements(self, by, sel):
        if "ProfileActions" in sel:
            return []
        friend_q = ("님 추가" in sel or sel.rstrip().endswith("추가')]"))
        if friend_q:
            out = []
            for uid, name in self._members():
                if uid in self._clicked:
                    continue
                b = _SopBtn(f"친구 {name}님 추가", on_click=lambda u=uid: self._clicked.add(u))
                b._container = _SopBox(uid, f"{name}\n1개월 전 가입")
                out.append(b)
            return out
        if "role='button'" in sel or "button" in sel:
            out = []
            for uid, name in self._members():
                if uid in self._clicked:
                    out.append(_SopBtn(f"{name}님에 대한 요청 취소", "요청 취소"))
            return out
        return []

    def find_element(self, by, sel):
        return _Box(self._body)

    def execute_script(self, script="", *a, **k):
        return None

    def quit(self):
        self.quit_called = True


@pytest.fixture
def _sop_env(tmp_path, monkeypatch):
    monkeypatch.setenv(_oc.FRIEND_LIVE_ENV, "true")
    monkeypatch.setattr(_oc, "_FRIEND_DAILY_PATH", tmp_path / "friend_daily.json")
    monkeypatch.setattr(_oc.time, "sleep", lambda *a, **k: None)


def test_friend_daily_run_continues_after_success_within_group(_sop_env):
    """SOP: 한 명 성공 후 STOP 하지 않고 같은 그룹의 다음 회원 계속."""
    d = _MultiGroupDriver({"/groups/AAA": [("11", "Mai Anh"), ("12", "Hnin Zar"), ("13", "Nadia")]})
    out = pl.friend_daily_run(dry_run=False, repo=_SopRepo(friend_cap=10),
                              group_urls=[("PG-A", "https://www.facebook.com/groups/AAA/members")],
                              driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["status"] == "done"
    assert out["sent"] == 3                      # 3명 전부 처리 (1명 후 STOP 아님)
    assert _oc._friend_daily_count("IDN-000041") == 3


def test_friend_daily_run_moves_to_next_group_when_exhausted(_sop_env):
    """SOP: 현재 그룹 소진되면 Airtable 다음 그룹으로 계속."""
    d = _MultiGroupDriver({
        "/groups/AAA": [("21", "Mai Anh")],
        "/groups/BBB": [("22", "Nadia"), ("23", "Zouache F")],
    })
    out = pl.friend_daily_run(dry_run=False, repo=_SopRepo(friend_cap=10),
                              group_urls=[("PG-A", "https://www.facebook.com/groups/AAA/members"),
                                          ("PG-B", "https://www.facebook.com/groups/BBB/members")],
                              driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["groups_visited"] == ["PG-A", "PG-B"]
    assert out["sent"] == 3


def test_friend_daily_run_stops_at_daily_limit(_sop_env):
    """SOP: daily_friend_limit 도달 시 즉시 종료 — 남은 그룹 방문 안 함."""
    d = _MultiGroupDriver({
        "/groups/AAA": [("31", "Mai Anh"), ("32", "Nadia"), ("33", "Rin T")],
        "/groups/BBB": [("34", "Later One")],
    })
    out = pl.friend_daily_run(dry_run=False, repo=_SopRepo(friend_cap=2),
                              group_urls=[("PG-A", "https://www.facebook.com/groups/AAA/members"),
                                          ("PG-B", "https://www.facebook.com/groups/BBB/members")],
                              driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["sent"] == 2
    assert _oc._friend_daily_count("IDN-000041") == 2
    assert out["groups_visited"] == ["PG-A"]          # 한도 도달 → PG-B 안 감
    assert not any("/groups/BBB" in g for g in d.gets)


def test_friend_daily_run_checkpoint_stops_all_groups(_sop_env):
    """SOP §6: checkpoint 는 전체 STOP + day-block, 다음 그룹 안 감."""
    d = _MultiGroupDriver({"/groups/AAA": [("41", "Mai Anh")],
                           "/groups/BBB": [("42", "Nadia")]},
                          body="please complete this security check")
    out = pl.friend_daily_run(dry_run=False, repo=_SopRepo(friend_cap=10),
                              group_urls=[("PG-A", "https://www.facebook.com/groups/AAA/members"),
                                          ("PG-B", "https://www.facebook.com/groups/BBB/members")],
                              driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["status"] == "stopped"
    assert out["reason"].startswith("checkpoint")
    assert out["groups_visited"] == ["PG-A"]
    assert _oc._friend_daily_blocked("IDN-000041")
    assert out["sent"] == 0


def test_friend_daily_run_dry_run_lists_groups_only(_sop_env):
    out = pl.friend_daily_run(repo=_SopRepo(),
                              group_urls=[("PG-A", "u1"), ("PG-B", "u2")])
    assert out["status"] == "dry_run"
    assert out["groups"] == ["PG-A", "PG-B"]
    assert _oc._friend_daily_count("IDN-000041") == 0
