import os
import time
from playwright.sync_api import sync_playwright
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

        try:
            print("🚀 Loading page...")
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", wait_until="load")

            # --- STEP 1: TRIGGER THE POSTBACK ---
            print("📍 Selecting Southern and triggering JavaScript...")
            # We don't just select; we select and then manually fire the 'change' event
            page.select_option("select[id='ddl_reg']", value="4")
            page.eval_on_selector("select[id='ddl_reg']", "el => el.dispatchEvent(new Event('change', { bubbles: True }))")
            
            # This causes a page reload. We must wait for the network to be quiet again.
            page.wait_for_load_state("networkidle")
            time.sleep(3) # Safety buffer for the ASP.NET state to settle

            # --- STEP 2: SELECT CITY & COURSE ---
            print("🏙️ Selecting Alappuzha & Course...")
            # Ensure the city dropdown is actually ready
            page.wait_for_selector("option[value='101']", state="attached", timeout=10000)
            
            page.select_option("select[id*='ddlPOU']", value="101")
            page.select_option("select[id*='ddlCourse']", value="48")

            # --- STEP 3: SEARCH ---
            print("🔍 Clicking Search...")
            # Using 'click' with a forced wait for the table
            page.click("input[id*='btnSearch']")
            
            # Look for the table specifically
            page.wait_for_selector("tr", timeout=15000)
            time.sleep(2)
            
            # Screenshot for your debug archive
            page.screenshot(path="debug_screenshot.png")

            # --- STEP 4: COUNT ---
            rows = page.query_selector_all("tr")
            total_seats = 0
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 2:
                    val = cols[1].inner_text().strip()
                    if val.isdigit():
                        total_seats += int(val)

            send_push(f"✅ Success! Found {total_seats} seats.")

        except Exception as e:
            print(f"❌ Error: {e}")
            page.screenshot(path="error_screenshot.png")
            send_push(f"⚠️ Script failed. Table did not load.")
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
