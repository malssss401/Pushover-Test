import requests
from bs4 import BeautifulSoup
import os

URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
PUSHOVER_USER = os.environ.get("PUSHOVER_USER")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def get_asp_state(soup):
    return {
        "__VIEWSTATE": soup.find("input", {"name": "__VIEWSTATE"})["value"],
        "__VIEWSTATEGENERATOR": soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"],
        "__EVENTVALIDATION": soup.find("input", {"name": "__EVENTVALIDATION"})["value"],
    }

def run_test():
    session = requests.Session()
    # Masking as a real browser is vital for ICAI
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    })

    try:
        # STEP 1: Initial load
        r1 = session.get(URL)
        soup = BeautifulSoup(r1.text, "html.parser")
        
        # STEP 2: Postback for Region (Triggers City List)
        data = get_asp_state(soup)
        data.update({"ddlRegion": "Southern", "__EVENTTARGET": "ddlRegion"})
        r2 = session.post(URL, data=data)
        soup = BeautifulSoup(r2.text, "html.parser")
        
        # STEP 3: Search for Alappuzha
        data = get_asp_state(soup)
        data.update({
            "ddlRegion": "Southern",
            "ddlPOU": "Alappuzha", 
            "ddlCourse": "AICITSS - Advanced Information Technology",
            "btnSearch": "Get List"
        })
        r3 = session.post(URL, data=data)
        soup = BeautifulSoup(r3.text, "html.parser")

        # --- DATA CAPTURE ---
        # Capture all rows into an array for processing
        all_rows = []
        for tr in soup.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                all_rows.append(cells)

        total_seats = 0
        batch_details = []

        # Iterate through our array
        for row in all_rows:
            # We look for rows that have seat data (usually column index 1)
            if len(row) >= 2:
                potential_seats = row[1]
                if potential_seats.isdigit():
                    count = int(potential_seats)
                    total_seats += count
                    if count > 0:
                        batch_details.append(f"Batch: {row[0]} -> {count} seats")

        # --- NOTIFICATION ---
        if total_seats > 0:
            final_msg = f"✅ Seats Detected!\nTotal: {total_seats}\n" + "\n".join(batch_details)
        else:
            # Check if the page is literally saying 'No Record'
            if "No Record Found" in soup.text:
                final_msg = "🔍 Search successful, but site reports 0 current batches."
            else:
                final_msg = "❓ 0 seats found. The server might have rejected the city selection."

        print(final_msg)
        requests.post("https://api.pushover.net/1/messages.json", 
                      data={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": final_msg})

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_test()
