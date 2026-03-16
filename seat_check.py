import requests
from bs4 import BeautifulSoup
import os

URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
PUSHOVER_USER = os.environ.get("PUSHOVER_USER")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def get_tokens(soup):
    return {
        "__VIEWSTATE": soup.find("input", {"name": "__VIEWSTATE"})["value"] if soup.find("input", {"name": "__VIEWSTATE"}) else "",
        "__VIEWSTATEGENERATOR": soup.find("input", {"name": "__VIEWSTATEGENERATOR"})["value"] if soup.find("input", {"name": "__VIEWSTATEGENERATOR"}) else "",
        "__EVENTVALIDATION": soup.find("input", {"name": "__EVENTVALIDATION"})["value"] if soup.find("input", {"name": "__EVENTVALIDATION"}) else "",
    }

def run_test():
    session = requests.Session()
    # Using a more standard browser header
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    try:
        # STEP 1: Initial Page Load
        r1 = session.get(URL)
        soup = BeautifulSoup(r1.text, "html.parser")
        
        # STEP 2: Select Region & POU
        # We combine these to try and force the server to recognize the selection
        data = get_tokens(soup)
        data.update({
            "ddlRegion": "Southern",
            "ddlPOU": "Alappuzha",
            "ddlCourse": "AICITSS - Advanced Information Technology",
            "btnSearch": "Get List"
        })

        r2 = session.post(URL, data=data)
        soup = BeautifulSoup(r2.text, "html.parser")

        # STEP 3: Robust Parsing
        # We look for the GridView table specifically
        total_seats = 0
        found_batches = []
        
        # Look for all table rows
        rows = soup.find_all("tr")
        print(f"Total table rows found: {len(rows)}")

        for row in rows:
            cells = row.find_all(["td", "th"])
            cell_texts = [c.get_text(strip=True) for c in cells]
            
            # Debug: Print rows that look like data
            if len(cell_texts) > 1:
                # Check every cell in the row for a number
                for i, text in enumerate(cell_texts):
                    if text.isdigit():
                        num = int(text)
                        # In your screenshot, seats were in the 2nd column
                        # We'll count it if it's a reasonable seat number (e.g., < 500)
                        if 0 < num < 500: 
                            total_seats += num
                            found_batches.append(f"Row: {' | '.join(cell_texts)}")
                            break # Move to next row once a seat count is found

        # STEP 4: Final Action
        result_msg = ""
        if total_seats > 0:
            result_msg = f"✅ SUCCESS! Found {total_seats} seats.\nDetails:\n" + "\n".join(found_batches[:3])
        else:
            # If 0 seats, let's see what the page actually says
            if "No Record Found" in soup.text:
                result_msg = "🔍 Search worked, but the site literally says 'No Record Found'."
            else:
                result_msg = "❓ 0 seats found, but no error. The table might be empty."

        print(result_msg)
        requests.post("https://api.pushover.net/1/messages.json", 
                      data={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": result_msg})

    except Exception as e:
        err = f"❌ Error: {str(e)}"
        print(err)
        requests.post("https://api.pushover.net/1/messages.json", 
                      data={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": err})

if __name__ == "__main__":
    run_test()
