"""
modules/infra/review_batch.py
학습 리뷰 그리드 배치 → Airtable payload 변환 순수 함수.
Airtable/Streamlit import 금지 — 입력을 출력으로 바꾸는 로직만 담당.
"""
from __future__ import annotations

from typing import Iterable


def build_review_payloads(
    batch_ids: list[str],
    block_ids: Iterable[str],
) -> list[dict[str, str]]:
    """batch_ids 각각에 대해 {record_id, review_status} payload를 생성한다.

    block_ids에 속한 record_id는 BLOCK, 그 외 전부는 PASS.
    batch_ids에 없는 block_ids 항목은 무시한다(배치 범위 밖 선택 방지).
    batch_ids 순서를 그대로 유지한다.
    """
    block_set = set(block_ids)
    return [
        {"record_id": rid, "review_status": "BLOCK" if rid in block_set else "PASS"}
        for rid in batch_ids
    ]
