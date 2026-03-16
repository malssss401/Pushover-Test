import requests
from bs4 import BeautifulSoup
import os

URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
PUSHOVER_USER = os.environ.get("PUSHOVER_USER")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def get_asp_vars(soup):
    return {
        "__VIEWSTATE": soup.find("input", {"name": "__VIEWSTATE"})["value"],
        "__VIEWSTATEGENERATOR": soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"],
        "__EVENTVALIDATION": soup.find("input", {"name": "__EVENTVALIDATION"})["value"],
    }

def run_test():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "X-MicrosoftAjax": "Delta=true"
    })

    try:
        # STEP 1: Initial GET
        print("1. Fetching initial page...")
        r1 = session.get(URL)
        soup = BeautifulSoup(r1.text, "html.parser")
        
        # STEP 2: Postback for Region (Required to populate city list)
        print("2. Selecting Region...")
        data = get_asp_vars(soup)
        data.update({
            "ctl00$ScriptManager1": "ctl00$ContentPlaceHolder1$UpdatePanel1|ctl00$ContentPlaceHolder1$ddlRegion",
            "ddlRegion": "Southern",
            "__EVENTTARGET": "ddlRegion",
            "__ASYNCPOST": "true"
        })
        r2 = session.post(URL, data=data)
        soup = BeautifulSoup(r2.text, "html.parser")

        # STEP 3: Final POST to Get List
        print("3. Clicking 'Get List' for Alappuzha...")
        data = get_asp_vars(soup)
        data.update({
            "ctl00$ScriptManager1": "ctl00$ContentPlaceHolder1$UpdatePanel1|ctl00$ContentPlaceHolder1$btnSearch",
            "ddlRegion": "Southern",
            "ddlPOU": "Alappuzha",
            "ddlCourse": "AICITSS - Advanced Information Technology",
            "btnSearch": "Get List",
            "__ASYNCPOST": "true"
        })
        r3 = session.post(URL, data=data)
        
        # --- ROBUST PARSING ---
        # We search the response text directly for numbers if soup fails
        soup = BeautifulSoup(r3.text, "html.parser")
        total_seats = 0
        all_data = []

        # Find all cells and copy into an array
        rows = soup.find_all("tr")
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) >= 2:
                # We assume column 2 is seats based on your image
                seat_val = cells[1]
                if seat_val.isdigit():
                    count = int(seat_val)
                    total_seats += count
                    all_data.append(f"{cells[0]}: {count}")

        # --- LOGGING & NOTIFICATION ---
        if total_seats > 0:
            msg = f"✅ SUCCESS! {total_seats} seats found.\n" + "\n".join(all_data)
        else:
            # Final check: see if the table exists in the response at all
            if "GridView" in r3.text or "tr" in r3.text:
                msg = "🔍 Connection okay, table found, but calculated 0 seats."
            else:
                msg = "❌ The server rejected the search. Response was empty."

        print(msg)
        requests.post("https://api.pushover.net/1/messages.json", 
                      data={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": msg})

    except Exception as e:
        print(f"Scraper Error: {e}")

if __name__ == "__main__":
    run_test()
