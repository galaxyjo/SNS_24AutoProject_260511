"""260811 ERR-109/ERR-111 — health_monitor.py의 code_freshness(Runtime 진입점
코드 신선도) 기능 단위 테스트. 실제 git 실행파일 대신 monkeypatch 또는
`.git` 유사 파일구조로 격리한다(ERR-111 — subprocess 기반 git 호출이 NSSM
서비스 계정에서 조용히 실패해 파일시스템 직접 읽기 방식으로 교체됨).
"""

import json

import modules.common.health_monitor as health_monitor


def _patch_git_head(monkeypatch, commit: str):
    """`_read_git_head_commit()`(record_boot_commit()/_check_code_freshness()
    양쪽에서 공유되는 실제 함수)을 고정된 commit 문자열로 대체한다."""
    monkeypatch.setattr(health_monitor, "_read_git_head_commit", lambda: commit)


def test_record_boot_commit_writes_state_file(tmp_path, monkeypatch):
    state_path = tmp_path / "launcher_boot_state.json"
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", state_path)
    _patch_git_head(monkeypatch, "abc1234567890")

    health_monitor.record_boot_commit()

    assert state_path.exists()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["commit"] == "abc1234567890"
    assert data["started_at"]


def test_record_boot_commit_fails_open_when_git_head_unreadable(tmp_path, monkeypatch):
    """`_read_git_head_commit()`이 빈 문자열을 반환해도(자체 Fail-open 계약)
    예외를 던지지 않고 조용히 넘어가야 한다 — 이 기록 실패가 실제 서비스
    기동을 막으면 안 된다."""
    state_path = tmp_path / "launcher_boot_state.json"
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", state_path)
    _patch_git_head(monkeypatch, "")

    health_monitor.record_boot_commit()  # 예외 없이 완료돼야 함

    assert state_path.exists()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["commit"] == ""


def test_freshness_unknown_when_state_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", tmp_path / "does_not_exist.json")

    status = health_monitor.get_code_freshness_status()

    assert status["status"] == "unknown"
    assert status["boot_commit"] is None
    assert status["head_commit"] is None


def test_freshness_fresh_when_boot_commit_matches_head(tmp_path, monkeypatch):
    state_path = tmp_path / "launcher_boot_state.json"
    state_path.write_text(
        json.dumps({"commit": "same1234", "started_at": "2026-08-11 05:56:43"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", state_path)
    _patch_git_head(monkeypatch, "same1234")

    status = health_monitor.get_code_freshness_status()

    assert status == {
        "status": "fresh",
        "boot_commit": "same1234",
        "head_commit": "same1234",
        "started_at": "2026-08-11 05:56:43",
    }


def test_freshness_stale_when_boot_commit_differs_from_head(tmp_path, monkeypatch):
    """260811 ERR-109 재현 시나리오 — 커밋은 새로 생겼지만(head) 프로세스는
    옛 커밋(boot)으로 여전히 떠 있는 상태를 "stale"로 판정해야 한다."""
    state_path = tmp_path / "launcher_boot_state.json"
    state_path.write_text(
        json.dumps({"commit": "old0000", "started_at": "2026-08-10 05:56:43"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", state_path)
    _patch_git_head(monkeypatch, "new9999")

    status = health_monitor.get_code_freshness_status()

    assert status["status"] == "stale"
    assert status["boot_commit"] == "old0000"
    assert status["head_commit"] == "new9999"


def test_freshness_unknown_when_git_head_lookup_fails(tmp_path, monkeypatch):
    state_path = tmp_path / "launcher_boot_state.json"
    state_path.write_text(
        json.dumps({"commit": "old0000", "started_at": "2026-08-10 05:56:43"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", state_path)
    _patch_git_head(monkeypatch, "")

    status = health_monitor.get_code_freshness_status()

    assert status["status"] == "unknown"


def test_freshness_unknown_when_state_file_corrupted(tmp_path, monkeypatch):
    state_path = tmp_path / "launcher_boot_state.json"
    state_path.write_text("not valid json {{{", encoding="utf-8")
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", state_path)
    _patch_git_head(monkeypatch, "whatever")

    status = health_monitor.get_code_freshness_status()

    assert status["status"] == "unknown"


# ── 260811 ERR-111 — _read_git_head_commit() 자체 검증(실제 파일구조, git 실행파일 미사용) ──

def _make_fake_repo(root):
    (root / ".git").mkdir()
    (root / ".git" / "refs" / "heads").mkdir(parents=True)


class TestReadGitHeadCommitFilesystemOnly:
    def test_resolves_via_normal_branch_ref(self, tmp_path, monkeypatch):
        _make_fake_repo(tmp_path)
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8")
        (tmp_path / ".git" / "refs" / "heads" / "master").write_text(
            "4b87ad61182a46d3bd2264d3b0b838218c8a7833\n", encoding="utf-8",
        )
        monkeypatch.setattr(health_monitor, "_ROOT", tmp_path)

        assert health_monitor._read_git_head_commit() == "4b87ad61182a46d3bd2264d3b0b838218c8a7833"

    def test_resolves_detached_head_raw_sha(self, tmp_path, monkeypatch):
        _make_fake_repo(tmp_path)
        (tmp_path / ".git" / "HEAD").write_text(
            "4b87ad61182a46d3bd2264d3b0b838218c8a7833\n", encoding="utf-8",
        )
        monkeypatch.setattr(health_monitor, "_ROOT", tmp_path)

        assert health_monitor._read_git_head_commit() == "4b87ad61182a46d3bd2264d3b0b838218c8a7833"

    def test_falls_back_to_packed_refs_when_loose_ref_missing(self, tmp_path, monkeypatch):
        """`git gc` 이후 흔한 상태 — loose ref 파일이 없고 packed-refs에만 있음."""
        _make_fake_repo(tmp_path)
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8")
        (tmp_path / ".git" / "packed-refs").write_text(
            "# pack-refs with: peeled fully-peeled sorted\n"
            "aaaa1111222233334444555566667777888899990000 refs/heads/other\n"
            "4b87ad61182a46d3bd2264d3b0b838218c8a7833 refs/heads/master\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(health_monitor, "_ROOT", tmp_path)

        assert health_monitor._read_git_head_commit() == "4b87ad61182a46d3bd2264d3b0b838218c8a7833"

    def test_returns_empty_string_when_git_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(health_monitor, "_ROOT", tmp_path)  # .git 자체가 없음

        assert health_monitor._read_git_head_commit() == ""

    def test_returns_empty_string_when_ref_unresolvable(self, tmp_path, monkeypatch):
        _make_fake_repo(tmp_path)
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/ghost-branch\n", encoding="utf-8")
        monkeypatch.setattr(health_monitor, "_ROOT", tmp_path)

        assert health_monitor._read_git_head_commit() == ""

    def test_no_subprocess_call_at_all(self, tmp_path, monkeypatch):
        """260811 ERR-111 핵심 계약 — git 실행파일에 전혀 의존하지 않는다."""
        _make_fake_repo(tmp_path)
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8")
        (tmp_path / ".git" / "refs" / "heads" / "master").write_text("deadbeef\n", encoding="utf-8")
        monkeypatch.setattr(health_monitor, "_ROOT", tmp_path)

        def _fail_if_called(*a, **k):
            raise AssertionError("subprocess는 호출되면 안 됨")

        monkeypatch.setattr(health_monitor.subprocess, "check_output", _fail_if_called)

        assert health_monitor._read_git_head_commit() == "deadbeef"
