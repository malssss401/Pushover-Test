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
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    })

    try:
        # 1. Fetch initial page
        res = session.get(URL)
        soup = BeautifulSoup(res.text, "html.parser")

        # Robust way to find the ASP.NET hidden fields
        def get_hidden_fields(s):
            fields = {}
            for field_id in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
                tag = s.find("input", {"id": field_id})
                if tag:
                    fields[field_id] = tag.get("value")
            return fields

        # Find the full names of the dropdowns and button
        # ASP.NET names often look like 'ctl00$ContentPlaceHolder1$ddlRegion'
        def find_name_by_partial_id(s, partial_id):
            tag = s.find(lambda t: t.has_attr('id') and partial_id in t['id'])
            return tag.get('name') if tag else None

        r_name = find_name_by_partial_id(soup, "ddlRegion")
        p_name = find_name_by_partial_id(soup, "ddlPOU")
        c_name = find_name_by_partial_id(soup, "ddlCourse")
        b_name = find_name_by_partial_id(soup, "btnSearch")

        if not r_name:
            # Fallback: Print what we see for debugging
            print(f"DEBUG: Found tags: {[t.get('id') for t in soup.find_all(id=True)][:10]}")
            raise Exception("Website layout changed or blocking bots. No IDs found.")

        # 2. Trigger the "Postback" for Region
        data = get_hidden_fields(soup)
        data.update({
            "__EVENTTARGET": r_name,
            r_name: "Southern"
        })
        res = session.post(URL, data=data)
        soup = BeautifulSoup(res.text, "html.parser")

        # 3. Final Search
        data = get_hidden_fields(soup)
        data.update({
            r_name: "Southern",
            p_name: "Alappuzha",
            c_name: "AICITSS - Advanced Information Technology",
            b_name: "Get List"
        })
        res = session.post(URL, data=data)
        soup = BeautifulSoup(res.text, "html.parser")

        # 4. Parse Table
        total_seats = 0
        table = soup.find("table") # Get the first table found
        
        if table:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    # Look for any digit in the second column
                    text = cols[1].get_text(strip=True)
                    if text.isdigit():
                        total_seats += int(text)

        if total_seats > 0:
            send_push(f"✅ Seats Found! Total: {total_seats}")
        else:
            # If search worked but 0 seats, the HTML will contain 'Alappuzha'
            if "Alappuzha" in res.text:
                send_push("🔍 Connection Success: Search worked, but 0 seats found.")
            else:
                send_push("⚠️ Connection Success: But the search results didn't load.")

    except Exception as e:
        send_push(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    run_test()
