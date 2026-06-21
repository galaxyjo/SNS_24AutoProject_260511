import os, hmac, hashlib, logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
import requests as _req

logger = logging.getLogger(__name__)

domeggook_ingest_bp = Blueprint('domeggook_ingest', __name__)

TRAINING_TABLE = 'Product_Training_Set'

INCLUDE_TERMS = ['선크림', '선블록', '선프로텍터', 'UV', 'SPF', '선스틱', '선쿠션', '선세럼', '선스프레이', '자외선차단', '스킨케어', '토너', '세럼', '앰플', '에센스', '크림', '로션', '마스크팩', '시트마스크', '클렌징', '폼클렌저', '립', '파운데이션', '쿠션', '비비', '컨실러', '아이섀도', '마스카라', '블러셔', '향수', '퍼퓸', '샴푸', '헤어', '바디', '핸드크림', '네일']
EXCLUDE_TERMS = ['강아지', '고양이', '반려동물', '애견', '펫', '슬리퍼', '샌들', '신발', '골프공', '인솔', '치약', '문구', '장난감', '찜질', '휴대폰', '자동차', '수납함', '케이스', '공병', '스티커']

def _verify_token(req):
    token = req.headers.get('X-Ingest-Key', '')
    expected = os.getenv('DOMEGGOOK_INGEST_KEY', '')
    return hmac.compare_digest(token, expected)

def _gate(title):
    for ex in EXCLUDE_TERMS:
        if ex in title:
            return 'FILTERED', 'NON_BEAUTY_PRODUCT_MATCH'
    for inc in INCLUDE_TERMS:
        if inc in title:
            return 'PASS', ''
    return 'FILTERED', 'NO_TARGET_PRODUCT_MATCH'

def _upsert_training(item, pilot_run_id, target_id, subcategory):
    base = os.getenv('AIRTABLE_BASE_ID')
    key = os.getenv('AIRTABLE_API_KEY')
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    url = 'https://api.airtable.com/v0/' + base + '/' + TRAINING_TABLE

    training_record_id = pilot_run_id + ':' + item['source_item_id']
    gate_status, gate_reason = _gate(item.get('title', ''))

    fields = {
        'training_record_id': training_record_id,
        'pilot_run_id':       pilot_run_id,
        'source_item_id':     item['source_item_id'],
        'source_platform':    'domeggook',
        'target_id':          target_id,
        'subcategory':        subcategory,
        'collected_at':       item.get('collected_at', datetime.now(timezone.utc).isoformat()),
        'title':              item.get('title', ''),
        'unit_price':         item.get('unit_price'),
        'currency':           item.get('currency', 'KRW'),
        'min_order_qty':      item.get('min_order_qty'),
        'seller_grade':       item.get('seller_grade', ''),
        'ranking_position':   item.get('rank_position') if item.get('sort_mode') == 'RANKING' else None,
        'popular_position':   item.get('rank_position') if item.get('sort_mode') == 'POPULAR' else None,
        'discovery_sort':     item.get('sort_mode', ''),
        'gate_status':        gate_status,
        'gate_reason':        gate_reason,
        'review_status':      'UNREVIEWED',
    }

    if item.get('image_url'):
        fields['image_url'] = item['image_url']
    if item.get('source_url'):
        fields['source_url'] = item['source_url']

    fields = {k: v for k, v in fields.items() if v is not None}

    # 중복 확인 (training_record_id 기준 필터)
    safe_id = training_record_id.replace("'", "\\'")
    chk = _req.get(url, headers={'Authorization': 'Bearer ' + key},
                   params={'maxRecords': 1,
                           'filterByFormula': "training_record_id='" + safe_id + "'"})
    existing = chk.json().get('records', [])

    if existing:
        return 'duplicate'

    r = _req.post(url, headers=headers, json={'fields': fields})
    if r.status_code in (200, 201):
        return gate_status
    logger.error('[ingest] Airtable 저장 실패: ' + str(r.status_code))
    return 'error'

@domeggook_ingest_bp.route('/api/v1/ingest/domeggook/training', methods=['POST'])
def ingest_training():
    if not _verify_token(request):
        return jsonify({'error': 'unauthorized'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'invalid json'}), 400

    required = ['schema_version', 'request_id', 'pilot_run_id', 'items']
    for f in required:
        if f not in data:
            return jsonify({'error': 'missing field: ' + f}), 400

    if data.get('schema_version') != 'domeggook.training.v1':
        return jsonify({'error': 'unsupported schema_version'}), 400

    items = data.get('items', [])
    if not items or len(items) > 100:
        return jsonify({'error': 'items must be 1-100'}), 400

    pilot_run_id = data['pilot_run_id']
    target_id = data.get('target_id', '')
    subcategory = data.get('subcategory', '')

    received = len(items)
    stored = duplicates = filtered = errors = 0

    for item in items:
        result = _upsert_training(item, pilot_run_id, target_id, subcategory)
        if result == 'duplicate':
            duplicates += 1
        elif result == 'PASS':
            stored += 1
        elif result == 'FILTERED':
            filtered += 1
        else:
            errors += 1

    logger.info('[ingest] 완료 | received=' + str(received) + ' stored=' + str(stored) + ' filtered=' + str(filtered))

    return jsonify({
        'status': 'accepted',
        'received': received,
        'stored': stored,
        'duplicates': duplicates,
        'filtered': filtered,
        'errors': errors
    })
