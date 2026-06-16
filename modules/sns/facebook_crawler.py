import hashlib
import json
import os
import re
import time
from dotenv import load_dotenv
load_dotenv(override=True)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from modules.common.airtable_bridge import get_table
from modules.sns.caption_generator import generate_caption, generate_caption_clone
from modules.sns.content_filter import detect_and_translate, passes_keyword_filter, clean_contact_info, replace_contacts, passes_image_filter, clean_fb_metadata
from modules.sns.post_id_generator import generate_sku, get_source_group, get_platform_code
from modules.sns.image_hosting import upload_to_imgbb
from modules.common.logger import get_logger

logger = get_logger(__name__)

CHROMEDRIVER_PATH = r"C:\Users\admin\AppData\Roaming\adspower_global\cwd_global\chrome_144\chromedriver.exe"
MAX_POSTS = int(os.getenv("FB_MAX_POSTS", "10"))


def load_supplier_blocklist() -> list:
    """Airtable Supplier_Blocklist 1회 로드 — author_name, page_name 반환."""
    import requests as _req
    _api_key = os.getenv('AIRTABLE_API_KEY', '')
    _base_id = os.getenv('AIRTABLE_BASE_ID', '')
    if not _api_key or not _base_id:
        logger.warning('[Blocklist] API_KEY/BASE_ID 없음 — 빈 목록 반환')
        return []
    _url = f'https://api.airtable.com/v0/{_base_id}/Supplier_Blocklist'
    _hdrs = {'Authorization': f'Bearer {_api_key}'}
    try:
        r = _req.get(_url, headers=_hdrs, timeout=10)
        records = r.json().get('records', [])
        blocklist = []
        for rec in records:
            fields = rec.get('fields', {})
            blocklist.append({
                'author_name': fields.get('author_name', '').strip().lower(),
                'page_name': fields.get('page_name', '').strip().lower(),
                'reason_code': fields.get('reason_code', ''),
            })
        logger.info(f'[Blocklist] 로드 완료 | {len(blocklist)}건')
        return blocklist
    except Exception as exc:
        logger.warning(f'[Blocklist] 로드 실패 — 빈 목록 반환 | {exc}')
        return []


def is_blocked_supplier(author_name: str, blocklist: list) -> dict:
    """author_name 이 blocklist 에 있으면 매칭된 항목 반환, 없으면 None."""
    normalized = author_name.strip().lower()
    for item in blocklist:
        if item['author_name'] and item['author_name'] in normalized:
            return item
        if item['page_name'] and item['page_name'] in normalized:
            return item
    return None


def start_browser(adspower_user_id: str = "k1bto3j4"):
    import urllib.request
    r = urllib.request.urlopen(f"http://local.adspower.net:50325/api/v1/browser/start?user_id={adspower_user_id}")
    data = json.loads(r.read())
    return data["data"]["debug_port"]


def get_driver(adspower_user_id: str = "k1bto3j4", proxy_opts: dict = None):
    port = start_browser(adspower_user_id)
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    if proxy_opts and proxy_opts.get("proxy_server"):
        options.add_argument(f'--proxy-server={proxy_opts["proxy_server"]}')
        logger.info(f"[FB Crawler] proxy 적용 | {proxy_opts['proxy_server']}")
    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver


_PROFILE_PATTERNS = ("p40x40", "p50x50", "p75x75", "p100x100", "p160x160",
                     "s32x32", "s40x40", "s50x50", "s60x60", "s160x160")


def extract_image_url(post_element, driver=None):
    """포스트 내 첫 번째 콘텐츠 이미지 URL 반환.
    프로필 사진(소형 썸네일) 및 100px 미만 이미지 제외.
    """
    imgs = post_element.find_elements(By.TAG_NAME, "img")
    for img in imgs:
        src = img.get_attribute("src") or img.get_attribute("data-src") or ""
        if not (src.startswith("https://") and "scontent" in src):
            continue
        # 프로필 사진 URL 패턴 제외
        if any(p in src for p in _PROFILE_PATTERNS):
            continue
        # 렌더링된 이미지 크기 확인 (driver 있을 때) — 100px 미만은 아이콘
        if driver:
            try:
                w = int(driver.execute_script("return arguments[0].naturalWidth || 0", img))
                h = int(driver.execute_script("return arguments[0].naturalHeight || 0", img))
                if 0 < w < 100 or 0 < h < 100:
                    continue
            except Exception:
                pass
        return src
    return ""


def expand_see_more(post, driver) -> None:
    """'더 보기' / 'See more' 버튼 클릭으로 포스트 전문 펼치기. 실패 시 silent skip."""
    try:
        btns = post.find_elements(
            By.XPATH,
            ".//div[contains(text(),'더 보기') or contains(text(),'See more')]"
            "| .//span[contains(text(),'더 보기') or contains(text(),'See more')]",
        )
        if btns:
            driver.execute_script("arguments[0].click();", btns[0])
            time.sleep(1)
    except Exception:
        pass


def save_to_airtable(image_url, source_url, text="", original_text=None, media_type="image", sku_code=""):
    if not image_url:
        print("[AIRTABLE] 이미지 URL 없음 - 저장 생략")
        return
    import requests as _req
    _api_key = os.getenv("AIRTABLE_API_KEY", "")
    _base_id = os.getenv("AIRTABLE_BASE_ID", "")
    if not _api_key or not _base_id:
        logger.error("[AIRTABLE] API_KEY 또는 BASE_ID 미설정")
        return
    _url = f"https://api.airtable.com/v0/{_base_id}/Instagram_Posts"
    _hdrs = {"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"}
    _m = re.search(r"/(\d+_\d+(?:_\d+)*)[_.]", image_url)
    _key = _m.group(1) if _m else image_url
    image_url_hash = hashlib.sha256(_key.encode("utf-8")).hexdigest()
    try:
        chk = _req.get(_url, headers=_hdrs, params={"filterByFormula": f"{{image_url_hash}}='{image_url_hash}'", "maxRecords": "1"}, timeout=10)
    except Exception as exc:
        logger.error(f"[AIRTABLE] 중복 체크 요청 실패 | {type(exc).__name__}")
        return
    if not chk.ok:
        logger.error(f"[AIRTABLE] 중복 체크 실패 | {chk.status_code} | {chk.text[:200]}")
        return
    try:
        records = chk.json().get("records", [])
    except ValueError:
        logger.error("[AIRTABLE] 중복 체크 응답 JSON 파싱 실패")
        return
    if records:
        print(f"[AIRTABLE] 중복 이미지 - 저장 생략: {image_url[:80]}...")
        return
    caption, hashtags = generate_caption_clone(text)
    print(f"[CAPTION] {caption[:60]}..." if caption else "[CAPTION] 생성 없음")
    _original = original_text or text
    try:
        # [Phase4] imgbb ???
        original_image_url = image_url
        post_status = "failed"
        from urllib.parse import urlparse as _urlparse
        _host = (_urlparse(image_url).hostname or "").lower()
        if caption and "fbcdn.net" in _host:
            try:
                _r = upload_to_imgbb(image_url)
                if _r.get("success"):
                    image_url = _r["public_url"]
                    post_status = "ready"
                    import logging; logging.getLogger(__name__).info("[ImgBB] ?? | " + image_url[:80])
                else:
                    import logging; logging.getLogger(__name__).warning("[ImgBB] ?? | " + str(_r.get("error")))
            except Exception as _e:
                import logging; logging.getLogger(__name__).warning("[ImgBB] ?? | " + str(_e))
        elif not caption:
            import logging; logging.getLogger(__name__).warning("[ImgBB] caption?? failed | " + original_image_url[:80])
        res = _req.post(_url, headers=_hdrs, json={"fields": {"image_url": image_url, "original_image_url": original_image_url, "image_url_hash": image_url_hash, "source_url": source_url, "post_status": post_status, "caption": caption, "hashtag": hashtags, "original_text": _original, "converted_text": text, "media_type": media_type, "insta_post_code": sku_code}}, timeout=10)
    except Exception as exc:
        logger.error(f"[AIRTABLE] 저장 요청 실패 | {type(exc).__name__}")
        return
    if res.ok:
        print(f"[AIRTABLE] 저장 완료: {image_url[:80]}...")
    else:
        logger.error(f"[AIRTABLE] 저장 실패 | {res.status_code} | {res.text[:200]}")


def run(target_url, max_posts=MAX_POSTS, adspower_user_id: str = "k1bto3j4", proxy_opts: dict = None):
    logger.info(f"[FB Crawler] 시작 | user={adspower_user_id} | url={target_url}")
    _blocklist = load_supplier_blocklist()  # DRY_RUN용 blocklist 1회 로드
    driver = get_driver(adspower_user_id, proxy_opts)
    try:
        driver.get(target_url)
        time.sleep(12)  # 초기 렌더링 대기 (7 → 12초)

        # 스크롤 다운 → lazy-load 이미지 강제 렌더링 후 상단 복귀
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        feed = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
        posts = feed.find_elements(By.XPATH, ".//div[@role='article']")

        if not posts:
            logger.warning(f"[FB Crawler] 포스트 없음 | url={target_url}")
            return []

        results = []
        for i, post in enumerate(posts[:max_posts], start=1):
            # 각 포스트를 뷰포트 중앙으로 스크롤 → lazy-load 트리거
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", post)
            time.sleep(1.5)

            image_url = extract_image_url(post, driver)
            expand_see_more(post, driver)
            # 서로게이트 등 latin-1 불가 문자 안전 처리
            raw_text = (post.text or "").encode("utf-8", errors="replace").decode("utf-8")
            raw_text = clean_fb_metadata(raw_text)
            _author_raw = raw_text.splitlines()[0] if raw_text else ""
            _matched = is_blocked_supplier(_author_raw, _blocklist)
            if _matched:
                logger.warning(f"[Blocklist] 차단 | author={_author_raw!r} | matched={_matched}")
                continue
            else:
                logger.info(f"[Blocklist] 통과 | author={_author_raw!r}")
            logger.info(f"[FB Crawler] POST {i} | image={image_url[:60] if image_url else '없음'}")
            filter_text = detect_and_translate(raw_text)
            if not filter_text or not passes_keyword_filter(filter_text):
                logger.info(f"[FB Crawler] POST {i} 필터 제외")
                continue
            if not passes_image_filter(image_url):
                logger.info(f"[FB Crawler] POST {i} 이미지 필터 제외")
                continue
            converted_text = replace_contacts(raw_text)
            sku = generate_sku(target_url)
            save_to_airtable(image_url, target_url, converted_text, original_text=raw_text, media_type="image", sku_code=sku)
            results.append({"target_url": target_url, "content": converted_text, "image_url": image_url})

        logger.info(f"[FB Crawler] 완료 | {len(results)}개 처리 | user={adspower_user_id}")

        try:
            from modules.metrics.crawl_monitor import record_crawl
            record_crawl(results, target_url=target_url)
        except Exception as exc:
            logger.warning(f"[FB Crawler] 이미지 비율 기록 실패 | {exc}")

        return results
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def run_all_accounts(max_posts=MAX_POSTS) -> dict:
    """활성 계정 전체의 crawl_urls를 순회하며 크롤링."""
    from modules.common.account_manager import get_active_accounts
    summary = {}
    for acct in get_active_accounts():
        if not acct.crawl_urls:
            logger.warning(f"[FB Crawler] crawl_urls 없음 — skip | account={acct.name}")
            continue
        acct_results = []
        proxy_opts = acct.selenium_proxy_options()
        for url in acct.crawl_urls:
            try:
                acct_results.extend(run(url, max_posts, acct.adspower_user_id, proxy_opts))
            except Exception as exc:
                logger.error(f"[FB Crawler] 크롤링 실패 | account={acct.name} | url={url} | {exc}")
        summary[acct.name] = len(acct_results)
        logger.info(f"[FB Crawler] 계정 완료 | account={acct.name} | {len(acct_results)}개")
    return summary
