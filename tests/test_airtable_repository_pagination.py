"""tests/test_airtable_repository_pagination.py — 260725 10단계 KPI 조사 중 발견된
fetch_all_instagram_posts()/fetch_all_lead_interactions() 미페이지네이션 버그 회귀 방지.
Airtable API가 100건 초과 시 반환하는 offset을 따라가지 않아 첫 페이지(최대 100건)만
반환하던 문제 — 실제 네트워크 호출 없이 requests.get만 mock으로 검증한다.
260729 P1-3: 동일 결함 클래스가 list_blocked_suppliers()에도 있어 여기에 회귀 테스트 추가."""

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


class TestListBlockedSuppliersPagination:
    def test_single_page_no_offset(self):
        page = _page_response([{"id": "rec1", "fields": {"author_name": "a", "page_name": "p", "reason_code": "r"}}])
        with patch("modules.infra.airtable_repository.requests.get", return_value=page) as mock_get:
            result = AirtableRepository().list_blocked_suppliers()
            assert len(result) == 1
            assert result[0]["author_name"] == "a"
            assert mock_get.call_count == 1

    def test_two_pages_follows_offset_and_aggregates_all_records(self):
        page1 = _page_response(
            [{"id": "rec1", "fields": {"author_name": "a1", "page_name": "p1", "reason_code": "r1"}}],
            offset="pageCursor1",
        )
        page2 = _page_response(
            [{"id": "rec2", "fields": {"author_name": "a2", "page_name": "p2", "reason_code": "r2"}}]
        )
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            result = AirtableRepository().list_blocked_suppliers()
            assert [r["author_name"] for r in result] == ["a1", "a2"]
            assert mock_get.call_count == 2
            second_call_params = mock_get.call_args_list[1].kwargs["params"]
            assert second_call_params["offset"] == "pageCursor1"

    def test_three_pages_210_records_none_dropped(self):
        page1 = _page_response(
            [{"id": f"rec{i}", "fields": {"author_name": f"a{i}", "page_name": "p", "reason_code": "r"}}
             for i in range(100)],
            offset="cursorA",
        )
        page2 = _page_response(
            [{"id": f"rec{i}", "fields": {"author_name": f"a{i}", "page_name": "p", "reason_code": "r"}}
             for i in range(100, 200)],
            offset="cursorB",
        )
        page3 = _page_response(
            [{"id": f"rec{i}", "fields": {"author_name": f"a{i}", "page_name": "p", "reason_code": "r"}}
             for i in range(200, 210)]
        )
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2, page3]):
            result = AirtableRepository().list_blocked_suppliers()
            assert len(result) == 210


class TestFetchActiveCrawlTargetsPagination:
    def test_single_page_no_offset(self):
        page = _page_response([{"id": "rec1", "fields": {"target_url": "u1", "platform": "facebook"}}])
        with patch("modules.infra.airtable_repository.requests.get", return_value=page) as mock_get:
            result = AirtableRepository().fetch_active_crawl_targets()
            assert len(result) == 1
            assert result[0]["target_url"] == "u1"
            assert mock_get.call_count == 1

    def test_two_pages_follows_offset_and_aggregates_all_records(self):
        page1 = _page_response(
            [{"id": "rec1", "fields": {"target_url": "u1", "platform": "facebook"}}], offset="pageCursor1"
        )
        page2 = _page_response([{"id": "rec2", "fields": {"target_url": "u2", "platform": "domeggook"}}])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            result = AirtableRepository().fetch_active_crawl_targets()
            assert [r["target_url"] for r in result] == ["u1", "u2"]
            assert mock_get.call_count == 2
            second_call_params = mock_get.call_args_list[1].kwargs["params"]
            assert second_call_params["offset"] == "pageCursor1"

    def test_filter_by_formula_preserved_across_all_pages(self):
        page1 = _page_response(
            [{"id": "rec1", "fields": {"target_url": "u1", "platform": "facebook"}}], offset="cursorA"
        )
        page2 = _page_response([{"id": "rec2", "fields": {"target_url": "u2", "platform": "facebook"}}])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            AirtableRepository().fetch_active_crawl_targets()
            for call in mock_get.call_args_list:
                assert call.kwargs["params"]["filterByFormula"] == (
                    "AND({status}='Active', NOT({collection_purpose}='training'))"
                )

    def test_three_pages_210_records_none_dropped(self):
        page1 = _page_response(
            [{"id": f"rec{i}", "fields": {"target_url": f"u{i}", "platform": "facebook"}} for i in range(100)],
            offset="cursorA",
        )
        page2 = _page_response(
            [{"id": f"rec{i}", "fields": {"target_url": f"u{i}", "platform": "facebook"}}
             for i in range(100, 200)],
            offset="cursorB",
        )
        page3 = _page_response(
            [{"id": f"rec{i}", "fields": {"target_url": f"u{i}", "platform": "facebook"}}
             for i in range(200, 210)]
        )
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2, page3]):
            result = AirtableRepository().fetch_active_crawl_targets()
            assert len(result) == 210


class TestFetchActiveTrainingTargetsPagination:
    def test_single_page_no_offset(self):
        page = _page_response([{"id": "rec1", "fields": {"target_url": "u1", "platform": "facebook"}}])
        with patch("modules.infra.airtable_repository.requests.get", return_value=page) as mock_get:
            result = AirtableRepository().fetch_active_training_targets(platform="facebook")
            assert len(result) == 1
            assert result[0]["target_url"] == "u1"
            assert mock_get.call_count == 1

    def test_two_pages_follows_offset_and_aggregates_all_records(self):
        page1 = _page_response(
            [{"id": "rec1", "fields": {"target_url": "u1", "platform": "facebook"}}], offset="pageCursor1"
        )
        page2 = _page_response([{"id": "rec2", "fields": {"target_url": "u2", "platform": "facebook"}}])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            result = AirtableRepository().fetch_active_training_targets(platform="facebook")
            assert [r["target_url"] for r in result] == ["u1", "u2"]
            assert mock_get.call_count == 2
            second_call_params = mock_get.call_args_list[1].kwargs["params"]
            assert second_call_params["offset"] == "pageCursor1"

    def test_filter_by_formula_includes_platform_across_all_pages(self):
        page1 = _page_response(
            [{"id": "rec1", "fields": {"target_url": "u1", "platform": "facebook"}}], offset="cursorA"
        )
        page2 = _page_response([{"id": "rec2", "fields": {"target_url": "u2", "platform": "facebook"}}])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            AirtableRepository().fetch_active_training_targets(platform="facebook")
            for call in mock_get.call_args_list:
                assert call.kwargs["params"]["filterByFormula"] == (
                    "AND({status}='Active', {collection_purpose}='training', {platform}='facebook')"
                )

    def test_three_pages_210_records_none_dropped(self):
        page1 = _page_response(
            [{"id": f"rec{i}", "fields": {"target_url": f"u{i}", "platform": "facebook"}} for i in range(100)],
            offset="cursorA",
        )
        page2 = _page_response(
            [{"id": f"rec{i}", "fields": {"target_url": f"u{i}", "platform": "facebook"}}
             for i in range(100, 200)],
            offset="cursorB",
        )
        page3 = _page_response(
            [{"id": f"rec{i}", "fields": {"target_url": f"u{i}", "platform": "facebook"}}
             for i in range(200, 210)]
        )
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2, page3]):
            result = AirtableRepository().fetch_active_training_targets(platform="facebook")
            assert len(result) == 210


class TestFetchCandidatePhashesPagination:
    def test_single_page_no_offset(self):
        page = _page_response([{"id": "rec1", "fields": {"phash": "h1"}}])
        with patch("modules.infra.airtable_repository.requests.get", return_value=page) as mock_get:
            result = AirtableRepository().fetch_candidate_phashes(limit=2000)
            assert result == ["h1"]
            assert mock_get.call_count == 1
            assert mock_get.call_args.kwargs["params"]["pageSize"] == 100

    def test_two_pages_follows_offset_and_aggregates_all_records(self):
        page1 = _page_response([{"id": "rec1", "fields": {"phash": "h1"}}], offset="pageCursor1")
        page2 = _page_response([{"id": "rec2", "fields": {"phash": "h2"}}])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            result = AirtableRepository().fetch_candidate_phashes(limit=2000)
            assert result == ["h1", "h2"]
            assert mock_get.call_count == 2
            second_call_params = mock_get.call_args_list[1].kwargs["params"]
            assert second_call_params["offset"] == "pageCursor1"

    def test_empty_phash_excluded(self):
        page = _page_response([{"id": "rec1", "fields": {"phash": ""}}, {"id": "rec2", "fields": {"phash": "h2"}}])
        with patch("modules.infra.airtable_repository.requests.get", return_value=page):
            result = AirtableRepository().fetch_candidate_phashes(limit=2000)
            assert result == ["h2"]

    def test_three_pages_210_records_none_dropped(self):
        page1 = _page_response(
            [{"id": f"rec{i}", "fields": {"phash": f"h{i}"}} for i in range(100)], offset="cursorA"
        )
        page2 = _page_response(
            [{"id": f"rec{i}", "fields": {"phash": f"h{i}"}} for i in range(100, 200)], offset="cursorB"
        )
        page3 = _page_response([{"id": f"rec{i}", "fields": {"phash": f"h{i}"}} for i in range(200, 210)])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2, page3]):
            result = AirtableRepository().fetch_candidate_phashes(limit=2000)
            assert len(result) == 210

    def test_limit_still_caps_total_across_pages(self):
        """limit=150일 때 100건짜리 1페이지 이후 두번째 요청은 나머지 50건만 요청해야 한다."""
        page1 = _page_response(
            [{"id": f"rec{i}", "fields": {"phash": f"h{i}"}} for i in range(100)], offset="cursorA"
        )
        page2 = _page_response([{"id": f"rec{i}", "fields": {"phash": f"h{i}"}} for i in range(100, 150)])
        with patch("modules.infra.airtable_repository.requests.get", side_effect=[page1, page2]) as mock_get:
            result = AirtableRepository().fetch_candidate_phashes(limit=150)
            assert len(result) == 150
            assert mock_get.call_count == 2
            assert mock_get.call_args_list[0].kwargs["params"]["pageSize"] == 100
            assert mock_get.call_args_list[1].kwargs["params"]["pageSize"] == 50
