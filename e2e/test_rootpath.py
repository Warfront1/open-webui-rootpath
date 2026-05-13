#!/usr/bin/env python3
"""
E2E test for Open WebUI running under a root path (/openwebui) via nginx reverse proxy.

Uses Selenium Chrome (headless) to:
1. Load the app at /openwebui/
2. Verify __sveltekit base path resolves correctly
3. Dismiss any onboarding modals
4. Select a model from the dropdown
5. Send a chat message and wait for a response

Prerequisites:
  - Docker Compose stack running (docker compose up -d)
  - Selenium Chrome container on the same Docker network
"""
import time
import sys
import os
import io
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# URL must use the Docker network hostname (nginx service name) and the root path prefix
ROOT_PATH = os.environ.get("E2E_ROOT_PATH", "/openwebui")
BASE_URL = os.environ.get("E2E_BASE_URL", f"http://nginx:80{ROOT_PATH}/")
MODEL_KEYWORD = os.environ.get("E2E_MODEL_KEYWORD", "minimax-m2.5")
CHAT_MESSAGE = os.environ.get("E2E_CHAT_MESSAGE", "Say hello in one word")
RESPONSE_TIMEOUT = int(os.environ.get("E2E_RESPONSE_TIMEOUT", "60"))
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", "/tmp/e2e-screenshots")

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1920,1080")

_log_buffer = io.StringIO()

class TeeOutput:
    def __init__(self, *targets):
        self._targets = targets
    def write(self, data):
        for t in self._targets:
            t.write(data)
    def flush(self):
        for t in self._targets:
            t.flush()

sys.stdout = TeeOutput(sys.__stdout__, _log_buffer)
sys.stderr = TeeOutput(sys.__stderr__, _log_buffer)

driver = webdriver.Chrome(options=opts)
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

def save_log(prefix="failure"):
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"{prefix}_{ts}.txt")
        with open(path, "w") as f:
            f.write(_log_buffer.getvalue())
        print(f"   Log saved: {path}")
    except Exception as log_err:
        print(f"   WARNING: Could not save log: {log_err}")

try:
    # ── Step 1: Load page ────────────────────────────────────────
    print(f"1. Loading {BASE_URL} ...")
    driver.get(BASE_URL)
    time.sleep(12)
    print(f"   URL: {driver.current_url}")
    print(f"   Title: {driver.title}")

    # ── Step 2: Verify __sveltekit base path ─────────────────────
    base_val = driver.execute_script("""
        for (var k of Object.keys(globalThis)) {
            if (k.startsWith('__sveltekit')) return globalThis[k].base;
        }
        return 'NOT_FOUND';
    """)
    print(f"   __sveltekit base: {base_val}")
    if base_val != ROOT_PATH:
        errors.append(f"Expected __sveltekit base '{ROOT_PATH}', got '{base_val}'")
    else:
        print(f"   PASS: __sveltekit base = {ROOT_PATH}")

    # ── Step 3: Dismiss modals ───────────────────────────────────
    print("\n2. Dismissing modals...")
    for _ in range(5):
        modals = driver.find_elements(By.CSS_SELECTOR, "[aria-modal='true']")
        if not modals:
            break
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        driver.execute_script(
            "document.querySelectorAll(\"[aria-modal='true']\").forEach(function(m){m.remove();});"
        )
        time.sleep(1)

    # ── Step 4: Select model ─────────────────────────────────────
    print("\n3. Selecting model...")
    model_btns = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Select a model']")
    if not model_btns:
        errors.append("No model selector button found")
    else:
        driver.execute_script("arguments[0].click();", model_btns[0])
        time.sleep(2)
        options = driver.find_elements(By.CSS_SELECTOR, "[role='option'], li")
        available_models = [opt.text.strip() for opt in options if opt.text.strip()]
        print(f"   Available models ({len(available_models)}): {available_models}")
        selected = False
        for opt in options:
            if MODEL_KEYWORD in opt.text.lower():
                driver.execute_script("arguments[0].click();", opt)
                print(f"   Selected model: {opt.text.strip()}")
                selected = True
                break
        if not selected:
            errors.append(f"No model matching '{MODEL_KEYWORD}' found in dropdown")
        time.sleep(2)

    # Dismiss any post-selection modals
    for _ in range(5):
        modals = driver.find_elements(By.CSS_SELECTOR, "[aria-modal='true']")
        if modals:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            driver.execute_script(
                "document.querySelectorAll(\"[aria-modal='true']\").forEach(function(m){m.remove();});"
            )
        time.sleep(0.5)

    # ── Step 5: Find chat input and send message ─────────────────
    print("\n4. Finding chat input...")
    chat_input = None
    textareas = driver.find_elements(By.TAG_NAME, "textarea")
    content_editables = driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
    if textareas:
        chat_input = textareas[0]
    elif content_editables:
        chat_input = content_editables[0]

    if not chat_input:
        errors.append("No chat input (textarea or contenteditable) found")
    else:
        print("   Chat input found")
        chat_input.click()
        time.sleep(0.5)
        chat_input.send_keys(CHAT_MESSAGE)
        time.sleep(1)

        send_btns = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Send']")
        if send_btns:
            driver.execute_script("arguments[0].click();", send_btns[0])
            print(f"   Sent: '{CHAT_MESSAGE}' (via send button)")
        else:
            chat_input.send_keys(Keys.RETURN)
            print(f"   Sent: '{CHAT_MESSAGE}' (via Enter key)")

        # ── Step 6: Wait for response ────────────────────────────
        print(f"\n5. Waiting up to {RESPONSE_TIMEOUT}s for LLM response...")
        time.sleep(RESPONSE_TIMEOUT)

        # Check for response completion indicator and extract assistant text
        responding = driver.execute_script("""
            var spinners = document.querySelectorAll(
                '[class*="loading"], [class*="spinner"], [class*="streaming"]'
            );
            var stillResponding = spinners.length > 0;
            var markdownEls = document.querySelectorAll(
                '.markdown, .prose, [class*="markdown"], [class*="prose"]'
            );
            var texts = [];
            for (var j = 0; j < markdownEls.length; j++) {
                var text = markdownEls[j].textContent.trim();
                if (text.length > 0) texts.push(text);
            }
            return { responding: stillResponding, texts: texts };
        """)

        user_msg = CHAT_MESSAGE.lower()
        all_texts = responding.get("texts", []) if responding else []
        still_responding = responding.get("responding", False) if responding else False

        # Filter out the user's own message and short metadata-only strings
        assistant_responses = [
            r for r in all_texts
            if r.lower() != user_msg and len(r) > 10
            and "today at" not in r.lower()
            and "internal server error" not in r.lower()
        ]

        has_server_error = any(
            "internal server error" in r.lower() for r in all_texts
        )

        print(f"   Still responding: {still_responding}")
        print(f"   Extracted {len(assistant_responses)} assistant responses")
        print(f"   Server error in response: {has_server_error}")
        for r in all_texts[:5]:
            print(f"     raw: {r[:200]}")

        if assistant_responses and not still_responding and not has_server_error:
            print("\n   PASS: Assistant response received")
        else:
            if has_server_error:
                errors.append("Internal Server Error in assistant response")
                print("\n   FAIL: Internal Server Error in assistant response")
            else:
                errors.append("No completed assistant response received (still spinning or empty)")
                print("\n   FAIL: No completed assistant response received")

    # ── Step 7: Check for JS errors ──────────────────────────────
    print("\n6. Checking for JS errors...")
    logs = driver.get_log("browser")
    severe = [l for l in logs if "SEVERE" in l.get("level", "")]
    # Filter out the expected Ollama version endpoint error
    unexpected_severe = [
        l for l in severe
        if "/ollama/api/version" not in l.get("message", "")
        and "/favicon" not in l.get("message", "")
        and "/static/favicon" not in l.get("message", "")
    ]
    print(f"   Total severe JS errors: {len(severe)}")
    print(f"   Unexpected severe errors: {len(unexpected_severe)}")
    for e in unexpected_severe[:5]:
        errors.append(f"JS error: {e['message'][:150]}")
        print(f"     {e['message'][:200]}")

    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print("FAILURES:")
        for e in errors:
            print(f"  - {e}")
        print("=" * 60)
        save_screenshot()
        save_log()
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        print("=" * 60)
        save_screenshot("success")
        save_log("success")
        sys.exit(0)

except Exception as e:
    print(f"FATAL: {e}")
    import traceback
    traceback.print_exc()
    save_screenshot()
    save_log()
    sys.exit(2)
finally:
    driver.quit()