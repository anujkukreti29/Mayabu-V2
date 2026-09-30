import asyncio
import json
import re
from pathlib import Path

from mayabu_scraper_base import BrowserSession, close_common_popups


async def dump(url: str, name: str) -> None:
    async with BrowserSession(headless=True, timeout_ms=45000) as session:
        page = await session.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await close_common_popups(page)
        await page.wait_for_timeout(4000)
        html = await page.content()
        Path(f"tmp_{name}.html").write_text(html, encoding="utf-8")
        ld = len(re.findall(r"application/ld\+json", html, re.I))
        next_data = "__NEXT_DATA__" in html
        product_links = len(re.findall(r"/p/", html, re.I))
        prices = len(re.findall(r"₹\s*[\d,]+", html))
        title = await page.title()
        # Sample first product-looking anchors
        anchors = await page.eval_on_selector_all(
            "a[href*='/p']",
            """els => els.slice(0, 12).map(a => ({
                href: a.getAttribute('href'),
                text: (a.innerText || a.getAttribute('title') || '').slice(0, 80)
            }))""",
        )
        print(
            json.dumps(
                {
                    "name": name,
                    "title": title,
                    "html_len": len(html),
                    "ld_json": ld,
                    "next_data": next_data,
                    "slash_p_count": product_links,
                    "rupee_prices": prices,
                    "sample_anchors": anchors,
                },
                ensure_ascii=False,
            )
        )


async def main() -> None:
    await dump("https://www.vijaysales.com/search/laptop", "vs_laptop")
    await dump("https://www.poorvika.com/search?q=laptop", "pv_laptop")
    await dump("https://www.jiomart.com/search/smartphone", "jm_phone")


if __name__ == "__main__":
    asyncio.run(main())
