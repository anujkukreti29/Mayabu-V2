import asyncio
import json
import re
from pathlib import Path

from mayabu_scraper_base import BrowserSession, close_common_popups


async def try_urls(urls: list[str], name: str) -> None:
    async with BrowserSession(headless=True, timeout_ms=45000) as session:
        page = await session.new_page()
        for url in urls:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await close_common_popups(page)
            await page.wait_for_timeout(2500)
            title = await page.title()
            final = page.url
            html = await page.content()
            p_links = len(set(re.findall(r"/p/\d+", html)))
            print(
                json.dumps(
                    {
                        "name": name,
                        "requested": url,
                        "final": final,
                        "title": title[:100],
                        "p_digit_links": p_links,
                        "rupee": len(re.findall(r"₹\s*[\d,]+", html)),
                    },
                    ensure_ascii=False,
                )
            )


async def capture_jiomart() -> None:
    async with BrowserSession(headless=True, timeout_ms=60000) as session:
        page = await session.new_page()
        responses: list[dict] = []

        async def on_response(resp):
            url = resp.url
            if any(t in url.lower() for t in ("algolia", "search", "product", "plp", "catalog")):
                try:
                    ct = (resp.headers.get("content-type") or "").lower()
                    body = None
                    if "json" in ct or "javascript" in ct or url.endswith(".json"):
                        body = await resp.text()
                    responses.append(
                        {
                            "url": url[:300],
                            "status": resp.status,
                            "ct": ct[:80],
                            "body_len": len(body or ""),
                            "body_head": (body or "")[:400],
                        }
                    )
                except Exception as exc:
                    responses.append({"url": url[:300], "error": str(exc)})

        page.on("response", on_response)
        await page.goto(
            "https://www.jiomart.com/search/smartphone",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await close_common_popups(page)
        await page.wait_for_timeout(8000)
        Path("tmp_jm_network.json").write_text(json.dumps(responses, indent=2)[:200000], encoding="utf-8")
        print(json.dumps({"jiomart_network_captures": len(responses)}))
        for item in responses[:20]:
            print(json.dumps(item, ensure_ascii=False)[:500])


async def capture_poorvika() -> None:
    async with BrowserSession(headless=True, timeout_ms=60000) as session:
        page = await session.new_page()
        responses: list[dict] = []

        async def on_response(resp):
            url = resp.url
            if any(t in url.lower() for t in ("search", "product", "algolia", "api", "graphql")):
                try:
                    ct = (resp.headers.get("content-type") or "").lower()
                    body = None
                    if "json" in ct:
                        body = await resp.text()
                    responses.append(
                        {
                            "url": url[:350],
                            "status": resp.status,
                            "ct": ct[:80],
                            "body_len": len(body or ""),
                            "body_head": (body or "")[:500],
                        }
                    )
                except Exception as exc:
                    responses.append({"url": url[:350], "error": str(exc)})

        page.on("response", on_response)
        await page.goto(
            "https://www.poorvika.com/search?q=laptop",
            wait_until="networkidle",
            timeout=60000,
        )
        await close_common_popups(page)
        await page.wait_for_timeout(5000)
        Path("tmp_pv_network.json").write_text(json.dumps(responses, indent=2)[:200000], encoding="utf-8")
        html = await page.content()
        Path("tmp_pv_laptop2.html").write_text(html, encoding="utf-8")
        m = re.search(
            r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.I | re.S
        )
        print(
            json.dumps(
                {
                    "poorvika_final": page.url,
                    "title": await page.title(),
                    "network": len(responses),
                    "next_data": bool(m),
                    "p_links": len(re.findall(r"/p(?:/|$|\?)", html)),
                    "rupee": len(re.findall(r"₹\s*[\d,]+", html)),
                }
            )
        )
        for item in responses[:15]:
            print(json.dumps(item, ensure_ascii=False)[:500])


async def main() -> None:
    await try_urls(
        [
            "https://www.vijaysales.com/search/?q=laptop",
            "https://www.vijaysales.com/search?q=laptop",
            "https://www.vijaysales.com/s/laptop",
            "https://www.vijaysales.com/product-listing-page?search=laptop",
            "https://www.vijaysales.com/product-listing-page?q=laptop",
            "https://www.vijaysales.com/c/laptops",
        ],
        "vijaysales",
    )
    await capture_poorvika()
    await capture_jiomart()


if __name__ == "__main__":
    asyncio.run(main())
