"""modules/common/aijomoojin_scheduled_publish_job.py — 260801 Step6B 완전자동
예약게시 MVP 오케스트레이터.

흐름: due 1건 조회(신규 Repository 메서드, account_code_ref 한정)
  → PER-002 Persona Gate(기존 aijomoojin_binding_adapter, REUSE)
  → Publish Ledger Reserve(신규, unique_publish_key 중복 차단)
  → claim → publish_single_fn 호출(주입, 실제 Meta 호출은 Caller 책임)
  → Instagram 성공 ID를 Ledger에 먼저 저장(Airtable 기록보다 항상 먼저)
  → Airtable mark_post_result 시도, 실패 시 Instagram 재호출 없이
    RECEIPT_SYNC_PENDING만 기록.

이 함수는 아직 launcher/main.py의 APScheduler에 등록되지 않았다(별도 승인
대상, 260801 Step6B Gate 범위 밖) — 오케스트레이터 로직 자체만 이번 단계에서
구현·검증한다. 실제 Meta·Airtable 호출은 전부 Caller가 주입하는 repo/
publish_single_fn을 통해서만 발생하며, 이 파일 자체는 네트워크 호출을
직접 수행하지 않는다.
"""

from datetime import datetime, timezone

from modules.common import publish_ledger
from modules.common.aijomoojin_binding_adapter import (
    AIJOMOOJIN_ACCOUNT_CODE,
    verify_aijomoojin_binding,
)
from modules.common.logger import get_logger

logger = get_logger(__name__)


def run_aijomoojin_scheduled_publish(repo, publish_single_fn, now: "datetime | None" = None) -> dict:
    """단일 due Record만 처리한다(다른 계정은 fetch_due_scheduled_post 자체가
    account_code_ref=IDN-000036로 한정하므로 관여하지 않음). 반환값은 결과
    상태를 나타내는 dict — 테스트·로그 확인용."""
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()

    post = repo.fetch_due_scheduled_post(AIJOMOOJIN_ACCOUNT_CODE, now_iso)
    if post is None:
        return {"status": "no_due_record"}

    post_id = post["post_id"]
    account_code_ref = post["account_code_ref"]
    if account_code_ref != AIJOMOOJIN_ACCOUNT_CODE:
        # fetch_due_scheduled_post 자체가 계정 한정이라 정상 경로로는 도달 불가 —
        # Repository 계약 위반 방어용 이중 확인.
        logger.warning("[ScheduledPublish] 예상치 못한 계정 — 게시 차단 | rid=%s | account=%s", post_id, account_code_ref)
        return {"status": "unexpected_account_defensive_block"}

    if not verify_aijomoojin_binding(account_code_ref, repo):
        logger.warning("[ScheduledPublish] Persona Gate 실패 — 게시 차단 | rid=%s", post_id)
        return {"status": "persona_gate_blocked"}

    # MVP 한계(HOLD 대상): Instagram_Posts에 content_id 필드가 없어 Airtable
    # Record ID(post_id)를 임시 대체 content_id로 사용한다 — Track B
    # content_id(Vault 산출물의 진짜 콘텐츠 식별자)와의 정식 연결은 별도 승인
    # 필요(Instagram_Posts Schema 확장 없이는 불가).
    content_id = post_id
    try:
        key = publish_ledger.reserve(content_id, account_code_ref, "instagram")
    except publish_ledger.PublishLedgerError:
        logger.warning("[ScheduledPublish] 중복 Reserve 차단 | rid=%s", post_id)
        return {"status": "duplicate_blocked"}

    if not repo.claim_post_for_upload(post_id):
        return {"status": "claim_failed", "ledger_key": key}

    publish_ledger.transition(key, "PUBLISHING")

    raw = publish_single_fn(post_id, post["image_url"], post["caption"], "", "")

    if raw.get("outcome_unknown"):
        publish_ledger.transition(key, "UNKNOWN", instagram_creation_id=raw.get("creation_id", ""))
        logger.error("[ScheduledPublish] OUTCOME_UNKNOWN — 자동재게시 금지 | rid=%s", post_id)
        return {"status": "outcome_unknown", "ledger_key": key}

    if not raw.get("ok"):
        publish_ledger.transition(key, "FAILED", last_error_code=raw.get("error", ""))
        return {"status": "failed", "ledger_key": key}

    ig_media_id = raw.get("ig_media_id", "")
    # 필수증명 4: Instagram 성공 ID를 Airtable 반영 전에 Ledger에 먼저 보존한다.
    publish_ledger.transition(key, "PUBLISHED", instagram_post_id=ig_media_id)

    try:
        from modules.infra.repository_interface import PostPublishResult

        repo.mark_post_result(
            post_id, PostPublishResult(status="posted", platform_post_id=ig_media_id, error_code="")
        )
    except Exception as exc:
        # 필수증명 5: Airtable 반영 실패 시 Instagram을 재호출하지 않고
        # RECEIPT_SYNC_PENDING으로만 분리 기록한다.
        publish_ledger.transition(key, "RECEIPT_SYNC_PENDING", last_error_code=str(exc))
        logger.error("[ScheduledPublish] Airtable 반영 실패 — RECEIPT_SYNC_PENDING | rid=%s", post_id)
        return {"status": "receipt_sync_pending", "ledger_key": key, "ig_media_id": ig_media_id}

    return {"status": "published", "ledger_key": key, "ig_media_id": ig_media_id}
