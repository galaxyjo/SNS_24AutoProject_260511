"""
tools/fb_dom_probe.py — Selenium 이 그룹 페이지에서 실제로 보는 DOM 을 찍는다 (진단 전용).

크롤러와 똑같이 AdsPower(k1bto3j4) 브라우저를 열고 group URL 로 이동한 뒤,
feed/article/버튼/로그인여부/main 텍스트를 덤프한다. 클릭 없음.

실행 (스케줄러 idle 구간 = 매시 대략 :10~:30, :40~:00):
    python tools/fb_dom_probe.py
    python tools/fb_dom_probe.py https://www.facebook.com/groups/koreanshop68
"""

import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

CHROMEDRIVER = r"C:\Users\admin\AppData\Roaming\adspower_global\cwd_global\chrome_144\chromedriver.exe"
UID = "k1bto3j4"
API = "http://local.adspower.net:50325/api/v1"
DEFAULT_GROUP = "https://www.facebook.com/groups/koreanshop68"


def _api(path: str) -> dict:
    r = urllib.request.urlopen(f"{API}/{path}", timeout=20)
    return json.loads(r.read())


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    print(">>> fb_dom_probe 시작", flush=True)
    group = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_GROUP
    started_here = False
    try:
        d = _api(f"browser/active?user_id={UID}")
        if d.get("data", {}).get("status") == "Active":
            port = d["data"]["debug_port"]
        else:
            d = _api(f"browser/start?user_id={UID}")
            port = d["data"]["debug_port"]
            started_here = True
            time.sleep(4)
    except Exception as e:
        print("AdsPower API ERR:", e)
        sys.exit(1)

    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    drv = webdriver.Chrome(service=Service(CHROMEDRIVER), options=opts)
    drv.set_page_load_timeout(45)
    drv.set_script_timeout(25)

    try:
        members_url = group.rstrip("/") + "/members"
        for label, url in (("GROUP FEED", group), ("GROUP MEMBERS", members_url)):
            print(f"\n================ {label}: {url}")
            try:
                drv.get(url)
            except Exception as e:
                print("  get() ERR:", e)
                continue
            time.sleep(14)
            is_members = url.endswith("/members")
            try:
                if is_members:
                    for _ in range(10):  # 관리자/신규멤버 위젯 지나 실제 멤버 리스트까지
                        drv.execute_script("window.scrollBy(0, 1500);")
                        time.sleep(1.5)
                else:
                    drv.execute_script("window.scrollBy(0, 1000);")
                    time.sleep(2)
                    drv.execute_script("window.scrollTo(0, 0);")
                    time.sleep(1)
            except Exception:
                pass
            print("  final_url:", drv.current_url[:120])
            print("  title    :", (drv.title or "")[:80])

            def _cnt(css):
                try:
                    return len(drv.find_elements(By.CSS_SELECTOR, css))
                except Exception:
                    return -1
            uc = _cnt("a[href*='/user/']")
            print(f"  feed={_cnt('div[role=feed]')} article={_cnt('div[role=article]')} "
                  f"user-links={uc} role-button={_cnt('div[role=button]')} h1={_cnt('h1')}")

            try:
                body = (drv.find_element(By.TAG_NAME, "body").text or "")
            except Exception:
                body = ""
            low = body.lower()
            flags = [w for w in ("log in", "로그인", "sign up", "가입하기", "join group",
                                 "그룹 가입", "content isn't available", "콘텐츠를 사용할 수 없",
                                 "회원만", "members only", "비공개 그룹", "private group")
                     if w in low]
            print("  body_flags:", flags)
            print("  body[:350]:", body[:350].replace("\n", " | "))

            for sel in ("div[role='main']", "[role='main']"):
                try:
                    m = drv.find_element(By.CSS_SELECTOR, sel)
                    print(f"  [{sel}] text[:400]:", (m.text or "")[:400].replace("\n", " | "))
                    break
                except Exception:
                    continue

            try:
                labels = []
                for b in drv.find_elements(
                    By.XPATH, "//div[@role='button'] | //button | //a[@role='button']"
                ):
                    t = (b.get_attribute("aria-label") or b.text or "").strip()
                    if t:
                        labels.append(t)
                print(f"  buttons({len(labels)}):", labels[:30])
            except Exception as e:
                print("  button scan ERR:", e)

            if is_members:
                # '친구 추가/팔로우' 를 가진 요소의 실제 태그·조상 구조 덤프
                try:
                    hits = drv.find_elements(
                        By.XPATH,
                        "//*[self::a or self::div or self::span or self::button]"
                        "[normalize-space(text())='친구 추가' or normalize-space(text())='팔로우'"
                        " or normalize-space(text())='Add friend' or normalize-space(text())='Follow']"
                    )
                    print(f"  '친구추가/팔로우' 텍스트 요소: {len(hits)}")
                    for h in hits[:4]:
                        try:
                            tag = h.tag_name
                            role = h.get_attribute("role")
                            txt = (h.text or "").strip()[:20]
                            # 조상 2단계 outerHTML 축약
                            anc = drv.execute_script(
                                "var e=arguments[0];for(var i=0;i<3&&e.parentElement;i++)e=e.parentElement;"
                                "return e.outerHTML.slice(0,600);", h)
                            print(f"    <{tag} role={role}> '{txt}' | 조상HTML: {anc}")
                        except Exception as e:
                            print("    dump ERR:", e)
                except Exception as e:
                    print("  친구추가 스캔 ERR:", e)
                # 회원 프로필 링크 샘플 (main 안, /user/ 형태)
                try:
                    us = []
                    for a in drv.find_elements(By.CSS_SELECTOR, "div[role='main'] a[href*='/user/']"):
                        h = (a.get_attribute("href") or "").split("?")[0]
                        n = (a.text or "").strip()
                        if h and n:
                            us.append(f"{n}={h[-40:]}")
                    print(f"  main내 회원링크(이름有) {len(us)}:", us[:8])
                except Exception as e:
                    print("  회원링크 스캔 ERR:", e)
    finally:
        try:
            drv.command_executor.close()
        except Exception:
            pass
        if started_here:
            try:
                _api(f"browser/stop?user_id={UID}")
                print("\n(probe 가 연 브라우저 — stop 함)")
            except Exception:
                pass


if __name__ == "__main__":
    main()
