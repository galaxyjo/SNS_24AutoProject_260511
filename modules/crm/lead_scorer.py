# modules/crm/lead_scorer.py
# Lead 스코어링 — 재문의/응답속도/키워드 가중치 → cold/warm/hot 등급 부여

import logging

from modules.common.logger import get_logger
from modules.infra.airtable_repository import AirtableRepository

logger = get_logger(__name__)

_repo = AirtableRepository()

# ── 가중치 ────────────────────────────────────────────────────────────────────
SCORE_REPEAT     = 10   # 동일 IGSID 재문의
SCORE_FAST       = 5    # 응답 속도 < 60초
SCORE_ORDER_KW   = 25   # 주문 키워드 포함
SCORE_PRICE_KW   = 5    # 단가 키워드만 포함

GRADE_HOT  = 25
GRADE_WARM = 10


def calc_score(
    is_repeat: bool = False,
    response_delay_sec: int = 999,
    has_order_keyword: bool = False,
    has_price_keyword: bool = True,
) -> tuple[int, str]:
    score = 0
    if is_repeat:
        score += SCORE_REPEAT
    if response_delay_sec < 60:
        score += SCORE_FAST
    if has_order_keyword:
        score += SCORE_ORDER_KW
    elif has_price_keyword:
        score += SCORE_PRICE_KW

    if score >= GRADE_HOT:
        grade = "hot"
    elif score >= GRADE_WARM:
        grade = "warm"
    else:
        grade = "cold"

    return score, grade


def is_repeat_inquiry(sender_igsid: str) -> bool:
    """동일 IGSID의 완료된 이전 레코드가 있으면 재문의로 판단."""
    try:
        return _repo.is_repeat_inquiry(sender_igsid)
    except Exception as exc:
        logger.warning(f"[Scorer] 재문의 확인 실패 | {exc}")
        return False


def _retry_update_lead_score(payload: dict) -> None:
    """retry_queue 핸들러 — 스코어 업데이트 재시도."""
    _repo.update_lead_score(payload["record_id"], payload["score"], payload["grade"])


def register_retry_handlers(rq) -> None:
    """260730(ERR-097 계열) — launcher 시작 시 즉시(eager) 호출해야 함(rq.start() 이전).
    실패 시점에만 지연등록하면 재시작 후 pending task가 handler를 못 찾고 dead 처리됨
    (comment_airtable_record/FP-047과 동일 계약)."""
    rq.register("lead_update_score", _retry_update_lead_score)


def update_lead_score(record_id: str, score: int, grade: str) -> None:
    """Lead_Interactions에 lead_score, lead_grade 업데이트.

    ERR-086: DM 웹훅은 재실행 주기가 없어 실패를 로그만 남기고 넘어가면 그 스코어는
    영구 유실된다 — retry_queue에 위임해 재시도 기회를 남긴다."""
    try:
        _repo.update_lead_score(record_id, score, grade)
        logger.info(f"[Scorer] 스코어 저장 | record={record_id} score={score} grade={grade}")
    except Exception as exc:
        logger.warning(f"[Scorer] 업데이트 예외 — retry queue 등록 | record={record_id} | {exc}")
        from modules.common.retry_queue import get_retry_queue

        rq = get_retry_queue()
        rq.register("lead_update_score", _retry_update_lead_score)
        rq.start()
        rq.enqueue("lead_update_score", {"record_id": record_id, "score": score, "grade": grade})
