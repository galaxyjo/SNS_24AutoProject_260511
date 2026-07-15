"""tests/test_comment_campaign_baseline_cli.py — 수동 baseline CLI 검증
(260715 Package 1 Phase A, Codex 5~8차 리뷰 반영: --verify 8개 계약 항목,
--apply 사전조건(allowlist 모드+config hash 필수), --activate 하드블록(enforce+
allowlist+runtime-proof+hash 전부 일치해야 함))."""

import json

import pytest

from tools import comment_campaign_baseline_cli as cli
from modules.comment import comment_poll_targets as pt
from modules.comment import comment_event_store as ces
from modules.comment import comment_campaign_config as cfg


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(pt, "_DB_PATH", tmp_path / "poll_targets_test.db")
    monkeypatch.setattr(pt, "_conn", None)
    monkeypatch.setattr(ces, "_DB_PATH", tmp_path / "poll_targets_test.db")  # 같은 DB 파일, 다른 테이블
    monkeypatch.setattr(ces, "_conn", None)
    monkeypatch.setattr(cfg, "_CONFIG_PATH", tmp_path / "campaign.json")
    cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": ["m1"]}), encoding="utf-8")
    # 260716 Codex 8차 리뷰 — apply는 allowlist 모드가 이미 켜져 있어야 하고,
    # activate는 enforce+allowlist가 모두 켜져 있어야 한다. 이 파일 대부분의
    # 테스트는 그 자체가 아니라 apply/verify/activate의 다른 로직을 검증하는
    # 것이므로, 기본값으로 두 조건을 모두 만족시켜 두고 예외 테스트만 개별적으로
    # env를 지운다.
    monkeypatch.setattr(pt, "is_allowlist_gating_enabled", lambda: True)
    monkeypatch.setenv("COMMENT_POLL_ALLOWLIST_MODE", "allowlist")
    monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "enforce")
    yield


CUTOVER = "2026-07-16T00:00:00+00:00"


def _comment(cid, ts):
    return {"id": cid, "text": "hi", "username": "u", "timestamp": ts, "from": {"id": "u1"}}


def _apply(media_id: str, cutover: str = CUTOVER, expected_config_hash: str | None = None) -> None:
    """테스트 편의 헬퍼 — hash를 안 주면 현재 캠페인 설정으로 자동 계산(드리프트
    테스트가 아닌 대부분의 테스트에서 매번 손으로 계산하지 않도록)."""
    if expected_config_hash is None:
        expected_config_hash = cli._current_campaign_config_hash()
    cli.cmd_apply(media_id, cutover, expected_config_hash)


def _activate(media_id: str, acknowledge_runtime_proof: bool = True) -> None:
    cli.cmd_activate(media_id, acknowledge_runtime_proof)


class TestDryRun:
    def test_dry_run_does_not_write_anything(self, monkeypatch, capsys):
        """260715 Codex 6차 리뷰 P0-3: dry-run은 poll_targets에 행조차 만들면 안 된다."""
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [_comment("c1", "2026-07-15T00:00:00+0000")])
        cli.cmd_dry_run("m1")
        assert pt.get_target("m1") is None, "dry-run은 sync_from_campaign_json을 호출하면 안 됨(순수 읽기 전용)"

    def test_dry_run_rejects_media_not_in_campaign(self, monkeypatch):
        with pytest.raises(cli.BaselineError):
            cli.cmd_dry_run("unknown-media")


class TestApply:
    def test_apply_requires_allowlist_mode_first(self, monkeypatch):
        """260716 Codex 8차 리뷰 P1 — allowlist 모드를 먼저 켜지 않으면 apply 자체를
        거부해야 한다(안전한 운영 순서 강제: 모든 media가 PENDING인 상태에서
        allowlist부터 켠 뒤 baseline 진행)."""
        monkeypatch.setattr(pt, "is_allowlist_gating_enabled", lambda: False)
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        with pytest.raises(cli.BaselineError):
            _apply("m1")

    def test_apply_requires_expected_config_hash(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        with pytest.raises(TypeError):
            cli.cmd_apply("m1", CUTOVER)  # expected_config_hash 없이 호출(필수 인자 누락)

    def test_apply_suppresses_only_pre_cutover_comments(self, monkeypatch):
        comments = [
            _comment("old1", "2026-07-15T00:00:00+0000"),
            _comment("old2", "2026-07-15T12:00:00+0000"),
            _comment("new1", "2026-07-16T01:00:00+0000"),
        ]
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: comments)
        _apply("m1")

        assert ces.get_status("instagram_comment", "old1")["migration_tag"] == "PRE_CUTOVER_SUPPRESSED"
        assert ces.get_status("instagram_comment", "old2")["migration_tag"] == "PRE_CUTOVER_SUPPRESSED"
        assert ces.get_status("instagram_comment", "new1") is None, "cutover 이후 댓글은 건드리면 안 됨"

        target = pt.get_target("m1")
        assert target["state"] == "PENDING_BASELINE", "apply만으로는 ACTIVE가 되면 안 됨"
        assert target["baseline_comment_count"] == 2

    def test_apply_fails_closed_on_unparseable_timestamp(self, monkeypatch):
        comments = [_comment("bad", None)]
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: comments)
        with pytest.raises(cli.BaselineError):
            _apply("m1")
        assert ces.get_status("instagram_comment", "bad") is None, "실패한 apply는 부분 쓰기를 남기면 안 됨"

    def test_apply_treats_shadow_seen_existing_row_as_safe_not_duplicate(self, monkeypatch):
        """P0-4(260715 Codex 6차 리뷰) — 실제 운영 DB에는 오늘 하루 종일 shadow
        모드로 관측된 SHADOW_SEEN 행이 이미 있다. apply는 이걸 막지 않고 "이미
        안전하게 처리됨"으로 인정해야 한다(suppress_pre_cutover를 또 부르지 않음)."""
        comments = [_comment("old1", "2026-07-15T00:00:00+0000")]
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: comments)
        ces.try_claim("instagram_comment", "old1", claimed_by="webhook", shadow=True)
        assert ces.get_status("instagram_comment", "old1")["migration_tag"] == "SHADOW_SEEN"

        _apply("m1")  # 예외 없이 통과해야 함

        status = ces.get_status("instagram_comment", "old1")
        assert status["migration_tag"] == "SHADOW_SEEN", "이미 SHADOW_SEEN인 행을 PRE_CUTOVER_SUPPRESSED로 덮어쓰면 안 됨"
        assert pt.get_target("m1")["baseline_comment_count"] == 1

    def test_apply_aborts_on_processing_row_needs_manual_review(self, monkeypatch):
        """P0-4: PROCESSING(아직 안 끝난 상태)인 기존 행은 자동으로 넘기면 안 되고
        apply 자체를 거부해야 한다(수동검토 대상)."""
        comments = [_comment("old1", "2026-07-15T00:00:00+0000")]
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: comments)
        ces.try_claim("instagram_comment", "old1", claimed_by="webhook")  # status=PROCESSING, migration_tag=None

        with pytest.raises(cli.BaselineError):
            _apply("m1")
        assert pt.get_target("m1")["baseline_applied_at"] is None, "실패한 apply는 baseline 기록을 남기면 안 됨"

    def test_apply_requires_pending_baseline_state(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        cli.cmd_verify("m1")
        _activate("m1")
        # 이미 ACTIVE인 상태에서 다시 apply 시도 — 거부돼야 함
        with pytest.raises(cli.BaselineError):
            _apply("m1")


class TestVerify:
    def test_verify_passes_after_correct_apply(self, monkeypatch):
        comments = [_comment("old1", "2026-07-15T00:00:00+0000"), _comment("new1", "2026-07-16T01:00:00+0000")]
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: comments)
        _apply("m1")
        cli.cmd_verify("m1")
        assert pt.get_target("m1")["baseline_verified_at"] is not None

    def test_verify_fails_if_comment_count_drifted(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [_comment("old1", "2026-07-15T00:00:00+0000")])
        _apply("m1")
        # apply 이후 댓글이 하나 더 생긴 것처럼 재조회 결과가 바뀜(드리프트)
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [
            _comment("old1", "2026-07-15T00:00:00+0000"),
            _comment("old2", "2026-07-15T06:00:00+0000"),
        ])
        with pytest.raises(cli.BaselineError):
            cli.cmd_verify("m1")

    def test_verify_without_apply_fails(self):
        with pytest.raises(cli.BaselineError):
            cli.cmd_verify("m1")

    def test_verify_checks_verify_baseline_return_value(self, monkeypatch):
        """260716 Codex 7차 리뷰 P1 — 모든 검증을 통과해도 DB 기록 함수 자체가
        실패(False)를 반환하면 "통과"라고 출력하면 안 된다."""
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        monkeypatch.setattr(pt, "verify_baseline", lambda media_id: False)
        with pytest.raises(cli.BaselineError):
            cli.cmd_verify("m1")

    def test_verify_fails_if_campaign_config_content_changed_even_if_media_untouched(self, monkeypatch):
        """P0-3(260715 Codex 6차 리뷰) — 이 media 자체는 목록에서 안 빠졌어도,
        캠페인 JSON 파일 내용이 apply~verify 사이에 바뀌면(다른 media 추가/제거 등)
        config hash 드리프트로 잡아야 한다."""
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": ["m1", "m2"]}), encoding="utf-8")  # m2 추가
        with pytest.raises(cli.BaselineError):
            cli.cmd_verify("m1")

    def test_verify_fails_if_campaign_json_changed_since_apply(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        # apply 이후 m1이 캠페인 목록에서 빠짐 → sync가 PAUSED로 전이시킴
        cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": []}), encoding="utf-8")
        with pytest.raises(cli.BaselineError):
            cli.cmd_verify("m1")


class TestApplyHardening:
    """260716 Codex 7차 리뷰 P1."""

    def test_apply_rejects_empty_comment_id(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [_comment("", "2026-07-15T00:00:00+0000")])
        with pytest.raises(cli.BaselineError):
            _apply("m1")

    def test_apply_dedupes_repeated_comment_id_across_pages(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [
            _comment("dup", "2026-07-15T00:00:00+0000"),
            _comment("dup", "2026-07-15T00:00:00+0000"),
        ])
        _apply("m1")
        assert pt.get_target("m1")["baseline_comment_count"] == 1

    def test_apply_rejects_drift_from_dry_run_hash(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        stale_hash = "0" * 64  # dry-run 이후 캠페인이 바뀐 것처럼 시뮬레이션
        with pytest.raises(cli.BaselineError):
            _apply("m1", expected_config_hash=stale_hash)

    def test_apply_accepts_matching_dry_run_hash(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        real_hash = cli._current_campaign_config_hash()
        _apply("m1", expected_config_hash=real_hash)  # 예외 없이 통과

    def test_apply_reports_shadow_seen_separately_from_confirmed_complete(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [
            _comment("shadow1", "2026-07-15T00:00:00+0000"),
            _comment("done1", "2026-07-15T01:00:00+0000"),
        ])
        ces.try_claim("instagram_comment", "shadow1", claimed_by="webhook", shadow=True)
        token = ces.try_claim("instagram_comment", "done1", claimed_by="webhook")
        ces.mark_airtable_done("instagram_comment", "done1", token)  # status=COMPLETED

        _apply("m1")

        out = capsys.readouterr().out
        assert "shadow-미검증" in out
        assert "기존 확정완료=1" in out


class TestActivate:
    def test_activate_without_verify_fails(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        with pytest.raises(cli.BaselineError):
            _activate("m1")
        assert pt.get_target("m1")["state"] == "PENDING_BASELINE"

    def test_activate_rejects_config_drift_after_verify(self, monkeypatch):
        """260716 Codex 7차 리뷰 P1 — verify 통과 후 activate 전에 캠페인 JSON이
        바뀌면(이 media 자체가 빠지지 않는 변경이라도) activate를 거부해야 한다."""
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        cli.cmd_verify("m1")
        cfg._CONFIG_PATH.write_text(json.dumps({"media_ids": ["m1", "m2"]}), encoding="utf-8")
        with pytest.raises(cli.BaselineError):
            _activate("m1")
        assert pt.get_target("m1")["state"] == "PENDING_BASELINE"

    def test_activate_hard_blocks_when_allowlist_mode_off(self, monkeypatch):
        """P0(260716 Codex 8차 리뷰, 실제 재현 확인) — allowlist+shadow 조합에서
        ACTIVE media는 다음 폴링 주기에 실제 발송으로 이어질 수 있다("경고만"은
        틀린 판단이었음). 두 모드가 모두 확정 전이면 activate 자체를 거부한다."""
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        cli.cmd_verify("m1")
        monkeypatch.delenv("COMMENT_POLL_ALLOWLIST_MODE", raising=False)
        with pytest.raises(cli.BaselineError):
            _activate("m1")
        assert pt.get_target("m1")["state"] == "PENDING_BASELINE"

    def test_activate_hard_blocks_when_event_store_mode_not_enforce(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        cli.cmd_verify("m1")
        monkeypatch.setenv("COMMENT_EVENT_STORE_MODE", "shadow")
        with pytest.raises(cli.BaselineError):
            _activate("m1")
        assert pt.get_target("m1")["state"] == "PENDING_BASELINE"

    def test_activate_requires_acknowledge_runtime_proof_flag(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        cli.cmd_verify("m1")
        with pytest.raises(cli.BaselineError):
            cli.cmd_activate("m1", acknowledge_runtime_proof=False)
        assert pt.get_target("m1")["state"] == "PENDING_BASELINE"

    def test_full_flow_dry_run_apply_verify_activate(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [
            _comment("old1", "2026-07-15T00:00:00+0000"),
        ])
        cli.cmd_dry_run("m1")
        _apply("m1")
        cli.cmd_verify("m1")
        _activate("m1")
        assert pt.get_target("m1")["state"] == "ACTIVE"
        assert pt.get_active_media_ids() == ["m1"]


class TestMainArgparse:
    def test_main_dry_run_exit_code_zero(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        rc = cli.main(["--media-id", "m1", "--dry-run"])
        assert rc == 0

    def test_main_apply_requires_cutover_at(self):
        rc = cli.main(["--media-id", "m1", "--apply"])
        assert rc == 1

    def test_main_apply_requires_expected_config_hash(self):
        rc = cli.main(["--media-id", "m1", "--apply", "--cutover-at", CUTOVER])
        assert rc == 1

    def test_main_unknown_media_exit_code_one(self):
        rc = cli.main(["--media-id", "does-not-exist", "--dry-run"])
        assert rc == 1

    def test_main_activate_requires_confirm_flag(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_all_comments", lambda media_id: [])
        _apply("m1")
        cli.cmd_verify("m1")
        rc = cli.main(["--media-id", "m1", "--activate"])
        assert rc == 1
