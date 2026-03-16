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
    print("Scanning all available batches...")
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        # Step 1: Initial GET to handle ASP.NET's security tokens
        response = session.get(URL, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")

        viewstate = soup.find("input", {"name": "__VIEWSTATE"})["value"]
        eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})["value"]
        viewstategen = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"]

        # Step 2: POST request to trigger the "Get List" button
        payload = {
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstategen,
            "__EVENTVALIDATION": eventvalidation,
            "ddlRegion": "Southern",
            "ddlPOU": "Alappuzha", 
            "ddlCourse": "AICITSS - Advanced Information Technology",
            "btnSearch": "Get List"
        }

        response = session.post(URL, data=payload, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Step 3: Find all table rows
        rows = soup.find_all("tr")
        total_seats = 0
        batches_with_seats = []

        for row in rows:
            cols = row.find_all("td")
            
            # The table header uses <th>, data rows use <td>. 
            # We only process rows that have at least 2 columns.
            if len(cols) >= 2:
                batch_name = cols[0].text.strip()
                seat_text = cols[1].text.strip()
                
                # Check if the seat column actually contains a number
                if seat_text.isdigit():
                    count = int(seat_text)
                    if count > 0:
                        total_seats += count
                        batches_with_seats.append(f"{batch_name}: {count} seats")

        # Step 4: Final Reporting
        if total_seats > 0:
            report = "\n".join(batches_with_seats)
            msg = f"🚨 ICAI Seats Found!\nTotal Seats: {total_seats}\n\n{report}"
            print(msg)
            send_notification(msg)
        else:
            print("Scan complete: 0 seats found across all batches.")
            send_notification("🔍 Check complete: 0 seats found.")

    except Exception as e:
        print(f"Error occurred: {e}")
        send_notification(f"❌ Scraper Error: {str(e)}")

if __name__ == "__main__":
    run_test()
