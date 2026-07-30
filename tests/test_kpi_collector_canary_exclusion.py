"""10.6-5B(ERR-095에서 원복됐던 설계를 별도 승인 하 재구현, 260731) —
_upload_stats()가 insta_post_code="IP-CANARY-"로 시작하는 레코드를 운영 KPI
집계에서 제외하는지, 그리고 None/누락 값에도 안전한지 검증한다(Codex P2 반영).

Runtime 상태변경 없이 순수 함수 호출만으로 검증한다.
"""

from modules.metrics.kpi_collector import _upload_stats


def test_canary_prefixed_post_excluded_from_upload_stats():
    posts = [
        {"insta_post_code": "IP-000123", "post_status": "posted"},
        {"insta_post_code": "IP-CANARY-AI-260730-2", "post_status": "posted"},
    ]

    stats = _upload_stats(posts)

    assert stats["total"] == 1
    assert stats["posted"] == 1


def test_non_canary_posts_unaffected_existing_behavior():
    posts = [
        {"insta_post_code": "IP-000123", "post_status": "posted"},
        {"insta_post_code": "IP-000124", "post_status": "ready"},
        {"insta_post_code": "IP-000125", "post_status": "failed"},
    ]

    stats = _upload_stats(posts)

    assert stats["total"] == 3
    assert stats["posted"] == 1
    assert stats["ready"] == 1
    assert stats["failed"] == 1


def test_missing_insta_post_code_field_not_excluded():
    posts = [{"post_status": "posted"}]

    stats = _upload_stats(posts)

    assert stats["total"] == 1
    assert stats["posted"] == 1


def test_none_insta_post_code_value_does_not_crash():
    """Codex P2 지적(260730) — 필드가 존재하되 값이 None이면 기존 .get(k, "")는
    기본값을 못 주고 .startswith()가 AttributeError를 던진다. (or "") 로 방어."""
    posts = [{"insta_post_code": None, "post_status": "posted"}]

    stats = _upload_stats(posts)

    assert stats["total"] == 1
    assert stats["posted"] == 1


def test_success_rate_denominator_excludes_canary_posts():
    """성공률 계산의 분모(total)에도 Canary가 안 들어가는지(Codex가 지적했던
    누락 테스트 커버)."""
    posts = [
        {"insta_post_code": "IP-000123", "post_status": "posted"},
        {"insta_post_code": "IP-000124", "post_status": "failed"},
        {"insta_post_code": "IP-CANARY-AI-260730-2", "post_status": "posted"},
    ]

    stats = _upload_stats(posts)

    assert stats["total"] == 2
    assert stats["success_rate"] == 50.0
