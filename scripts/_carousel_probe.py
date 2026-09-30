"""Inspect homepage carousel slides."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1366, "height": 768})
    page.emulate_media(reduced_motion="reduce")
    page.goto("http://127.0.0.1:5173/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector('[aria-roledescription="carousel"]', timeout=20000)
    titles = page.eval_on_selector_all(
        '[aria-roledescription="slide"]',
        "els => els.map(e => ({label: e.getAttribute('aria-label'), hidden: e.getAttribute('aria-hidden')}))",
    )
    print("slides", titles)
    page.get_by_role("button", name="Next slide").click()
    page.wait_for_timeout(600)
    titles2 = page.eval_on_selector_all(
        '[aria-roledescription="slide"]',
        "els => els.map(e => ({label: e.getAttribute('aria-label'), hidden: e.getAttribute('aria-hidden')}))",
    )
    print("after next", titles2)
    browser.close()
