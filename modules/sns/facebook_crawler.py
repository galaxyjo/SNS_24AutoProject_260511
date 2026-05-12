import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from modules.common.airtable_bridge import get_table
from modules.sns.caption_generator import generate_caption
from modules.common.logger import get_logger

logger = get_logger(__name__)

CHROMEDRIVER_PATH = r"C:\Users\admin\AppData\Roaming\adspower_global\cwd_global\chrome_144\chromedriver.exe"
MAX_POSTS = 5


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


def extract_image_url(post_element):
    imgs = post_element.find_elements(By.TAG_NAME, "img")
    for img in imgs:
        src = img.get_attribute("src") or img.get_attribute("data-src") or ""
        if "scontent" in src and src.startswith("https://"):
            return src
    return ""


def save_to_airtable(image_url, source_url, text=""):
    if not image_url:
        print("[AIRTABLE] 이미지 URL 없음 - 저장 생략")
        return
    table = get_table("Instagram_Posts")
    escaped = image_url.replace("'", "\\'")
    existing = table.all(formula=f"{{image_url}}='{escaped}'")
    if existing:
        print(f"[AIRTABLE] 중복 이미지 - 저장 생략: {image_url[:80]}...")
        return
    caption, hashtags = generate_caption(text)
    print(f"[CAPTION] {caption[:60]}..." if caption else "[CAPTION] 생성 없음")
    table.create({
        "image_url": image_url,
        "source_url": source_url,
        "post_status": "ready",
        "caption": caption,
        "hashtag": hashtags,
    })
    print(f"[AIRTABLE] 저장 완료: {image_url[:80]}...")


def run(target_url, max_posts=MAX_POSTS, adspower_user_id: str = "k1bto3j4", proxy_opts: dict = None):
    logger.info(f"[FB Crawler] 시작 | user={adspower_user_id} | url={target_url}")
    driver = get_driver(adspower_user_id, proxy_opts)
    driver.get(target_url)
    time.sleep(7)

    feed = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
    posts = feed.find_elements(By.XPATH, ".//div[@role='article']")

    if not posts:
        logger.warning(f"[FB Crawler] 포스트 없음 | url={target_url}")
        return []

    results = []
    for i, post in enumerate(posts[:max_posts], start=1):
        image_url = extract_image_url(post)
        text = post.text
        logger.info(f"[FB Crawler] POST {i} | image={image_url[:60] if image_url else '없음'}")
        save_to_airtable(image_url, target_url, text)
        results.append({"target_url": target_url, "content": text, "image_url": image_url})

    logger.info(f"[FB Crawler] 완료 | {len(results)}개 처리 | user={adspower_user_id}")
    return results


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
