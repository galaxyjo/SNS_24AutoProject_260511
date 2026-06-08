"""
modules/sns/post_id_generator.py — SKU 코드 자동 생성

형식: [소스그룹]-[플랫폼코드][번호]-[날짜]-[순번]
예시: A-F1-260608-001

소스 그룹:
    A = 페이스북 그룹
    B = B2B 사이트
    C = 원천공급사
    D = 국내유통
"""

from datetime import datetime

# 그룹 URL → 플랫폼코드+번호 매핑
SOURCE_MAP = {
    # A: 페이스북 그룹
    '1676627532598134': ('A', 'F1'),
    '610113703703488':  ('A', 'F2'),
    '345179878828208':  ('A', 'F3'),
    '755455243345993':  ('A', 'F4'),
    '3289570041331131': ('A', 'F5'),
    '1827528710833477': ('A', 'F6'),
    # B: B2B 사이트
    'tradekorea':       ('B', 'B1'),
    'beautetrade':      ('B', 'B2'),
    'cmtstory':         ('B', 'B3'),
    'gobizkorea':       ('B', 'B4'),
    'tradequarter':     ('B', 'B5'),
    # D: 국내유통
    'naverband':        ('D', 'N1'),
    'domaekok':         ('D', 'N2'),
}

# 당일 순번 카운터 (메모리, 재시작 시 초기화)
_daily_counter: dict = {}


def generate_sku(source_url: str) -> str:
    """
    source_url 기반으로 SKU 코드 생성.
    예: https://www.facebook.com/groups/345179878828208 -> A-F3-260608-001
    """
    today = datetime.now().strftime('%y%m%d')

    # URL에서 그룹 ID 또는 사이트명 추출
    platform_key = None
    for key in SOURCE_MAP:
        if key in source_url:
            platform_key = key
            break

    if platform_key:
        group, code = SOURCE_MAP[platform_key]
    else:
        # 미등록 소스 → X-F0
        group, code = 'X', 'F0'

    # 당일 순번 증가
    counter_key = f'{code}-{today}'
    _daily_counter[counter_key] = _daily_counter.get(counter_key, 0) + 1
    seq = str(_daily_counter[counter_key]).zfill(3)

    return f'{group}-{code}-{today}-{seq}'


def get_source_group(source_url: str) -> str:
    """소스 그룹 반환 (A/B/C/D/X)"""
    for key in SOURCE_MAP:
        if key in source_url:
            return SOURCE_MAP[key][0]
    return 'X'


def get_platform_code(source_url: str) -> str:
    """플랫폼 코드 반환 (F1/F2/B1 등)"""
    for key in SOURCE_MAP:
        if key in source_url:
            return SOURCE_MAP[key][1]
    return 'F0'
