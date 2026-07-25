"""tests/test_airtable_repository_pagination.py — 260725 10단계 KPI 조사 중 발견된
fetch_all_instagram_posts()/fetch_all_lead_interactions() 미페이지네이션 버그 회귀 방지.
Airtable API가 100건 초과 시 반환하는 offset을 따라가지 않아 첫 페이지(최대 100건)만
반환하던 문제 — 실제 네트워크 호출 없이 requests.get만 mock으로 검증한다."""

from unittest.mock import MagicMock, patch

from modules.infra.airtable_repository import AirtableRepository


def _page_response(records: list[dict], offset: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    body = {"records": records}
    if offset:
        body["offset"] = offset
    resp.json.return_value = body
    return resp


class TestFetchAllInstagramPostsPagination:
    def test_single_page_no_offset(self):
        page = _page_response([{"id": "rec1", "fields": {"post_status": "posted"}}])
        with patch("modules.infra.airtable_repository.requests.get", return_value=page) as mock_get:
            result = AirtableRepository().fetch_all_instagram_posts()
            assert result == [{"id": "rec1", "post_status": "posted"}]
            assert mock_get.call_count == 1

    def test_two_pages_follows_offset_and_aggregates_all_records(self):
        page1 = _page_response([{"id": "rec1", "fields": {"post_status": "posted"}}], offset="pageCursor1")
        page2 = _page_response([{"id": "rec2", "fields": {"post_status": "failed"}}])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            result = AirtableRepository().fetch_all_instagram_posts()
            assert result == [
                {"id": "rec1", "post_status": "posted"},
                {"id": "rec2", "post_status": "failed"},
            ]
            assert mock_get.call_count == 2
            second_call_params = mock_get.call_args_list[1].kwargs["params"]
            assert second_call_params["offset"] == "pageCursor1"

    def test_three_pages_594_records_none_dropped(self):
        """실제 발견 사례 재현 축소판 — 100건 초과 다중 페이지에서도 전량 반환돼야 한다."""
        page1 = _page_response(
            [{"id": f"rec{i}", "fields": {"post_status": "posted"}} for i in range(100)],
            offset="cursorA",
        )
        page2 = _page_response(
            [{"id": f"rec{i}", "fields": {"post_status": "posted"}} for i in range(100, 200)],
            offset="cursorB",
        )
        page3 = _page_response(
            [{"id": f"rec{i}", "fields": {"post_status": "posted"}} for i in range(200, 210)]
        )
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2, page3]):
            result = AirtableRepository().fetch_all_instagram_posts()
            assert len(result) == 210


class TestFetchAllLeadInteractionsPagination:
    def test_two_pages_follows_offset_and_aggregates_all_records(self):
        page1 = _page_response([{"id": "lead1", "fields": {"lead_status": "new"}}], offset="pageCursor1")
        page2 = _page_response([{"id": "lead2", "fields": {"lead_status": "converted"}}])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            result = AirtableRepository().fetch_all_lead_interactions()
            assert result == [
                {"id": "lead1", "lead_status": "new"},
                {"id": "lead2", "lead_status": "converted"},
            ]
            assert mock_get.call_count == 2

    def test_since_utc_filter_preserved_across_all_pages(self):
        page1 = _page_response([{"id": "lead1", "fields": {}}], offset="cursorA")
        page2 = _page_response([{"id": "lead2", "fields": {}}])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            AirtableRepository().fetch_all_lead_interactions(since_utc="2026-07-01T00:00:00.000Z")
            for call in mock_get.call_args_list:
                assert call.kwargs["params"]["filterByFormula"] == "{relay_scheduled_at}>='2026-07-01T00:00:00.000Z'"

    def test_no_since_utc_omits_filter(self):
        page1 = _page_response([{"id": "lead1", "fields": {}}])
        with patch("modules.infra.airtable_repository.requests.get", return_value=page1) as mock_get:
            AirtableRepository().fetch_all_lead_interactions()
            assert "filterByFormula" not in mock_get.call_args.kwargs["params"]
