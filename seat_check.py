import os
from playwright.sync_api import sync_playwright
import requests

# Credentials
USER_KEY = os.environ.get("PUSHOVER_USER")
API_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def send_push(message):
    requests.post("https://api.pushover.net/1/messages.json", data={
        "token": API_TOKEN, "user": USER_KEY, "message": message
    })

def run_test():
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        try:
            print("Navigating to ICAI...")
            page.goto("https://www.icaionlineregistration.org/launchbatchdetail.aspx", wait_until="networkidle")

            # 1. Select Region
            print("Selecting Region...")
            page.select_option("select[id*='ddlRegion']", label="Southern")
            page.wait_for_load_state("networkidle") # Wait for City list to refresh

            # 2. Select POU (City)
            print("Selecting City...")
            page.select_option("select[id*='ddlPOU']", label="Alappuzha")
            
            # 3. Select Course
            print("Selecting Course...")
            page.select_option("select[id*='ddlCourse']", label="AICITSS - Advanced Information Technology")

            # 4. Click Search
            print("Clicking Search...")
            page.click("input[id*='btnSearch']")
            page.wait_for_load_state("networkidle")

            # 5. Parse the table
            print("Parsing results...")
            rows = page.query_selector_all("tr")
            total_seats = 0
            
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 2:
                    text = cols[1].inner_text().strip()
                    if text.isdigit():
                        total_seats += int(text)

            if total_seats > 0:
                send_push(f"✅ Playwright Success! Found {total_seats} seats in Alappuzha.")
            else:
                send_push("🔍 Playwright Success: 0 seats found (Search worked).")

        except Exception as e:
            print(f"Error: {e}")
            send_push(f"❌ Playwright Error: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_test()
