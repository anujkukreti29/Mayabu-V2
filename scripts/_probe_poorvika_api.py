import asyncio
import json
import re
from pathlib import Path

from mayabu_scraper_base import BrowserSession, close_common_popups


async def main() -> None:
    async with BrowserSession(headless=True, timeout_ms=60000) as session:
        page = await session.new_page()
        responses: list[dict] = []

        async def on_response(resp):
            u = resp.url
            if "poorvika.com/api" in u.lower():
                try:
                    ct = (resp.headers.get("content-type") or "").lower()
                    body = await resp.text() if "json" in ct else ""
                    responses.append(
                        {
                            "url": u[:450],
                            "status": resp.status,
                            "body_len": len(body),
                            "head": body[:350],
                        }
                    )
                except Exception as exc:
                    responses.append({"url": u[:450], "error": str(exc)})

        page.on("response", on_response)

        candidates = [
            "https://www.poorvika.com/computers-tablets/page",
            "https://www.poorvika.com/laptops/page",
            "https://www.poorvika.com/search/laptop",
            "https://www.poorvika.com/search/results?q=laptop",
            "https://www.poorvika.com/api/pim-v4/products?search=laptop",
            "https://www.poorvika.com/api/pim-v4/search?q=laptop",
            "https://www.poorvika.com/api/search?q=laptop",
        ]
        for url in candidates:
            responses.clear()
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await close_common_popups(page)
                await page.wait_for_timeout(3500)
                html = await page.content()
                status = resp.status if resp else None
                print(
                    json.dumps(
                        {
                            "requested": url,
                            "final": page.url,
                            "http": status,
                            "title": (await page.title())[:100],
                            "api_calls": len(responses),
                            "slash_p": len(re.findall(r"/p(?:/|$|\?)", html)),
                            "rupee": len(re.findall(r"₹\s*[\d,]+", html)),
                            "product_word": html.lower().count("product"),
                        }
                    )
                )
                for item in responses[:8]:
                    print("  API", json.dumps(item, ensure_ascii=False)[:300])
            except Exception as exc:
                print(json.dumps({"requested": url, "error": repr(exc)}))

        # Direct API probes via page.evaluate fetch from origin
        for api in (
            "/api/pim-v4/search?q=laptop&page=1",
            "/api/pim-v4/products/search?q=laptop",
            "/api/pim-v4/products?q=laptop&limit=20",
            "/api/search/products?q=laptop",
            "/api/catalog/search?q=laptop",
        ):
            try:
                data = await page.evaluate(
                    """async (path) => {
                      const r = await fetch(path, {credentials:'include'});
                      const t = await r.text();
                      return {status: r.status, len: t.length, head: t.slice(0, 400)};
                    }""",
                    api,
                )
                print(json.dumps({"fetch": api, **data}, ensure_ascii=False))
            except Exception as exc:
                print(json.dumps({"fetch": api, "error": repr(exc)}))


if __name__ == "__main__":
    asyncio.run(main())
