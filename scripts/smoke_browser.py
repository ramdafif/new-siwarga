import json
import os
from io import BytesIO
from pathlib import Path

from dotenv import dotenv_values
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
OUTPUT = ROOT / "test-results" / "browser"


def capture(page, name):
    page.evaluate("document.fonts.ready")
    brand = page.locator(".brand-symbol")
    assert brand.count() == 1 and brand.evaluate("image => image.complete && image.naturalWidth > 0"), f"Brand logo missing: {name}"
    color = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--brand-blue').trim()")
    assert color == "#005baa", f"Brand stylesheet missing: {name}"
    page.screenshot(path=str(OUTPUT / f"{name}.png"), full_page=True)
    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    if overflow:
        outside = page.evaluate("({width: innerWidth, scrollWidth: document.documentElement.scrollWidth, elements: [...document.querySelectorAll('body *')].filter(element => element.getBoundingClientRect().right > innerWidth + 1 && !element.closest('.table-scroll,.dashboard-art')).map(element => ({tag: element.tagName, className: String(element.className), right: element.getBoundingClientRect().right})).slice(0, 20)})")
        raise AssertionError(f"Page overflow: {name}; {outside}")


def main():
    password = os.getenv("DEMO_PASSWORD") or dotenv_values(ROOT / ".env").get("DEMO_PASSWORD")
    if not password:
        raise SystemExit("Seed data and DEMO_PASSWORD are required.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as automation:
        channel = os.getenv("PLAYWRIGHT_BROWSER", "chrome")
        browser = automation.chromium.launch(headless=True, **({} if channel == "chromium" else {"channel": channel}))
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1, reduced_motion="reduce")
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        for route, name in (("/", "landing-desktop"), ("/login", "login-desktop"), ("/register", "register-desktop")):
            response = page.goto(BASE_URL + route)
            assert response.status == 200, route
            capture(page, name)
        page.set_viewport_size({"width": 390, "height": 844})
        capture(page, "register-mobile")
        page.set_viewport_size({"width": 320, "height": 740})
        capture(page, "register-small-mobile")
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(BASE_URL + "/login")
        capture(page, "login-tablet")
        page.goto(BASE_URL)
        capture(page, "landing-tablet")
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(BASE_URL)
        capture(page, "landing-mobile")
        page.set_viewport_size({"width": 320, "height": 740})
        capture(page, "landing-small-mobile")
        page.set_viewport_size({"width": 1440, "height": 1000})
        for handle in ("warga", "rt", "rw", "karangtaruna", "admin"):
            page.goto(BASE_URL + "/login")
            page.get_by_label("Alamat email", exact=True).fill(f"{handle}@siwarga.id")
            page.get_by_label("Kata sandi", exact=True).fill(password)
            page.get_by_role("button", name="Masuk ke SiWarga").click()
            page.wait_for_url("**/dashboard")
            capture(page, f"dashboard-{handle}-desktop")
            if handle == "warga":
                for width in (820, 1024):
                    page.set_viewport_size({"width": width, "height": 1000})
                    capture(page, f"dashboard-warga-tablet-{width}")
                page.set_viewport_size({"width": 390, "height": 844})
                capture(page, "dashboard-warga-mobile")
                page.set_viewport_size({"width": 320, "height": 740})
                capture(page, "dashboard-warga-small-mobile")
                page.set_viewport_size({"width": 390, "height": 844})
                page.get_by_role("button", name="Buka menu").click()
                assert page.locator("body").evaluate("element => element.classList.contains('nav-open')")
                page.get_by_role("link", name="Pengaduan saya", exact=True).click()
                page.wait_for_url("**/pengaduan")
                capture(page, "tickets-mobile")
                page.locator(".ticket-title").first.click()
                capture(page, "detail-mobile")
                page.goto(BASE_URL + "/pengaduan/baru")
                image = BytesIO()
                Image.new("RGB", (16, 16), "#92b9a0").save(image, "PNG")
                page.locator('[name="foto"]').set_input_files({"name": "bukti.png", "mimeType": "image/png", "buffer": image.getvalue()})
                assert page.locator(".preview-item img").count() == 1
                capture(page, "create-mobile")
                page.get_by_role("button", name="Hapus foto bukti.png").click()
                assert page.locator(".preview-item").count() == 0
                page.goto(BASE_URL + "/notifikasi")
                capture(page, "notifications-mobile")
                page.set_viewport_size({"width": 1440, "height": 1000})
            if handle == "karangtaruna":
                page.locator(".ticket-title").first.click()
                assert page.get_by_role("button", name="Tandai selesai").count() == 0
                assert page.get_by_role("button", name="Simpan progres").count() == 1
                capture(page, "task-karangtaruna-desktop")
            if handle == "admin":
                for route in ("wilayah", "kategori", "pengurus"):
                    page.goto(BASE_URL + "/admin/" + route)
                    capture(page, f"admin-{route}-desktop")
                page.set_viewport_size({"width": 390, "height": 844})
                capture(page, "admin-pengurus-mobile")
                page.set_viewport_size({"width": 1440, "height": 1000})
            page.get_by_role("button", name="Keluar", exact=True).click()
            page.wait_for_url("**/login")
        context.close()
        browser.close()
    assert not errors, errors
    report = {"roles_checked": 5, "javascript_errors": errors, "screenshots": len(list(OUTPUT.glob("*.png"))), "overflow": False}
    (OUTPUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
