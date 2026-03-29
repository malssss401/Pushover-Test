import os
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
import requests

# Credentials
USER_KEY = os.environ.get("PUSHOVER_USER")
API_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def send_push(message):
    print(f"Pushing: {message}")
    if USER_KEY and API_TOKEN:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": API_TOKEN, "user": USER_KEY, "message": message
        })

def run_test():
    with sync_playwright() as p:
        # 1. Launch Browser with Stealth
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        stealth_sync(page) # Mimics human browser fingerprint
        
        page.set_default_timeout(60000) # 60s timeout for every action

        try:
            print("🚀 Step 1: Loading ICAI Website...")
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", wait_until="domcontentloaded")

            # --- STEP 2: SELECT REGION ---
            print("📍 Step 2: Selecting Southern (Value 4)...")
            # We use the ID 'ddl_reg' from your screenshot
            page.wait_for_selector("#ddl_reg", state="visible")
            page.select_option("#ddl_reg", value="4")
            
            # CRITICAL: Wait for the page to 'freeze' and 'unfreeze' (The Postback)
            print("⏳ Waiting for City list to refresh (Postback)...")
            time.sleep(5) 
            page.wait_for_load_state("networkidle")

            # --- STEP 3: SELECT CITY ---
            print("🏙️ Step 3: Selecting Alappuzha (Value 101)...")
            # Wait until the option '101' actually exists in the HTML
            page.wait_for_selector("option[value='101']", state="attached", timeout=30000)
            page.select_option("select[id*='ddlPOU']", value="101")
            
            # --- STEP 4: SELECT COURSE ---
            print("📚 Step 4: Selecting Course (Value 48)...")
            page.select_option("select[id*='ddlCourse']", value="48")

            # --- STEP 5: SEARCH ---
            print("🔍 Step 5: Clicking Search...")
            page.click("input[id*='btnSearch']")
            
            # Wait for the result table or 'No Record' message
            print("⏳ Waiting for results table...")
            page.wait_for_selector("table, .alert, b", timeout=30000)
            time.sleep(3) # Final render buffer
            
            # Take Success Screenshot
            page.screenshot(path="debug_screenshot.png", full_page=True)

            # --- STEP 6: PARSE ---
            rows = page.query_selector_all("tr")
            total_seats = 0
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 2:
                    text = cols[1].inner_text().strip()
                    if text.isdigit():
                        total_seats += int(text)

            send_push(f"✅ Success! Found {total_seats} seats in Alappuzha.")

        except Exception as e:
            print(f"❌ Script Error: {e}")
            # Take Error Screenshot to see what went wrong
            try:
                page.screenshot(path="error_screenshot.png", full_page=True)
            except:
                pass
            send_push(f"⚠️ Search failed. Check GitHub Artifacts for error_screenshot.")
            exit(1) # Keeps the 'Exit Code 1' for GitHub logs
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
