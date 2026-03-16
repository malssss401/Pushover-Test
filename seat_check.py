import requests
from bs4 import BeautifulSoup
import os

URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
USER_KEY = os.environ.get("PUSHOVER_USER")
API_TOKEN = os.environ.get("PUSHOVER_TOKEN")

def send_push(message):
    requests.post("https://api.pushover.net/1/messages.json", data={
        "token": API_TOKEN, "user": USER_KEY, "message": message
    })

def run_test():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    try:
        # 1. Get Initial Page
        res = session.get(URL)
        soup = BeautifulSoup(res.text, "html.parser")

        # Function to find the exact name attribute for dropdowns
        def find_name(id_part):
            tag = soup.find(lambda t: t.name in ['select', 'input'] and id_part in t.get('id', ''))
            return tag.get('name') if tag else None

        # Dynamically find the full ASP.NET names
        region_name = find_name("ddlRegion")
        pou_name = find_name("ddlPOU")
        course_name = find_name("ddlCourse")
        button_name = find_name("btnSearch")

        if not all([region_name, pou_name, course_name]):
            raise Exception("Could not find form control IDs on the page.")

        # 2. First Postback (Select Region)
        data = {
            "__VIEWSTATE": soup.find("input", {"id": "__VIEWSTATE"})["value"],
            "__VIEWSTATEGENERATOR": soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
            "__EVENTVALIDATION": soup.find("input", {"id": "__EVENTVALIDATION"})["value"],
            "__EVENTTARGET": region_name,
            region_name: "Southern"
        }
        res = session.post(URL, data=data)
        soup = BeautifulSoup(res.text, "html.parser")

        # 3. Final Search (Select City & Course)
        data = {
            "__VIEWSTATE": soup.find("input", {"id": "__VIEWSTATE"})["value"],
            "__VIEWSTATEGENERATOR": soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"],
            "__EVENTVALIDATION": soup.find("input", {"id": "__EVENTVALIDATION"})["value"],
            region_name: "Southern",
            pou_name: "Alappuzha",
            course_name: "AICITSS - Advanced Information Technology",
            button_name: "Get List"
        }
        res = session.post(URL, data=data)
        soup = BeautifulSoup(res.text, "html.parser")

        # 4. Parse Results
        total_seats = 0
        # Check for any table with 'gv' or 'GridView' in the ID
        table = soup.find("table", id=lambda x: x and 'gv' in x)
        
        if table:
            for row in table.find_all("tr")[1:]: # Skip header
                cols = row.find_all("td")
                if len(cols) >= 2 and cols[1].get_text(strip=True).isdigit():
                    total_seats += int(cols[1].get_text(strip=True))

        if total_seats > 0:
            send_push(f"✅ SUCCESS! {total_seats} seats found in Alappuzha.")
        elif "No Record Found" in res.text:
            send_push("🔍 Search worked: The site explicitly says 'No Record Found'.")
        else:
            # If we reach here, search still didn't trigger
            send_push("⚠️ Search failed to refresh. Server ignored the 'Get List' click.")

    except Exception as e:
        send_push(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    run_test()
