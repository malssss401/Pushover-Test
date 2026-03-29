"""
ICAI Seat Monitor — One-Time Test
===================================
Key insight: After region postback, the FIRST city in the list
(Alappuzha) is automatically selected by the site. No POU click needed.
For any other city, we explicitly select by label after postback.

Set POU_LABEL = None to use the auto-selected city (Alappuzha).
Set POU_LABEL = "Chennai" (or any city name) to override.
"""

import os
import time
import requests

PUSHOVER_USER  = os.environ.get("PUSHOVER_USER", "")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")

URL = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"

# ── Change these values to monitor a different city/course ────────────────────
REGION_VAL = "4"          # Southern
POU_LABEL  = None         # None = use auto-selected first city (Alappuzha)
                          # e.g. "Chennai" to explicitly pick a different city
COURSE_VAL = "48"         # AICITSS – Advanced IT
# ─────────────────────────────────────────────────────────────────────────────

def _load_stealth():
    for name in ("stealth_sync", "stealth"):
        try:
            import playwright_stealth as _m
            fn = getattr(_m, name, None)
            if callable(fn):
                return fn
        except ImportError:
            pass
    return None

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
        print(f"Screenshot error: {e}")

def main():
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    stealth_fn = _load_stealth()
    print("🕵️  Stealth active." if stealth_fn else "⚠️  No stealth.")

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
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,otf,css}",
            lambda route: route.abort(),
        )
        if stealth_fn:
            stealth_fn(page)

        try:
            # ── 1. Load ────────────────────────────────────────────────────
            print("\n[1/4] Loading page …")
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            screenshot(page, "debug_screenshot.png")

            # ── 2. Select Region → __doPostBack → full page reload ─────────
            print(f"[2/4] Selecting Region (value={REGION_VAL}) …")
            page.wait_for_selector("select[id*='reg']", state="visible", timeout=15_000)
            page.select_option("select[id*='reg']", value=REGION_VAL)
            page.wait_for_load_state("domcontentloaded", timeout=30_000)
            time.sleep(2)   # Let postback finish writing option tags

            # ── 3. POU selection (conditional) ────────────────────────────
            if POU_LABEL is None:
                # Alappuzha (or whichever city) is already auto-selected
                # Just log what the site chose
                auto = page.eval_on_selector(
                    "select[id*='POU'], select[id*='pou'], select[id*='Pou']",
                    "el => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : 'unknown'"
                )
                print(f"[3/4] POU auto-selected by site: '{auto}' — no override needed.")
            else:
                # Explicitly pick a different city by its visible label
                print(f"[3/4] Selecting POU label='{POU_LABEL}' …")
                pou_sel = "select[id*='POU'], select[id*='pou'], select[id*='Pou']"

                # Log all available cities so we can verify
                options = page.eval_on_selector(
                    pou_sel,
                    "el => Array.from(el.options).map(o => o.value + ' = ' + o.text)"
                )
                print(f"   Available POU options: {options}")

                page.select_option(pou_sel, label=POU_LABEL)

            # ── 4. Select Course ───────────────────────────────────────────
            course_sel = "select[id*='Course'], select[id*='course']"

            # Log available courses — useful to verify COURSE_VAL is correct
            course_options = page.eval_on_selector(
                course_sel,
                "el => Array.from(el.options).map(o => o.value + ' = ' + o.text)"
            )
            print(f"   Available Course options: {course_options}")

            try:
                page.select_option(course_sel, value=COURSE_VAL)
                print(f"   Course selected: value={COURSE_VAL}")
            except Exception:
                print(f"   ⚠️  value={COURSE_VAL} not found — see course options above")
                raise

            # ── 5. Click Get List ──────────────────────────────────────────
            print("[4/4] Clicking Get List …")
            page.click("input[value='Get List']")
            page.wait_for_load_state("domcontentloaded", timeout=30_000)
            time.sleep(3)
            screenshot(page, "debug_screenshot.png")   # Overwrite with results state

            # ── Parse results table ────────────────────────────────────────
            rows = page.query_selector_all("tr")
            data = []
            for row in rows:
                cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
                if cells:
                    data.append(cells)

            print(f"\n   Table rows parsed : {len(data)}")
            if data:
                print(f"   Sample rows       : {data[:3]}")

            total_seats   = 0
            batch_details = []
            for row in data:
                if len(row) < 2:
                    continue
                if row[1].isdigit() and 1 <= int(row[1]) <= 999:
                    count = int(row[1])
                    total_seats += count
                    batch_details.append(f"{row[0][:45]}: {count} seats")

            print(f"   Total seats found : {total_seats}")

            # Always notify in test mode
            city_label = POU_LABEL if POU_LABEL else auto
            if total_seats > 0:
                msg = (
                    f"🚨 {total_seats} seats found in {city_label}!\n"
                    + "\n".join(batch_details)
                )
            else:
                msg = (
                    f"✅ Pipeline OK — scrape completed.\n"
                    f"City: {city_label}  |  Seats: 0  |  Rows: {len(data)}\n"
                    "(Check debug_screenshot in Artifacts)"
                )
            send_push(msg)

        except Exception as exc:
            print(f"\n❌  {exc}")
            screenshot(page, "error_screenshot.png")
            send_push(f"❌ Test failed: {str(exc)[:120]}", title="ICAI Test — ERROR")
            # No sys.exit(1) — keeps artifact upload step alive

        finally:
            browser.close()

    print("\nDone.")

if __name__ == "__main__":
    main()
