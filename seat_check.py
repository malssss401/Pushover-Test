import requests
from bs4 import BeautifulSoup
import os

URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
PUSHOVER_USER = os.environ.get("PUSHOVER_USER")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def get_asp_vars(soup):
    """Extracts the hidden ASP.NET form variables."""
    return {
        "__VIEWSTATE": soup.find("input", {"id": "__VIEWSTATE"})["value"],
        "__VIEWSTATEGENERATOR": soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
        "__EVENTVALIDATION": soup.find("input", {"id": "__EVENTVALIDATION"})["value"],
    }

def run_test():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

    try:
        # 1. Initial Load to get tokens
        res = session.get(URL)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 2. Select Region (Crucial: This triggers the City list to load)
        data = get_asp_vars(soup)
        data.update({"ddlRegion": "Southern", "__EVENTTARGET": "ddlRegion"})
        res = session.post(URL, data=data)
        soup = BeautifulSoup(res.text, "html.parser")

        # 3. Select City and Search
        data = get_asp_vars(soup)
        data.update({
            "ddlRegion": "Southern",
            "ddlPOU": "Alappuzha",
            "ddlCourse": "AICITSS - Advanced Information Technology",
            "btnSearch": "Get List"
        })
        res = session.post(URL, data=data)
        soup = BeautifulSoup(res.text, "html.parser")

        # --- COPY DATA TO ARRAY ---
        # We find the table (usually has 'gv' or 'GridView' in ID)
        table = soup.find("table")
        web_data_array = []
        
        if table:
            for row in table.find_all("tr"):
                # Copy each cell's text into a sub-array
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if cells:
                    web_data_array.append(cells)

        # --- PARSE THE ARRAY ---
        total_seats = 0
        batch_info = []

        # Start from index 1 to skip header
        for row in web_data_array[1:]:
            # In your screenshot, Available Seats is column 2 (index 1)
            if len(row) >= 2:
                batch_name = row[0]
                seats_str = row[1]
                
                if seats_str.isdigit():
                    count = int(seats_str)
                    total_seats += count
                    if count > 0:
                        batch_info.append(f"{batch_name}: {count}")

        # Final Notification
        if total_seats > 0:
            msg = f"✅ SUCCESS: {total_seats} seats found!\n" + "\n".join(batch_info)
        else:
            msg = "🔍 Check complete: 0 seats found. (The table was copied but no numbers found)."

        requests.post("https://api.pushover.net/1/messages.json", 
                      data={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": msg})
        print(msg)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_test()
