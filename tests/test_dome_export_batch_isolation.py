"""9-10-3-C Defect D — export_to_instagram_posts()의 claim/중복확인/상태갱신 호출 중
하나가 실패해도 그 배치의 나머지 후보 처리가 막히지 않는지 검증한다.
(ig_payload 저장 자체와 caption/imgbb 재시도 로직은 기존 설계 그대로이며 HOLD 대상이라
건드리지 않는다 — 이 테스트도 그 부분은 항상 성공하는 것으로 고정한다.)

Runtime 상태변경(Airtable Write, 실제 네트워크 호출) 없이 Mock으로만 검증한다.
"""

import pytest


def _import_source_exporter(monkeypatch):
    from modules.crawlers import source_exporter
    monkeypatch.setattr(source_exporter, "generate_caption", lambda text: ("caption", "#tag"))
    monkeypatch.setattr(
        source_exporter,
        "upload_to_imgbb",
        lambda url: {"success": True, "public_url": f"https://img.example/{url}", "content_hash": f"hash-{url}"},
    )
    return source_exporter


class _FakeRepo:
    def __init__(self, items, fail_on=None):
        """fail_on: {"claim"|"exists"|"status": {source_item_id, ...}}"""
        self._items = items
        self._fail_on = fail_on or {}
        self.claimed = []
        self.saved = []
        self.statuses = []

    def validate_instagram_post_context(self, account, classification, canary=""):
        return {
            "account_code": account,
            "credential_key": "YUNA",
            "api_provider": "facebook_login",
            "ig_user_id": "x",
        }

    def recover_stale_queued_source_items(self, threshold):
        return 0

    def fetch_source_items_for_export(self, batch_size=3, target_id=None):
        return self._items

    def _maybe_fail(self, method, sid):
        if sid in self._fail_on.get(method, set()):
            raise RuntimeError(f"{method} 실패(시뮬레이션): {sid}")

    def claim_source_item_for_export(self, record_id, started_at, account):
        self._maybe_fail("claim", record_id)
        self.claimed.append(record_id)

    def exists_post_by_image_url(self, image_url):
        self._maybe_fail("exists", image_url)
        return False

    def save_instagram_post(self, payload):
        self.saved.append(payload["source_item_id"])
        return "rec-post"

    def update_source_item_status(self, record_id, status):
        self._maybe_fail("status", record_id)
        self.statuses.append((record_id, status))

    def update_source_item_retry(self, *args):
        raise AssertionError("이 테스트 범위에서는 caption/imgbb/save 재시도가 호출되면 안 됨")


def _item(sid):
    return {
        "record_id": sid,
        "source_item_id": sid,
        "title": "item",
        "image_url": sid,
        "source_url": "",
        "export_retry_count": 0,
        "account_code_ref": "IDN-000041",
    }


class TestDomeExportBatchIsolation:
    def test_claim_failure_on_one_item_does_not_block_the_rest(self, monkeypatch):
        source_exporter = _import_source_exporter(monkeypatch)
        repo = _FakeRepo([_item("good"), _item("claim-fail")], fail_on={"claim": {"claim-fail"}})
        monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: repo)

        result = source_exporter.export_to_instagram_posts(
            batch_size=5,
            dry_run=False,
            target_publish_account_code_ref="IDN-000041",
            data_classification="production",
        )

        assert result["exported"] == 1
        assert result["failed"] == 1
        assert repo.saved == ["good"]

    def test_exists_check_failure_on_one_item_does_not_block_the_rest(self, monkeypatch):
        source_exporter = _import_source_exporter(monkeypatch)
        repo = _FakeRepo([_item("exists-fail"), _item("good")], fail_on={"exists": {"exists-fail"}})
        monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: repo)

        result = source_exporter.export_to_instagram_posts(
            batch_size=5,
            dry_run=False,
            target_publish_account_code_ref="IDN-000041",
            data_classification="production",
        )

        assert result["exported"] == 1
        assert result["failed"] == 1
        assert repo.saved == ["good"]

    def test_status_update_failure_after_successful_ig_save_is_counted_separately(self, monkeypatch):
        source_exporter = _import_source_exporter(monkeypatch)
        repo = _FakeRepo(
            [_item("status-fail"), _item("good")], fail_on={"status": {"status-fail"}}
        )
        monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: repo)

        result = source_exporter.export_to_instagram_posts(
            batch_size=5,
            dry_run=False,
            target_publish_account_code_ref="IDN-000041",
            data_classification="production",
        )

        # IG 저장은 이미 성공했으므로 saved에는 두 항목 다 들어있어야 한다(실제 게시 데이터
        # 유실 없음). 반환 계약(exported/skipped/failed)은 기존 그대로 유지하며, 상태갱신만
        # 실패한 경우는 failed로 집계하되 구조화 로그로 "IG 저장은 이미 성공"을 구분해 남긴다.
        assert repo.saved == ["status-fail", "good"]
        assert result["exported"] == 1
        assert result["failed"] == 1

    def test_all_items_succeed_unaffected(self, monkeypatch):
        source_exporter = _import_source_exporter(monkeypatch)
        repo = _FakeRepo([_item("a"), _item("b")])
        monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: repo)

        result = source_exporter.export_to_instagram_posts(
            batch_size=5,
            dry_run=False,
            target_publish_account_code_ref="IDN-000041",
            data_classification="production",
        )

        assert result == {"exported": 2, "skipped": 0, "failed": 0}
