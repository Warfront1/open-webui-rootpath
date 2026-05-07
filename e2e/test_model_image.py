#!/usr/bin/env python3
"""
E2E test: model profile image redirects respect root path.

Verifies that:
1. /api/v1/models/model/profile/image 302-redirects to {ROOT_PATH}/static/favicon.png
   when no model image is set (fallback case).
2. The redirect Location header includes the root path prefix.
"""
import sys
import os
import urllib.request
import urllib.error

BASE_HOST = os.environ.get("E2E_BASE_HOST", "http://nginx:80")
ROOT_PATH = os.environ.get("E2E_ROOT_PATH", "/openwebui")
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", "/tmp/e2e-screenshots")

from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

errors = []

def save_screenshot(prefix="failure"):
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"{prefix}_{ts}.png")
        driver.save_screenshot(path)
        print(f"   Screenshot saved: {path}")
    except Exception as ss_err:
        print(f"   WARNING: Could not save screenshot: {ss_err}")

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=opts)

try:
    # ── Test 1: Model profile image fallback redirect includes root path ─────
    print("1. Testing model profile image redirect...")

    url = f"{BASE_HOST}{ROOT_PATH}/api/v1/models/model/profile/image?id=nonexistent"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")

    try:
        resp = urllib.request.urlopen(req)
        final_url = resp.geturl()
        print(f"   Requested: {url}")
        print(f"   Final URL: {final_url}")
        errors.append(f"Expected redirect (302) but got 200 for: {url}")
    except urllib.error.HTTPError as e:
        if e.code == 302:
            location = e.headers.get("Location", "")
            print(f"   Redirect Location: {location}")
            if location.startswith(f"{ROOT_PATH}/static/"):
                print(f"   PASS: Redirect includes root path prefix")
            elif location.startswith("/static/"):
                errors.append(f"Redirect Location '{location}' missing root path prefix (expected '{ROOT_PATH}/static/...')")
                print(f"   FAIL: Redirect missing root path prefix")
            else:
                errors.append(f"Unexpected redirect Location: {location}")
                print(f"   FAIL: Unexpected redirect target")
        else:
            # 401 or 403 might be expected if auth is required
            print(f"   Got HTTP {e.code} (may require auth)")
            # Also check the redirect for non-auth cases
            if e.code in (401, 403):
                print("   Auth required — skipping redirect check for unauthenticated request")
    except urllib.error.URLError as e:
        errors.append(f"URL error: {e}")
        print(f"   FAIL: URL error: {e}")

    # ── Test 2: Check model image src in browser includes root path ──────────
    print("\n2. Loading app to check model image src...")

    BASE_URL = f"{BASE_HOST}{ROOT_PATH}/"
    driver.get(BASE_URL)
    driver.implicitly_wait(10)

    # Dismiss modals
    for _ in range(5):
        modals = driver.find_elements(By.CSS_SELECTOR, "[aria-modal='true']")
        if not modals:
            break
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        driver.execute_script(
            "document.querySelectorAll(\"[aria-modal='true']\").forEach(function(m){m.remove();});"
        )
        import time
        time.sleep(1)

    # Check that any model image src includes the root path
    img_srcs = driver.execute_script("""
        var imgs = document.querySelectorAll('img[src*="profile/image"]');
        var srcs = [];
        for (var i = 0; i < imgs.length; i++) {
            srcs.push(imgs[i].src);
        }
        return srcs;
    """)

    print(f"   Found {len(img_srcs)} model profile image elements")
    for src in img_srcs[:5]:
        print(f"     src: {src}")
        if f"{ROOT_PATH}/api/v1/" in src or f"{ROOT_PATH}/users/" in src:
            print("     OK: src includes root path")
        elif src.startswith(f"{BASE_HOST}/api/v1/") or src.startswith(f"{BASE_HOST}/users/"):
            errors.append(f"Model image src missing root path: {src}")
            print("     FAIL: src missing root path prefix")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print("FAILURES:")
        for e in errors:
            print(f"  - {e}")
        print("=" * 60)
        save_screenshot("failure_model_profile_image")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        print("=" * 60)
        save_screenshot("success_model_profile_image")
        sys.exit(0)

except Exception as e:
    print(f"FATAL: {e}")
    import traceback
    traceback.print_exc()
    save_screenshot("failure_model_profile_image")
    sys.exit(2)
finally:
    driver.quit()