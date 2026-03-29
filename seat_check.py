"""
ICAI Seat Monitor — One-Time Test
===================================
Fix: ASP.NET __doPostBack causes a FULL PAGE RELOAD (not a DOM update).
     Replaced wait_for_function with wait_for_load_state("domcontentloaded").
     Screenshots confirm page + dropdowns load fine on GitHub runners.
"""

import os
import time
import requests

PUSHOVER_USER  = os.environ.get("PUSHOVER_USER", "")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")

# ── Config ─────────────────────────────────────────────────────────────────────
URL         = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
REGION_VAL  = "4"    # Southern
POU_VAL     = "101"  # Alappuzha
COURSE_VAL  = "48"   # AICITSS – Advanced IT (value from page source)

# ── Stealth loader (handles all playwright-stealth API versions) ───────────────
def _load_stealth():
    try:
        from playwright_stealth import stealth_sync
        if callable(stealth_sync):
            return stealth_sync
    except (ImportError, TypeError):
        pass
    try:
        from playwright_stealth import stealth
        if callable(stealth):
            return stealth
    except (ImportError, TypeError):
        pass
    return None

# ── Pushover ───────────────────────────────────────────────────────────────────
def send_push(message: str, title: str = "ICAI Test") -> None:
    if not PUSHOVER_USER or not PUSHOVER_TOKEN:
        print("⚠️  Pushover secrets missing.")
        return
    try:
        r = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER,
                  "title": title, "message": message},
            timeout=15,
        )
        print(f"Pushover → HTTP {r.status_code}: {r.text}")
    except Exception as e:
        print(f"Pushover error: {e}")

def screenshot(page, path: str) -> None:
    try:
        page.screenshot(path=path, full_page=True)
        print(f"📸  {path}")
    except Exception as e:
        print(f"Screenshot failed: {e}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    stealth_fn = _load_stealth()
    print("🕵️  Stealth active." if stealth_fn else "⚠️  No stealth (continuing anyway).")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # Block heavy assets — speeds up government server
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,otf,css}",
            lambda route: route.abort(),
        )
        if stealth_fn:
            stealth_fn(page)

        try:
            # ── 1. Load page ───────────────────────────────────────────────
            print("\n[1/5] Loading page …")
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            screenshot(page, "debug_screenshot.png")

            # ── 2. Select Region → triggers ASP.NET __doPostBack (full reload)
            print(f"[2/5] Selecting Region ({REGION_VAL}) …")
            page.wait_for_selector("select[id*='reg']", state="visible", timeout=15_000)
            page.select_option("select[id*='reg']", value=REGION_VAL)

            # KEY FIX: __doPostBack reloads the entire page.
            # wait_for_load_state waits for that reload to complete.
            # Do NOT use wait_for_function — the DOM is replaced, not updated.
            print("   ↳ Waiting for page reload (postback) …")
            page.wait_for_load_state("domcontentloaded", timeout=30_000)

            # ── 3. Select POU and Course (POU list is now populated) ───────
            print(f"[3/5] Selecting POU ({POU_VAL}) …")
            page.wait_for_selector(
                f"select[id*='POU'] option[value='{POU_VAL}']",
                state="attached", timeout=15_000
            )
            page.select_option("select[id*='POU']",    value=POU_VAL)
            page.select_option("select[id*='Course']", value=COURSE_VAL)

            # ── 4. Click Get List → another full page reload ───────────────
            print("[4/5] Clicking Get List …")
            page.click("input[value='Get List']")
            page.wait_for_load_state("domcontentloaded", timeout=30_000)
            time.sleep(2)   # Let table rows finish rendering
            screenshot(page, "debug_screenshot.png")

            # ── 5. Parse all table rows into array ─────────────────────────
            print("[5/5] Parsing results …")
            rows = page.query_selector_all("tr")
            data = []
            for row in rows:
                cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
                if cells:
                    data.append(cells)

            print(f"   Rows in table : {len(data)}")

            total_seats   = 0
            batch_details = []
            for row in data:
                if len(row) < 2:
                    continue
                seat_text = row[1]
                # Must be a plain integer 1–999 (excludes dates like "20")
                if seat_text.isdigit() and 1 <= int(seat_text) <= 999:
                    count = int(seat_text)
                    total_seats += count
                    batch_details.append(f"{row[0][:45]}: {count} seats")

            print(f"   Total seats   : {total_seats}")

            # Always notify in test mode regardless of seat count
            if total_seats > 0:
                msg = (
                    f"🚨 {total_seats} seats found!\n"
                    + "\n".join(batch_details)
                )
            else:
                msg = (
                    f"✅ Pipeline OK — scrape ran successfully.\n"
                    f"Seats: 0  |  Table rows parsed: {len(data)}\n"
                    "(Check debug_screenshot in Artifacts if seats exist on site)"
                )
            send_push(msg)

        except Exception as exc:
            print(f"\n❌  {exc}")
            screenshot(page, "error_screenshot.png")
            send_push(f"❌ Test failed: {str(exc)[:120]}", title="ICAI Test — ERROR")
            # No sys.exit(1) — ensures GitHub uploads screenshots

        finally:
            browser.close()

    print("\nDone.")

if __name__ == "__main__":
    main()
