import requests
from bs4 import BeautifulSoup
import os
import time

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

def check_seats():
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}

    # Step 1: load page
    response = session.get(URL, headers=headers, timeout=30)
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract ASP.NET hidden fields
    viewstate = soup.find("input", {"name": "__VIEWSTATE"})["value"]
    eventvalidation = soup.find("input", {"name": "__EVENTVALIDATION"})["value"]
    viewstategen = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"]

    # Step 2: simulate dropdown selection
    payload = {
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": viewstategen,
        "__EVENTVALIDATION": eventvalidation,
        "ddlRegion": "Southern",
        "ddlPOU": "Chennai",
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
                seats = int(col)
                seats_found = max(seats_found, seats)
    
    return seats_found

# Main Loop: Runs 10 times with a 5-minute gap (approx 50 mins total)
iterations = 10 
delay = 300 # 5 minutes in seconds

print(f"Starting Monitor: Checking {iterations} times with {delay}s intervals.")

for i in range(iterations):
    try:
        print(f"Attempt {i+1}/{iterations}...")
        found = check_seats()
        print(f"Seats detected: {found}")

        if found > 0:
            send_notification(f"🚨 ICAI Seats Available! {found} seats open.")
            # Optional: break if you only want one notification per hour
            # break 
            
    except Exception as e:
        print(f"Error during check: {e}")
    
    if i < iterations - 1: # Don't sleep after the last check
        time.sleep(delay)
