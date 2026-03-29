import os
import time
from playwright.sync_api import sync_playwright
import requests

# Credentials
USER_KEY = os.environ.get("PUSHOVER_USER")
API_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def send_push(message):
    print(f"Sending: {message}")
    requests.post("https://api.pushover.net/1/messages.json", data={
        "token": API_TOKEN, "user": USER_KEY, "message": message
    })

def run_test():
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        try:
            print("1. Navigating to ICAI...")
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", wait_until="domcontentloaded")

            # 1. Select Region (Value 4)
            print("2. Selecting Southern (Value 4)...")
            page.select_option("select[id*='ddlRegion']", value="4")
            
            # Wait for the City dropdown to actually contain the value 101
            print("Waiting for City list to populate...")
            page.wait_for_selector("select[id*='ddlPOU'] option[value='101']", timeout=10000)

            # 2. Select POU (Value 101)
            print("3. Selecting Alappuzha (Value 101)...")
            page.select_option("select[id*='ddlPOU']", value="101")
            
            # 3. Select Course (Value 48)
            print("4. Selecting Course (Value 48)...")
            page.select_option("select[id*='ddlCourse']", value="48")

            # 4. Click Search
            print("5. Clicking Search...")
            # We use 'dispatch_event' to ensure the ASP.NET click fires correctly
            page.click("input[id*='btnSearch']")
            
            # Wait for the table to appear (looking for the GridView ID)
            print("Waiting for results table...")
            page.wait_for_selector("table[id*='gvLaunchBatch']", timeout=10000)
            
            # Capture screenshot for your debug zip
            page.screenshot(path="debug_screenshot.png")

            # 5. Parse the table
            rows = page.query_selector_all("table[id*='gvLaunchBatch'] tr")
            total_seats = 0
            
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 2:
                    text = cols[1].inner_text().strip()
                    if text.isdigit():
                        total_seats += int(text)

            msg = f"✅ Success! Found {total_seats} seats using ID codes."
            send_push(msg)

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="error_screenshot.png")
            send_push(f"❌ Playwright Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
