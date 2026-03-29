import os
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
import requests

USER_KEY = os.environ.get("PUSHOVER_USER")
API_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def send_push(message):
    if USER_KEY and API_TOKEN:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": API_TOKEN, "user": USER_KEY, "message": message
        })

def run_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = context.new_page()
        stealth_sync(page)

        try:
            print("🚀 Loading Website...")
            # We use a very long timeout (90s) just for the initial load
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", timeout=90000)
            
            # 1. Check for Cloudflare/Bot protection
            time.sleep(5)
            page.screenshot(path="debug_screenshot.png") # Save immediately to see what we're looking at
            
            print("📍 Looking for Region dropdown...")
            # We use a broader selector in case the ID is slightly different
            region_dropdown = page.wait_for_selector("select", timeout=30000)
            
            # 2. Select Southern
            # Using the value '4' directly on the first select found if ID fails
            page.select_option("select[id*='reg']", value="4")
            print("✅ Selected Southern. Waiting for Postback...")
            
            # Wait for the City dropdown to become 'enabled'
            page.wait_for_function("() => !document.querySelector('select[id*=\"POU\"]').disabled", timeout=30000)
            
            # 3. Select City and Course
            print("🏙️ Selecting Alappuzha & Course...")
            page.select_option("select[id*='POU']", value="101")
            page.select_option("select[id*='Course']", value="48")

            # 4. Search
            print("🔍 Clicking Search...")
            page.click("input[id*='Search']")
            
            # Wait for any table to appear
            page.wait_for_selector("table", timeout=30000)
            page.screenshot(path="debug_screenshot.png")

            # 5. Parse
            rows = page.query_selector_all("tr")
            total_seats = 0
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 2:
                    val = cols[1].inner_text().strip()
                    if val.isdigit():
                        total_seats += int(val)

            send_push(f"✅ Success! Seats: {total_seats}")

        except Exception as e:
            print(f"❌ Crash Details: {e}")
            page.screenshot(path="error_screenshot.png")
            send_push(f"⚠️ Script crashed: {str(e)[:50]}")
            # Don't exit(1) yet so the Action finishes 'successfully' and uploads the artifact
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
