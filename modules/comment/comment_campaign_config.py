# modules/comment/comment_campaign_config.py
# 캠페인 게시물 allowlist 공용 loader (260715, Package 1 Phase A)
#
# configs/comment_campaign_posts.json을 comment_safety_guard(발송 게이트)와
# comment_poll_targets(감시 대상 상태머신)가 서로 다르게 해석하면(중복 처리, 빈 문자열
# 통과 등) 두 목록이 어긋나는 사고가 재발한다(260715 이번에 잡은 버그의 원인 패턴).
# 이 모듈 하나만 두 곳 모두 사용하도록 강제한다.

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "comment_campaign_posts.json"


class CampaignConfigError(Exception):
    """파일 손상/스키마 위반 — 호출부는 반드시 fail-closed(이번 주기 처리 생략)로 대응해야 한다."""


def load_campaign_media_ids(path: Path | None = None) -> list[str]:
    """캠페인 media_id 목록을 검증된 리스트로 반환.
    - 파일 없음/파싱 실패/스키마 위반(media_ids 누락, list가 아님, 빈 문자열/비문자열
      포함) → 전부 CampaignConfigError. "의도적으로 캠페인이 0개"는 파일이 실제로
      존재하며 {"media_ids": []}여야 한다 — 파일 자체가 없는 건 실수로 지워졌거나
      배포/권한 문제일 수 있어 "빈 리스트"와 구분해야 한다(260715 Codex 6차 리뷰
      P1 — sync_from_campaign_json()이 파일 소실을 "캠페인 전부 제거"로 오인해
      이미 ACTIVE인 media를 전부 PAUSED시키는 사고 방지). 호출부는 이 예외를
      "빈 리스트"로 대체하면 안 된다.
    - 중복 media_id는 에러가 아니라 조용히 제거(순서는 최초 등장 기준 유지).
    - 앞뒤 공백은 정규화(strip)한다 — 공백 포함 media_id가 그대로 저장되면 실제
      Graph API media_id와 영원히 매칭 안 되는 유령 항목이 생긴다.
    - path 인자는 테스트 격리 용도(기본은 이 모듈의 _CONFIG_PATH = 실제 운영 파일).
      운영 코드(comment_safety_guard/comment_poll_targets)는 항상 같은 물리 파일을
      가리키므로 인자 없이 호출하는 것이 원칙이다."""
    target = path or _CONFIG_PATH
    if not target.exists():
        raise CampaignConfigError(f"{target} 파일 없음 — 첫 실행이면 빈 파일({{\"media_ids\": []}})을 명시적으로 생성할 것")
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CampaignConfigError(f"{target} 파싱 실패: {exc}") from exc

    if not isinstance(raw, dict) or "media_ids" not in raw:
        raise CampaignConfigError(f"{target} 스키마 위반: media_ids 키 없음")

    media_ids = raw["media_ids"]
    if not isinstance(media_ids, list):
        raise CampaignConfigError(f"{target} 스키마 위반: media_ids가 list가 아님")

    seen: set[str] = set()
    result: list[str] = []
    for item in media_ids:
        if not isinstance(item, str) or not item.strip():
            raise CampaignConfigError(f"{target} 스키마 위반: 빈 문자열/문자열이 아닌 media_id 포함")
        normalized = item.strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
