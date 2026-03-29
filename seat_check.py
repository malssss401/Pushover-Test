import os
import time
from playwright.sync_api import sync_playwright
# Using the specific sync function to avoid the 'module' error
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
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        # Corrected function call
        stealth_sync(page)

        try:
            print("🚀 Loading Website...")
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", timeout=90000)
            
            # Save an immediate screenshot
            time.sleep(5)
            page.screenshot(path="debug_screenshot.png")
            
            print("📍 Selecting Region...")
            page.wait_for_selector("select[id*='reg']", timeout=30000)
            page.select_option("select[id*='reg']", value="4")
            
            print("⏳ Waiting for POU to unlock...")
            # Wait for the City dropdown to become enabled
            page.wait_for_function("() => !document.querySelector('select[id*=\"POU\"]').disabled", timeout=30000)
            
            print("🏙️ Selecting City & Course...")
            page.select_option("select[id*='POU']", value="101")
            page.select_option("select[id*='Course']", value="48")

            print("🔍 Clicking Search...")
            page.click("input[id*='Search']")
            
            # Wait for results table
            page.wait_for_selector("tr", timeout=30000)
            time.sleep(2)
            page.screenshot(path="debug_screenshot.png")

            # Parse table
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
            print(f"❌ Error: {e}")
            page.screenshot(path="error_screenshot.png")
            send_push(f"⚠️ Script Error: Check artifacts.")
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
