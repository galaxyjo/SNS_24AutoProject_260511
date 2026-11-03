"""modules/sns/reuse_replenisher.py 단위 테스트 — Repository·ImgBB·Graph 는 모두 가짜(네트워크·운영 경로 접근 없음)."""

from datetime import datetime

import pytest

from modules.sns import reuse_replenisher as rr

NOW = datetime(2026, 11, 3, 15, 30, 0)


class FakeRepo:
    def __init__(self, ready=None, enabled=None, source=None, acct_hashes=None, recent_failed=0):
        self.ready = ready or []          # ready 행의 account_code_ref 목록
        self.enabled = enabled if enabled is not None else {}
        self.source = source or []
        self.acct_hashes = acct_hashes or {}
        self.recent_failed = recent_failed
        self.saved = []

    def count_ready_posts_by_account(self):
        counts = {}
        for a in self.ready:
            counts[a] = counts.get(a, 0) + 1
        return counts

    def count_recent_failed_posts_by_run_prefix(self, run_id_prefix, hours):
        assert run_id_prefix == "R041-AUTO" and hours == 24
        return self.recent_failed

    def get_publish_account(self, account_code):
        if account_code not in self.enabled:
            return None
        return {"account_code": account_code, "automation_enabled": self.enabled[account_code]}

    def fetch_reuse_source_posts(self, source_account_code):
        assert source_account_code == "IDN-000041"
        return list(self.source)

    def fetch_image_hashes_for_account(self, account_code):
        return set(self.acct_hashes.get(account_code, []))

    def save_instagram_post(self, post):
        self.saved.append(post)
        return f"recNEW{len(self.saved)}"


class FakeImages:
    def __init__(self, alive=None, upload="https://i.ibb.co/new/x.jpg", graph="", graph_raises=False):
        self._alive = alive if alive is not None else set()
        self._upload = upload
        self._graph = graph
        self._graph_raises = graph_raises
        self.uploaded = []

    def alive(self, url):
        return url in self._alive

    def upload(self, url):
        self.uploaded.append(url)
        return self._upload

    def graph_media_url(self, ig_media_id):
        if self._graph_raises:
            raise rr.GraphAuthError("graph_code=190")
        return self._graph


def src(n, **over):
    p = {"post_id": f"recS{n}", "image_url": f"https://i.ibb.co/{n}.jpg", "original_image_url": f"https://fb/{n}.jpg",
         "caption": f"cap{n}", "hashtag": "#k", "source_url": "https://facebook.com/groups/1",
         "image_url_hash": f"h{n}", "insta_post_code": f"A-{n:03d}", "ig_media_id": f"m{n}", "media_type": "image",
         "original_text": ""}
    p.update(over)
    return p


def run(repo, images, accounts, tmp_path, notify=None, **kw):
    return rr.run_once(accounts, repo=repo, images=images, notify=notify or (lambda m: None),
                       state_path=tmp_path / "state.json", lock_path=tmp_path / "lock", now=NOW, **kw)


ALL_ALIVE = {f"https://i.ibb.co/{n}.jpg" for n in range(1, 10)}


def test_creates_up_to_ready_target(tmp_path):
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(i) for i in range(1, 6)])
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert res["created"] == {"IDN-000007": 2}
    assert len(repo.saved) == 2
    f = repo.saved[0]
    assert f["account_code_ref"] == "IDN-000007" and f["post_status"] == "ready"
    assert f["data_classification"] == "production" and "canary_run_id" not in f
    assert f["run_id"] == "R041-AUTO-261103" and f["insta_post_code"].startswith("R041-AUTO-261103-007-")
    assert f["caption"] == "cap1" and f["image_url"] == "https://i.ibb.co/1.jpg"


def test_tops_up_only_the_shortfall(tmp_path):
    repo = FakeRepo(ready=["IDN-000007"], enabled={"IDN-000007": True}, source=[src(i) for i in range(1, 6)])
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert res["created"] == {"IDN-000007": 1}


def test_no_creation_when_at_target(tmp_path):
    repo = FakeRepo(ready=["IDN-000007", "IDN-000007"], enabled={"IDN-000007": True}, source=[src(1)])
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert repo.saved == [] and res["created"] == {}


def test_global_cap_blocks_everything(tmp_path):
    repo = FakeRepo(ready=["IDN-000099"] * 40, enabled={"IDN-000007": True}, source=[src(1)])
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert res["skipped"] == "GLOBAL_CAP" and repo.saved == []


def test_global_cap_limits_partial_creation(tmp_path):
    repo = FakeRepo(ready=["IDN-000099"] * 39, enabled={"IDN-000007": True}, source=[src(i) for i in range(1, 6)])
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert res["created"] == {"IDN-000007": 1}


def test_skips_same_account_duplicate_hash(tmp_path):
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(i) for i in range(1, 5)],
                    acct_hashes={"IDN-000007": ["h1", "h2"]})
    run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert [f["image_url_hash"] for f in repo.saved] == ["h3", "h4"]


def test_automation_disabled_or_unknown_account_is_skipped(tmp_path):
    repo = FakeRepo(enabled={"IDN-000007": False}, source=[src(1)])
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007", "IDN-000014"], tmp_path)
    assert repo.saved == [] and res["created"] == {}


def test_source_account_and_invalid_codes_are_ignored(tmp_path):
    repo = FakeRepo(enabled={"IDN-000041": True}, source=[src(1)])
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000041", "bad", ""], tmp_path)
    assert res["skipped"] == "NO_TARGETS" and repo.saved == []


def test_image_fallback_order(tmp_path):
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
    images = FakeImages(alive={"https://fb/1.jpg"}, upload="https://i.ibb.co/up.jpg")
    run(repo, images, ["IDN-000007"], tmp_path)
    assert images.uploaded == ["https://fb/1.jpg"] and repo.saved[0]["image_url"] == "https://i.ibb.co/up.jpg"


def test_graph_recovery_when_both_urls_dead(tmp_path):
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
    images = FakeImages(alive=set(), graph="https://cdn/graph.jpg", upload="https://i.ibb.co/g.jpg")
    run(repo, images, ["IDN-000007"], tmp_path)
    assert images.uploaded == ["https://cdn/graph.jpg"] and repo.saved[0]["image_url"] == "https://i.ibb.co/g.jpg"


def test_unrecoverable_image_is_skipped_and_counted(tmp_path):
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1), src(2)])
    images = FakeImages(alive={"https://i.ibb.co/2.jpg"}, graph="")
    res = run(repo, images, ["IDN-000007"], tmp_path)
    assert [f["image_url_hash"] for f in repo.saved] == ["h2"] and res["failed_images"] == 1


def test_graph_auth_error_aborts_and_notifies_once_per_day(tmp_path):
    msgs = []
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
    images = FakeImages(alive=set(), graph_raises=True)
    res1 = run(repo, images, ["IDN-000007"], tmp_path, notify=msgs.append)
    res2 = run(repo, images, ["IDN-000007"], tmp_path, notify=msgs.append)
    assert res1["skipped"] == "GRAPH_AUTH" and res2["skipped"] == "GRAPH_AUTH"
    assert repo.saved == [] and len(msgs) == 1


def test_exhausted_account_notifies_once(tmp_path):
    msgs = []
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)], acct_hashes={"IDN-000007": ["h1"]})
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path, notify=msgs.append)
    run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path, notify=msgs.append)
    assert res["exhausted"] == ["IDN-000007"] and len(msgs) == 1


def test_publish_failure_breaker_stops_creation_and_alerts_once(tmp_path):
    msgs = []
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(i) for i in range(1, 6)], recent_failed=3)
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path, notify=msgs.append)
    run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path, notify=msgs.append)
    assert res["skipped"] == "PUBLISH_FAILURES" and repo.saved == [] and len(msgs) == 1


def test_below_breaker_threshold_still_creates(tmp_path):
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(i) for i in range(1, 6)], recent_failed=2)
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert res["created"] == {"IDN-000007": 2}


def test_concurrent_run_is_blocked_while_lock_is_held(tmp_path):
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
    with rr._file_lock(tmp_path / "lock") as outer:
        assert outer is True
        res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert res["skipped"] == "LOCKED" and repo.saved == []


def test_long_held_lock_is_never_taken_over(tmp_path):
    """오래된 잠금 파일이어도 살아 있는 소유자가 쥐고 있으면 빼앗지 않는다(stale 회수 없음)."""
    import os
    lock = tmp_path / "lock"
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
    with rr._file_lock(lock) as outer:
        assert outer is True
        old = lock.stat().st_mtime - 3 * 3600
        os.utime(lock, (old, old))
        res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert res["skipped"] == "LOCKED" and repo.saved == []


def test_lock_is_released_after_run_and_after_error(tmp_path):
    class Boom(FakeRepo):
        def count_ready_posts_by_account(self):
            raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        run(Boom(enabled={"IDN-000007": True}), FakeImages(), ["IDN-000007"], tmp_path)
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert res["created"] == {"IDN-000007": 1}


def test_repository_without_optional_methods_stops_loudly(tmp_path):
    class Legacy:
        def count_ready_posts_by_account(self):
            raise NotImplementedError

    res = run(Legacy(), FakeImages(), ["IDN-000007"], tmp_path)
    assert res["skipped"] == "REPO_UNSUPPORTED"


@pytest.mark.parametrize("missing", ["count_recent_failed_posts_by_run_prefix", "fetch_reuse_source_posts",
                                     "fetch_image_hashes_for_account"])
def test_each_optional_method_missing_is_classified_as_unsupported(tmp_path, missing):
    class Partial(FakeRepo):
        pass

    def boom(self, *a, **k):
        raise NotImplementedError

    setattr(Partial, missing, boom)
    repo = Partial(enabled={"IDN-000007": True}, source=[src(1)])
    res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert res["skipped"] == "REPO_UNSUPPORTED" and repo.saved == []


def test_notimplemented_from_non_repository_code_is_not_misclassified(tmp_path):
    class BadImages(FakeImages):
        def alive(self, url):
            raise NotImplementedError("images")

    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
    with pytest.raises(NotImplementedError):
        run(repo, BadImages(), ["IDN-000007"], tmp_path)


_HOLDER = r"""
import os, sys
fh = open(sys.argv[1], "a+b")
if fh.seek(0, os.SEEK_END) == 0:
    fh.write(b"0"); fh.flush()
fh.seek(0)
if os.name == "nt":
    import msvcrt; msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
else:
    import fcntl; fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
print("HELD", flush=True)
sys.stdin.read()
"""


def test_lock_excludes_other_process_and_is_released_when_owner_dies(tmp_path):
    """별도 프로세스가 잠금을 쥔 동안은 LOCKED, 그 프로세스를 강제 종료하면 OS 가 풀어 다시 획득된다."""
    import subprocess
    import sys

    lock = tmp_path / "lock"
    child = subprocess.Popen([sys.executable, "-c", _HOLDER, str(lock)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "HELD"
        repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
        res = run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
        assert res["skipped"] == "LOCKED" and repo.saved == []
    finally:
        child.kill()
        child.wait(timeout=10)
    # Windows 는 종료된 프로세스의 잠금을 "시스템 자원에 따라 지연되어" 푼다(LockFile 문서) → 짧게 재시도한다.
    import time
    res2 = None
    for _ in range(50):
        repo2 = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
        res2 = run(repo2, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
        if res2["skipped"] != "LOCKED":
            break
        time.sleep(0.2)
    assert res2["created"] == {"IDN-000007": 1}


def test_state_file_written_to_given_path_only(tmp_path):
    repo = FakeRepo(enabled={"IDN-000007": True}, source=[src(1)])
    run(repo, FakeImages(alive=ALL_ALIVE), ["IDN-000007"], tmp_path)
    assert (tmp_path / "state.json").exists()
