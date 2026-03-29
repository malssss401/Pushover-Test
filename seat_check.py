import os
import time
from playwright.sync_api import sync_playwright
import requests

# Credentials
USER_KEY = os.environ.get("PUSHOVER_USER")
API_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def send_push(message):
    print(f"Pushover: {message}")
    if USER_KEY and API_TOKEN:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": API_TOKEN, "user": USER_KEY, "message": message
        })

def run_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = context.new_page()
        page.set_default_timeout(90000) 

        try:
            print("1. Loading ICAI Page...")
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", wait_until="networkidle")

            # Select Region (Value 4)
            print("2. Selecting Southern (4)...")
            page.select_option("select[id*='ddlRegion']", value="4")
            
            # Wait for City List (Value 101)
            print("3. Waiting for Alappuzha (101)...")
            page.wait_for_selector("option[value='101']", state="attached", timeout=30000)

            # Select City (101) & Course (48)
            print("4. Selecting City & Course...")
            page.select_option("select[id*='ddlPOU']", value="101")
            page.select_option("select[id*='ddlCourse']", value="48")

            # Click Search
            print("5. Clicking Search...")
            page.click("input[id*='btnSearch']")
            
            # Wait for results
            print("6. Waiting for table...")
            page.wait_for_load_state("networkidle")
            time.sleep(5) 

            # Screenshot for Artifacts
            page.screenshot(path="debug_screenshot.png", full_page=True)

            # Parse Table
            rows = page.query_selector_all("tr")
            total_seats = 0
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 2:
                    text = cols[1].inner_text().strip()
                    if text.isdigit():
                        total_seats += int(text)

            msg = f"✅ Final Seat Count: {total_seats}"
            print(msg)
            send_push(msg)

        except Exception as e:
            print(f"❌ Error: {e}")
            page.screenshot(path="error_screenshot.png")
            send_push(f"❌ Playwright Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
