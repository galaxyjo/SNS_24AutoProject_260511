import copy

COSMETIC_KEYWORDS = [
    "크림", "앰플", "세럼", "마스크팩", "스킨", "로션", "클렌징", "토너", "에센스",
    "선크림", "자외선차단", "콜라겐", "히알루론산",
    "cream", "ampoule", "serum", "mask", "skin", "lotion", "cleansing", "toner", "essence", "sunscreen",
]
IRRELEVANT_HINTS = [
    "공병", "용기", "스프레이통", "진열대", "받침대", "전시대", "케이스", "파티션", "수납",
    "칫솔", "가그린", "구강", "눈썹칼", "면도", "그루밍", "led", "마사지기", "미용기기",
]

def _is_irrelevant_category(item):
    category_code = item.get('category_code') or ''
    title = (item.get('title') or '').lower()

    if category_code == 'Healthy':
        return False

    if category_code == 'BEAUTY':
        if any(k.lower() in title for k in IRRELEVANT_HINTS):
            return True
        if any(k.lower() in title for k in COSMETIC_KEYWORDS):
            return False
        return True

    return True

FILTER_RULES = [
    ('adult_only', lambda i: i.get('adult_only') is True, 'FILTERED', 'ADULT_CONTENT'),
    ('title',      lambda i: not i.get('title'),           'ERROR',    'MISSING_TITLE'),
    ('unit_price', lambda i: i.get('unit_price') is None,  'ERROR',    'MISSING_PRICE'),
    ('image_url',  lambda i: not i.get('image_url'),       'ERROR',    'MISSING_IMAGE'),
    ('relevance',  _is_irrelevant_category,                'FILTERED', 'IRRELEVANT_CATEGORY'),
]

def run_gate(items: list) -> list:
    result = []
    for item in items:
        out = copy.deepcopy(item)
        out['quality_status'] = 'READY'
        out['filter_reason'] = ''
        for _, check, status, reason in FILTER_RULES:
            if check(out):
                out['quality_status'] = status
                out['filter_reason'] = reason
                break
        result.append(out)
    return result