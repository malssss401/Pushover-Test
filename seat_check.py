"""
ICAI Seat Monitor — One-Time Test
===================================
Updated for:
  • BENGALURU city (explicit POU selection by label)
  • Advanced (ICITSS) MCS Course
  • Per-batch notification — alerts if ANY single batch has seats > 0
  • Full 8-column table parsed correctly (seats in column index 1)

To switch city/course, edit the CONFIG block only.
"""

import os
import time
import requests

PUSHOVER_USER  = os.environ.get("PUSHOVER_USER", "")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG — edit these values only
# ══════════════════════════════════════════════════════════════════════════════
URL        = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
REGION_VAL = "4"            # Southern

# POU: set to None to use auto-selected first city, or a city name string
# Note: site uses ALL CAPS for city names — match exactly
POU_LABEL  = "BENGALURU"    # None = auto (Alappuzha), or e.g. "BENGALURU", "CHENNAI"

# Course: value from page source. Script will print all options if this fails.
# 48  = AICITSS – Advanced Information Technology
# MCS = Advanced (ICITSS) MCS Course — value printed by script on first run
COURSE_LABEL = "Advanced (ICITSS) MCS Course"   # Select by label (more reliable than value)
# ══════════════════════════════════════════════════════════════════════════════

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

def send_push(message: str, title: str = "ICAI Monitor") -> None:
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
    print(f"   City   : {POU_LABEL or 'auto (first in list)'}")
    print(f"   Course : {COURSE_LABEL}")

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

            # ── 2. Select Region → full page reload via __doPostBack ───────
            print("[2/4] Selecting Region …")
            page.wait_for_selector("select[id*='reg']", state="visible", timeout=15_000)
            page.select_option("select[id*='reg']", value=REGION_VAL)
            page.wait_for_load_state("domcontentloaded", timeout=30_000)
            time.sleep(2)

            # ── 3. POU selection ───────────────────────────────────────────
            pou_sel    = "select[id*='POU'], select[id*='pou'], select[id*='Pou']"
            course_sel = "select[id*='Course'], select[id*='course']"

            # Always log available cities — helps debug any future label mismatch
            pou_options = page.eval_on_selector(
                pou_sel,
                "el => Array.from(el.options).map(o => o.value + ' = ' + o.text)"
            )
            print(f"   Available POU options: {pou_options}")

            if POU_LABEL is None:
                auto = page.eval_on_selector(
                    pou_sel,
                    "el => el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : 'unknown'"
                )
                print(f"[3/4] POU auto-selected: '{auto}'")
            else:
                print(f"[3/4] Selecting POU '{POU_LABEL}' …")
                page.select_option(pou_sel, label=POU_LABEL)

            # ── 4. Select Course ───────────────────────────────────────────
            course_options = page.eval_on_selector(
                course_sel,
                "el => Array.from(el.options).map(o => o.value + ' = ' + o.text)"
            )
            print(f"   Available Course options: {course_options}")
            print(f"   Selecting course by label: '{COURSE_LABEL}' …")
            page.select_option(course_sel, label=COURSE_LABEL)

            # ── 5. Click Get List ──────────────────────────────────────────
            print("[4/4] Clicking Get List …")
            page.click("input[value='Get List']")
            page.wait_for_load_state("domcontentloaded", timeout=30_000)
            time.sleep(3)
            screenshot(page, "debug_screenshot.png")

            # ── Parse table ────────────────────────────────────────────────
            # Table columns (from screenshot):
            # [0] Batch No  [1] Available Seats  [2] From Date  [3] To Date
            # [4] Batch Time  [5] Pou Name  [6] Course  [7] Open For
            rows = page.query_selector_all("tr")
            data = []
            for row in rows:
                cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
                if cells:
                    data.append(cells)

            print(f"\n   Table rows parsed : {len(data)}")
            if data:
                print(f"   Header/sample row : {data[0]}")

            # ── Per-batch seat check ───────────────────────────────────────
            # Notify if ANY batch has at least 1 seat — even if others are zero
            batches_with_seats = []
            batches_zero       = []

            for row in data:
                # Need at least: Batch No + Available Seats columns
                if len(row) < 2:
                    continue

                batch_no   = row[0]
                seat_text  = row[1]
                from_date  = row[2] if len(row) > 2 else ""
                to_date    = row[3] if len(row) > 3 else ""
                batch_time = row[4] if len(row) > 4 else ""

                # Skip header rows (seat col is not a number)
                if not seat_text.isdigit():
                    continue

                seats = int(seat_text)

                if seats > 0:
                    batches_with_seats.append({
                        "batch": batch_no,
                        "seats": seats,
                        "dates": f"{from_date} – {to_date}",
                        "time":  batch_time,
                    })
                else:
                    batches_zero.append(batch_no)

            # ── Summary to log ─────────────────────────────────────────────
            city_display = POU_LABEL or "auto"
            print(f"\n   Batches WITH seats : {len(batches_with_seats)}")
            print(f"   Batches ZERO seats : {len(batches_zero)}")
            for b in batches_with_seats:
                print(f"     ✅  {b['batch']} → {b['seats']} seats | {b['dates']} | {b['time']}")
            for bn in batches_zero:
                print(f"     ⭕  {bn} → 0 seats")

            # ── Notification ───────────────────────────────────────────────
            if batches_with_seats:
                lines = []
                for b in batches_with_seats:
                    lines.append(
                        f"• {b['batch']}\n"
                        f"  Seats: {b['seats']}  |  {b['dates']}\n"
                        f"  Time : {b['time']}"
                    )
                msg = (
                    f"🚨 Seats Available — {city_display}!\n"
                    f"{COURSE_LABEL}\n\n"
                    + "\n\n".join(lines)
                )
                if batches_zero:
                    msg += f"\n\n(+ {len(batches_zero)} batch(es) fully booked)"
                send_push(msg, title=f"ICAI — {city_display} Seats Open!")
            else:
                total_batches = len(batches_with_seats) + len(batches_zero)
                msg = (
                    f"✅ Pipeline OK — scrape completed.\n"
                    f"City: {city_display}  |  Course: {COURSE_LABEL}\n"
                    f"Seats: 0 across {total_batches} batch(es)\n"
                    "(Check debug_screenshot in Artifacts)"
                )
                send_push(msg, title="ICAI Test — 0 Seats")

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
