"""
tests/test_smoke_crm.py — CRM 로직 smoke tests

lead_scorer / order_detector — 외부 서비스 호출 없이 순수 로직만 검증.
"""

import pytest


# ── lead_scorer ───────────────────────────────────────────────────────────────

from modules.crm.lead_scorer import calc_score, GRADE_HOT, GRADE_WARM


def test_calc_score_cold_default():
    score, grade = calc_score()
    assert grade == "cold"
    assert score < GRADE_WARM


def test_calc_score_warm_repeat():
    score, grade = calc_score(is_repeat=True)
    assert grade == "warm"


def test_calc_score_warm_order_keyword_alone():
    # SCORE_ORDER_KW=20 < GRADE_HOT=25 → warm
    score, grade = calc_score(has_order_keyword=True)
    assert grade == "warm"
    assert score == 20


def test_calc_score_hot_order_plus_repeat():
    # 주문(20) + 재문의(10) = 30 >= GRADE_HOT(25) → hot
    score, grade = calc_score(is_repeat=True, has_order_keyword=True)
    assert grade == "hot"
    assert score >= GRADE_HOT


def test_calc_score_fast_response_adds_points():
    score_fast, _ = calc_score(response_delay_sec=30)
    score_slow, _ = calc_score(response_delay_sec=999)
    assert score_fast > score_slow


def test_calc_score_hot_repeat_plus_order():
    score, grade = calc_score(is_repeat=True, has_order_keyword=True)
    assert grade == "hot"


def test_calc_score_grade_thresholds():
    _, grade_warm = calc_score(is_repeat=True)                        # 10점 → warm
    _, grade_hot  = calc_score(is_repeat=True, has_order_keyword=True)  # 30점 → hot
    assert grade_warm == "warm"
    assert grade_hot  == "hot"


# ── order_detector ────────────────────────────────────────────────────────────

from modules.crm.order_detector import detect_order


@pytest.mark.parametrize("text", [
    "주문하고 싶어요",
    "구매 가능한가요?",
    "결제 방법이 어떻게 되나요",
    "계좌번호 알려주세요",
    "I want to order",
    "살게요!",
    "입금 어디로 해요",
])
def test_detect_order_true(text):
    assert detect_order(text) is True


@pytest.mark.parametrize("text", [
    "안녕하세요",
    "이 제품 어때요?",
    "사진 예쁘네요",
    "정보 감사합니다",
    "",
])
def test_detect_order_false(text):
    assert detect_order(text) is False


def test_detect_order_case_insensitive():
    assert detect_order("ORDER please") is True
    assert detect_order("BUY now") is True
