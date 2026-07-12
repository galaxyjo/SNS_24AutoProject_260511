import os, re, logging
from datetime import datetime, timezone
import requests
from modules.crawlers.base_connector import BaseCrawlConnector, ConnectorError

logger = logging.getLogger(__name__)
ENDPOINT = 'https://openapi.naver.com/v1/search/image'


def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text or '').strip()


class NaverSearchConnector(BaseCrawlConnector):
    """
    Naver 검색 오픈API(이미지 검색) 커넥터.
    NOTE: 이미지 검색 API는 이미지 파일 URL(link)만 반환하고 별도 게시물 페이지 URL은
    주지 않는다 — source_url은 image_url과 동일하게 채운다(Pilot 단계에서 실제 응답
    구조로 확인된 제약, 향후 blog/cafearticle API로 게시물 페이지 보강 검토 가능).
    작성자/판매자 정보도 이 API는 제공하지 않아 seller_id는 항상 빈칸이다.
    """

    def __init__(self):
        self.client_id = os.getenv('NAVER_CLIENT_ID')
        self.client_secret = os.getenv('NAVER_CLIENT_SECRET')
        if not self.client_id or not self.client_secret:
            raise ConnectorError('NAVER_CLIENT_ID/NAVER_CLIENT_SECRET not set')

    def _headers(self) -> dict:
        return {
            'X-Naver-Client-Id': self.client_id,
            'X-Naver-Client-Secret': self.client_secret,
        }

    def fetch(self, target: dict) -> list:
        query = target.get('keyword') or target.get('kw')
        if not query:
            raise ConnectorError('target must have keyword')
        max_posts = min(int(target.get('max_posts', 20)), 100)

        try:
            r = requests.get(
                ENDPOINT,
                headers=self._headers(),
                params={'query': query, 'display': max_posts, 'sort': 'sim'},
                timeout=15,
            )
            r.raise_for_status()
        except Exception as e:
            raise ConnectorError(f'HTTP error: {e}')

        try:
            data = r.json()
        except Exception as e:
            raise ConnectorError(f'JSON parse error: {e}')

        items = data.get('items', [])

        results = []
        for raw in items:
            try:
                results.append(self._normalize(raw, target, query))
            except Exception as e:
                logger.warning(f'item parse skip link={raw.get("link")} err={e}')
                continue

        return results

    def _normalize(self, raw: dict, target: dict, query: str) -> dict:
        image_url = raw.get('link') or None
        title = _strip_html(raw.get('title', ''))

        return {
            'source_platform': 'naver',
            'search_query':    query,
            'source_url':      image_url,
            'image_url':       image_url,
            'text_content':    title,
            'target_id_ref':   target.get('target_id') or '',
            'collected_at':    datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        }

    def health_check(self) -> bool:
        try:
            r = requests.get(
                ENDPOINT,
                headers=self._headers(),
                params={'query': 'test', 'display': 1},
                timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False
