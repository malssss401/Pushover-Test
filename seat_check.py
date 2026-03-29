"""
ICAI Seat Monitor — One-Time Test
===================================
Uses full course names as they appear in the ICAI dropdown.
Course matching is case-insensitive so minor site-side text changes
(extra spaces, capitalisation) do not break the script.

CONFIG block is the only section you need to edit.
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

# POU: set to None to use auto-selected first city (Alappuzha).
# Otherwise use the city name exactly as it appears in the dropdown (ALL CAPS).
POU_LABEL  = "CHENNAI"  # e.g. "CHENNAI", "BENGALURU", "ALAPPUZHA", or None

# Full course name exactly as shown in the ICAI dropdown:
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
    Selects the course whose label matches course_name (case-insensitive,
    strips extra whitespace). Prints all available options to the GitHub
    Actions log so you can verify the exact label the site uses.
    Returns the full label of the matched course.
    Raises ValueError with the full option list if no match is found.
    """
    options = page.eval_on_selector(
        course_sel,
        "el => Array.from(el.options).map(o => ({value: o.value, text: o.text.trim()}))"
    )

    print(f"   Available Course options:")
    for opt in options:
        print(f"     value={opt['value']}  →  '{opt['text']}'")

    target = course_name.strip().lower()
    match  = next(
        (o for o in options if o["text"].lower() == target),
        None
    )

    # Fallback: partial match in case the site adds/removes a prefix
    if not match:
        match = next(
            (o for o in options if target in o["text"].lower()),
            None
        )
        if match:
            print(f"   ⚠️  Exact match not found — using partial match: '{match['text']}'")

    if not match:
        raise ValueError(
            f"Course '{course_name}' not found in dropdown.\n"
            f"Available options: {[o['text'] for o in options]}"
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
            # ── 1. Load page ───────────────────────────────────────────────
            print("\n[1/4] Loading page …")
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            screenshot(page, "debug_screenshot.png")

            # ── 2. Select Region → __doPostBack causes full page reload ────
            print("[2/4] Selecting Region …")
            page.wait_for_selector("select[id*='reg']", state="visible", timeout=15_000)
            page.select_option("select[id*='reg']", value=REGION_VAL)
            page.wait_for_load_state("domcontentloaded", timeout=30_000)
            time.sleep(2)   # Let postback finish writing POU option tags

            # ── 3. POU selection ───────────────────────────────────────────
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
                    # Case-insensitive JS fallback
                    print("   ⚠️  Exact label failed — trying case-insensitive JS match …")
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

            # ── 4. Select Course ───────────────────────────────────────────
            print(f"[4/4a] Selecting course '{COURSE_NAME}' …")
            selected_course = select_course(page, course_sel, COURSE_NAME)

            # Screenshot after course selected — confirms correct selection
            # before we wait on Get List (useful if Get List times out)
            screenshot(page, "debug_screenshot.png")

            # ── 5. Click Get List ──────────────────────────────────────────
            print("[4/4b] Clicking Get List …")
            page.click("input[value='Get List']")

            # 60s timeout — Chennai / large cities return more rows and the
            # ICAI server takes proportionally longer to respond
            page.wait_for_load_state("domcontentloaded", timeout=60_000)
            time.sleep(3)
            screenshot(page, "debug_screenshot.png")   # Final state with results

            # ── Parse results table ────────────────────────────────────────
            # Column layout confirmed from site screenshots:
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
                    continue   # Skip header rows

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

            # ── Notification ───────────────────────────────────────────────
            if batches_with_seats:
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
            else:
                total = len(batches_with_seats) + len(batches_zero)
                msg = (
                    f"✅ Pipeline OK — scrape completed.\n"
                    f"City   : {city_display}\n"
                    f"Course : {selected_course}\n"
                    f"Seats  : 0 across {total} batch(es)"
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
