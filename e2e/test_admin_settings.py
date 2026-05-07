#!/usr/bin/env python3
"""
E2E test: admin settings page links respect root path.

Verifies that:
1. Navigation links on /admin/settings pages include the root path prefix.
2. goto() calls in the admin/settings pages produce correct URLs.
3. The page loads correctly under the root path.
"""
import time
import sys
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_HOST = os.environ.get("E2E_BASE_HOST", "http://nginx:80")
ROOT_PATH = os.environ.get("E2E_ROOT_PATH", "/openwebui")
BASE_URL = os.environ.get("E2E_BASE_URL", f"{BASE_HOST}{ROOT_PATH}/")
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", "/tmp/e2e-screenshots")

errors = []

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=opts)

def save_screenshot(prefix="failure"):
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"{prefix}_{ts}.png")
        driver.save_screenshot(path)
        print(f"   Screenshot saved: {path}")
    except Exception as ss_err:
        print(f"   WARNING: Could not save screenshot: {ss_err}")

try:
    # ── Step 1: Load the admin settings page ──────────────────────────────
    admin_url = f"{BASE_HOST}{ROOT_PATH}/admin/settings"
    print(f"1. Loading {admin_url} ...")
    driver.get(admin_url)
    time.sleep(8)
    print(f"   URL: {driver.current_url}")
    print(f"   Title: {driver.title}")

    # ── Step 2: Dismiss modals ─────────────────────────────────────────────
    print("\n2. Dismissing modals...")
    for _ in range(5):
        modals = driver.find_elements(By.CSS_SELECTOR, "[aria-modal='true']")
        if not modals:
            break
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        driver.execute_script(
            'document.querySelectorAll("[aria-modal=\'true\']").forEach(function(m){m.remove();});'
        )
        time.sleep(1)

    # ── Step 3: Check all anchor hrefs on the page ──────────────────────────
    print("\n3. Checking all links on admin settings page...")
    link_data = driver.execute_script("""
        var links = document.querySelectorAll('a[href]');
        var results = [];
        for (var i = 0; i < links.length; i++) {
            var href = links[i].getAttribute('href');
            var text = links[i].textContent.trim().substring(0, 50);
            var ariaLabel = links[i].getAttribute('aria-label') || '';
            // Only check internal links (not external, not #, not javascript)
            if (href && !href.startsWith('http') && !href.startsWith('#') &&
                !href.startsWith('javascript') && !href.startsWith('mailto')) {
                results.push({href: href, text: text, ariaLabel: ariaLabel});
            }
        }
        return results;
    """)

    print(f"   Found {len(link_data)} internal links")
    bad_links = []
    for link in link_data:
        href = link['href']
        text = link['text']
        aria = link['ariaLabel']
        label = f"'{text}'" if text else f"'{aria}'" if aria else href

        if href.startswith('/') and not href.startswith(ROOT_PATH) and href != '/':
            bad_links.append(link)
            print(f"     BROKEN: {label} -> {href}")
        elif href.startswith(ROOT_PATH):
            print(f"     OK: {label} -> {href}")

    if bad_links:
        errors.append(f"{len(bad_links)} internal links missing root path prefix on admin/settings")
        print(f"\n   FAIL: {len(bad_links)} links missing root path prefix:")
        for link in bad_links:
            print(f"     {link['text'] or link['ariaLabel']} -> {link['href']}")
    else:
        print("\n   PASS: All internal links include root path prefix")

    # ── Step 4: Check for JS errors ────────────────────────────────────────
    print("\n4. Checking for JS errors...")
    logs = driver.get_log("browser")
    severe = [l for l in logs if "SEVERE" in l.get("level", "")]
    unexpected_severe = [
        l for l in severe
        if "/ollama/api/version" not in l.get("message", "")
        and "/favicon" not in l.get("message", "")
        and "/static/favicon" not in l.get("message", "")
        and "404" not in l.get("message", "").lower() or ROOT_PATH not in l.get("message", "")
    ]
    # 404s for paths WITH root path are expected (route may not exist or redirect)
    # 404s for paths WITHOUT root path are broken links
    broken_404s = [
        l for l in logs
        if "404" in l.get("message", "").lower()
        and "http://" in l.get("message", "")
        and ROOT_PATH not in l.get("message", "")
        and "/api/" not in l.get("message", "")
        and "/ollama/" not in l.get("message", "")
        and "/ws/" not in l.get("message", "")
    ]
    print(f"   Total severe JS errors: {len(severe)}")
    print(f"   Unexpected severe errors: {len(unexpected_severe)}")
    print(f"   Broken 404s (missing root path): {len(broken_404s)}")
    for e in broken_404s[:5]:
        errors.append(f"Broken 404: {e['message'][:150]}")
        print(f"     {e['message'][:200]}")

    # ── Step 5: Also check the admin/settings/general sub-page ──────────────
    print("\n5. Loading admin/settings/general sub-page...")
    driver.get(f"{BASE_HOST}{ROOT_PATH}/admin/settings/general")
    time.sleep(5)

    # Check links on this sub-page too
    sub_link_data = driver.execute_script("""
        var links = document.querySelectorAll('a[href]');
        var results = [];
        for (var i = 0; i < links.length; i++) {
            var href = links[i].getAttribute('href');
            var text = links[i].textContent.trim().substring(0, 50);
            if (href && !href.startsWith('http') && !href.startsWith('#') &&
                !href.startsWith('javascript') && !href.startsWith('mailto')) {
                results.push({href: href, text: text});
            }
        }
        return results;
    """)

    print(f"   Found {len(sub_link_data)} internal links on sub-page")
    sub_bad_links = []
    for link in sub_link_data:
        href = link['href']
        text = link['text']
        if href.startswith('/') and not href.startswith(ROOT_PATH) and href != '/':
            sub_bad_links.append(link)
            print(f"     BROKEN: {text} -> {href}")
        elif href.startswith(ROOT_PATH):
            print(f"     OK: {text} -> {href}")

    if sub_bad_links:
        errors.append(f"{len(sub_bad_links)} links missing root path prefix on admin/settings/general")
        print(f"\n   FAIL: {len(sub_bad_links)} links missing root path on sub-page")
    else:
        print("\n   PASS: All links on sub-page include root path")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print("FAILURES:")
        for e in errors:
            print(f"  - {e}")
        print("=" * 60)
        save_screenshot("failure_admin_settings_links")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        print("=" * 60)
        save_screenshot("success_admin_settings_links")
        sys.exit(0)

except Exception as e:
    print(f"FATAL: {e}")
    import traceback
    traceback.print_exc()
    save_screenshot("failure_admin_settings_links")
    sys.exit(2)
finally:
    driver.quit()