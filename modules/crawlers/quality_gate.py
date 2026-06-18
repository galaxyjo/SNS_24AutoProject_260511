import copy

FILTER_RULES = [
    ('adult_only', lambda i: i.get('adult_only') is True, 'FILTERED', 'ADULT_CONTENT'),
    ('title',      lambda i: not i.get('title'),           'ERROR',    'MISSING_TITLE'),
    ('unit_price', lambda i: i.get('unit_price') is None,  'ERROR',    'MISSING_PRICE'),
    ('image_url',  lambda i: not i.get('image_url'),       'ERROR',    'MISSING_IMAGE'),
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
