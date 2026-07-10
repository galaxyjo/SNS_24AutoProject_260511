from dotenv import load_dotenv; load_dotenv()
from modules.sns.facebook_crawler import get_driver
from selenium.webdriver.common.by import By
import time

driver = get_driver()
driver.get("https://www.facebook.com/groups/1676627532598134")
time.sleep(12)
feed = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
posts = feed.find_elements(By.XPATH, ".//div[@role='article']")
for i, p in enumerate(posts[:10], 1):
    print(f"=== POST {i} ===")
    print(p.text[:300])
    print()
driver.quit()
