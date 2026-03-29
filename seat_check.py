"""
ICAI Seat Monitor — One-Time Test
===================================
Single scrape run against the live ICAI website.
Always sends a Pushover notification (success or failure) so you
can confirm the full pipeline works before enabling the hourly schedule.
"""

import os
import sys
import time
import requests

# ── Stealth: handles ALL known playwright-stealth API versions ─────────────────
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
    print("⚠️  playwright-stealth not available — continuing without stealth.")
    return None


# ── Config ─────────────────────────────────────────────────────────────────────
URL         = "https://www.icaionlineregistration.org/launchbatchdetail.aspx"
REGION_VAL  = "4"    # Southern
POU_VAL     = "101"  # Alappuzha (change to your target city value)
COURSE_VAL  = "48"   # AICITSS – Advanced Information Technology

PUSHOVER_USER  = os.environ.get("PUSHOVER_USER", "")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")


# ── Helpers ────────────────────────────────────────────────────────────────────
def send_push(message: str, title: str = "ICAI Test") -> None:
    if not PUSHOVER_USER or not PUSHOVER_TOKEN:
        print("⚠️  Pushover secrets missing — skipping notification.")
        return
    try:
        resp = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER,
                  "title": title, "message": message},
            timeout=15,
        )
        print(f"Pushover → HTTP {resp.status_code}: {resp.text}")
    except Exception as exc:
        print(f"Pushover send failed: {exc}")


def screenshot(page, path: str) -> None:
    """Save screenshot — never raises so artifacts always exist."""
    try:
        page.screenshot(path=path, full_page=True)
        print(f"📸  Saved {path}")
    except Exception as exc:
        print(f"Screenshot failed ({path}): {exc}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    STEALTH = _load_stealth()
    print("🕵️  Stealth active." if STEALTH else "⚠️  No stealth.")

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

        # Block images/fonts/CSS — speeds up load on slow government server
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,otf,css}",
            lambda route: route.abort(),
        )

        if STEALTH:
            STEALTH(page)

        try:
            # ── Step 1: Load page ──────────────────────────────────────────
            print("\n[1/6] Loading ICAI page …")
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            screenshot(page, "debug_screenshot.png")   # Save immediately

            # ── Step 2: Select Region ──────────────────────────────────────
            print(f"[2/6] Selecting Region (value={REGION_VAL}) …")
            page.wait_for_selector("select[id*='reg']", state="visible", timeout=20_000)
            page.select_option("select[id*='reg']", value=REGION_VAL)

            # ── Step 3: Wait for POU dropdown to unlock (ASP.NET postback) ─
            print("[3/6] Waiting for POU dropdown to unlock …")
            try:
                page.wait_for_function(
                    "() => {"
                    "  const el = document.querySelector('select[id*=\"POU\"]');"
                    "  return el && !el.disabled && el.options.length > 1;"
                    "}",
                    timeout=30_000,
                )
            except PWTimeout:
                print("   ↳ Timeout — firing JS change event as fallback …")
                page.eval_on_selector(
                    "select[id*='reg']",
                    "el => el.dispatchEvent(new Event('change', { bubbles: true }))",
                )
                page.wait_for_function(
                    "() => {"
                    "  const el = document.querySelector('select[id*=\"POU\"]');"
                    "  return el && !el.disabled;"
                    "}",
                    timeout=20_000,
                )

            # ── Step 4: Select POU (city) and Course ──────────────────────
            print(f"[4/6] Selecting POU ({POU_VAL}) and Course ({COURSE_VAL}) …")
            page.wait_for_selector(
                f"option[value='{POU_VAL}']", state="attached", timeout=15_000
            )
            page.select_option("select[id*='POU']",    value=POU_VAL)
            time.sleep(1)
            page.select_option("select[id*='Course']", value=COURSE_VAL)

            # ── Step 5: Click Search ───────────────────────────────────────
            print("[5/6] Clicking Search …")
            page.click(
                "input[id*='Search'], "
                "input[id*='search'], "
                "input[value='Get List'], "
                "input[type='submit']"
            )
            try:
                page.wait_for_selector("tr", timeout=30_000)
            except PWTimeout:
                pass
            time.sleep(3)
            screenshot(page, "debug_screenshot.png")   # Overwrite with post-search state

            # ── Step 6: Parse table into array and count seats ─────────────
            print("[6/6] Parsing results …")
            rows = page.query_selector_all("tr")
            data = []
            for row in rows:
                cells = [c.inner_text().strip() for c in row.query_selector_all("td")]
                if cells:
                    data.append(cells)

            total_seats   = 0
            batch_details = []
            for row in data:
                if len(row) < 2:
                    continue
                seat_text = row[1]
                if seat_text.isdigit():
                    count = int(seat_text)
                    if 1 <= count <= 999:
                        total_seats += count
                        batch_details.append(f"{row[0][:40]}: {count} seats")

            print(f"   Total rows parsed : {len(data)}")
            print(f"   Total seats found : {total_seats}")

            # Always notify in test mode
            if total_seats > 0:
                msg = (
                    f"✅ Test OK — {total_seats} seats found!\n"
                    + "\n".join(batch_details)
                )
            else:
                msg = (
                    f"✅ Pipeline works! Scrape ran successfully.\n"
                    f"Seats available: 0  |  Rows parsed: {len(data)}\n"
                    f"(If seats exist on the site, check debug_screenshot in Artifacts)"
                )
            send_push(msg)

        except Exception as exc:
            print(f"\n❌ Error: {exc}")
            screenshot(page, "error_screenshot.png")
            send_push(f"❌ Test failed: {str(exc)[:120]}", title="ICAI Test — ERROR")
            # No sys.exit(1) — lets GitHub upload screenshots first

        finally:
            browser.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
