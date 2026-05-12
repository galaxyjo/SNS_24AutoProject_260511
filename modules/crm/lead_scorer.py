# modules/crm/lead_scorer.py
# Lead 스코어링 — 재문의/응답속도/키워드 가중치 → cold/warm/hot 등급 부여

import os
import json as _json
import logging
import requests

logger = logging.getLogger(__name__)

# ── 가중치 ────────────────────────────────────────────────────────────────────
SCORE_REPEAT     = 10   # 동일 IGSID 재문의
SCORE_FAST       = 5    # 응답 속도 < 60초
SCORE_ORDER_KW   = 20   # 주문 키워드 포함
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
    base = os.getenv("AIRTABLE_BASE_ID", "")
    # dm_received 상태 이외 = 이미 처리된 이전 상호작용이 있음
    formula = (
        f"AND({{inquiry_user_handle}}='{sender_igsid}',"
        f"NOT({{bridge_status}}='dm_received'))"
    )
    try:
        resp = requests.get(
            f"https://api.airtable.com/v0/{base}/Lead_Interactions",
            headers={"Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY", "")},
            params={"filterByFormula": formula, "maxRecords": 1},
            timeout=10,
        )
        return len(resp.json().get("records", [])) > 0
    except Exception as exc:
        logger.warning(f"[Scorer] 재문의 확인 실패 | {exc}")
        return False


def update_lead_score(record_id: str, score: int, grade: str) -> None:
    """Airtable Lead_Interactions 레코드에 lead_score, lead_grade 업데이트.

    Airtable에 해당 필드가 없을 경우 422 응답 — 경고 로그 후 무시.
    필드 추가 방법: Airtable > Lead_Interactions > + Add field
      - lead_score (Number)
      - lead_grade (Single line text)
    """
    base = os.getenv("AIRTABLE_BASE_ID", "")
    headers = {
        "Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY", ""),
        "Content-Type": "application/json; charset=utf-8",
    }
    body = _json.dumps(
        {"fields": {"lead_score": score, "lead_grade": grade}},
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        resp = requests.patch(
            f"https://api.airtable.com/v0/{base}/Lead_Interactions/{record_id}",
            headers=headers,
            data=body,
            timeout=15,
        )
        if resp.ok:
            logger.info(f"[Scorer] 스코어 저장 | record={record_id} score={score} grade={grade}")
        else:
            logger.warning(f"[Scorer] PATCH 실패(필드 미생성?) | {resp.status_code} {resp.text[:120]}")
    except Exception as exc:
        logger.warning(f"[Scorer] 업데이트 예외 | {exc}")
