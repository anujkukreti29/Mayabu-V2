"""Probe 360px homepage/menu overflow."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 360, "height": 740})
    page.goto("http://127.0.0.1:5173/", wait_until="domcontentloaded", timeout=60000)
    page.get_by_role("button", name="Open menu").click()
    page.wait_for_timeout(400)
    info = page.evaluate(
        """() => {
      const offenders = [];
      for (const el of document.querySelectorAll('body *')) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.right > window.innerWidth + 2) {
          offenders.push({
            tag: el.tagName,
            cls: (el.className || '').toString().slice(0, 100),
            right: Math.round(r.right),
            w: Math.round(r.width),
            text: (el.textContent || '').trim().slice(0, 40),
          });
          if (offenders.length >= 10) break;
        }
      }
      return { scrollW: document.documentElement.scrollWidth, inner: window.innerWidth, offenders };
    }"""
    )
    print(info)
    browser.close()
