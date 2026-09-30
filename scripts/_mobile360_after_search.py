"""Probe overflow after mobile 360 search navigation."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 360, "height": 740})
    page.goto("http://127.0.0.1:5173/", wait_until="domcontentloaded", timeout=60000)
    page.get_by_role("button", name="Open menu").click()
    menu = page.get_by_role("dialog").get_by_role("combobox", name="Search Mayabu products")
    menu.fill("galaxy")
    page.wait_for_timeout(400)
    opt = page.get_by_role("option").first
    if opt.is_visible():
        opt.click()
    else:
        menu.press("Enter")
    page.wait_for_timeout(1500)
    info = page.evaluate(
        """() => {
      const offenders = [];
      for (const el of document.querySelectorAll('body *')) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && (r.right > window.innerWidth + 2) && el.getBoundingClientRect) {
          const style = getComputedStyle(el);
          offenders.push({
            tag: el.tagName,
            cls: (el.className || '').toString().slice(0, 90),
            right: Math.round(r.right),
            overflow: style.overflowX,
            text: (el.textContent || '').trim().slice(0, 30),
          });
          if (offenders.length >= 8) break;
        }
      }
      return {
        url: location.href,
        scrollW: document.documentElement.scrollWidth,
        inner: window.innerWidth,
        offenders,
      };
    }"""
    )
    print(info)
    browser.close()
