import argparse
import json
import os
from pathlib import Path
from time import perf_counter

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def measure(browser, base, ticket_id, password):
    context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1,
                                  is_mobile=True, has_touch=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "/login")
    page.locator('[name="email"]').fill("warga@siwarga.id")
    page.locator('[name="password"]').fill(password)
    page.locator('button[type="submit"]').click()
    page.wait_for_url("**/dashboard")
    session = context.new_cdp_session(page)
    session.send("Network.enable")
    session.send("Network.setCacheDisabled", {"cacheDisabled": True})
    session.send("Network.emulateNetworkConditions", dict(offline=False, latency=150,
        downloadThroughput=200000, uploadThroughput=93750, connectionType="cellular3g"))
    session.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    started = perf_counter()
    response = page.goto(base + f"/pengaduan/{ticket_id}", wait_until="load", timeout=120000)
    if response.status != 200:
        raise RuntimeError(f"Detail returned HTTP {response.status}")
    page.evaluate("document.fonts.ready")
    initial = page.evaluate("""() => ({
      transfer_bytes: performance.getEntriesByType('navigation')[0].transferSize + performance.getEntriesByType('resource').reduce((total, entry) => total + entry.transferSize, 0),
      load_ms: performance.getEntriesByType('navigation')[0].loadEventEnd,
      resources: performance.getEntriesByType('resource').length
    })""")
    for image in page.locator('.photo-link img').all():
        image.scroll_into_view_if_needed(timeout=120000)
        image.evaluate("image => image.decode()", timeout=120000)
    full = page.evaluate("""() => {
      const entries = performance.getEntriesByType('resource');
      const navigation = performance.getEntriesByType('navigation')[0];
      return {
        transfer_bytes: navigation.transferSize + entries.reduce((total, entry) => total + entry.transferSize, 0),
        last_response_ms: Math.max(navigation.responseEnd, ...entries.map(entry => entry.responseEnd)),
        photo_requests: entries.filter(entry => new URL(entry.name).pathname.startsWith('/lampiran/')).map(entry => ({path: new URL(entry.name).pathname + new URL(entry.name).search, bytes: entry.transferSize}))
      };
    }""")
    full["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
    full["image_count"] = page.locator('.photo-link img').count()
    full["javascript_errors"] = errors
    if full["image_count"] != 3 or errors:
        raise RuntimeError("Fixture must show three photos without JavaScript errors")
    context.close()
    return dict(initial=initial, all_photos=full)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--ticket-id", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.runs <= 10:
        parser.error("Use 1-10 runs")
    password = os.environ.get("BENCHMARK_PASSWORD", "BenchmarkPassword123!")
    with sync_playwright() as automation:
        channel = os.getenv("PLAYWRIGHT_BROWSER", "chrome")
        browser = automation.chromium.launch(headless=True, **({} if channel == "chromium" else {"channel": channel}))
        results = [measure(browser, args.base_url.rstrip("/"), args.ticket_id, password) for unused in range(args.runs)]
        version = browser.version
        browser.close()
    report = dict(profile=dict(viewport="390x844", device_scale_factor=1, download_bytes_per_second=200000,
        upload_bytes_per_second=93750, latency_ms=150, cpu_throttling=4, cache="disabled"),
        browser=version, runs=results)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
