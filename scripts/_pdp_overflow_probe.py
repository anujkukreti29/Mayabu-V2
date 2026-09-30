"""Probe PDP horizontal overflow offenders at phone width."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto("http://127.0.0.1:5173/search?q=laptop", wait_until="domcontentloaded", timeout=60000)
    page.locator("main a[href*='/products/']").first.click()
    page.wait_for_url("**/products/**", timeout=20000)
    page.wait_for_selector("h1", timeout=15000)
    info = page.evaluate(
        """() => {
      const doc = document.documentElement;
      const offenders = [];
      for (const el of document.querySelectorAll('body *')) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.right > window.innerWidth + 2) {
          offenders.push({
            tag: el.tagName,
            cls: (el.className || '').toString().slice(0, 120),
            right: Math.round(r.right),
            w: Math.round(r.width),
            text: (el.textContent || '').trim().slice(0, 60),
          });
          if (offenders.length >= 12) break;
        }
      }
      return { scrollW: doc.scrollWidth, inner: window.innerWidth, offenders };
    }"""
    )
    print(info)
    browser.close()
