import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from modules.common.airtable_bridge import get_table

CHROMEDRIVER_PATH = r"C:\Users\admin\AppData\Roaming\adspower_global\cwd_global\chrome_144\chromedriver.exe"


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


def save_to_airtable(image_url, source_url):
    if not image_url:
        print("[AIRTABLE] 이미지 URL 없음 - 저장 생략")
        return
    table = get_table("Instagram_Posts")
    escaped = image_url.replace("'", "\\'")
    existing = table.all(formula=f"{{image_url}}='{escaped}'")
    if existing:
        print(f"[AIRTABLE] 중복 이미지 - 저장 생략: {image_url[:80]}...")
        return
    table.create({
        "image_url": image_url,
        "source_url": source_url,
        "post_status": "ready",
    })
    print(f"[AIRTABLE] 저장 완료: {image_url[:80]}...")


def run(target_url):
    print("🟢 시작: run_facebook_crawler")
    driver = get_driver()
    print(f"[CRAWL] {target_url}")
    driver.get(target_url)
    time.sleep(7)

    feed = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
    posts = feed.find_elements(By.XPATH, ".//div[@role='article']")

    if posts:
        post = posts[0]
        text = post.text
        image_url = extract_image_url(post)
        print("[SUCCESS] POST TEXT")
        print(text)
        print(f"[IMAGE] {image_url or '없음'}")
        save_to_airtable(image_url, target_url)
        return {"target_url": target_url, "content": text, "image_url": image_url}
    else:
        print("[FAIL] No posts found")
        return {"target_url": target_url, "content": "", "image_url": ""}
