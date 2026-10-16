"""261016 Threads 최소 자동게시 — modules/sns/threads_publisher.py + launcher 연결부 Target Test.

실제 네트워크·Airtable·Slack·게시 없음(전부 가짜). 토큰은 가짜 문자열.
"""

from types import SimpleNamespace

import pytest

import modules.sns.threads_publisher as tp

TOKEN = "THAAfakeThreadsToken0000000000000000"
UID = "2884584040837965"


class _R:
    def __init__(self, status=200, body=None, raise_json=False):
        self.status_code = status
        self._body = body or {}
        self._raise = raise_json

    def json(self):
        if self._raise:
            raise ValueError("bad json")
        return self._body


class FakeHttp:
    def __init__(self, me_id=UID, container=(200, {"id": "C1"}), statuses=("FINISHED",), publish=(200, {"id": "M1"})):
        self.me_id, self.container, self.statuses, self.publish = me_id, container, list(statuses), publish
        self.posts, self.gets = [], []

    def get(self, url, params=None, timeout=None):
        self.gets.append(url)
        if url.endswith("/me"):
            return _R(200, {"id": self.me_id})
        st = self.statuses.pop(0) if self.statuses else "IN_PROGRESS"
        return _R(200, {"status": st})

    def post(self, url, params=None, timeout=None):
        self.posts.append((url, dict(params or {})))
        if url.endswith("/threads"):
            s, b = self.container
            return _R(s, b)
        p = self.publish
        if isinstance(p, Exception):
            raise p
        s, b = p
        return _R(s, b, raise_json=(b == "BAD"))


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("SALE1_THREADS_USER_ID", UID)
    monkeypatch.setattr(tp, "get_threads_token", lambda k: TOKEN if k == "SALE1" else "")


def run(http, **kw):
    clock = iter(range(0, 10_000, 10))
    args = dict(credential_key="SALE1", image_url="https://img/x.jpg", text="hello")
    args.update(kw)
    return tp.publish_threads(http=http, sleep=lambda s: None, clock=lambda: next(clock), **args)


# ── 스위치 ────────────────────────────────────────────────────────────────

def test_enabled_for_default_off(monkeypatch):
    monkeypatch.delenv("THREADS_PUBLISH_ENABLED", raising=False)
    monkeypatch.setenv("THREADS_PUBLISH_KEYS", "SALE1")
    assert tp.enabled_for("SALE1") is False


def test_enabled_for_requires_allowlist(monkeypatch):
    monkeypatch.setenv("THREADS_PUBLISH_ENABLED", "true")
    monkeypatch.setenv("THREADS_PUBLISH_KEYS", "SALE1,IDN_000017")
    assert tp.enabled_for("SALE1") and tp.enabled_for("IDN_000017")
    assert not tp.enabled_for("YUNA") and not tp.enabled_for("AI") and not tp.enabled_for("")


# ── publish_threads ───────────────────────────────────────────────────────

def test_success_two_posts_exactly(creds):
    h = FakeHttp()
    out = run(h)
    assert out["status"] == "posted" and out["threads_media_id"] == "M1"
    assert [u.rsplit("/", 1)[-1] for u, _ in h.posts] == ["threads", "threads_publish"]
    assert h.posts[0][1]["media_type"] == "IMAGE" and h.posts[1][1]["creation_id"] == "C1"


def test_no_credential_skips_without_http(monkeypatch):
    monkeypatch.setattr(tp, "get_threads_token", lambda k: "")
    h = FakeHttp()
    assert run(h)["status"] == "skipped" and not h.posts and not h.gets


def test_text_over_500_skips_without_truncation(creds):
    h = FakeHttp()
    out = run(h, text="가" * 501)
    assert out["status"] == "skipped" and out["error"].startswith("TEXT_TOO_LONG") and not h.posts


def test_account_mismatch_fail_closed(creds):
    h = FakeHttp(me_id="999")
    out = run(h)
    assert out == {"status": "failed", "threads_media_id": "", "creation_id": "", "error": "ACCOUNT_MISMATCH"}
    assert not h.posts


def test_container_rejected_is_definite_failure(creds):
    h = FakeHttp(container=(400, {"error": {"message": f"bad {TOKEN}"}}))
    out = run(h)
    assert out["status"] == "failed" and TOKEN not in out["error"]
    assert len(h.posts) == 1


def test_container_error_status_never_publishes(creds):
    h = FakeHttp(statuses=("IN_PROGRESS", "ERROR"))
    out = run(h)
    assert out["status"] == "failed" and out["error"] == "CONTAINER_ERROR" and len(h.posts) == 1


def test_container_not_finished_by_deadline_never_publishes(creds):
    h = FakeHttp(statuses=())
    out = run(h)
    assert out["status"] == "failed" and len(h.posts) == 1


@pytest.mark.parametrize("pub", [TimeoutError("t"), (502, {}), (200, "BAD")])
def test_publish_ambiguous_is_outcome_unknown_no_retry(creds, pub):
    h = FakeHttp(publish=pub)
    out = run(h)
    assert out["status"] == "outcome_unknown" and out["creation_id"] == "C1"
    assert sum(1 for u, _ in h.posts if u.endswith("threads_publish")) == 1     # 재시도 없음


def test_publish_4xx_is_failed(creds):
    out = run(FakeHttp(publish=(400, {"error": {"message": "nope"}})))
    assert out["status"] == "failed" and out["error"].startswith("PUBLISH_REJECTED")


def test_token_never_in_result(creds):
    for h in (FakeHttp(), FakeHttp(me_id="x"), FakeHttp(publish=(400, {"error": {"message": TOKEN}}))):
        assert TOKEN not in str(run(h))


def test_record_pending_separate_file_no_token(tmp_path):
    p = tmp_path / "threads_publish_pending.json"
    tp.record_pending("rec9", credential_key="SALE1", creation_id="C1", error="PUBLISH_NO_RESPONSE", path=p)
    text = p.read_text(encoding="utf-8")
    assert "rec9" in text and "C1" in text and TOKEN not in text


# ── launcher 연결부 ───────────────────────────────────────────────────────

class FakeRepo:
    def __init__(self, existing=""):
        self.existing, self.set_calls, self.get_calls = existing, [], []

    def get_threads_media_id(self, rid):
        self.get_calls.append(rid)
        return self.existing

    def set_threads_media_id(self, rid, mid):
        self.set_calls.append((rid, mid))


@pytest.fixture
def m(monkeypatch):
    from launcher import main as _m
    monkeypatch.setattr(_m, "_slack", None)
    return _m


def _hook(m, repo, key="SALE1"):
    m._maybe_publish_threads(repo, "rec1", key, "IDN-000048", "https://img/x.jpg", "hello")


def test_hook_off_does_nothing(m, monkeypatch):
    monkeypatch.delenv("THREADS_PUBLISH_ENABLED", raising=False)
    called = []
    monkeypatch.setattr(tp, "publish_threads", lambda **k: called.append(1))
    repo = FakeRepo()
    _hook(m, repo)
    assert called == [] and repo.get_calls == [] and repo.set_calls == []


def test_hook_not_in_allowlist_does_nothing(m, monkeypatch):
    monkeypatch.setenv("THREADS_PUBLISH_ENABLED", "true")
    monkeypatch.setenv("THREADS_PUBLISH_KEYS", "SALE1")
    called = []
    monkeypatch.setattr(tp, "publish_threads", lambda **k: called.append(1))
    repo = FakeRepo()
    _hook(m, repo, key="YUNA")
    assert called == [] and repo.set_calls == []


def test_hook_skips_when_already_posted(m, monkeypatch):
    monkeypatch.setenv("THREADS_PUBLISH_ENABLED", "true")
    monkeypatch.setenv("THREADS_PUBLISH_KEYS", "SALE1")
    called = []
    monkeypatch.setattr(tp, "publish_threads", lambda **k: called.append(1))
    repo = FakeRepo(existing="M0")
    _hook(m, repo)
    assert called == [] and repo.set_calls == []


def test_hook_posted_records_media_id_once(m, monkeypatch):
    monkeypatch.setenv("THREADS_PUBLISH_ENABLED", "true")
    monkeypatch.setenv("THREADS_PUBLISH_KEYS", "SALE1")
    monkeypatch.setattr(tp, "publish_threads", lambda **k: {"status": "posted", "threads_media_id": "M1", "creation_id": "C1", "error": ""})
    repo = FakeRepo()
    _hook(m, repo)
    assert repo.set_calls == [("rec1", "M1")]


def test_hook_outcome_unknown_records_pending_not_airtable(m, monkeypatch, tmp_path):
    monkeypatch.setenv("THREADS_PUBLISH_ENABLED", "true")
    monkeypatch.setenv("THREADS_PUBLISH_KEYS", "SALE1")
    monkeypatch.setattr(tp, "_PENDING_PATH", tmp_path / "p.json")
    monkeypatch.setattr(tp, "publish_threads", lambda **k: {"status": "outcome_unknown", "threads_media_id": "", "creation_id": "C1", "error": "PUBLISH_NO_RESPONSE"})
    repo = FakeRepo()
    _hook(m, repo)
    assert repo.set_calls == [] and "C1" in (tmp_path / "p.json").read_text(encoding="utf-8")


def test_hook_swallows_exceptions(m, monkeypatch):
    monkeypatch.setenv("THREADS_PUBLISH_ENABLED", "true")
    monkeypatch.setenv("THREADS_PUBLISH_KEYS", "SALE1")
    class Boom(FakeRepo):
        def get_threads_media_id(self, rid):
            raise RuntimeError("airtable down")
    _hook(m, Boom())                                    # 예외가 밖으로 나오지 않아야 함


# ── _job_insta_upload 통합: IG 성공 시에만, 정확한 키로 1회 ──────────────────

def _job_setup(monkeypatch, m, ig_ok):
    monkeypatch.delenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", raising=False)
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    calls = SimpleNamespace(hook=[], mark=[])

    class Repo:
        def fetch_pending_posts(self, limit=50):
            return [{"post_id": "rec1", "image_url": "http://img", "caption": "c", "hashtag": "",
                     "account_code_ref": "IDN-000048"}]

        def get_publish_account(self, code):
            return {"account_code": code, "api_provider": "facebook_login", "ig_user_id": "178KB",
                    "credential_key": "SALE1", "automation_enabled": True}

        def claim_post_for_upload(self, post_id):
            return True

        def mark_post_result(self, post_id, result):
            calls.mark.append(dict(result))

    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: Repo())
    monkeypatch.setattr("modules.common.canary_classification.validate_publication_candidate", lambda *a, **k: None)
    monkeypatch.setattr("modules.common.credential_resolver.resolve_credential",
                        lambda key: SimpleNamespace(ig_user_id="178KB", access_token="fake"))
    monkeypatch.setattr(m, "resolve_publish_gate", lambda caption, code, **k: (True, "PUBLISH_ALLOWED"))
    monkeypatch.setattr(m, "publish_single", lambda *a, **k: {"ok": ig_ok, "ig_media_id": "IG1" if ig_ok else "", "error": "" if ig_ok else "x"})
    monkeypatch.setattr(m, "_maybe_publish_threads", lambda repo, rid, key, code, img, cap: calls.hook.append((rid, key, code)))
    return calls


def test_job_calls_threads_hook_after_ig_success(m, monkeypatch):
    calls = _job_setup(monkeypatch, m, ig_ok=True)
    m._job_insta_upload()
    assert calls.mark[0]["status"] == "posted" and calls.hook == [("rec1", "SALE1", "IDN-000048")]


def test_job_skips_threads_hook_when_ig_failed(m, monkeypatch):
    calls = _job_setup(monkeypatch, m, ig_ok=False)
    m._job_insta_upload()
    assert calls.mark[0]["status"] == "failed" and calls.hook == []
