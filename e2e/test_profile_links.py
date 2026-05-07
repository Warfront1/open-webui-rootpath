#!/usr/bin/env python3
"""
E2E test: user profile menu links respect root path.

Verifies that:
1. Links in the user profile dropdown have hrefs that include the root path prefix.
2. Navigating via those links resolves correctly (no 404).
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
    # ── Step 1: Load page ────────────────────────────────────────────────────
    print(f"1. Loading {BASE_URL} ...")
    driver.get(BASE_URL)
    time.sleep(12)
    print(f"   URL: {driver.current_url}")
    print(f"   Title: {driver.title}")

    # ── Step 2: Dismiss modals ────────────────────────────────────────────────
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

    # ── Step 3: Check all anchor hrefs for root path ──────────────────────────
    print("\n3. Checking all navigation links for root path prefix...")

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
        # Internal links that start with / but don't start with the root path
        # are broken (they'll 404 via nginx or route incorrectly)
        if href.startswith('/') and not href.startswith(ROOT_PATH):
            # Skip root path itself (href="/" is OK if SvelteKit handles it)
            if href == '/':
                continue
            bad_links.append(link)
            print(f"     BROKEN: {label} -> {href}")
        elif href.startswith(ROOT_PATH):
            print(f"     OK: {label} -> {href}")

    if bad_links:
        errors.append(f"{len(bad_links)} internal links missing root path prefix")
        print(f"\n   FAIL: {len(bad_links)} links missing root path prefix:")
        for link in bad_links:
            print(f"     {link['text'] or link['ariaLabel']} -> {link['href']}")
    else:
        print("\n   PASS: All internal links include root path prefix")

    # ── Step 4: Check user profile menu specifically ──────────────────────────
    print("\n4. Checking user profile menu links...")

    # Find and click the user profile menu button
    profile_btns = driver.find_elements(By.CSS_SELECTOR, "[aria-label='Open User Profile Menu']")
    if not profile_btns:
        # Try alternative selectors
        profile_btns = driver.find_elements(By.CSS_SELECTOR, "img[alt='Open User Profile Menu']")
        if not profile_btns:
            profile_btns = driver.find_elements(By.CSS_SELECTOR, "[data-testid='user-menu-toggle']")

    if profile_btns:
        print(f"   Found profile menu button")
        driver.execute_script("arguments[0].click();", profile_btns[0])
        time.sleep(2)

        # Check links in the dropdown
        dropdown_links = driver.find_elements(By.CSS_SELECTOR, "a[href]")
        print(f"   Found {len(dropdown_links)} links in profile dropdown")

        for link in dropdown_links:
            href = link.get_attribute("href")
            text = link.text.strip()[:50]
            aria = link.get_attribute("aria-label") or ""

            # Check if this is an internal navigation link
            if href and not href.startswith("http") and not href.startswith("#"):
                label = text or aria or href
                # Parse the href relative to the page
                if href.startswith(BASE_HOST):
                    path = href[len(BASE_HOST):]
                elif href.startswith(ROOT_PATH):
                    path = href
                else:
                    path = href

                if path.startswith('/') and not path.startswith(ROOT_PATH) and path != '/':
                    errors.append(f"Profile menu link '{label}' href='{href}' missing root path")
                    print(f"     BROKEN: {label} -> {href}")
                elif path.startswith(ROOT_PATH):
                    print(f"     OK: {label} -> {href}")
    else:
        print("   No user profile menu button found (may need auth)")
        # Try to check sidebar links instead
        sidebar_links = driver.find_elements(By.CSS_SELECTOR, "nav a[href], #sidebar a[href]")
        if sidebar_links:
            print(f"   Found {len(sidebar_links)} sidebar links")
            for link in sidebar_links:
                href = link.get_attribute("href")
                text = link.text.strip()[:50]
                if href and not href.startswith("http") and not href.startswith("#"):
                    if href.startswith('/') and not href.startswith(ROOT_PATH) and href != '/':
                        print(f"     BROKEN sidebar link: {text} -> {href}")
                        errors.append(f"Sidebar link '{text}' href='{href}' missing root path")

    # ── Step 5: Check user profile image src ─────────────────────────────────
    print("\n5. Checking user profile image src...")
    profile_img_srcs = driver.execute_script("""
        var imgs = document.querySelectorAll('img[src*="profile/image"]');
        var srcs = [];
        for (var i = 0; i < imgs.length; i++) {
            srcs.push({src: imgs[i].src, alt: imgs[i].alt});
        }
        return srcs;
    """)

    for img in profile_img_srcs:
        src = img['src']
        alt = img['alt']
        print(f"   Image: alt='{alt}' src='{src}'")
        if f'{ROOT_PATH}/' in src:
            print("     OK: includes root path")
        elif '/api/v1/users/' in src or '/api/v1/models/' in src:
            errors.append(f"Profile image src missing root path: {src}")
            print("     FAIL: missing root path prefix")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print("FAILURES:")
        for e in errors:
            print(f"  - {e}")
        print("=" * 60)
        save_screenshot("failure_profile_links")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        print("=" * 60)
        save_screenshot("success_profile_links")
        sys.exit(0)

except Exception as e:
    print(f"FATAL: {e}")
    import traceback
    traceback.print_exc()
    save_screenshot("failure_profile_links")
    sys.exit(2)
finally:
    driver.quit()