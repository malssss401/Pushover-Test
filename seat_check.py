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
        # Launch with specific arguments to bypass detection
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        
        # Mimic a high-end Windows Chrome user perfectly
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        try:
            print("⚡ Navigating...")
            # We go to the URL and wait only for the first bit of data
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", wait_until="commit", timeout=30000)

            # --- STEP 1: REGION ---
            print("📍 Selecting Southern (4)...")
            page.wait_for_selector("select[id*='ddlRegion']", timeout=10000)
            page.select_option("select[id*='ddlRegion']", value="4")
            
            # --- STEP 2: WAIT FOR AJAX ---
            # Instead of networkidle, we wait for the POU dropdown to NOT be disabled
            print("⏳ Waiting for POU to unlock...")
            page.wait_for_function("id => !document.getElementById(id).disabled", 
                                    arg="ctl00_ContentPlaceHolder1_ddlPOU", timeout=15000)

            # --- STEP 3: CITY & COURSE ---
            print("🏙️ Selecting Alappuzha (101)...")
            page.select_option("select[id*='ddlPOU']", value="101")
            page.select_option("select[id*='ddlCourse']", value="48")

            # --- STEP 4: SEARCH ---
            print("🔍 Clicking Search...")
            page.click("input[id*='btnSearch']")
            
            # Wait specifically for the results table or the "No Record" message
            page.wait_for_selector("table, .alert, b", timeout=15000)
            
            # Final 2-second breath for the text to render
            time.sleep(2)
            page.screenshot(path="debug_screenshot.png")

            # --- STEP 5: COUNT ---
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
            send_push(f"⚠️ Script failed. Server might be blocking.")
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
