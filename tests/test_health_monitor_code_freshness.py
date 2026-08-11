"""260811 ERR-109 — health_monitor.py의 code_freshness(Runtime 진입점 코드
신선도) 기능 단위 테스트. 실제 git/파일시스템 대신 monkeypatch로 격리한다.
"""

import json

import modules.common.health_monitor as health_monitor


def _patch_git_head(monkeypatch, commit: str):
    """subprocess.check_output(["git", "rev-parse", "HEAD"], ...) 호출을
    고정된 commit 문자열로 대체한다. record_boot_commit()과
    _check_code_freshness() 양쪽에서 재사용되는 실제 함수를 그대로 패치한다."""

    def _fake_check_output(cmd, **kwargs):
        if cmd[:2] == ["git", "rev-parse"]:
            return commit + "\n"
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(health_monitor.subprocess, "check_output", _fake_check_output)


def test_record_boot_commit_writes_state_file(tmp_path, monkeypatch):
    state_path = tmp_path / "launcher_boot_state.json"
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", state_path)
    _patch_git_head(monkeypatch, "abc1234567890")

    health_monitor.record_boot_commit()

    assert state_path.exists()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["commit"] == "abc1234567890"
    assert data["started_at"]


def test_record_boot_commit_fails_open_when_git_unavailable(tmp_path, monkeypatch):
    """git 명령 자체가 실패해도(예: git 미설치) 예외를 던지지 않고 조용히
    넘어가야 한다 — 이 기록 실패가 실제 서비스 기동을 막으면 안 된다."""
    state_path = tmp_path / "launcher_boot_state.json"
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", state_path)

    def _raise(*a, **k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(health_monitor.subprocess, "check_output", _raise)

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

    def _raise(*a, **k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(health_monitor.subprocess, "check_output", _raise)

    status = health_monitor.get_code_freshness_status()

    assert status["status"] == "unknown"


def test_freshness_unknown_when_state_file_corrupted(tmp_path, monkeypatch):
    state_path = tmp_path / "launcher_boot_state.json"
    state_path.write_text("not valid json {{{", encoding="utf-8")
    monkeypatch.setattr(health_monitor, "_BOOT_STATE_PATH", state_path)
    _patch_git_head(monkeypatch, "whatever")

    status = health_monitor.get_code_freshness_status()

    assert status["status"] == "unknown"
