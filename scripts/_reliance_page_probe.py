"""One Reliance page-9 continuation, timed, without moving plan cursors."""
from __future__ import annotations

import asyncio
import time

from mayabu_scraper_base import BrowserSession, wait_for_any_selector
from reliancedigital_scraper import CARD_SELECTORS, detect_max_pages

QUERY = "canon eos"
PAGE = 9
OVERALL_S = 90


async def probe() -> None:
    url = (
        "https://www.reliancedigital.in/products?q=canon+eos"
        f"&page_no={PAGE}&page_size=12&page_type=number"
    )
    started = time.perf_counter()

    async def run() -> None:
        async with BrowserSession(headless=True, timeout_ms=25000) as session:
            page = await session.new_page()
            t0 = time.perf_counter()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                nav = "ok"
            except Exception as exc:
                nav = type(exc).__name__
            nav_ms = round((time.perf_counter() - t0) * 1000)
            t1 = time.perf_counter()
            selector = await wait_for_any_selector(page, CARD_SELECTORS, timeout_ms=20000)
            sel_ms = round((time.perf_counter() - t1) * 1000)
            cards = 0
            if selector:
                cards = len(await page.query_selector_all(selector))
            detected = await detect_max_pages(page, 0)
            title = await page.title()
            final_url = page.url
            text = (await page.inner_text("body"))[:400].replace("\n", " ")
            lowered = text.lower()
            challenge = any(token in lowered for token in ("captcha", "access denied", "robot", "verify you"))
            print(
                {
                    "nav": nav,
                    "nav_ms": nav_ms,
                    "selector": selector,
                    "selector_ms": sel_ms,
                    "cards": cards,
                    "detected_pages": detected,
                    "title": title[:120],
                    "final_url": final_url[:180],
                    "challenge": challenge,
                    "text": text[:220],
                    "total_ms": round((time.perf_counter() - started) * 1000),
                },
                flush=True,
            )

    await asyncio.wait_for(run(), timeout=OVERALL_S)


if __name__ == "__main__":
    asyncio.run(probe())
