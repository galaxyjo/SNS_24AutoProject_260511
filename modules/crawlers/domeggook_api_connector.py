import os, hashlib, logging
from datetime import datetime, timezone
import requests
from modules.crawlers.base_connector import BaseCrawlConnector, ConnectorError

logger = logging.getLogger(__name__)
ENDPOINT = 'https://domeggook.com/ssl/api/'

class DomeggookApiConnector(BaseCrawlConnector):

    def __init__(self):
        self.api_key = os.getenv('DOMEGGOOK_API_KEY')
        if not self.api_key:
            raise ConnectorError('DOMEGGOOK_API_KEY not set')

    def fetch(self, target: dict) -> list:
        kw = target.get('kw') or target.get('keyword')
        ca = target.get('ca') or target.get('category_code')
        max_posts = min(int(target.get('max_posts', 10)), 50)

        if not kw and not ca:
            raise ConnectorError('target must have kw or ca')

        params = {
            'ver': '4.1',
            'mode': 'getItemList',
            'aid': self.api_key,
            'market': 'dome',
            'om': 'json',
            'sz': str(max_posts),
            'pg': '1',
            'so': 'da',
            'org': 'kr',
        }
        if kw:
            params['kw'] = kw
        if ca:
            params['ca'] = ca

        try:
            r = requests.get(ENDPOINT, params=params, timeout=15)
            r.raise_for_status()
        except Exception as e:
            raise ConnectorError(f'HTTP error: {e}')

        try:
            data = r.json()
        except Exception as e:
            raise ConnectorError(f'JSON parse error: {e}')

        root = data.get('domeggook', data)
        items = root.get('list', {}).get('item', [])
        if isinstance(items, dict):
            items = [items]

        results = []
        for raw in items:
            try:
                results.append(self._normalize(raw, target))
            except Exception as e:
                logger.warning(f'item parse skip no={raw.get("no")} err={e}')
                continue

        return results

    def _normalize(self, raw: dict, target: dict) -> dict:
        no = str(raw.get('no', ''))
        title = raw.get('title', '')
        price_val = raw.get('price')
        image_url = raw.get('thumb') or None
        source_url = raw.get('url') or None

        unit_price = int(price_val) if price_val is not None else None
        hash_src = f"{no}:{title}:{unit_price}:{image_url}"
        content_hash = hashlib.sha256(hash_src.encode()).hexdigest()

        return {
            'source_item_id':  f'domeggook:{no}',
            'source_platform': 'domeggook',
            'source_url':      source_url,
            'content_hash':    content_hash,
            'title':           title,
            'unit_price':      unit_price,
            'currency':        'KRW',
            'price_type':      'supply',
            'min_order_qty':   int(raw['unitQty']) if raw.get('unitQty') is not None else None,
            'image_url':       image_url,
            'seller_id':       raw.get('id') or None,
            'adult_only':      str(raw.get('adultOnly', 'false')).lower() == 'true',
            'category_code':   target.get('category_code') or None,
            'keyword':         target.get('kw') or target.get('keyword') or None,
            'quality_status':  'PENDING',
            'filter_reason':   '',
            'raw_payload':     raw,
            'collected_at':    datetime.now(timezone.utc).isoformat(),
        }

    def health_check(self) -> bool:
        try:
            r = requests.get(ENDPOINT, params={
                'ver': '4.1', 'mode': 'getItemList',
                'aid': self.api_key, 'market': 'dome',
                'om': 'json', 'kw': 'test', 'sz': '1'
            }, timeout=10)
            return r.status_code == 200
        except Exception:
            return False
