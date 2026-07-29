"""9-10-3-E Defect E — collect_kpi()가 Airtable 조회 실패를 "진짜 0건"과 구분해서
result["fetch_errors"]에 남기는지 검증한다(_fetch_leads/_fetch_posts의 기존
"실패 시 빈 리스트 반환" 하위호환 계약은 손대지 않는다 — 기존 회귀도 함께 확인).

Runtime 상태변경(Airtable Write, 실제 네트워크 호출) 없이 Mock으로만 검증한다.
"""

from unittest.mock import patch

from modules.metrics.kpi_collector import (
    collect_kpi,
    _fetch_leads,
    _fetch_posts,
)


def test_collect_kpi_no_errors_when_both_fetches_succeed():
    with patch("modules.metrics.kpi_collector.AirtableRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.fetch_all_instagram_posts.return_value = [{"post_status": "posted"}]
        mock_repo.fetch_all_lead_interactions.return_value = [{"lead_status": "converted"}]

        result = collect_kpi("today")

        assert result["fetch_errors"] == []
        assert result["upload"]["total"] == 1
        assert result["lead"]["total"] == 1


def test_collect_kpi_marks_upload_fetch_failure_distinct_from_zero_posts():
    with patch("modules.metrics.kpi_collector.AirtableRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.fetch_all_instagram_posts.side_effect = Exception("429 too many requests")
        mock_repo.fetch_all_lead_interactions.return_value = []

        result = collect_kpi("today")

        assert result["fetch_errors"] == ["upload"]
        assert result["upload"]["total"] == 0
        assert result["upload"]["success_rate"] == 0.0
        # lead 쪽은 실제로 성공한 진짜 0건이므로 fetch_errors에 없어야 한다
        assert "lead" not in result["fetch_errors"]


def test_collect_kpi_marks_lead_fetch_failure():
    with patch("modules.metrics.kpi_collector.AirtableRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.fetch_all_instagram_posts.return_value = []
        mock_repo.fetch_all_lead_interactions.side_effect = Exception("429 too many requests")

        result = collect_kpi("today")

        assert result["fetch_errors"] == ["lead"]
        assert result["lead"]["total"] == 0


def test_collect_kpi_marks_both_fetch_failures():
    with patch("modules.metrics.kpi_collector.AirtableRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.fetch_all_instagram_posts.side_effect = Exception("boom")
        mock_repo.fetch_all_lead_interactions.side_effect = Exception("boom")

        result = collect_kpi("today")

        assert result["fetch_errors"] == ["upload", "lead"]


class TestExistingFetchHelpersUnchanged:
    """_fetch_leads/_fetch_posts의 기존 하위호환 계약(실패 시 빈 리스트)이 그대로인지
    재확인 — Defect E 수정이 이 계약을 건드리지 않았음을 보장한다."""

    def test_fetch_leads_returns_empty_list_on_exception(self):
        with patch("modules.metrics.kpi_collector.AirtableRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.fetch_all_lead_interactions.side_effect = Exception("Airtable down")
            assert _fetch_leads(None) == []

    def test_fetch_posts_returns_empty_list_on_exception(self):
        with patch("modules.metrics.kpi_collector.AirtableRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.fetch_all_instagram_posts.side_effect = Exception("Airtable down")
            assert _fetch_posts() == []
