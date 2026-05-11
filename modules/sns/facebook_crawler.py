import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from modules.common.airtable_bridge import get_table
from modules.sns.caption_generator import generate_caption

CHROMEDRIVER_PATH = r"C:\Users\admin\AppData\Roaming\adspower_global\cwd_global\chrome_144\chromedriver.exe"
MAX_POSTS = 5


def start_browser():
    import urllib.request
    r = urllib.request.urlopen("http://local.adspower.net:50325/api/v1/browser/start?user_id=k1bto3j4")
    data = json.loads(r.read())
    return data["data"]["debug_port"]


def get_driver():
    port = start_browser()
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
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


def run(target_url, max_posts=MAX_POSTS):
    print(f"🟢 시작: run_facebook_crawler (최대 {max_posts}개)")
    driver = get_driver()
    print(f"[CRAWL] {target_url}")
    driver.get(target_url)
    time.sleep(7)

    feed = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
    posts = feed.find_elements(By.XPATH, ".//div[@role='article']")

    if not posts:
        print("[FAIL] No posts found")
        return []

    results = []
    for i, post in enumerate(posts[:max_posts], start=1):
        image_url = extract_image_url(post)
        text = post.text
        print(f"[POST {i}] image={image_url[:60] if image_url else '없음'}")
        save_to_airtable(image_url, target_url, text)
        results.append({"target_url": target_url, "content": text, "image_url": image_url})

    print(f"[DONE] {len(results)}개 처리 완료")
    return results
