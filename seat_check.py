import requests
from bs4 import BeautifulSoup
import os
import time

URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
USER_KEY = os.environ.get("PUSHOVER_USER")
API_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def send_push(message):
    print(f"Sending Pushover: {message[:50]}...")
    resp = requests.post("https://api.pushover.net/1/messages.json", data={
        "token": API_TOKEN,
        "user": USER_KEY,
        "message": message
    })
    print(f"Pushover Response: {resp.status_code} - {resp.text}")

def run_test():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": URL
    })

    try:
        # STEP 1: Get tokens
        r = session.get(URL)
        soup = BeautifulSoup(r.text, "html.parser")
        
        def get_data(s):
            return {
                "__VIEWSTATE": s.find("input", {"id": "__VIEWSTATE"})["value"],
                "__VIEWSTATEGENERATOR": s.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
                "__EVENTVALIDATION": s.find("input", {"id": "__EVENTVALIDATION"})["value"],
            }

        # STEP 2: Trigger the Region Change
        data = get_data(soup)
        data.update({
            "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlRegion",
            "ctl00$ContentPlaceHolder1$ddlRegion": "Southern"
        })
        r = session.post(URL, data=data)
        time.sleep(1) # Small delay for server processing
        
        # STEP 3: Final Search
        soup = BeautifulSoup(r.text, "html.parser")
        data = get_data(soup)
        data.update({
            "ctl00$ContentPlaceHolder1$ddlRegion": "Southern",
            "ctl00$ContentPlaceHolder1$ddlPOU": "Alappuzha",
            "ctl00$ContentPlaceHolder1$ddlCourse": "AICITSS - Advanced Information Technology",
            "ctl00$ContentPlaceHolder1$btnSearch": "Get List"
        })
        
        r = session.post(URL, data=data)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # --- PARSING ---
        total_seats = 0
        table = soup.find("table", {"id": "ctl00_ContentPlaceHolder1_gvLaunchBatch"})
        
        if table:
            rows = table.find_all("tr")[1:] # Skip header
            for row in rows:
                cols = row.find_all("td")
                if len(cols) > 1:
                    seats = cols[1].text.strip()
                    if seats.isdigit():
                        total_seats += int(seats)
        
        # Notification logic
        if total_seats > 0:
            send_push(f"✅ Found {total_seats} seats in Alappuzha!")
        else:
            # Check if search actually happened
            if "Alappuzha" in r.text:
                send_push("🔍 Search worked, but table is empty (0 seats).")
            else:
                send_push("⚠️ Search failed to refresh. Still on home page.")

    except Exception as e:
        send_push(f"❌ Script Error: {str(e)}")

if __name__ == "__main__":
    run_test()
