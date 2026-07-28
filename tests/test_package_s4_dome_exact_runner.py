"""8단계 Safety Package S4 — Dome Exact-Record Runner 테스트."""

import sys
import types
from unittest.mock import MagicMock

import pytest

from modules.common.canary_execution_guard import CanaryWriteOperation

# S4는 승인된 caption·기존 image URL만 사용한다. 선택적 AI/ImgBB SDK는 이
# Package의 import 및 테스트 대상이 아니므로 실제 모듈 import 전에 격리한다.
_caption_module = types.ModuleType("modules.sns.caption_generator")
_caption_module.generate_caption = MagicMock(
    side_effect=AssertionError("Caption AI 호출 금지")
)
sys.modules.setdefault("modules.sns.caption_generator", _caption_module)
_image_module = types.ModuleType("modules.sns.image_hosting")
_image_module.upload_to_imgbb = MagicMock(
    side_effect=AssertionError("ImgBB 호출 금지")
)
sys.modules.setdefault("modules.sns.image_hosting", _image_module)

from modules.crawlers import source_exporter
from modules.crawlers.source_exporter import DomeCanaryError
from modules.infra.repository_interface import (
    RepositoryValidationError,
    SourceItemStatus,
)


def _ready_item(**overrides):
    item = {
        "record_id": "recSource123",
        "source_item_id": "DG-123",
        "quality_status": "READY",
        "pipeline_status": "NEW",
        "account_code_ref": "",
        "source_url": "https://dome.example/item/123",
    }
    item.update(overrides)
    return item


class _Guard:
    def __init__(self, events):
        self.events = events

    def authorize_write(self, operation, **kwargs):
        self.events.append(("authorize", operation, kwargs.get("record_id", "")))
        return 1


def test_repository_exact_record_get_maps_required_fields(monkeypatch):
    from modules.infra.airtable_repository import AirtableRepository

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "id": "recSource123",
        "fields": {
            "source_item_id": "DG-123",
            "quality_status": "READY",
            "pipeline_status": "NEW",
            "account_code_ref": "IDN-000041",
            "image_url": "https://source.example/item.jpg",
        },
    }
    get = MagicMock(return_value=response)
    monkeypatch.setattr("modules.infra.airtable_repository.requests.get", get)
    monkeypatch.setattr(
        "modules.infra.airtable_repository.log_api_call", lambda *a, **k: None
    )

    item = AirtableRepository().get_source_item_by_record_id("recSource123")

    assert get.call_args.args[0].endswith("/Source_Items/recSource123")
    assert item["record_id"] == "recSource123"
    assert item["quality_status"] == "READY"
    assert item["pipeline_status"] == "NEW"
    assert item["account_code_ref"] == "IDN-000041"


def test_repository_invalid_record_id_calls_airtable_get_zero_times(monkeypatch):
    from modules.infra.airtable_repository import AirtableRepository

    get = MagicMock()
    monkeypatch.setattr("modules.infra.airtable_repository.requests.get", get)
    with pytest.raises(RepositoryValidationError):
        AirtableRepository().get_source_item_by_record_id("not-a-record")
    get.assert_not_called()


@pytest.mark.parametrize(
    "image_url",
    [
        "",
        "http://img.example/existing.jpg",
        "https://facebook.com/photo/123",
        "https://scontent.fbcdn.net/photo.jpg",
    ],
)
def test_invalid_approved_image_stops_before_repository(monkeypatch, image_url):
    repo = MagicMock()
    monkeypatch.setattr(source_exporter, "AirtableRepository", repo)

    with pytest.raises(DomeCanaryError):
        source_exporter.export_exact_source_item_canary(
            source_record_id="recSource123",
            approved_image_url=image_url,
            approved_caption="Approved",
            canary_run_id="canary-s4",
            write_guard=_Guard([]),
        )

    repo.assert_not_called()


def test_invalid_source_record_id_stops_before_repository(monkeypatch):
    repo = MagicMock()
    monkeypatch.setattr(source_exporter, "AirtableRepository", repo)

    with pytest.raises(DomeCanaryError):
        source_exporter.export_exact_source_item_canary(
            source_record_id="recSource123/other",
            approved_image_url="https://img.example/existing.jpg",
            approved_caption="Approved",
            canary_run_id="canary-s4",
            write_guard=_Guard([]),
        )

    repo.assert_not_called()


def test_exact_runner_success_uses_only_one_record_and_two_patches(monkeypatch):
    events = []

    class _Repo:
        def validate_instagram_post_context(self, account, classification, run_id, status):
            events.append(("validate", classification, status))
            return {"account_code": account}

        def get_source_item_by_record_id(self, record_id):
            events.append(("get_exact", record_id))
            return _ready_item(record_id=record_id)

        def fetch_source_items_for_export(self, *args, **kwargs):
            raise AssertionError("Batch 조회 금지")

        def recover_stale_queued_source_items(self, *args, **kwargs):
            raise AssertionError("stale 복구 금지")

        def exists_post_by_image_url(self, image_url):
            events.append(("dedup", image_url))
            return False

        def claim_source_item_for_export(self, record_id, started_at, account):
            events.append(("claim", record_id, account))

        def save_instagram_post(self, payload):
            events.append(("save", dict(payload)))
            return "recPost123"

        def update_source_item_status(self, record_id, status, reason_code=""):
            events.append(("status", record_id, status, reason_code))

    monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: _Repo())
    monkeypatch.setattr(
        source_exporter,
        "upload_to_imgbb",
        MagicMock(side_effect=AssertionError("ImgBB 호출 금지")),
    )
    monkeypatch.setattr(
        source_exporter,
        "generate_caption",
        MagicMock(side_effect=AssertionError("Caption AI 호출 금지")),
    )

    result = source_exporter.export_exact_source_item_canary(
        source_record_id="recSource123",
        approved_image_url="https://img.example/existing.jpg",
        approved_caption="Approved caption",
        canary_run_id="canary-s4",
        write_guard=_Guard(events),
    )

    assert result == {
        "created": 1,
        "post_record_id": "recPost123",
        "source_record_id": "recSource123",
        "post_status": "draft",
    }
    assert [event[0] for event in events] == [
        "validate",
        "get_exact",
        "dedup",
        "authorize",
        "claim",
        "authorize",
        "save",
        "authorize",
        "status",
    ]
    assert events[-1][2] == SourceItemStatus.EXPORTED
    payload = next(event[1] for event in events if event[0] == "save")
    assert payload["post_status"] == "draft"
    assert payload["data_classification"] == "test"
    assert payload["account_code_ref"] == "IDN-000041"


def test_duplicate_image_stops_before_any_patch(monkeypatch):
    events = []

    class _Repo:
        def validate_instagram_post_context(self, *args):
            return {"account_code": "IDN-000041"}

        def get_source_item_by_record_id(self, record_id):
            return _ready_item(record_id=record_id)

        def exists_post_by_image_url(self, image_url):
            return True

    monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: _Repo())
    with pytest.raises(DomeCanaryError, match="기존 Post"):
        source_exporter.export_exact_source_item_canary(
            source_record_id="recSource123",
            approved_image_url="https://img.example/existing.jpg",
            approved_caption="Approved",
            canary_run_id="canary-s4",
            write_guard=_Guard(events),
        )

    assert events == []


@pytest.mark.parametrize(
    "item",
    [
        _ready_item(record_id="recOther"),
        _ready_item(source_item_id=""),
        _ready_item(quality_status="FILTERED"),
        _ready_item(pipeline_status="QUEUED"),
        _ready_item(account_code_ref="IDN-000036"),
    ],
)
def test_invalid_exact_source_stops_before_patch(monkeypatch, item):
    events = []

    class _Repo:
        def validate_instagram_post_context(self, *args):
            return {"account_code": "IDN-000041"}

        def get_source_item_by_record_id(self, record_id):
            return item

        def exists_post_by_image_url(self, image_url):
            return False

        def claim_source_item_for_export(self, *args):
            events.append("claim")

    monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: _Repo())
    with pytest.raises(DomeCanaryError):
        source_exporter.export_exact_source_item_canary(
            source_record_id="recSource123",
            approved_image_url="https://img.example/existing.jpg",
            approved_caption="Approved",
            canary_run_id="canary-s4",
            write_guard=_Guard(events),
        )
    assert events == []


def test_post_create_failure_uses_second_patch_to_reject_source(monkeypatch):
    events = []

    class _Repo:
        def validate_instagram_post_context(self, *args):
            return {"account_code": "IDN-000041"}

        def get_source_item_by_record_id(self, record_id):
            return _ready_item(record_id=record_id)

        def exists_post_by_image_url(self, image_url):
            return False

        def claim_source_item_for_export(self, record_id, started_at, account):
            events.append(("claim", record_id))

        def save_instagram_post(self, payload):
            events.append(("save_failed",))
            raise RuntimeError("expected")

        def update_source_item_status(self, record_id, status, reason_code=""):
            events.append(("status", status, reason_code))

    monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: _Repo())
    with pytest.raises(RuntimeError, match="expected"):
        source_exporter.export_exact_source_item_canary(
            source_record_id="recSource123",
            approved_image_url="https://img.example/existing.jpg",
            approved_caption="Approved",
            canary_run_id="canary-s4",
            write_guard=_Guard(events),
        )

    authorizations = [event for event in events if event[0] == "authorize"]
    assert authorizations == [
        ("authorize", CanaryWriteOperation.SOURCE_ITEM_PATCH, "recSource123"),
        ("authorize", CanaryWriteOperation.INSTAGRAM_POST_CREATE, ""),
        ("authorize", CanaryWriteOperation.SOURCE_ITEM_PATCH, "recSource123"),
    ]
    assert events[-1] == ("status", SourceItemStatus.REJECTED, "CANARY_FAILED")


def test_final_patch_failure_never_attempts_a_third_patch(monkeypatch):
    events = []

    class _Repo:
        def validate_instagram_post_context(self, *args):
            return {"account_code": "IDN-000041"}

        def get_source_item_by_record_id(self, record_id):
            return _ready_item(record_id=record_id)

        def exists_post_by_image_url(self, image_url):
            return False

        def claim_source_item_for_export(self, *args):
            events.append(("claim",))

        def save_instagram_post(self, payload):
            events.append(("save",))
            return "recPost123"

        def update_source_item_status(self, *args, **kwargs):
            events.append(("status_failed",))
            raise RuntimeError("final patch failed")

    monkeypatch.setattr(source_exporter, "AirtableRepository", lambda: _Repo())
    with pytest.raises(RuntimeError, match="final patch failed"):
        source_exporter.export_exact_source_item_canary(
            source_record_id="recSource123",
            approved_image_url="https://img.example/existing.jpg",
            approved_caption="Approved",
            canary_run_id="canary-s4",
            write_guard=_Guard(events),
        )

    patch_authorizations = [
        event
        for event in events
        if event[0] == "authorize"
        and event[1] == CanaryWriteOperation.SOURCE_ITEM_PATCH
    ]
    assert len(patch_authorizations) == 2
    assert events.count(("status_failed",)) == 1


def test_runner_cli_has_no_batch_publish_or_imgbb_override():
    from tools.run_dome_canary import build_parser

    destinations = {action.dest for action in build_parser()._actions}
    assert "batch_size" not in destinations
    assert "publish" not in destinations
    assert "imgbb" not in destinations
    assert "target_publish_account_code_ref" not in destinations


def test_tool_begins_runs_and_completes(monkeypatch):
    from tools import run_dome_canary

    events = []

    class _GuardImpl:
        def __init__(self, run_id, source, budget):
            events.append(("guard", run_id, source, budget.route.value))

        def begin(self):
            events.append(("begin",))

        def complete(self):
            events.append(("complete",))

        def fail(self, code):
            events.append(("fail", code))

    def _run(**kwargs):
        events.append(("run", kwargs["target_publish_account_code_ref"]))
        return {"created": 1}

    monkeypatch.setattr(run_dome_canary, "CanaryExecutionGuard", _GuardImpl)
    monkeypatch.setattr(run_dome_canary, "export_exact_source_item_canary", _run)

    result = run_dome_canary.execute_dome_canary(
        canary_run_id="canary-s4",
        source_record_id="recSource123",
        approved_image_url="https://img.example/existing.jpg",
        approved_caption="Approved",
    )

    assert result == {"created": 1}
    assert events == [
        ("guard", "canary-s4", "recSource123", "dome"),
        ("begin",),
        ("run", "IDN-000041"),
        ("complete",),
    ]


def test_tool_marks_failed_and_never_completes_after_runner_error(monkeypatch):
    from tools import run_dome_canary

    events = []

    class _GuardImpl:
        def __init__(self, run_id, source, budget):
            events.append(("guard", run_id, source, budget.route.value))

        def begin(self):
            events.append(("begin",))

        def complete(self):
            events.append(("complete",))

        def fail(self, code):
            events.append(("fail", code))

    def _run(**kwargs):
        events.append(("run",))
        raise DomeCanaryError("expected")

    monkeypatch.setattr(run_dome_canary, "CanaryExecutionGuard", _GuardImpl)
    monkeypatch.setattr(run_dome_canary, "export_exact_source_item_canary", _run)

    with pytest.raises(DomeCanaryError, match="expected"):
        run_dome_canary.execute_dome_canary(
            canary_run_id="canary-s4",
            source_record_id="recSource123",
            approved_image_url="https://img.example/existing.jpg",
            approved_caption="Approved",
        )

    assert events == [
        ("guard", "canary-s4", "recSource123", "dome"),
        ("begin",),
        ("run",),
        ("fail", "DOMECANARYERROR"),
    ]
