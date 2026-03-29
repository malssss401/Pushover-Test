"""
ICAI Seat Monitor — One-Time Test Script
=========================================
Runs a SINGLE check against the live ICAI website and sends a Pushover
notification regardless of seat count, so you can verify the entire
pipeline (browser → scrape → notify) works end-to-end.

Use the companion workflow:  .github/workflows/test_monitor.yml
"""

import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Configuration (must match seat_check.py) ──────────────────────────────────
CONFIG = {
    "url":        "https://www.icaionlineregistration.org/launchbatchdetail.aspx",
    "region_val": "4",    # Southern
    "pou_val":    "101",  # Alappuzha (testing) — change to your city for prod
    "course_val": "48",   # AICITSS – Advanced IT
}

PUSHOVER_USER  = os.environ.get("PUSHOVER_USER", "")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")


# ── Stealth import ─────────────────────────────────────────────────────────────
def _load_stealth():
    try:
        from playwright_stealth import stealth_sync
        return stealth_sync
    except ImportError:
        pass
    try:
        from playwright_stealth import stealth
        if callable(stealth):
            return stealth
    except ImportError:
        pass
    return None

STEALTH_FN = _load_stealth()


# ── Pushover ───────────────────────────────────────────────────────────────────
def send_push(message: str, title: str = "ICAI Test") -> None:
    if not PUSHOVER_USER or not PUSHOVER_TOKEN:
        print("⚠️  Pushover credentials not found in environment.")
        return
    resp = requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token":   PUSHOVER_TOKEN,
            "user":    PUSHOVER_USER,
            "title":   title,
            "message": message,
        },
        timeout=15,
    )
    print(f"Pushover response → HTTP {resp.status_code}: {resp.text}")


# ── Screenshot helper ──────────────────────────────────────────────────────────
def _safe_screenshot(page, path: str) -> None:
    try:
        page.screenshot(path=path, full_page=True)
        print(f"📸  Screenshot saved → {path}")
    except Exception as exc:
        print(f"⚠️  Screenshot failed: {exc}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=== ICAI One-Time Test ===\n")

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

        # Block heavy assets
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,otf,css}",
            lambda route: route.abort(),
        )

        if STEALTH_FN:
            STEALTH_FN(page)
            print("🕵️  Stealth mode active.")

        try:
            # Step 1: Load
            print("1. Loading ICAI page …")
            page.goto(CONFIG["url"], wait_until="domcontentloaded", timeout=60_000)
            _safe_screenshot(page, "debug_screenshot.png")  # Early capture

            # Step 2: Region
            print(f"2. Selecting Region ({CONFIG['region_val']}) …")
            page.wait_for_selector("select[id*='reg']", state="visible", timeout=20_000)
            page.select_option("select[id*='reg']", value=CONFIG["region_val"])

            # Step 3: Wait for POU
            print("3. Waiting for POU dropdown to unlock …")
            try:
                page.wait_for_function(
                    "() => { const el = document.querySelector('select[id*=\"POU\"]'); "
                    "return el && !el.disabled && el.options.length > 1; }",
                    timeout=30_000,
                )
            except PWTimeout:
                # Fallback: manually fire the change event
                print("   Fallback: dispatching change event on Region …")
                page.eval_on_selector(
                    "select[id*='reg']",
                    "el => el.dispatchEvent(new Event('change', { bubbles: true }))"
                )
                page.wait_for_function(
                    "() => { const el = document.querySelector('select[id*=\"POU\"]'); "
                    "return el && !el.disabled; }",
                    timeout=20_000,
                )

            # Step 4: POU & Course
            print(f"4. Selecting POU ({CONFIG['pou_val']}) and Course ({CONFIG['course_val']}) …")
            page.wait_for_selector(f"option[value='{CONFIG['pou_val']}']", state="attached", timeout=15_000)
            page.select_option("select[id*='POU']",    value=CONFIG["pou_val"])
            time.sleep(1)
            page.select_option("select[id*='Course']", value=CONFIG["course_val"])

            # Step 5: Search
            print("5. Clicking Search …")
            page.click("input[id*='Search'], input[id*='search'], input[type='submit']")

            try:
                page.wait_for_selector("tr", timeout=30_000)
            except PWTimeout:
                pass

            time.sleep(3)
            _safe_screenshot(page, "debug_screenshot.png")  # Post-search capture

            # Step 6: Parse into array
            print("6. Parsing results …")
            rows = page.query_selector_all("tr")
            data_array = [
                [c.inner_text().strip() for c in row.query_selector_all("td")]
                for row in rows
            ]
            data_array = [r for r in data_array if r]  # Remove empties

            total_seats = 0
            batch_details = []
            for row in data_array:
                if len(row) < 2:
                    continue
                if row[1].isdigit():
                    count = int(row[1])
                    if 1 <= count <= 999:
                        total_seats += count
                        batch_details.append(f"{row[0][:40]}: {count} seats")

            # Step 7: Notify — always send in test mode
            print(f"7. Total seats detected: {total_seats}")
            if total_seats > 0:
                msg = (
                    f"✅ TEST SUCCESS — {total_seats} seats found!\n"
                    + "\n".join(batch_details)
                )
            else:
                msg = (
                    "✅ Pipeline works! Connection OK.\n"
                    f"Seats currently available: 0\n"
                    f"(Table rows parsed: {len(data_array)})"
                )
            send_push(msg, title="ICAI Test Result")

        except Exception as exc:
            err_msg = f"❌ Test failed: {exc}"
            print(err_msg)
            _safe_screenshot(page, "error_screenshot.png")
            send_push(err_msg[:150], title="ICAI Test — ERROR")
            # Do NOT sys.exit(1) here — lets GitHub upload the screenshots first

        finally:
            browser.close()

    print("\n=== Test complete ===")


if __name__ == "__main__":
    main()
