"""Compare Reliance page 1 and page 9 for the same query. No cursor writes."""
from __future__ import annotations

import asyncio
import time

from mayabu_scraper_base import BrowserSession

QUERY_URL = "https://www.reliancedigital.in/products?q=canon+eos&page_size=12&page_type=number&page_no={page}"


async def inspect(page_no: int) -> None:
    async with BrowserSession(headless=True, timeout_ms=25000) as session:
        page = await session.new_page()
        t0 = time.perf_counter()
        await page.goto(QUERY_URL.format(page=page_no), wait_until="domcontentloaded", timeout=25000)
        nav_ms = round((time.perf_counter() - t0) * 1000)
        try:
            await page.wait_for_selector("a[href*='/product/'], div.product-card, [class*='product-card']", timeout=12000)
            hydrated = True
        except Exception:
            hydrated = False
        stats = await page.evaluate(
            """() => {
                const html = document.documentElement.innerHTML;
                const links = [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href') || '');
                return {
                    productLinks: links.filter(h => h.includes('/product/')).length,
                    productCards: document.querySelectorAll('[class*=product-card], [class*=ProductCard], div.product-card').length,
                    goto: document.querySelectorAll("span[aria-label^='Goto page number']").length,
                    htmlHasProduct: html.includes('product-card') || html.includes('ProductCard'),
                    title: document.title.slice(0, 80),
                };
            }"""
        )
        print({"page": page_no, "nav_ms": nav_ms, "hydrated": hydrated, **stats}, flush=True)


async def main() -> None:
    await asyncio.wait_for(inspect(1), timeout=45)
    await asyncio.wait_for(inspect(9), timeout=45)


if __name__ == "__main__":
    asyncio.run(main())
