"""
ICAI Seat Monitor — One-Time Test
===================================
Handles all three outcomes the ICAI site can return:

  Outcome 1 — No batches scheduled
              Site shows: "Sorry, no records found."
              Meaning: No batches announced yet for this city/course.

  Outcome 2 — Batches exist but all seats taken
              Site shows the table, but every Available Seats column = 0.

  Outcome 3 — Seats available
              At least one batch has seats > 0.  ← the alert that matters

TEST MODE  : All three outcomes send a Pushover notification.
PRODUCTION : Only Outcome 3 sends a notification (silence on 1 & 2).
"""

import os
import time
import requests

PUSHOVER_USER  = os.environ.get("PUSHOVER_USER", "")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG — only edit this block
# ══════════════════════════════════════════════════════════════════════════════
URL        = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
REGION_VAL = "4"        # Southern = 4

# POU: None = auto-selected first city (Alappuzha).
# Otherwise use city name exactly as shown in dropdown (ALL CAPS).
POU_LABEL  = "CHENNAI"  # e.g. "CHENNAI", "BENGALURU", "ALAPPUZHA", or None

# Full course name exactly as shown in ICAI dropdown:
#   "AICITSS - Advanced Information Technology"
#   "Advanced (ICITSS) MCS Course"
COURSE_NAME = "AICITSS - Advanced Information Technology"
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


def select_course(page, course_sel: str, course_name: str) -> str:
    """
    Selects course by full name (case-insensitive, trims whitespace).
    Falls back to partial match if exact match not found.
    Prints all available options to the GitHub Actions log.
    Raises ValueError with full option list if no match at all.
    """
    options = page.eval_on_selector(
        course_sel,
        "el => Array.from(el.options).map(o => ({value: o.value, text: o.text.trim()}))"
    )
    print("   Available Course options:")
    for opt in options:
        print(f"     value={opt['value']}  →  '{opt['text']}'")

    target = course_name.strip().lower()

    # Try exact match first
    match = next((o for o in options if o["text"].lower() == target), None)

    # Fall back to partial match
    if not match:
        match = next((o for o in options if target in o["text"].lower()), None)
        if match:
            print(f"   ⚠️  Exact match not found — using partial match: '{match['text']}'")

    if not match:
        raise ValueError(
            f"Course '{course_name}' not found.\n"
            f"Available: {[o['text'] for o in options]}"
        )

    page.select_option(course_sel, value=match["value"])
    print(f"   ✅  Course selected: '{match['text']}'")
    return match["text"]


def main():
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    stealth_fn = _load_stealth()
    print("🕵️  Stealth active." if stealth_fn else "⚠️  No stealth.")
    print(f"   City   : {POU_LABEL or 'auto (first in list)'}")
    print(f"   Course : {COURSE_NAME}")

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
            print("[2/4] Selecting Region …")
            page.wait_for_selector("select[id*='reg']", state="visible", timeout=15_000)
            page.select_option("select[id*='reg']", value=REGION_VAL)
            page.wait_for_load_state("domcontentloaded", timeout=30_000)
            time.sleep(2)

            # ── 3. POU ─────────────────────────────────────────────────────
            pou_sel    = "select[id*='POU'], select[id*='pou'], select[id*='Pou']"
            course_sel = "select[id*='Course'], select[id*='course']"

            pou_options = page.eval_on_selector(
                pou_sel,
                "el => Array.from(el.options).map(o => o.value + ' = ' + o.text)"
            )
            print(f"   Available POU options: {pou_options}")

            if POU_LABEL is None:
                city_display = page.eval_on_selector(
                    pou_sel,
                    "el => el.options[el.selectedIndex]?.text ?? 'unknown'"
                )
                print(f"[3/4] POU auto-selected: '{city_display}'")
            else:
                city_display = POU_LABEL
                print(f"[3/4] Selecting POU '{POU_LABEL}' …")
                try:
                    page.select_option(pou_sel, label=POU_LABEL, timeout=10_000)
                except Exception:
                    print("   ⚠️  Exact label failed — trying JS case-insensitive match …")
                    matched = page.eval_on_selector(
                        pou_sel,
                        f"""el => {{
                            const opt = Array.from(el.options).find(
                                o => o.text.trim().toUpperCase() === '{POU_LABEL.upper()}'
                            );
                            if (opt) {{ el.value = opt.value; return opt.text.trim(); }}
                            return null;
                        }}"""
                    )
                    if not matched:
                        raise ValueError(
                            f"City '{POU_LABEL}' not found in POU dropdown.\n"
                            f"Available: {pou_options}"
                        )
                    print(f"   ✅  Matched via JS: '{matched}'")

            # ── 4. Course ──────────────────────────────────────────────────
            print(f"[4/4a] Selecting course …")
            selected_course = select_course(page, course_sel, COURSE_NAME)
            screenshot(page, "debug_screenshot.png")   # Confirm correct course before Get List

            # ── 5. Get List ────────────────────────────────────────────────
            print("[4/4b] Clicking Get List …")
            page.click("input[value='Get List']")
            # 60s — Chennai and larger cities take longer to return results
            page.wait_for_load_state("domcontentloaded", timeout=60_000)
            time.sleep(3)
            screenshot(page, "debug_screenshot.png")   # Final state with results

            # ── Detect site-level "no records" message ─────────────────────
            page_text  = page.inner_text("body").lower()
            no_records = "no records found" in page_text

            # ── Parse table ────────────────────────────────────────────────
            # Columns: [0] Batch No  [1] Available Seats  [2] From Date
            #          [3] To Date   [4] Batch Time        [5] Pou Name
            #          [6] Course    [7] Open For
            rows = page.query_selector_all("tr")
            data = []
            for row in rows:
                cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
                if cells:
                    data.append(cells)

            print(f"\n   Table rows parsed : {len(data)}")
            if data:
                print(f"   First data row    : {data[0]}")

            batches_with_seats = []
            batches_zero       = []

            for row in data:
                if len(row) < 2:
                    continue
                batch_no   = row[0]
                seat_text  = row[1]
                from_date  = row[2] if len(row) > 2 else ""
                to_date    = row[3] if len(row) > 3 else ""
                batch_time = row[4] if len(row) > 4 else ""

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

            print(f"\n   Batches WITH seats : {len(batches_with_seats)}")
            print(f"   Batches ZERO seats : {len(batches_zero)}")
            for b in batches_with_seats:
                print(f"     ✅  {b['batch']} → {b['seats']} seats | {b['dates']} | {b['time']}")
            for bn in batches_zero:
                print(f"     ⭕  {bn} → 0 seats")

            # ══════════════════════════════════════════════════════════════
            # NOTIFICATION LOGIC
            # Three outcomes — all notify in TEST mode.
            # In production only Outcome 3 will send a notification.
            # ══════════════════════════════════════════════════════════════

            if batches_with_seats:
                # ── OUTCOME 3: Seats available ─────────────────────────────
                # This is the ONLY outcome that notifies in production.
                lines = [
                    f"• {b['batch']}\n"
                    f"  Seats : {b['seats']}  |  {b['dates']}\n"
                    f"  Time  : {b['time']}"
                    for b in batches_with_seats
                ]
                msg = (
                    f"🚨 Seats Available — {city_display}!\n"
                    f"{selected_course}\n\n"
                    + "\n\n".join(lines)
                )
                if batches_zero:
                    msg += f"\n\n(+ {len(batches_zero)} batch(es) fully booked)"
                send_push(msg, title=f"ICAI — {city_display} Seats Open!")

            elif no_records:
                # ── OUTCOME 1: No batches announced yet ────────────────────
                # Confirmed on Chennai MCS — site returns this when no batches
                # have been scheduled for the city/course combination.
                # Production: silent. Test: notify to confirm pipeline works.
                print("   ℹ️   Site returned 'no records found'.")
                msg = (
                    f"ℹ️ No Batches Scheduled — {city_display}\n"
                    f"{selected_course}\n\n"
                    f"The ICAI site returned:\n"
                    f"\"Sorry, no records found. Please change your "
                    f"search parameters and try again.\"\n\n"
                    f"Scraper is working correctly.\n"
                    f"(Production will stay silent for this outcome.)"
                )
                send_push(msg, title="ICAI Test — No Batches Scheduled")

            else:
                # ── OUTCOME 2: Batches exist but all seats = 0 ─────────────
                # Production: silent. Test: notify to confirm pipeline works.
                total = len(batches_zero)
                print(f"   ℹ️   {total} batch(es) found, all seats = 0.")
                msg = (
                    f"ℹ️ All Batches Fully Booked — {city_display}\n"
                    f"{selected_course}\n\n"
                    f"{total} batch(es) found, every seat is taken.\n\n"
                    f"(Production will stay silent for this outcome.)"
                )
                send_push(msg, title="ICAI Test — All Seats Taken")

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
