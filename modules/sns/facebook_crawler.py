"""Module docstring."""

import time

from selenium import webdriver
from selenium.webdriver.common.by import By

from decorators.log_trace import log_trace


@log_trace
def run_facebook_crawler():
    """Function `run_facebook_crawler` docstring."""
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    fb_id = "nhm880808@gmail.com"
    fb_pw = "**Gg2022!"
    driver.get("https://www.facebook.com/login")
    time.sleep(2)
    driver.find_element(By.ID, "email").send_keys(fb_id)
    driver.find_element(By.ID, "pass").send_keys(fb_pw)
    driver.find_element(By.NAME, "login").click()
    time.sleep(5)
    group_urls = [
        "https://www.facebook.com/groups/group_id_1",
        "https://www.facebook.com/groups/group_id_2",
        "https://www.facebook.com/groups/group_id_3",
        "https://www.facebook.com/groups/group_id_4",
    ]
    all_posts = []
    for url in group_urls:
        driver.get(url)
        time.sleep(5)
        posts = driver.find_elements(By.CSS_SELECTOR, "div[role='article']")
        all_posts.extend([p.text[:100] for p in posts[:2]])
    driver.quit()
    print(f"✅ 크롤링 완료: {all_posts}")
    return {"status": "success", "posts": all_posts}
