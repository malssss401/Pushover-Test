import os
import time
from playwright.sync_api import sync_playwright
import requests

USER_KEY = os.environ.get("PUSHOVER_USER")
API_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def send_push(message):
    requests.post("https://api.pushover.net/1/messages.json", data={
        "token": API_TOKEN, "user": USER_KEY, "message": message
    })

def run_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Higher timeout (60s) to handle slow government servers
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = context.new_page()
        page.set_default_timeout(60000) 

        try:
            print("1. Loading ICAI Page...")
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", wait_until="networkidle")

            # Select Region
            print("2. Selecting Southern (Value 4)...")
            page.select_option("select[id*='ddlRegion']", value="4")
            
            # Wait for the City list to actually contain Alappuzha (101)
            page.wait_for_selector("option[value='101']", state="attached", timeout=30000)

            # Select City & Course
            print("3. Selecting Alappuzha & Course...")
            page.select_option("select[id*='ddlPOU']", value="101")
            page.select_option("select[id*='ddlCourse']", value="48")

            # Click Search
            print("4. Clicking Search...")
            page.click("input[id*='btnSearch']")
            
            # CRITICAL: Wait for the network to go quiet after the search
            print("Waiting for results to load...")
            page.wait_for_load_state("networkidle")
            time.sleep(5) # Extra buffer for the table to render

            # Take the debug screenshot
            page.screenshot(path="debug_screenshot.png", full_page=True)

            # Parse Table
            rows = page.query_selector_all("tr")
            total_seats = 0
            found_data = []

            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 2:
                    text = cols[1].inner_text().strip()
                    if text.isdigit():
                        count = int(text)
                        total_seats += count
                        found_data.append(f"Batch: {cols[0].inner_text()[:15]}.. -> {count}")

            if total_seats > 0:
                msg = f"✅ SUCCESS! Total Seats: {total_seats}\n" + "\n".join(found_data)
            else:
                msg = "🔍 Search finished, but 0 seats were counted in the table."
            
            send_push(msg)

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="error_screenshot.png")
            send_push(f"❌ Playwright Timeout/Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
