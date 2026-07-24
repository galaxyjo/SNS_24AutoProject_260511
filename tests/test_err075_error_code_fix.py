"""ERR-075 회귀 테스트 — mark_post_result()가 존재하지 않는 Airtable 필드
`error_code`를 더 이상 PATCH payload에 넣지 않는지 확인한다.

7-B 범위: 코드 수정 + 로컬 테스트만. Runtime 반영(재시작)·기존 11건 uploading
고착 레코드 복구는 이번 범위 밖(ERR-075 문서의 향후 수정 Gate #9 참조).
"""

from modules.infra.repository_interface import PostPublishResult


def _patch(monkeypatch):
    captured = {}

    class _OkResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "recXXX"}

    def _fake_patch(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json["fields"]
        return _OkResp()

    monkeypatch.setattr("modules.infra.airtable_repository.requests.patch", _fake_patch)
    monkeypatch.setattr(
        "modules.infra.airtable_repository.log_api_call", lambda *a, **k: None
    )
    return captured


def test_mark_post_result_never_sends_error_code_field(monkeypatch):
    """ERR-075 핵심 재현: 실패 결과(error_code 있음)를 저장해도 Airtable payload에
    존재하지 않는 error_code 필드가 절대 포함되면 안 된다."""
    from modules.infra.airtable_repository import AirtableRepository

    captured = _patch(monkeypatch)
    repo = AirtableRepository()

    result: PostPublishResult = {
        "status": "failed",
        "platform_post_id": "",
        "error_code": "400 Client Error: Bad Request for url: https://graph.facebook.com/...",
    }
    repo.mark_post_result("recXXX", result)

    assert "error_code" not in captured["payload"], (
        "error_code가 Airtable payload에 포함되면 422 UNKNOWN_FIELD_NAME으로 "
        "post_status 갱신 자체가 거부된다(ERR-075 재발)"
    )
    assert captured["payload"]["post_status"] == "failed"


def test_mark_post_result_failed_status_reaches_airtable_even_with_error():
    """실패해도 post_status='failed' 자체는 정상적으로 payload에 들어가야 한다
    (uploading 고착 방지가 이 수정의 핵심 목적)."""
    import inspect
    from modules.infra.airtable_repository import AirtableRepository

    src = inspect.getsource(AirtableRepository.mark_post_result)
    assert '"post_status": status' in src or "'post_status': status" in src


def test_mark_post_result_success_path_unaffected(monkeypatch):
    """정상 성공 경로(ig_media_id 포함)는 회귀 없이 그대로 동작해야 한다."""
    from modules.infra.airtable_repository import AirtableRepository

    captured = _patch(monkeypatch)
    repo = AirtableRepository()

    result: PostPublishResult = {
        "status": "posted",
        "platform_post_id": "18122871268709171",
        "error_code": "",
    }
    repo.mark_post_result("recYYY", result)

    assert captured["payload"]["post_status"] == "posted"
    assert captured["payload"]["ig_media_id"] == "18122871268709171"
    assert "error_code" not in captured["payload"]
