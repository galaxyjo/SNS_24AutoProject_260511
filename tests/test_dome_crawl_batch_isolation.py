"""9-10-3-B Defect C — Dome Crawl에서 타겟·아이템 1건 실패가 나머지 정상 데이터의
수집을 막지 않는지 검증한다(launcher/main.py::_job_dome_crawl()만 대상).

Runtime 상태변경(Airtable Write, 실제 네트워크 호출) 없이 Mock으로만 검증한다.
"""

import pytest


class _FakeRepo:
    def __init__(self, targets):
        self._targets = targets
        self.saved: list[str] = []
        self.statuses: list[tuple] = []

    def fetch_active_crawl_targets(self):
        return self._targets

    def find_source_item_by_hash(self, content_hash):
        return None

    def save_source_item(self, item):
        self.saved.append(item["content_hash"])
        return f"rec-{item['content_hash']}"

    def update_source_item_status(self, record_id, status):
        self.statuses.append((record_id, status))


class _FakeConnector:
    """target_id별로 fetch() 결과 또는 예외를 미리 지정."""

    def __init__(self, responses: dict):
        self._responses = responses

    def fetch(self, target: dict) -> list:
        outcome = self._responses[target["target_id"]]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _item(content_hash, quality_status="READY"):
    return {
        "source_item_id": f"src-{content_hash}",
        "source_platform": "domeggook",
        "title": "item",
        "currency": "KRW",
        "content_hash": content_hash,
        "quality_status": quality_status,
        "collected_at": "2026-07-29T00:00:00.000Z",
    }


def _import_launcher_main(monkeypatch, targets, connector_responses, gate_fn=None):
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository",
        lambda: _FakeRepo(targets),
    )
    monkeypatch.setattr(
        "modules.crawlers.domeggook_api_connector.DomeggookApiConnector",
        lambda: _FakeConnector(connector_responses),
    )
    monkeypatch.setattr(
        "modules.crawlers.quality_gate.run_gate",
        gate_fn or (lambda items: items),
    )
    from launcher import main as launcher_main
    return launcher_main


def _target(target_id):
    return {"target_id": target_id, "platform": "domeggook", "keyword": "", "category_code": ""}


class TestDomeCrawlBatchIsolation:
    def test_one_target_fetch_failure_does_not_block_other_targets(self, monkeypatch, caplog):
        targets = [_target("D001"), _target("D002")]
        connector_responses = {
            "D001": RuntimeError("Domeggook API 오류"),
            "D002": [_item("hash-b")],
        }
        launcher_main = _import_launcher_main(monkeypatch, targets, connector_responses)

        with caplog.at_level("INFO"):
            launcher_main._job_dome_crawl()

        assert any("타겟 처리 실패" in r.message and "D001" in r.message for r in caplog.records)
        assert any("D002 fetch=1 ready=1" in r.message for r in caplog.records)

    def test_one_item_save_failure_does_not_block_other_items(self, monkeypatch, caplog):
        targets = [_target("D001")]
        connector_responses = {"D001": [_item("hash-good"), _item("hash-bad")]}
        launcher_main = _import_launcher_main(monkeypatch, targets, connector_responses)

        real_repo = _FakeRepo(targets)

        def _save_source_item(item):
            if item["content_hash"] == "hash-bad":
                raise RuntimeError("저장 실패(시뮬레이션)")
            real_repo.saved.append(item["content_hash"])
            return f"rec-{item['content_hash']}"

        real_repo.save_source_item = _save_source_item
        monkeypatch.setattr(
            "modules.infra.airtable_repository.AirtableRepository", lambda: real_repo
        )

        with caplog.at_level("INFO"):
            launcher_main._job_dome_crawl()

        assert real_repo.saved == ["hash-good"]
        assert any(
            "아이템 저장 실패" in r.message and "hash-bad" in r.message for r in caplog.records
        )

    def test_all_targets_failing_raises_for_handle_errors_slack_path(self, monkeypatch):
        targets = [_target("D001"), _target("D002")]
        connector_responses = {
            "D001": RuntimeError("실패1"),
            "D002": RuntimeError("실패2"),
        }
        launcher_main = _import_launcher_main(monkeypatch, targets, connector_responses)

        # _job_dome_crawl는 @handle_errors로 감싸여 예외를 삼키므로, 데코레이터 없는
        # 원본 함수(__wrapped__)를 직접 호출해 예외 전파 자체를 검증한다.
        with pytest.raises(launcher_main.DomeCrawlAllTargetsFailedError):
            launcher_main._job_dome_crawl.__wrapped__()
