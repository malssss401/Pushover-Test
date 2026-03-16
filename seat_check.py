import requests
from bs4 import BeautifulSoup
import os

URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
PUSHOVER_USER = os.environ.get("PUSHOVER_USER")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def send_notification(message):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": PUSHOVER_TOKEN,
            "user": PUSHOVER_USER,
            "message": message
        }
    )

def run_test():
    print("Starting one-time test check...")
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        # Step 1: Load page and get ASP.NET hidden fields
        response = session.get(URL, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")

        viewstate = soup.find("input", {"name": "__VIEWSTATE"})["value"]
        eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})["value"]
        viewstategen = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"]

        # Step 2: Simulate Search
        payload = {
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstategen,
            "__EVENTVALIDATION": eventvalidation,
            "ddlRegion": "Southern",
            "ddlPOU": "Alappuzha",
            "ddlCourse": "AICITSS - Advanced Information Technology",
            "btnSearch": "Search"
        }

        response = session.post(URL, data=payload, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.find_all("tr")

        seats_found = 0
        for row in rows:
            cols = [c.text.strip() for c in row.find_all("td")]
            for col in cols:
                if col.isdigit():
                    seats_found = max(seats_found, int(col))

        print(f"Test complete. Seats detected: {seats_found}")
        
        # We send a notification NO MATTER WHAT for the test
        status_msg = "✅ Connection successful!"
        seat_msg = f"Seats currently available: {seats_found}"
        send_notification(f"{status_msg}\n{seat_msg}")
        print("Notification sent to Pushover.")

    except Exception as e:
        error_msg = f"❌ Test Failed: {str(e)}"
        print(error_msg)
        send_notification(error_msg)

if __name__ == "__main__":
    run_test()
