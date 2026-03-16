import requests
from bs4 import BeautifulSoup
import os

URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
PUSHOVER_USER = os.environ.get("PUSHOVER_USER")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def get_tokens(soup):
    return {
        "__VIEWSTATE": soup.find("input", {"name": "__VIEWSTATE"})["value"],
        "__VIEWSTATEGENERATOR": soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"],
        "__EVENTVALIDATION": soup.find("input", {"name": "__EVENTVALIDATION"})["value"],
    }

def run_test():
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        # STEP 1: Get initial page
        resp1 = session.get(URL, headers=headers)
        soup = BeautifulSoup(resp1.text, "html.parser")
        tokens = get_tokens(soup)

        # STEP 2: "Select" Region (This triggers the city list to load server-side)
        payload1 = {
            **tokens,
            "ddlRegion": "Southern",
            "__EVENTTARGET": "ddlRegion",  # Tells the server we clicked the Region dropdown
        }
        resp2 = session.post(URL, data=payload1, headers=headers)
        soup = BeautifulSoup(resp2.text, "html.parser")
        tokens = get_tokens(soup) # Update tokens for the next step

        # STEP 3: Search for Batch
        payload2 = {
            **tokens,
            "ddlRegion": "Southern",
            "ddlPOU": "Alappuzha",
            "ddlCourse": "AICITSS - Advanced Information Technology",
            "btnSearch": "Get List"
        }
        resp3 = session.post(URL, data=payload2, headers=headers)
        soup = BeautifulSoup(resp3.text, "html.parser")

        # STEP 4: Parse table
        total_seats = 0
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                seat_text = cols[1].text.strip()
                if seat_text.isdigit():
                    total_seats += int(seat_text)

        # Notification
        if total_seats > 0:
            msg = f"✅ SUCCESS: {total_seats} seats found in Alappuzha!"
        else:
            msg = "🔍 Connection works, but 0 seats detected. Is the city correct?"
        
        requests.post("https://api.pushover.net/1/messages.json", 
                      data={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": msg})
        print(msg)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_test()
