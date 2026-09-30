"""Debug carousel next-button behavior."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1366, "height": 768})
    page.emulate_media(reduced_motion="reduce")
    page.on("console", lambda msg: print("CONSOLE", msg.type, msg.text))
    page.on("pageerror", lambda err: print("PAGEERROR", err))
    page.goto("http://127.0.0.1:5173/", wait_until="networkidle", timeout=60000)
    carousel = page.get_by_role("region", name="Mayabu homepage highlights")
    print("carousel count", carousel.count())
    next_btn = carousel.get_by_role("button", name="Next slide")
    print("next visible", next_btn.is_visible())
    before = page.eval_on_selector(
        '[aria-roledescription="slide"]:not([aria-hidden="true"])',
        "e => e.getAttribute('aria-label')",
    )
    print("before", before)
    next_btn.click()
    page.wait_for_timeout(800)
    after = page.eval_on_selector(
        '[aria-roledescription="slide"]:not([aria-hidden="true"])',
        "e => e.getAttribute('aria-label')",
    )
    print("after click", after)
    page.get_by_role("button", name="Go to slide 2").click()
    page.wait_for_timeout(500)
    after2 = page.eval_on_selector(
        '[aria-roledescription="slide"]:not([aria-hidden="true"])',
        "e => e.getAttribute('aria-label')",
    )
    print("after go-to-2", after2)
    browser.close()
