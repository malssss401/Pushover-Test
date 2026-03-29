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
        # Launch with stealth settings
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        # Apply stealth to the context
        page = context.new_page()
        stealth_sync(page)

        try:
            print("🚀 Loading ICAI with Stealth Mode...")
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", wait_until="load")

            # --- HUMAN-LIKE INTERACTION ---
            # Instead of just selecting, we click it first to 'focus'
            reg_selector = "select[id='ddl_reg']"
            page.wait_for_selector(reg_selector)
            
            print("🖱️ Hovering and Clicking Region...")
            page.hover(reg_selector)
            page.click(reg_selector)
            
            # Select Southern (4)
            page.select_option(reg_selector, value="4")
            
            # Wait for the ASP.NET Postback to finish
            print("⏳ Waiting for page refresh (Postback)...")
            page.wait_for_load_state("networkidle")
            time.sleep(5) # The critical 'patience' buffer

            # --- SELECT CITY & COURSE ---
            # Using the specific value you found (101)
            print("🏙️ Selecting Alappuzha (101)...")
            page.wait_for_selector("option[value='101']", state="attached")
            page.select_option("select[id*='ddlPOU']", value="101")
            
            page.select_option("select[id*='ddlCourse']", value="48")

            # --- SEARCH ---
            print("🔍 Clicking Search...")
            page.click("input[id*='btnSearch']")
            
            # Use a longer timeout for the result table
            page.wait_for_selector("tr", timeout=20000)
            page.screenshot(path="debug_screenshot.png")

            # --- COUNT ---
            rows = page.query_selector_all("tr")
            total_seats = 0
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 2:
                    val = cols[1].inner_text().strip()
                    if val.isdigit():
                        total_seats += int(val)

            send_push(f"✅ Stealth Success! Found {total_seats} seats.")

        except Exception as e:
            print(f"❌ Error: {e}")
            page.screenshot(path="error_screenshot.png")
            send_push(f"⚠️ Table did not load. Check debug_screenshot in Artifacts.")
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
