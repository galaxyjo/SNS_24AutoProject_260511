"""260915 — facebook_crawler.run() 점진 수집(FB_PROGRESSIVE_CRAWL_ENABLED) 검증.

배경: 운영 크롤 페이지가 visibilityState=hidden 이라 Facebook 이 첫 게시물 1개만 채웠다.
A/B 실측에서 CDP 포커스 흉내만으로 실제 게시물 1개 → 32개가 됐다.

실제 브라우저·AdsPower·Airtable·OCR·네트워크·운영 로그 기록 없음:
가짜 드라이버 + 게시물 처리 의존성 전부 Mock + crawl_monitor 가짜 모듈 + 기록용 로거.
"""

import sys
from types import SimpleNamespace

import pytest

import modules.sns.facebook_crawler as fc

URL = "https://www.facebook.com/groups/1827528710833477"
EMPTY = ""


# ── 가짜 드라이버 ─────────────────────────────────────────────────────────────
class FakeArticle:
    def __init__(self, text):
        self.text = text


class FakeFeed:
    def __init__(self, driver):
        self.driver = driver

    def find_elements(self, by, value):
        return list(self.driver.batches[self.driver.batch_idx])


class FakeDriver:
    """scrollHeight 로 바닥까지 스크롤할 때마다 다음 배치(article 목록)를 보여준다."""

    def __init__(self, batches, cdp_fail=False):
        self.batches = [[FakeArticle(t) for t in b] for b in batches]
        self.batch_idx = 0
        self.calls = []
        self.cdp_fail = cdp_fail

    def execute_cdp_cmd(self, cmd, params):
        self.calls.append(("cdp", cmd, params))
        if self.cdp_fail:
            raise RuntimeError("cdp unavailable")

    def get(self, url):
        self.calls.append(("get", url))

    def execute_script(self, script, *args):
        self.calls.append(("script", script))
        if "document.documentElement.scrollHeight" in script:
            self.batch_idx = min(self.batch_idx + 1, len(self.batches) - 1)

    def find_element(self, by, value):
        return FakeFeed(self)

    def quit(self):
        self.calls.append(("quit",))

    def bottom_scrolls(self):
        return sum(1 for c in self.calls if c[0] == "script" and "scrollHeight" in c[1])


class RecLogger:
    def __init__(self):
        self.records = []

    def _add(self, level, msg):
        self.records.append((level, str(msg)))

    def info(self, msg, *a, **k): self._add("info", msg)
    def warning(self, msg, *a, **k): self._add("warning", msg)
    def error(self, msg, *a, **k): self._add("error", msg)
    def debug(self, msg, *a, **k): self._add("debug", msg)

    def has(self, level, needle):
        return any(l == level and needle in m for l, m in self.records)


# ── 공통 환경 ─────────────────────────────────────────────────────────────────
@pytest.fixture
def env(monkeypatch):
    """run() 의 외부 의존성을 전부 가짜로 바꾸고, 저장 호출(원문 텍스트)을 기록한다."""
    state = SimpleNamespace(saved=[], driver=None, log=RecLogger())

    for name in ("FB_PROGRESSIVE_CRAWL_ENABLED", "FB_PROGRESSIVE_MAX_POSTS",
                 "FB_PROGRESSIVE_MAX_ROUNDS", "FB_PROGRESSIVE_BUDGET_SEC",
                 "FB_FOCUS_EMULATION_ENABLED"):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setattr(fc, "logger", state.log)
    monkeypatch.setattr(fc, "_stage_log", lambda *a, **k: None)
    monkeypatch.setattr(fc, "_validate_publish_context", lambda *a, **k: None)
    monkeypatch.setattr(fc, "load_supplier_blocklist", lambda: [])
    monkeypatch.setattr(fc, "is_blocked_supplier", lambda *a, **k: None)
    monkeypatch.setattr(fc, "get_driver", lambda *a, **k: state.driver)
    monkeypatch.setattr(fc, "stop_browser", lambda *a, **k: None)
    monkeypatch.setattr(fc, "extract_image_url", lambda *a, **k: "https://scontent.example/x.jpg")
    monkeypatch.setattr(fc, "expand_see_more", lambda *a, **k: None)
    monkeypatch.setattr(fc, "clean_fb_metadata", lambda t: t)
    monkeypatch.setattr(fc, "keyword_filter_text", lambda t: t)      # 빈 텍스트 → "" → 필터 제외
    monkeypatch.setattr(fc, "passes_keyword_filter", lambda t: True)
    monkeypatch.setattr(fc, "passes_image_filter", lambda url: True)
    monkeypatch.setattr(fc, "replace_contacts", lambda t: t)
    monkeypatch.setattr(fc, "generate_sku", lambda url: "SKU")

    def _save(image_url, target_url, converted_text, **kw):
        state.saved.append(kw.get("original_text", converted_text))
        return True

    monkeypatch.setattr(fc, "save_to_airtable", _save)
    monkeypatch.setattr(fc.time, "sleep", lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "modules.metrics.crawl_monitor",
                        SimpleNamespace(record_crawl=lambda *a, **k: None))
    return state


def _run(env, batches, *, max_posts=20, cdp_fail=False):
    env.driver = FakeDriver(batches, cdp_fail=cdp_fail)
    fc.run(URL, max_posts, target_publish_account_code_ref="IDN-000041",
           data_classification="production")
    return env.driver


# ── 1. Flag OFF: 기존 1회 수집 그대로 ─────────────────────────────────────────
def test_flag_off_keeps_single_collection(env):
    d = _run(env, [["post A", EMPTY, EMPTY], ["post B", "post C"]])
    assert env.saved == ["post A"]                      # 빈 틀은 기존처럼 필터에서 제외
    assert not any(c[0] == "cdp" for c in d.calls)      # 포커스 흉내 호출 없음
    assert d.bottom_scrolls() == 0                      # 추가 스크롤 없음


# ── 2. Flag ON: 페이지 로드 전에 포커스 흉내 ─────────────────────────────────
def test_flag_on_enables_focus_emulation_before_page_load(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "true")
    d = _run(env, [["post A"]])
    kinds = [c[0] for c in d.calls]
    assert kinds.index("cdp") < kinds.index("get")
    cdp = [c for c in d.calls if c[0] == "cdp"]
    assert cdp == [("cdp", "Emulation.setFocusEmulationEnabled", {"enabled": True})]


# ── 2-A. 260921 P1-1: 포커스 흉내 단독 Flag (점진 스크롤과 분리) ─────────────
def test_both_flags_off_makes_no_cdp_call(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "false")
    monkeypatch.setenv("FB_FOCUS_EMULATION_ENABLED", "false")
    d = _run(env, [["post A"], ["post A", "post B"]])
    assert not any(c[0] == "cdp" for c in d.calls)
    assert d.bottom_scrolls() == 0
    assert env.saved == ["post A"]


def test_focus_flag_only_enables_cdp_without_progressive_scroll(env, monkeypatch):
    monkeypatch.setenv("FB_FOCUS_EMULATION_ENABLED", "true")
    d = _run(env, [["post A"], ["post A", "post B"]])
    cdp = [c for c in d.calls if c[0] == "cdp"]
    assert cdp == [("cdp", "Emulation.setFocusEmulationEnabled", {"enabled": True})]
    kinds = [c[0] for c in d.calls]
    assert kinds.index("cdp") < kinds.index("get")
    assert d.bottom_scrolls() == 0
    assert env.saved == ["post A"]
    assert not env.log.has("info", "점진 수집 종료")


def test_focus_flag_only_cdp_failure_continues_crawl(env, monkeypatch):
    monkeypatch.setenv("FB_FOCUS_EMULATION_ENABLED", "true")
    d = _run(env, [["post A"], ["post A", "post B"]], cdp_fail=True)
    assert env.log.has("warning", "포커스 흉내 실패")
    assert env.saved == ["post A"]
    assert d.bottom_scrolls() == 0


# ── 3. 라운드별 새 글만 처리, 빈 틀·중복 건너뜀 ─────────────────────────────
def test_collects_new_posts_across_rounds_skipping_empty_and_duplicates(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "true")
    _run(env, [
        ["post A", EMPTY, EMPTY],
        ["post A", "post B", EMPTY],
        ["post B", "post C", "post D"],
    ])
    assert env.saved == ["post A", "post B", "post C", "post D"]
    assert env.log.has("info", "사유=no_new_posts")


# ── 4. 상한: 기본 5개 ─────────────────────────────────────────────────────────
def test_default_cap_is_five(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "true")
    _run(env, [[f"post {n}" for n in range(10)]])
    assert len(env.saved) == 5
    assert env.log.has("info", "사유=cap")


def test_smaller_max_posts_wins(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "true")
    _run(env, [[f"post {n}" for n in range(10)]], max_posts=2)
    assert len(env.saved) == 2


# ── 5. 2라운드 연속 새 글 없으면 정지 ─────────────────────────────────────────
def test_stops_after_two_idle_rounds(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "true")
    d = _run(env, [["post A"]])
    assert env.saved == ["post A"]
    assert d.bottom_scrolls() == 2
    assert env.log.has("info", "사유=no_new_posts")


# ── 6. 최대 라운드에서 정지 (마지막 라운드 뒤 불필요한 스크롤 없음) ───────────
def test_stops_at_max_rounds(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "true")
    monkeypatch.setenv("FB_PROGRESSIVE_MAX_POSTS", "100")
    monkeypatch.setenv("FB_PROGRESSIVE_MAX_ROUNDS", "3")
    d = _run(env, [[f"post {n}"] for n in range(10)], max_posts=100)
    assert env.saved == ["post 0", "post 1", "post 2"]
    assert d.bottom_scrolls() == 2
    assert env.log.has("info", "사유=max_rounds")


# ── 7. 시간 예산 초과 시 정지 ─────────────────────────────────────────────────
def test_stops_when_budget_exceeded(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "true")
    ticks = iter([0.0] + [1000.0] * 50)
    monkeypatch.setattr(fc.time, "monotonic", lambda: next(ticks))
    d = _run(env, [["post A", "post B"], ["post C"]])
    assert env.saved == ["post A", "post B"]
    assert d.bottom_scrolls() == 0
    assert env.log.has("info", "사유=budget")


# ── 8. 포커스 흉내 실패해도 크롤은 계속 ───────────────────────────────────────
def test_focus_emulation_failure_is_logged_and_crawl_continues(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "true")
    _run(env, [["post A"], ["post A", "post B"]], cdp_fail=True)
    assert env.log.has("warning", "포커스 흉내 실패")
    assert env.saved == ["post A", "post B"]


# ── 9. 스크롤 중 오류 시 안전 정지 ───────────────────────────────────────────
def test_scroll_error_stops_safely(env, monkeypatch):
    monkeypatch.setenv("FB_PROGRESSIVE_CRAWL_ENABLED", "true")

    class BrokenDriver(FakeDriver):
        def execute_script(self, script, *args):
            if "scrollHeight" in script:
                raise RuntimeError("tab crashed")
            return super().execute_script(script, *args)

    env.driver = BrokenDriver([["post A"]])
    fc.run(URL, 20, target_publish_account_code_ref="IDN-000041",
           data_classification="production")
    assert env.saved == ["post A"]
    assert env.log.has("info", "사유=scroll_error:RuntimeError")
