"""
STEP 3 (260901) — modules.interaction_engine.outbound_connector.follow_once mock 검증.

실 브라우저(AdsPower/Selenium)·실 Airtable 미접촉 — FakeDriver / FakeRepo 주입.
Target Test 대응:
  1. automation_enabled=false → outbound action 실행 안 됨
  2. automation_enabled=true → Follow 1회 경로 동작 + 클릭 정확히 1회
  3. 동일 target 재호출 → 중복 실행 방지
  4. 결과가 SSOT(create_outbound_action)에 기록됨
  (+ dry_run 기본 / Live 게이트 / URL Fail-closed / 버튼 미발견 failed)
"""

import re

import pytest

from modules.interaction_engine import outbound_connector as oc

TARGET = "https://www.facebook.com/profile.php?id=100000000000001"


class _FakeEl:
    def __init__(self, label, on_click=None, aria=None):
        self._label = label
        self._aria = label if aria is None else aria
        self.clicks = 0
        self._on_click = on_click

    def get_attribute(self, name):
        return self._aria if name == "aria-label" else None

    @property
    def text(self):
        return self._label

    def click(self):
        self.clicks += 1
        if self._on_click:
            self._on_click()


class _FakeDriver:
    def __init__(self, before=None, after=None):
        self._before = list(before or [])
        self._after = list(after or [])
        self._clicked = False
        self.gets = []
        self.quit_called = False

    def get(self, url):
        self.gets.append(url)

    def find_elements(self, by, xpath):
        return self._after if self._clicked else self._before

    def _mark_clicked(self):
        self._clicked = True

    def quit(self):
        self.quit_called = True


class _FakeRepo:
    def __init__(self, *, automation_enabled=True, existing=None,
                 limits=None, used_today=0):
        self._automation_enabled = automation_enabled
        self._existing = existing
        # 기본 한도는 넉넉히 — 한도 테스트만 명시적으로 낮춘다
        self._limits = dict(limits) if limits is not None else {
            "follow": 50, "friend": 50, "comment": 50}
        self._used_today = used_today
        self.created = []

    def get_publish_account(self, account_code):
        return {"account_code": account_code,
                "automation_enabled": self._automation_enabled}

    def get_account_outbound_limits(self, account_code):
        return dict(self._limits)

    def count_outbound_actions_today(self, account_code_ref, action_type):
        return self._used_today

    def find_outbound_action(self, account_code_ref, target_identifier, action_type):
        return self._existing

    def create_outbound_action(self, data):
        self.created.append(data)
        return "recFAKEOA1"


def _boom():
    raise AssertionError("driver_factory 는 호출되면 안 된다")


@pytest.fixture(autouse=True)
def _fast(tmp_path, monkeypatch):
    """테스트 격리: 로컬 dedup db + friend 일일집계 파일 분리 + sleep 제거."""
    monkeypatch.setattr(oc, "_DB_PATH", tmp_path / "outbound_actions.db")
    monkeypatch.setattr(oc, "_FRIEND_DAILY_PATH", tmp_path / "outbound_friend_daily.json")
    monkeypatch.setattr(oc.time, "sleep", lambda *a, **k: None)


@pytest.fixture
def _live(monkeypatch):
    monkeypatch.setenv(oc.LIVE_ENV, "true")


def _follow_button_driver():
    d = _FakeDriver()
    d._before = [_FakeEl("팔로우", on_click=d._mark_clicked)]
    d._after = [_FakeEl("팔로잉")]
    return d


# ── Target Test 1 ────────────────────────────────────────────────────────────

def test_kill_switch_off_blocks_click():
    repo = _FakeRepo(automation_enabled=False)
    out = oc.follow_once(TARGET, dry_run=False, repo=repo,
                         driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"] == "automation_disabled"
    assert repo.created == []


def test_kill_switch_missing_field_treated_false():
    class _NoField(_FakeRepo):
        def get_publish_account(self, account_code):
            return {"account_code": account_code}  # automation_enabled 키 없음

    repo = _NoField()
    out = oc.follow_once(TARGET, dry_run=False, repo=repo,
                         driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"] == "automation_disabled"


# ── Target Test 2 + 4 ───────────────────────────────────────────────────────

def test_follow_success_single_click_and_recorded(_live):
    driver = _follow_button_driver()
    repo = _FakeRepo()
    out = oc.follow_once(TARGET, dry_run=False, repo=repo,
                         driver_factory=lambda: driver, browser_stopper=lambda: None)

    assert out["result"] == "success"
    assert driver._before[0].clicks == 1          # 정확히 1회 클릭
    assert driver.gets == [TARGET]
    assert driver.quit_called is True

    assert len(repo.created) == 1                  # SSOT 기록 1건
    rec = repo.created[0]
    assert rec["account_code_ref"] == "IDN-000041"
    assert rec["target_identifier"] == "100000000000001"
    assert rec["action_type"] == "follow"
    assert rec["result"] == "success"
    assert rec["target_url"] == TARGET
    assert rec["occurred_at"].endswith("Z")


# ── Target Test 3 ───────────────────────────────────────────────────────────

def test_second_call_same_target_deduped_local(_live):
    driver = _follow_button_driver()
    repo = _FakeRepo()
    first = oc.follow_once(TARGET, dry_run=False, repo=repo,
                           driver_factory=lambda: driver, browser_stopper=lambda: None)
    assert first["result"] == "success"

    repo2 = _FakeRepo()  # SSOT 엔 없지만 로컬 db 가 막아야 한다
    second = oc.follow_once(TARGET, dry_run=False, repo=repo2,
                            driver_factory=_boom, browser_stopper=lambda: None)
    assert second["result"] == "skipped"
    assert second["reason"] == "duplicate_local"
    assert repo2.created == []


def test_dedup_via_ssot_when_prior_record_exists(_live):
    repo = _FakeRepo(existing="recPRIOR")
    out = oc.follow_once(TARGET, dry_run=False, repo=repo,
                         driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"] == "duplicate_ssot"
    assert out["record_id"] == "recPRIOR"
    assert repo.created == []


# ── STEP 3-C: 일일 한도 게이트 ─────────────────────────────────────────────

def test_follow_daily_limit_zero_blocks(_live):
    repo = _FakeRepo(limits={"follow": 0, "friend": 0, "comment": 0})
    out = oc.follow_once(TARGET, dry_run=False, repo=repo,
                         driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"].startswith("daily_limit_exceeded")
    assert repo.created == []


def test_follow_daily_limit_reached_blocks(_live):
    repo = _FakeRepo(limits={"follow": 20, "friend": 10, "comment": 0}, used_today=20)
    out = oc.follow_once(TARGET, dry_run=False, repo=repo,
                         driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"] == "daily_limit_exceeded:20/20"


def test_follow_under_limit_proceeds(_live):
    driver = _follow_button_driver()
    repo = _FakeRepo(limits={"follow": 20, "friend": 0, "comment": 0}, used_today=5)
    out = oc.follow_once(TARGET, dry_run=False, repo=repo,
                         driver_factory=lambda: driver, browser_stopper=lambda: None)
    assert out["result"] == "success"


# ── dry_run / Live gate / Fail-closed ──────────────────────────────────────

def test_dry_run_is_default_no_browser_no_record():
    repo = _FakeRepo()
    out = oc.follow_once(TARGET, repo=repo,
                         driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"] == "dry_run"
    assert repo.created == []


def test_live_requires_env_flag(monkeypatch):
    monkeypatch.delenv(oc.LIVE_ENV, raising=False)
    repo = _FakeRepo()
    with pytest.raises(oc.OutboundActionError):
        oc.follow_once(TARGET, dry_run=False, repo=repo,
                       driver_factory=lambda: _follow_button_driver(),
                       browser_stopper=lambda: None)


@pytest.mark.parametrize("bad_url", [
    "http://www.facebook.com/someone",          # https 아님
    "https://evil.example.com/yuna",            # facebook 아님
    "https://www.facebook.com/",               # 식별자 없음
])
def test_invalid_target_url_fail_closed(bad_url):
    with pytest.raises(oc.OutboundActionError):
        oc.follow_once(bad_url, repo=_FakeRepo())


@pytest.mark.parametrize("url,expected", [
    ("https://www.facebook.com/profile.php?id=100064", "100064"),
    ("https://www.facebook.com/yuna.official", "yuna.official"),
    ("https://www.facebook.com/people/Some-One/100077/", "100077"),
])
def test_extract_target_identifier(url, expected):
    assert oc.extract_target_identifier(url) == expected


# ── 버튼 미발견 → failed 기록 ──────────────────────────────────────────────

def test_follow_button_not_found_records_failed(_live):
    driver = _FakeDriver(before=[_FakeEl("메시지")], after=[])
    repo = _FakeRepo()
    out = oc.follow_once(TARGET, dry_run=False, repo=repo,
                         driver_factory=lambda: driver, browser_stopper=lambda: None)
    assert out["result"] == "failed"
    assert out["reason"] == "follow_button_not_found"
    assert driver.quit_called is True
    assert len(repo.created) == 1
    assert repo.created[0]["result"] == "failed"


def test_already_following_button_not_treated_as_follow(_live):
    driver = _FakeDriver(before=[_FakeEl("팔로잉"), _FakeEl("메시지")], after=[])
    repo = _FakeRepo()
    out = oc.follow_once(TARGET, dry_run=False, repo=repo,
                         driver_factory=lambda: driver, browser_stopper=lambda: None)
    assert out["result"] == "failed"
    assert out["reason"] == "follow_button_not_found"


# ── 친구추가 (friend_in_group) — STEP 3-B1R ────────────────────────────────

GROUP = "https://www.facebook.com/groups/1930721300516777"


@pytest.mark.parametrize("label,expected", [
    ("친구 추가", True), ("친구추가", True), ("Add friend", True),
    ("김야나님에게 친구 추가", True),
    ("친구 요청 취소", False), ("Cancel request", False),
    ("친구", False), ("메시지", False), ("팔로우", False), ("Requested", False),
])
def test_friend_add_label(label, expected):
    assert oc._is_friend_add_label(label) is expected


class _FriendDriver:
    """친구추가 시나리오용 — get() 으로 이동, 클릭 후 버튼 상태 전이."""
    def __init__(self, author_url="", profile_buttons_before=None, profile_buttons_after=None,
                 body_text="normal page"):
        self.author_url = author_url
        self._before = list(profile_buttons_before or [])
        self._after = list(profile_buttons_after or [])
        self._clicked = False
        self.body_text = body_text
        self.current_url = "https://www.facebook.com/"
        self.gets = []
        self.quit_called = False

    def get(self, url):
        self.gets.append(url)
        self.current_url = url

    def find_elements(self, by, sel):
        if "role='feed'" in sel or "role=\"feed\"" in sel:
            return [_FeedArticle(self.author_url)] if self.author_url else []
        return self._after if self._clicked else self._before

    def find_element(self, by, sel):
        return _Body(self.body_text)

    def _mark_clicked(self):
        self._clicked = True

    def quit(self):
        self.quit_called = True


class _Body:
    def __init__(self, text):
        self.text = text


class _FeedArticle:
    def __init__(self, author_url, name="Author", text="post body"):
        self._author_url = author_url
        self._name = name
        self.text = text

    def find_elements(self, by, sel):
        if sel == "a[href]":
            return [_Anchor(self._author_url, self._name)]
        return []


class _Anchor:
    def __init__(self, href, text=""):
        self._href = href
        self.text = text

    def get_attribute(self, name):
        if name == "href":
            return self._href
        if name == "aria-label":
            return self.text
        return None


@pytest.fixture
def _friend_live(monkeypatch):
    monkeypatch.setenv(oc.FRIEND_LIVE_ENV, "true")


def test_friend_kill_switch_off():
    repo = _FakeRepo(automation_enabled=False)
    out = oc.friend_in_group(GROUP, dry_run=False, repo=repo,
                             driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"] == "automation_disabled"


def test_friend_dry_run_default_no_browser():
    out = oc.friend_in_group(GROUP, repo=_FakeRepo(),
                             driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"] == "dry_run"


def test_friend_live_requires_env(monkeypatch):
    monkeypatch.delenv(oc.FRIEND_LIVE_ENV, raising=False)
    with pytest.raises(oc.OutboundActionError):
        oc.friend_in_group(GROUP, dry_run=False, repo=_FakeRepo(),
                           driver_factory=lambda: _FriendDriver(),
                           browser_stopper=lambda: None)


def test_friend_success_from_group_first_author(_friend_live):
    author = "https://www.facebook.com/groups/1930721300516777/user/100055/"
    d = _FriendDriver(author_url=author)
    add_btn = _FakeEl("친구 추가", on_click=d._mark_clicked)
    d._before = [add_btn, _FakeEl("메시지")]
    d._after = [_FakeEl("친구 요청 취소"), _FakeEl("메시지")]
    out = oc.friend_in_group(GROUP, dry_run=False, repo=_FakeRepo(),
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert add_btn.clicks == 1
    assert out["target_url"] == author
    assert d.quit_called is True


def test_friend_checkpoint_aborts_without_click(_friend_live):
    d = _FriendDriver(author_url="https://www.facebook.com/x", body_text="Please complete this security check")
    would = _FakeEl("친구 추가")
    d._before = [would]
    out = oc.friend_in_group(GROUP, dry_run=False, repo=_FakeRepo(),
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"].startswith("checkpoint:")
    assert would.clicks == 0


def test_friend_button_not_found(_friend_live):
    author = "https://www.facebook.com/groups/1930721300516777/user/999/"
    d = _FriendDriver(author_url=author)
    d._before = [_FakeEl("메시지"), _FakeEl("팔로우")]
    out = oc.friend_in_group(GROUP, dry_run=False, repo=_FakeRepo(),
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed"
    assert out["reason"] == "friend_button_not_found"


def test_friend_explicit_target_skips_group_scan(_friend_live):
    t = "https://www.facebook.com/some.person"
    d = _FriendDriver()  # no author_url — group scan would fail
    add_btn = _FakeEl("Add friend", on_click=d._mark_clicked)
    d._before = [add_btn]
    d._after = [_FakeEl("Cancel request")]
    out = oc.friend_in_group(GROUP, dry_run=False, target_url=t, repo=_FakeRepo(),
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert out["target_url"] == t
    assert GROUP not in d.gets  # 그룹 안 열고 바로 대상으로


def test_friend_daily_limit_zero_blocks(_friend_live):
    repo = _FakeRepo(limits={"follow": 50, "friend": 0, "comment": 0})
    out = oc.friend_in_group(GROUP, dry_run=False, repo=repo,
                             driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"].startswith("daily_limit_exceeded")


def test_friend_success_records_to_outbound_actions(_friend_live):
    author = "https://www.facebook.com/groups/1930721300516777/user/100088/"
    d = _FriendDriver(author_url=author)
    add_btn = _FakeEl("친구 추가", on_click=d._mark_clicked)
    d._before = [add_btn]
    d._after = [_FakeEl("요청 취소")]
    repo = _FakeRepo()
    out = oc.friend_in_group(GROUP, dry_run=False, repo=repo,
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert len(repo.created) == 1
    rec = repo.created[0]
    assert rec["action_type"] == "friend_request"
    assert rec["result"] == "success"
    assert rec["target_identifier"] == "100088"
    assert rec["target_url"] == author


# ── STEP 3-G: 그룹 목록 → 프로필 페이지 친구추가 (friend_request_canary) ──────

@pytest.fixture
def _friend_live_env(monkeypatch):
    monkeypatch.setenv(oc.FRIEND_LIVE_ENV, "true")
    monkeypatch.setattr("modules.sns.facebook_crawler.load_supplier_blocklist", lambda: [])


class _AriaTextEl:
    """aria-label 과 보이는 텍스트가 다른 요소 (FB 실제 DOM 모사)."""
    def __init__(self, aria, text):
        self._aria = aria
        self.text = text

    def get_attribute(self, k):
        return self._aria if k == "aria-label" else None


def test_is_friend_add_el_matches_visible_text_when_aria_differs():
    # aria-label 은 '친구 요청 보내기', 보이는 텍스트는 '친구 추가'
    assert oc._is_friend_add_el(_AriaTextEl("Jade Lei님에게 친구 요청 보내기", "친구 추가")) is True
    # aria-label 만 매칭돼도 True
    assert oc._is_friend_add_el(_AriaTextEl("친구 추가", "")) is True
    # 이미 보낸 요청 — NEG 우선
    assert oc._is_friend_add_el(_AriaTextEl("보낸 친구 요청 취소", "요청됨")) is False
    # 팔로우 전용 → False
    assert oc._is_friend_add_el(_AriaTextEl("Bob 팔로우", "팔로우")) is False
    # 알림 문장 오탐 차단 — "…님이 친구 요청을 보냈습니다" 는 친구버튼 아님
    assert oc._is_friend_add_el(_AriaTextEl("읽은 상태로 표시, Kim Hong님이 친구 요청을 보냈습니다.", "")) is False


# ── STEP 3-G 프로필 경로 canary ────────────────────────────────────────────

class _MemberAnchor:
    """/members 목록의 회원 프로필 링크 <a> (조상 카드 텍스트도 제공)."""
    def __init__(self, uid, name, card_text=""):
        self._href = f"https://www.facebook.com/groups/1/user/{uid}/"
        self.text = name
        self._ct = card_text or (name + "\nMember")

    def get_attribute(self, k):
        if k == "href":
            return self._href
        if k == "aria-label":
            return self.text
        return None

    def find_element(self, by, xpath):
        return _Body(self._ct)


class _FakeBtn:
    """FB 버튼 1개. aria-label 은 대상 이름을 포함할 수 있고(주 액션 영역),
    ./ancestor::div → 자신이 속한 컨테이너(_FakeContainer).
    visible=False 면 rect 0x0 (DOM 에만 있는 미렌더 노드) — _element_visible 이 걸러야 함."""
    def __init__(self, aria, text=None, on_click=None, visible=True):
        self._aria = aria
        self._text = text if text is not None else aria
        self._label = self._text          # 구 테스트 호환(_label 로 버튼 식별)
        self._on_click = on_click
        self._visible = visible
        self.clicks = 0
        self._container = None

    def get_attribute(self, name):
        return self._aria if name == "aria-label" else None

    @property
    def text(self):
        return self._text

    def click(self):
        self.clicks += 1
        if self._on_click:
            self._on_click()

    def is_displayed(self):
        return self._visible

    @property
    def rect(self):
        return ({"x": 20, "y": 30, "width": 100, "height": 30} if self._visible
                else {"x": 0, "y": 0, "width": 0, "height": 0})

    @property
    def size(self):
        return {"width": 100, "height": 30} if self._visible else {"width": 0, "height": 0}

    def find_elements(self, by, xpath):
        if "ancestor" in xpath:
            return [self._container] if self._container is not None else []
        return []


class _FakeContainer:
    """프로필 주 액션 영역 컨테이너. .//button → 이 안의 버튼."""
    def __init__(self, buttons):
        self._buttons = list(buttons)
        for b in self._buttons:
            b._container = self

    def find_elements(self, by, xpath):
        if "button" in xpath or "role='button'" in xpath:
            return list(self._buttons)
        return []


class _CardMemberBox:
    """회원카드 컨테이너 — 친구버튼의 ./ancestor::div 로 반환. /user/ 링크 + 카드텍스트 제공."""
    def __init__(self, uid, card_text):
        self._uid = uid
        self.text = card_text

    def find_elements(self, by, sel):
        if "/user/" in sel:
            return [_MemberAnchor(self._uid, "", self.text)]
        return []


class _ProfileCanaryDriver:
    """STEP 3-G+S3-FINAL (260903): 목록에서 후보 스캔 → 카드버튼이 화면에 실제 보이면(visible)
    목록에서 native click, 0x0 이면 그 후보 프로필 1회 진입해 프로필 버튼 native click.
    members: [(uid, name, card_text), ...]
    profiles: {uid: 상태}
      - 'add'                    : 클릭하면 '{name}님에 대한 요청 취소' 로 전이(성공)
      - 'add_but_following_after': 클릭 후 '팔로잉' (실패)
      - 'add_no_effect'          : 클릭해도 '친구 추가' 그대로 (실패)
      - 'no_area'                : 클릭 후 대상 이름 든 버튼 없음 → 주 액션 영역 식별 실패
      - 'follow_only'/'pending'/'already_friends' : 목록에 '친구 추가' 버튼 없음(스캔 후보 아님)
    card_visible: {uid: bool} — 카드 '친구 추가' 버튼 렌더 여부 (기본 True). False 면 프로필 fallback.
    sidebars: {uid: [라벨,...]} — 제3자 버튼(이름 불일치). 260902 FP 재현용.
    members_body / profile_body: checkpoint 재현용."""

    _ADDLIKE = ("add", "add_but_following_after", "add_no_effect", "no_area")

    def __init__(self, members, profiles, members_body="Members",
                 profile_names=None, sidebars=None, has_profile_actions=False,
                 profile_texts=None, group_name="", card_visible=None,
                 profile_body="profile page"):
        self._members = members
        self._profiles = profiles
        self._members_body = members_body
        self._profile_body = profile_body
        self.title = f"{group_name} | Facebook" if group_name else ""
        self._profile_names = profile_names or {}
        self._sidebars = sidebars or {}
        self._card_visible = card_visible or {}
        self._clicked_uids = set()
        self._cur_uid = None
        self._on_members = True
        self.current_url = "https://www.facebook.com/"
        self.gets = []
        self.quit_called = False
        self.click_count = 0

    def get(self, url):
        self.gets.append(url)
        self.current_url = url
        m = re.search(r"/user/(\d+)", url)
        self._on_members, self._cur_uid = (False, m.group(1)) if m else (True, None)

    def _name(self, uid):
        return (self._profile_names.get(uid)
                or next((n for (u, n, c) in self._members if u == uid), "Someone"))

    def _mk(self, uid):
        def _c():
            self.click_count += 1
            self._clicked_uids.add(uid)
        return _c

    def _card_btn(self, uid, name, card_text):
        b = _FakeBtn(f"친구 {name}님 추가", "친구 추가", on_click=self._mk(uid),
                     visible=self._card_visible.get(uid, True))
        b._container = _CardMemberBox(uid, card_text)
        return b

    def _profile_add_btn(self, uid):
        return _FakeBtn(f"친구 {self._name(uid)}님 추가", "친구 추가",
                        on_click=self._mk(uid), visible=True)

    def _state_btn(self, uid):
        """클릭 후 / 기존 상태 버튼 (목록·프로필 공통)."""
        nm = self._name(uid)
        st = self._profiles.get(uid, "follow_only")
        if st in ("add", "pending"):
            return _FakeBtn(f"{nm}님에 대한 요청 취소", "요청 취소")
        if st == "add_but_following_after":
            return _FakeBtn(f"{nm}님 팔로잉", "팔로잉")
        if st == "add_no_effect":
            return _FakeBtn(f"친구 {nm}님 추가", "친구 추가")
        if st == "no_area":
            return _FakeBtn("요청 취소", "요청 취소")     # 이름 없음 → 앵커 불가
        if st == "already_friends":
            return _FakeBtn(f"{nm}님 - 친구", "친구")
        return _FakeBtn(f"{nm}님 팔로우", "팔로우")        # follow_only

    def _sidebar_btns(self, uid):
        return [_FakeBtn(f"제3자 Someone Else — {lbl}", lbl)
                for lbl in self._sidebars.get(uid, [])]

    def find_elements(self, by, sel):
        friend_add_q = ("님 추가" in sel or "님추가" in sel or sel.rstrip().endswith("추가')]"))
        if "ProfileActions" in sel:
            return []
        if self._on_members:
            if friend_add_q:
                out = []
                for (uid, name, card_text) in self._members:
                    st = self._profiles.get(uid, "follow_only")
                    if st not in self._ADDLIKE:
                        continue
                    if uid in self._clicked_uids and st != "add_no_effect":
                        continue
                    out.append(self._card_btn(uid, name, card_text))
                return out
            if "role='button'" in sel or "button" in sel:
                res = []
                for uid in self._clicked_uids:      # 목록 native click 후 상태확인용
                    res.append(self._state_btn(uid))
                    res += self._sidebar_btns(uid)
                return res
            return []
        # 프로필 모드
        uid = self._cur_uid
        if friend_add_q or "role='button'" in sel or "button" in sel:
            if uid in self._clicked_uids:
                return [self._state_btn(uid)] + self._sidebar_btns(uid)
            st = self._profiles.get(uid, "follow_only")
            if st in self._ADDLIKE:
                return [self._profile_add_btn(uid)] + self._sidebar_btns(uid)
            return [self._state_btn(uid)] + self._sidebar_btns(uid)
        return []

    def find_element(self, by, sel):
        return _Body(self._members_body if self._on_members else self._profile_body)

    def execute_script(self, script="", *a, **k):
        s = script if isinstance(script, str) else ""
        if "arguments[0].click()" in s and a and hasattr(a[0], "click"):
            a[0].click()
        return None

    def quit(self):
        self.quit_called = True


def test_friend_request_canary_success(_friend_live_env):
    d = _ProfileCanaryDriver(
        members=[("700", "Linh", "Linh\nHo Chi Minh")],
        profiles={"700": "add"})
    repo = _MRepo()
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=repo,
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert d.click_count == 1
    assert d.quit_called is True
    assert d.gets[0].endswith("/members")          # 목록만 연다
    assert not any("/user/700/" in g for g in d.gets)   # STEP 3-G+S3: 프로필 진입 없음
    # STEP 3-G: 개인별 저장 없음 — Outbound_Actions Write 안 함, 로컬 집계만 +1
    assert repo.created == []
    assert out["daily_count"] == 1
    assert oc._friend_daily_count("IDN-000041") == 1


def test_friend_request_canary_skips_explicit_korean(_friend_live_env):
    d = _ProfileCanaryDriver(
        members=[("800", "Kim Minsu", "Kim Minsu\n한국인 · Seoul"),
                 ("801", "Mai", "Mai\nHanoi")],
        profiles={"800": "add", "801": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "801"        # 한국인 명시 → skip
    assert not any("/user/800/" in g for g in d.gets)  # 800 프로필 방문조차 안 함


def test_friend_request_canary_all_hangul_name_skipped(_friend_live_env):
    """260902 STEP 3-G+R: 이름(한글/로마자) 미판정. 820 은 location Evidence 없음 → skip,
    821 은 Taipei(해외) → eligible."""
    d = _ProfileCanaryDriver(
        members=[("820", "이승연", "이승연\n디지털 크리에이터"),
                 ("821", "A-Lin Lin", "A-Lin Lin\nTaipei")],
        profiles={"820": "add", "821": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "821"


def test_friend_request_canary_skips_follow_only_profile_tries_next(_friend_live_env):
    # 프로필에 친구버튼 없고 팔로우만 → 다음 회원으로
    d = _ProfileCanaryDriver(
        members=[("900", "Nina", "Nina\nJakarta"), ("901", "Rose", "Rose\nManila")],
        profiles={"900": "follow_only", "901": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "901"


def test_friend_request_canary_skips_already_pending(_friend_live_env):
    d = _ProfileCanaryDriver(
        members=[("910", "Ken", "Ken\nBangkok"), ("911", "Ann", "Ann\nHanoi")],
        profiles={"910": "pending", "911": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "911"


def test_friend_request_canary_no_friendable_cards(_friend_live_env):
    # 목록 회원 전원 '팔로우'만(창작자/페이지) → 친구 가능 카드 0 → failed
    d = _ProfileCanaryDriver(
        members=[("930", "X", "X\nHanoi"), ("931", "Y", "Y\nManila")],
        profiles={"930": "follow_only", "931": "follow_only"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed"
    assert out["reason"] == "group_exhausted"


def test_friend_request_canary_no_members(_friend_live_env):
    d = _ProfileCanaryDriver(members=[], profiles={})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed"
    assert out["reason"] == "group_exhausted"


def test_friend_request_canary_local_daily_limit_blocks(_friend_live_env):
    # 로컬 집계가 한도에 도달하면 브라우저도 안 켜고 skip (Fail-closed)
    oc._friend_daily_increment("IDN-000041")   # count=1
    repo = _FakeRepo(limits={"follow": 50, "friend": 1, "comment": 0})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=repo,
                                   driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"].startswith("daily_limit:1/1")


def test_friend_request_canary_zero_limit_fail_closed(_friend_live_env):
    repo = _FakeRepo(limits={"follow": 50, "friend": 0, "comment": 0})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=repo,
                                   driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"].startswith("daily_limit:0/0")


# ── STEP 3-G+R (260902): Foreign Eligibility Gate (이름·국적추정 폐기) ──────────
def test_foreign_eligibility_pure():
    # A. 명시적 해외 location → eligible
    assert oc._foreign_eligibility("Mai\nHanoi, Vietnam") == (True, "")
    assert oc._foreign_eligibility("Ann", "Lives in Jakarta, Indonesia") == (True, "")
    # B. 명시적 Korea location → skip
    assert oc._foreign_eligibility("Kim\n서울") == (False, "korea_evidence")
    assert oc._foreign_eligibility("Lee", "Lives in Seoul") == (False, "korea_evidence")
    # C. location/overseas Evidence UNKNOWN → skip (Fail-closed)
    assert oc._foreign_eligibility("Ym Ym Jong Jong\nMember") == (False, "no_overseas_evidence")
    assert oc._foreign_eligibility("", "") == (False, "no_overseas_evidence")
    # D. 로마자 한국식 이름만 있음 → 이름 미사용, overseas Evidence 없음 → skip
    assert oc._foreign_eligibility("Jung Yumi") == (False, "no_overseas_evidence")
    assert oc._foreign_eligibility("Seo Yoon Hyun") == (False, "no_overseas_evidence")
    # Korea + overseas 둘 다 있으면 Fail-closed (korea 우선)
    assert oc._foreign_eligibility("Hanoi", "originally from Seoul") == (False, "korea_evidence")


# ── STEP 3-G+S1 (260902 GPT): Eligibility Source Scope — 그룹명/chrome 오염 제거 ──
class _LocDriver:
    """_profile_location_text 단위 검증용 최소 fake (title + body)."""
    def __init__(self, body, title=""):
        self._body = body
        self.title = title

    def find_element(self, by, sel):
        return _Body(self._body)

    def find_elements(self, by, sel):
        return []


_GROUP = "Korean Cosmetic Wholesale"
_CHROME = "{n}님이 Korean Cosmetic Wholesale에 아직 게시물을 올리지 않았습니다."


def test_stepG_s1_A_overseas_location_despite_group_name():
    # A. group_name = "Korean Cosmetic Wholesale" + target_location 해외 → eligible
    body = f"Nguyen Van A\n{_GROUP}\n{_CHROME.format(n='Nguyen Van A')}\nLives in Ho Chi Minh City, Vietnam"
    loc = oc._profile_location_text(_LocDriver(body), _GROUP)
    assert "korean cosmetic wholesale" not in loc.lower()   # 그룹명 오염 0
    assert oc._foreign_eligibility("", loc) == (True, "")


def test_stepG_s1_B_no_personal_location_is_skip():
    # B. group_name 있음 + 개인 location 없음 → no_overseas_evidence
    body = f"Nguyen Van A\n{_GROUP}\n{_CHROME.format(n='Nguyen Van A')}"
    loc = oc._profile_location_text(_LocDriver(body), _GROUP)
    assert loc == ""
    assert oc._foreign_eligibility("", loc) == (False, "no_overseas_evidence")


def test_stepG_s1_C_explicit_korea_location_is_skip():
    # C. 개인 location 이 Seoul → korea_evidence (그룹명과 무관하게 개인정보로 판정)
    body = f"Kim\n{_GROUP}\nLives in Seoul, South Korea"
    loc = oc._profile_location_text(_LocDriver(body), _GROUP)
    assert oc._foreign_eligibility("", loc) == (False, "korea_evidence")


def test_stepG_s1_D_romanized_korean_name_not_used():
    # D. 로마자 한국식/베트남식 이름만 있고 location 없음 → 이름 미사용, skip
    body = f"Nguyen Vu Nam\n{_GROUP}\n디지털 크리에이터"
    loc = oc._profile_location_text(_LocDriver(body), _GROUP)
    assert loc == ""
    assert oc._foreign_eligibility("Nguyen Vu Nam", loc) == (False, "no_overseas_evidence")


def test_stepG_s1_E_group_name_only_body_is_not_korea():
    # E. profile body 에 그룹명만 존재 → Korea 판정 금지, no_overseas_evidence
    for body in (_GROUP, f"{_GROUP}\n{_CHROME.format(n='Someone')}"):
        loc = oc._profile_location_text(_LocDriver(body), _GROUP)
        assert loc == "", body
        assert oc._foreign_eligibility("", loc) == (False, "no_overseas_evidence")


def test_stepG_s1_strip_group_chrome_keeps_personal_bio():
    txt = f"{_GROUP}\n{_CHROME.format(n='Mai')}\nBeauty reseller since 2019\nLives in Jakarta"
    kept = oc._strip_group_chrome(txt, _GROUP)
    assert "Korean Cosmetic Wholesale" not in kept
    assert "아직 게시물" not in kept
    assert "Beauty reseller since 2019" in kept and "Lives in Jakarta" in kept


def test_stepG_s1_group_name_from_page_title():
    assert oc._group_name_from_page(_LocDriver("", title="Korean Cosmetic Wholesale | Facebook")) == _GROUP
    # FB 미읽음 알림 수 프리픽스 '(3) ' 제거 (라이브 probe 16:54 에서 발견)
    assert oc._group_name_from_page(_LocDriver("", title="(3) Korean Cosmetic Wholesale | Facebook")) == _GROUP
    assert oc._group_name_from_page(_LocDriver("", title="(12+) Korean Cosmetic Wholesale | Facebook")) == _GROUP
    assert oc._group_name_from_page(_LocDriver("", title="")) == ""


def test_stepG_s1_notif_prefix_group_name_still_stripped():
    # 라이브 probe 재현: title 이 '(3) Korean Cosmetic Wholesale | Facebook' 여도
    # body 의 'Korean Cosmetic Wholesale' 줄이 제거돼야 한다.
    d = _LocDriver("소개\ninfluencer\nKorean Cosmetic Wholesale\n가입", title="(3) Korean Cosmetic Wholesale | Facebook")
    gname = oc._group_name_from_page(d)
    loc = oc._profile_location_text(d, gname)
    assert "korean cosmetic wholesale" not in loc.lower()
    assert oc._foreign_eligibility("", loc) == (False, "no_overseas_evidence")


def test_friend_request_canary_seoul_only_skipped_260902(_friend_live_env):
    # 카드에 "Seoul" = 한국 Evidence → skip. 811 은 비한국 → 친구후보.
    d = _ProfileCanaryDriver(
        members=[("810", "Theshy Jj", "Theshy Jj\nSeoul"),
                 ("811", "Ct Cossmetic YU", "Ct Cossmetic YU\n호찌민 시")],
        profiles={"810": "add", "811": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "811"


def test_friend_request_canary_s3_skips_korean_candidates(_friend_live_env):
    """S3: 한글이름 / 로마자 한국성씨 → skip. 그 외(사는곳 없어도) → 친구후보."""
    d = _ProfileCanaryDriver(
        members=[("812", "박보미", "박보미\n60포인트"),                     # 한글 → skip
                 ("813", "Jung Yumi", "Jung Yumi\n디지털 크리에이터"),        # 'jung' 성씨 → skip
                 ("814", "Hnin Thu Zar", "Hnin Thu Zar\n20시간 전에 가입함")],  # 미얀마 → 후보
        profiles={"812": "add", "813": "add", "814": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "814"
    assert d.click_count == 1


def test_friend_request_canary_card_without_location_still_friendable(_friend_live_env):
    """S3: 카드에 사는곳 정보가 없어도 한국인/공장이 아니면 친구후보 (whitelist 폐기)."""
    d = _ProfileCanaryDriver(
        members=[("815", "Noi", "Noi\n1개월 전에 가입함")],
        profiles={"815": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert out["target_identifier"] == "815"


def test_friend_request_canary_following_only_is_not_success(_friend_live_env):
    """클릭 후 '팔로잉' 만 뜨고 '요청 취소' 없으면 실패 — daily 집계 안 함 (260902 False Positive 재발방지)."""
    d = _ProfileCanaryDriver(members=[("977", "Ray Priya", "Ray Priya\nHo Chi Minh")],
                             profiles={"977": "add_but_following_after"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed", out
    assert out["reason"] == "friend_request_failed_following_only"
    assert out["daily_count"] == 0
    assert oc._friend_daily_count("IDN-000041") == 0


def test_friend_request_canary_success_requires_cancel_request(_friend_live_env):
    """성공은 '요청 취소' 확인 시에만. (버튼 소멸/pending 추정 아님)"""
    d = _ProfileCanaryDriver(members=[("978", "Mai", "Mai\nHanoi")], profiles={"978": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert out["daily_count"] == 1


# ── STEP 3-G+ (260902): Target-Scoped Success Verification ────────────────────
# 원인: 전역 스캔이 프로필의 "알 수도 있는 사람" 카드에 있는 제3자의 "요청 취소"를
# 대상 본인 것으로 오인 → False Positive (Ym Ym Jong Jong 실제 발생).
# 수정: 프로필 이름 <h1> 과 같은 주 액션 영역 안의 버튼만 보고 판정.

def test_targetscoped_A_primary_following_plus_sidebar_cancel_is_false(_friend_live_env):
    """A. 대상 주버튼='팔로잉' + sidebar 제3자='요청 취소' → 절대 SUCCESS 아님.
    (실제 Ym Ym Jong Jong(100093793984688)은 _FRIEND_CANARY_SKIP_IDS 에 등재됨 — 여기선 로직만 검증)."""
    uid = "221"
    d = _ProfileCanaryDriver(
        members=[(uid, "Dara", "Dara\nPhnom Penh, Cambodia")],
        profiles={uid: "add_but_following_after"},
        sidebars={uid: ["요청 취소", "삭제", "친구 추가"]})   # 알 수도 있는 사람 카드
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed", out
    assert out["reason"] == "friend_request_failed_following_only"
    assert out["daily_count"] == 0
    assert oc._friend_daily_count("IDN-000041") == 0


def test_targetscoped_B_primary_cancel_is_true_regardless_of_sidebar(_friend_live_env):
    """B. 대상 주버튼='요청 취소' → sidebar 상태 무관하게 SUCCESS."""
    d = _ProfileCanaryDriver(
        members=[("222", "Mai", "Mai\nHanoi")],
        profiles={"222": "add"},
        sidebars={"222": ["친구 추가", "팔로잉", "삭제"]})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert out["daily_count"] == 1


def test_targetscoped_C_primary_still_add_is_false(_friend_live_env):
    """C. 클릭해도 대상 주버튼이 '친구 추가' 그대로 → SUCCESS 아님, count 증가 없음."""
    d = _ProfileCanaryDriver(
        members=[("223", "Lan", "Lan\nBangkok")],
        profiles={"223": "add_no_effect"},
        sidebars={"223": ["요청 취소"]})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed", out
    assert out["reason"] == "click_had_no_effect_still_add"
    assert oc._friend_daily_count("IDN-000041") == 0


def test_targetscoped_D_no_action_area_is_failed_no_count(_friend_live_env):
    """D. 대상 주 액션 영역(대상 이름이 든 버튼) 식별 실패 → FAILED, count 증가 금지."""
    d = _ProfileCanaryDriver(
        members=[("224", "Rani", "Rani\nDelhi")],
        profiles={"224": "no_area"},
        sidebars={"224": ["요청 취소"]})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed", out
    assert out["reason"] == "target_action_area_unresolved"
    assert oc._friend_daily_count("IDN-000041") == 0


def test_daily_sent_count_not_reduced_by_cancel():
    """E. 발송 후 취소해도 sent_today(=daily count)는 줄지 않는다 (플랫폼 Action Budget).
    취소는 코드 밖(회장 수동)이며 감소 API 자체가 없다."""
    assert oc._friend_daily_increment("IDN-000041") == 1
    assert oc._friend_daily_increment("IDN-000041") == 2
    assert not hasattr(oc, "_friend_daily_decrement")
    oc._friend_daily_mark_blocked("IDN-000041", "checkpoint:x")   # 차단해도
    assert oc._friend_daily_count("IDN-000041") == 2               # 카운트 보존


def test_area_friend_state_pure():
    assert oc._area_friend_state(["요청 취소", "메시지"]) == "cancel"
    assert oc._area_friend_state(["팔로잉", "메시지"]) == "following"
    assert oc._area_friend_state(["친구 추가", "메시지"]) == "add"
    assert oc._area_friend_state(["친구", "메시지"]) == "friends"
    assert oc._area_friend_state(["메시지"]) == "unknown"
    assert oc._area_friend_state([]) == "unknown"
    assert oc._area_friend_state(["요청 취소", "팔로잉"]) == "cancel"   # cancel 우선


def test_classify_action_label_pure():
    assert oc._classify_action_label("친구 요청 취소") == "cancel"
    assert oc._classify_action_label("Cancel Request") == "cancel"
    assert oc._classify_action_label("친구 추가") == "add"
    assert oc._classify_action_label("팔로잉") == "following"
    assert oc._classify_action_label("친구") == "friends"
    assert oc._classify_action_label("메시지") == ""
    assert oc._classify_action_label("") == ""


def test_friend_request_canary_batch_sends_up_to_max(_friend_live_env):
    """max_requests>1 이면 한 세션에서 여러 해외 회원에게 연속 발송."""
    d = _ProfileCanaryDriver(
        members=[("301", "Mai", "Mai\nHanoi"), ("302", "Lan", "Lan\nBangkok"),
                 ("303", "Rani", "Rani\nDelhi"), ("304", "Sara", "Sara\nBali")],
        profiles={"301": "add", "302": "add", "303": "add", "304": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   max_requests=3, pace_range=(0, 0),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert out["sent"] == 3
    assert out["daily_count"] == 3
    ok = [r["identifier"] for r in out["results"] if r["result"] == "success"]
    assert ok == ["301", "302", "303"]   # 304 는 목표 3건 도달로 미실행


def test_friend_request_canary_batch_stops_at_daily_limit(_friend_live_env):
    """max_requests 가 커도 daily_friend_limit 에서 멈춘다."""
    oc._friend_daily_increment("IDN-000041")
    oc._friend_daily_increment("IDN-000041")   # 오늘 이미 2건
    repo = _FakeRepo(limits={"follow": 50, "friend": 3, "comment": 0})
    d = _ProfileCanaryDriver(
        members=[("311", "Mai", "Mai\nHanoi"), ("312", "Lan", "Lan\nBangkok"),
                 ("313", "Rani", "Rani\nDelhi")],
        profiles={"311": "add", "312": "add", "313": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=repo,
                                   max_requests=10, pace_range=(0, 0),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["sent"] == 1            # 2 + 1 = 3 = 한도
    assert out["daily_count"] == 3


def test_friend_request_canary_general_failure_skips_and_continues(_friend_live_env):
    """Human SOP §6: 일반 버튼 오류는 그 대상만 skip 하고 **다음 사람 계속** (전체 STOP 아님)."""
    d = _ProfileCanaryDriver(
        members=[("321", "Bad", "Bad\nManila"), ("322", "Good", "Good\nHanoi")],
        profiles={"321": "add_but_following_after", "322": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   max_requests=5, pace_range=(0, 0),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert out["sent"] == 1
    assert [r["identifier"] for r in out["results"] if r["result"] == "success"] == ["322"]
    assert any(r["identifier"] == "321" and r["result"] == "failed" for r in out["results"])


def test_verify_friend_add_button():
    class _E:
        def __init__(self, a, t): self._a, self.text = a, t
        def get_attribute(self, k): return self._a if k == "aria-label" else None
    assert oc._verify_friend_add_button(_E("친구 Ray Priya님 추가", "친구 추가"))[0] is True
    assert oc._verify_friend_add_button(_E("", "친구 추가"))[0] is True
    assert oc._verify_friend_add_button(_E("Add friend", ""))[0] is True
    assert oc._verify_friend_add_button(_E("메시지 보내기", "메시지"))[0] is False
    assert oc._verify_friend_add_button(_E("팔로우", "팔로우"))[0] is False
    assert oc._verify_friend_add_button(_E("보낸 친구 요청 취소", "요청됨"))[0] is False


def test_friend_request_canary_skips_korean_profile_name(_friend_live_env):
    """260902 STEP 3-G+R: 990 카드에 'Seoul' = 한국 Evidence → skip. 991 = Ho Chi Minh → eligible.
    (이름 '정유미'는 판정에 쓰지 않는다 — location Evidence Gate 만.)"""
    d = _ProfileCanaryDriver(
        members=[("990", "Yumi Jung", "Yumi Jung\nSeoul area"),
                 ("991", "Linh", "Linh\nHo Chi Minh")],
        profiles={"990": "add", "991": "add"},
        profile_names={"990": "정유미"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "991"


def test_profile_name_from_btn():
    class _E:
        def __init__(self, a): self._a = a
        def get_attribute(self, k): return self._a if k == "aria-label" else None
    assert oc._profile_name_from_btn(_E("친구 정유미님 추가")) == "정유미"
    assert oc._profile_name_from_btn(_E("친구 Ray Priya님 추가")) == "Ray Priya"
    assert oc._profile_name_from_btn(_E("친구 추가")) == ""


def test_friend_request_canary_skips_excluded_id(_friend_live_env):
    """제외 대상(Ray Priya id)은 프로필 방문조차 안 하고 다음 회원으로."""
    d = _ProfileCanaryDriver(
        members=[("100095223146372", "Ray Priya", "Ray Priya\nHo Chi Minh"),
                 ("981", "Lan", "Lan\nHanoi")],
        profiles={"100095223146372": "add", "981": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "981"
    assert not any("/user/100095223146372/" in g for g in d.gets)


def test_friend_request_canary_skips_ym_ym_jong_jong(_friend_live_env):
    """260902: Ym Ym Jong Jong(로마자 한국 이름, 회장이 직접 요청 취소) 프로필 방문 안 함."""
    d = _ProfileCanaryDriver(
        members=[("100093793984688", "Ym Ym Jong Jong", "Ym Ym Jong Jong\nMember"),
                 ("982", "Noi", "Noi\nBangkok")],
        profiles={"100093793984688": "add", "982": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "982"
    assert not any("/user/100093793984688/" in g for g in d.gets)


def test_friend_request_canary_click_exception_no_count(_friend_live_env):
    """S3-FINAL: native click 이 예외면 failed + count 0, 재시도 없음."""
    from selenium.common.exceptions import ElementClickInterceptedException

    d = _ProfileCanaryDriver(members=[("950", "Mei", "Mei\nTaipei")],
                             profiles={"950": "add"})
    orig_find = d.find_elements

    def _patched(by, sel):
        els = orig_find(by, sel)
        for e in els:
            if getattr(e, "_label", "") == "친구 추가":
                def _boom():
                    raise ElementClickInterceptedException("element click intercepted")
                e._on_click = _boom
        return els
    d.find_elements = _patched

    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed"
    assert out["reason"] == "click_exc:ElementClickInterceptedException"
    assert out["daily_count"] == 0
    assert oc._friend_daily_count("IDN-000041") == 0


def test_friend_request_canary_checkpoint(_friend_live_env):
    d = _ProfileCanaryDriver(members=[("1", "A", "A\nHanoi")], profiles={"1": "add"},
                             members_body="please complete this security check")
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"].startswith("checkpoint:")


# ── STEP 3-G+ (260902): 제한 신호 → 그날 남은 실행 Fail-closed ────────────────
def test_checkpoint_marks_day_blocked(_friend_live_env):
    d = _ProfileCanaryDriver(members=[("1", "A", "A\nHanoi")], profiles={"1": "add"},
                             members_body="please complete this security check")
    oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    # 검증 1(정상)→검증 2(제한 후): 같은 날 재실행은 실제 요청 함수(브라우저) 미호출
    blocked = oc._friend_daily_blocked("IDN-000041")
    assert blocked.startswith("checkpoint:")
    out2 = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                    driver_factory=_boom, browser_stopper=lambda: None)
    assert out2["result"] == "skipped"
    assert out2["reason"].startswith("daily_blocked:checkpoint:")


def test_day_block_preserves_prior_count(_friend_live_env):
    # 그날 1건 보낸 뒤 checkpoint → count 는 1 유지, blocked 만 추가
    d1 = _ProfileCanaryDriver(members=[("700", "Linh", "Linh\nHo Chi Minh")],
                              profiles={"700": "add"})
    oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                             driver_factory=lambda: d1, browser_stopper=lambda: None)
    assert oc._friend_daily_count("IDN-000041") == 1
    d2 = _ProfileCanaryDriver(members=[("701", "Mai", "Mai\nHanoi")], profiles={"701": "add"},
                              members_body="your account has been temporarily blocked")
    oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                             driver_factory=lambda: d2, browser_stopper=lambda: None)
    assert oc._friend_daily_count("IDN-000041") == 1          # 유실 안 됨
    assert oc._friend_daily_blocked("IDN-000041")


def test_day_block_auto_clears_next_day(_friend_live_env, monkeypatch):
    # 검증 3: 어제 날짜로 차단 기록이 있어도 오늘은 정상 운영
    import json as _json
    oc._FRIEND_DAILY_PATH.write_text(
        _json.dumps({"IDN-000041": {"date": "2000-01-01", "count": 5,
                                    "blocked": True, "blocked_reason": "checkpoint:x"}}),
        encoding="utf-8")
    assert oc._friend_daily_blocked("IDN-000041") == ""
    assert oc._friend_daily_count("IDN-000041") == 0
    d = _ProfileCanaryDriver(members=[("710", "Rin", "Rin\nHanoi")],
                             profiles={"710": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"


def test_friend_request_canary_kill_switch_off():
    repo = _FakeRepo(automation_enabled=False)
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=repo,
                                   driver_factory=_boom, browser_stopper=lambda: None)
    assert out["result"] == "skipped" and out["reason"] == "automation_disabled"


def test_friend_request_canary_dry_run():
    out = oc.friend_request_canary(GROUP, repo=_FakeRepo(), driver_factory=_boom)
    assert out["result"] == "skipped" and out["reason"] == "dry_run"


def test_group_members_url():
    assert oc.group_members_url("https://www.facebook.com/groups/123") == \
        "https://www.facebook.com/groups/123/members"
    assert oc.group_members_url("https://www.facebook.com/groups/123/?ref=x") == \
        "https://www.facebook.com/groups/123/members"


def test_group_members_url_keeps_ground_truth_subview():
    # 260902 Ground Truth Canary — 이미 /members(/things_in_common 등) 형태로 온 URL 은
    # "/members" 를 중복으로 덧붙이지 않는다.
    url = "https://www.facebook.com/groups/755455243345993/members/things_in_common"
    assert oc.group_members_url(url) == url
    assert oc.group_members_url(url + "/") == url


def test_find_group_members_extracts_and_dedups():
    class _Box:
        def __init__(self, t): self.text = t

    class _ML:
        def __init__(self, href, name):
            self._href, self.text = href, name
        def get_attribute(self, k):
            return self._href if k == "href" else (self.text if k == "aria-label" else None)
        def find_element(self, by, xpath):
            return _Box(self.text + "\nKorean cosmetics wholesale")

    class _D:
        def __init__(self, links):
            self._links = links
        def find_elements(self, by, sel):
            return self._links if "/user/" in sel else []
        def find_element(self, by, sel):
            return _Box("Members")
        def execute_script(self, *a, **k):
            return None

    g = "https://www.facebook.com/groups/610113703703488/user/"
    links = [_ML(g + "500/", "A"), _ML(g + "500/", "A dup"), _ML(g + "501/", "B"),
             _ML("https://www.facebook.com/groups/9/posts/1", "not a member")]
    out = oc._find_group_members(_D(links), limit=15)
    assert [m["identifier"] for m in out] == ["500", "501"]
    assert out[0]["profile_url"].endswith("/user/500/")
    assert "wholesale" in out[0]["card_text"].lower()


class _MembersFriendDriver:
    """target_source='members' 통합 시나리오용.
    /members 에서는 회원링크, 프로필에서는 h1/body/친구버튼을 돌려준다."""
    def __init__(self, member_hrefs, profile_h1="Anna", profile_body="Anna\nVietnam\ncosmetics",
                 friend_button=True, after_click_pending=True):
        self._members = member_hrefs
        self._h1 = profile_h1
        self._body = profile_body
        self._fb = friend_button
        self._after_pending = after_click_pending
        self._on_profile = False
        self._clicked = False
        self.gets = []
        self.current_url = "https://www.facebook.com/"
        self.quit_called = False

    def get(self, url):
        self.gets.append(url)
        self.current_url = url
        if "/members" in url:
            self._on_members = True
            self._on_profile = False
        elif getattr(self, "_on_members", False):
            self._on_profile = True

    def find_elements(self, by, sel):
        if "/user/" in sel and not self._on_profile:
            return [_Anchor(h, "Member") for h in self._members]
        if "button" in sel or "role='button'" in sel:
            if not self._on_profile:
                return []
            if self._clicked:
                return [_FakeEl("요청 취소")] if self._after_pending else [_FakeEl("메시지")]
            return [_FakeEl("친구 추가", on_click=self._mark), _FakeEl("메시지")] if self._fb else [_FakeEl("메시지")]
        return []

    def find_element(self, by, sel):
        if "h1" in sel:
            if not self._h1:
                raise Exception("no h1")
            return _Body(self._h1)
        return _Body(self._body)

    def _mark(self):
        self._clicked = True

    def execute_script(self, *a, **k):
        return None

    def quit(self):
        self.quit_called = True


class _MRepo(_FakeRepo):
    def find_prospect_by_target(self, ident, action_type):
        return None

    def find_outbound_action(self, account_code_ref, target_identifier, action_type):
        return None


def test_pick_first_eligible_member(monkeypatch):
    monkeypatch.setattr("modules.sns.facebook_crawler.load_supplier_blocklist", lambda: [])
    monkeypatch.setattr(oc.time, "sleep", lambda *a, **k: None)
    d = _MembersFriendDriver(
        ["https://www.facebook.com/groups/1/user/5001/",
         "https://www.facebook.com/groups/1/user/5002/"])
    url = oc._pick_first_eligible_member(d, _MRepo(), "IDN-000041")
    assert url == "https://www.facebook.com/groups/1/user/5001/"


def test_friend_in_group_members_source_e2e(_friend_live, monkeypatch):
    monkeypatch.setattr("modules.sns.facebook_crawler.load_supplier_blocklist", lambda: [])
    d = _MembersFriendDriver(
        ["https://www.facebook.com/groups/1/user/7777/"],
        profile_h1="Anna Shop", profile_body="Anna Shop\nLives in Hanoi, Vietnam\nKorean cosmetics wholesale")
    repo = _MRepo()
    out = oc.friend_in_group(GROUP, dry_run=False, target_source="members", repo=repo,
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert out["target_url"] == "https://www.facebook.com/groups/1/user/7777/"
    assert d.quit_called is True
    assert len(repo.created) == 1
    assert repo.created[0]["action_type"] == "friend_request"


def test_friend_in_group_members_korean_excluded(_friend_live, monkeypatch):
    monkeypatch.setattr("modules.sns.facebook_crawler.load_supplier_blocklist", lambda: [])
    d = _MembersFriendDriver(
        ["https://www.facebook.com/groups/1/user/8888/"],
        profile_h1="박지민", profile_body="박지민\n서울특별시 거주\n일상")
    repo = _MRepo()
    out = oc.friend_in_group(GROUP, dry_run=False, target_source="members", repo=repo,
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "skipped"
    assert out["reason"].startswith("korean_excluded")
    assert repo.created == []


def test_friend_in_group_members_no_candidate(_friend_live, monkeypatch):
    monkeypatch.setattr("modules.sns.facebook_crawler.load_supplier_blocklist", lambda: [])
    d = _MembersFriendDriver([])  # 회원 0
    out = oc.friend_in_group(GROUP, dry_run=False, target_source="members", repo=_MRepo(),
                             driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed"
    assert out["reason"] == "no_eligible_member"


def test_friend_dedup_second_call(_friend_live):
    author = "https://www.facebook.com/groups/1930721300516777/user/55/"
    d1 = _FriendDriver(author_url=author)
    b1 = _FakeEl("친구 추가", on_click=d1._mark_clicked)
    d1._before = [b1]
    d1._after = [_FakeEl("요청됨")]
    first = oc.friend_in_group(GROUP, dry_run=False, repo=_FakeRepo(),
                               driver_factory=lambda: d1, browser_stopper=lambda: None)
    assert first["result"] == "success"

    d2 = _FriendDriver(author_url=author)
    d2._before = [_FakeEl("친구 추가")]
    second = oc.friend_in_group(GROUP, dry_run=False, repo=_FakeRepo(),
                                driver_factory=lambda: d2, browser_stopper=lambda: None)
    assert second["result"] == "skipped"
    assert second["reason"] == "duplicate_local"


# ── STEP 3-G+S3 (260903): 목록 카드 판정 (_should_skip_target) + 카드 스캔 ──────
def test_should_skip_target_pure():
    S = oc._should_skip_target
    # 한국인 → skip
    assert S("박보미", "박보미\n60포인트") == (True, "hangul_name")
    assert S("Jung Yumi", "Jung Yumi\nBeauty") == (True, "korean_surname")
    assert S("Bomi Park", "") == (True, "korean_surname")            # 끝 토큰 'park'
    assert S("Anna", "Anna\nSeoul, South Korea") == (True, "korea_location")
    assert S("Trang", "Trang\nHotline +82 10 1234 5678") == (True, "kr_phone")
    # 중국공장 → skip
    assert S("Starplex Gaby", "Starplex Gaby\nGuangzhou Cosmetics Factory")[0] is True
    assert S("Gaby", "Shenzhen OEM/ODM manufacturer")[1] == "mfg_factory"
    # 그 외(사는곳 없어도) → 친구후보
    assert S("Hnin Thu Zar", "Hnin Thu Zar\n20시간 전에 가입함") == (False, "")
    assert S("Nguyen Van A", "Hanoi wholesale, ship worldwide") == (False, "")
    # bio 에 'Korean'(형용사)만 있는 해외 도매상 → 걸리지 않는다
    assert S("Linlin", "I sell Korean cosmetics wholesale")[0] is False


def test_has_hangul_pure():
    assert oc._has_hangul("박보미") is True
    assert oc._has_hangul("Kim") is False
    assert oc._has_hangul("Anna 안나") is True
    assert oc._has_hangul("") is False


def test_scan_member_cards_extracts_name_uid_skips_follow_only():
    class _Anc:
        def __init__(self, uid, text):
            self._uid, self.text = uid, text
        def find_elements(self, by, sel):
            return [_MemberAnchor(self._uid, "", self.text)] if "/user/" in sel else []

    class _B:
        def __init__(self, aria, text, anc):
            self._aria, self._text, self._anc = aria, text, anc
        def get_attribute(self, k):
            return self._aria if k == "aria-label" else None
        @property
        def text(self):
            return self._text
        def find_elements(self, by, xpath):
            return [self._anc] if "ancestor" in xpath else []

    class _D:
        def __init__(self, btns):
            self._btns = btns
        def find_elements(self, by, sel):
            return self._btns if ("님 추가" in sel or sel.rstrip().endswith("추가')]")) else []
        def execute_script(self, *a, **k):
            return None

    btns = [
        _B("친구 박보미님 추가", "친구 추가", _Anc("111", "박보미 | 60포인트")),
        _B("친구 Hnin Thu Zar님 추가", "친구 추가", _Anc("222", "Hnin Thu Zar | 20시간 전")),
        _B("Ho Sung Jung 팔로우", "팔로우", _Anc("333", "Ho Sung Jung")),   # 팔로우 → 무시
    ]
    out = oc._scan_member_cards(_D(btns), limit=10)
    assert [(c["identifier"], c["name"]) for c in out] == [("111", "박보미"), ("222", "Hnin Thu Zar")]
    assert "60포인트" in out[0]["card_text"]


def test_friend_canary_s3_skips_factory_friends_wholesaler(_friend_live_env):
    """S3 통합: 중국공장 skip, 해외 도매상 친구요청."""
    d = _ProfileCanaryDriver(
        members=[("901", "Starplex Gaby", "Starplex Gaby\nGuangzhou Cosmetics Factory"),
                 ("902", "Mai Anh", "Mai Anh\nHanoi beauty shop, wholesale")],
        profiles={"901": "add", "902": "add"})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "902"
    assert d.click_count == 1


# ── STEP 3-G+S3-FINAL (260903): visible 카드 native click / 0x0 → 프로필 fallback ──
def test_element_visible_pure():
    class _E:
        def __init__(self, disp, w, h):
            self._d, self._w, self._h = disp, w, h
        def is_displayed(self):
            return self._d
        @property
        def rect(self):
            return {"x": 0, "y": 0, "width": self._w, "height": self._h}
    assert oc._element_visible(_E(True, 100, 30)) is True
    assert oc._element_visible(_E(True, 0, 0)) is False       # rect 0x0 → 미렌더
    assert oc._element_visible(_E(False, 100, 30)) is False    # is_displayed False
    assert oc._element_visible(None) is False


def test_s3final_A_visible_card_button_native_click(_friend_live_env):
    """A. 카드 버튼이 visible → 목록에서 native click, 프로필 진입 안 함."""
    d = _ProfileCanaryDriver(
        members=[("410", "Mai Anh", "Mai Anh\nHanoi")],
        profiles={"410": "add"}, card_visible={"410": True})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out
    assert out["target_identifier"] == "410"
    assert out["daily_count"] == 1
    assert d.click_count == 1
    assert not any("/user/410/" in g for g in d.gets)     # 프로필 진입 없음


def test_s3final_B_zero_rect_card_falls_back_to_profile(_friend_live_env):
    """B. 카드 버튼 0x0(미렌더) → 그 후보 프로필 1회 진입 → 프로필 버튼 click."""
    d = _ProfileCanaryDriver(
        members=[("411", "Zouache Fatiha", "Zouache Fatiha\n1개월 전 가입")],
        profiles={"411": "add"}, card_visible={"411": False})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success", out           # C. 프로필 requested → success
    assert out["target_identifier"] == "411"
    assert out["daily_count"] == 1
    assert any("/user/411/" in g for g in d.gets)     # 프로필 1회 진입함


def test_s3final_B_profile_still_add_is_failed_no_count(_friend_live_env):
    """C(반대). 프로필에서도 클릭 후 '친구 추가' 그대로면 failed + count 0 + STOP."""
    d = _ProfileCanaryDriver(
        members=[("412", "Rin", "Rin\nBangkok")],
        profiles={"412": "add_no_effect"}, card_visible={"412": False})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "failed"
    assert out["reason"] == "click_had_no_effect_still_add"
    assert out["daily_count"] == 0
    assert oc._friend_daily_count("IDN-000041") == 0


def test_s3final_D_korean_skipped_before_profile(_friend_live_env):
    """D. 한국인/중국공장 → 프로필 진입 전 skip (카드가 0x0 이어도 프로필 안 감)."""
    d = _ProfileCanaryDriver(
        members=[("413", "박보미", "박보미\n60포인트"),
                 ("414", "Guangzhou XY", "Guangzhou XY Cosmetics Factory"),
                 ("415", "Nadia", "Nadia\nCairo")],
        profiles={"413": "add", "414": "add", "415": "add"},
        card_visible={"413": False, "414": False, "415": False})
    out = oc.friend_request_canary(GROUP, dry_run=False, repo=_MRepo(),
                                   driver_factory=lambda: d, browser_stopper=lambda: None)
    assert out["result"] == "success"
    assert out["target_identifier"] == "415"                       # Nadia 만 후보
    assert not any("/user/413/" in g for g in d.gets)              # 박보미 프로필 안 감
    assert not any("/user/414/" in g for g in d.gets)              # 공장 프로필 안 감
    assert any("/user/415/" in g for g in d.gets)
