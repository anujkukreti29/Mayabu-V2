import asyncio
import json
import re
from pathlib import Path

from mayabu_scraper_base import BrowserSession, close_common_popups


async def capture(url: str, out_prefix: str, wait_ms: int = 7000) -> None:
    async with BrowserSession(headless=True, timeout_ms=60000) as session:
        page = await session.new_page()
        responses: list[dict] = []

        async def on_response(resp):
            u = resp.url
            if any(t in u.lower() for t in ("algolia", "search", "product", "plp", "catalog", "api", "graphql")):
                try:
                    ct = (resp.headers.get("content-type") or "").lower()
                    body = ""
                    if "json" in ct:
                        body = await resp.text()
                    responses.append(
                        {
                            "url": u[:400],
                            "status": resp.status,
                            "ct": ct[:100],
                            "body_len": len(body),
                            "body_head": body[:600],
                        }
                    )
                except Exception as exc:
                    responses.append({"url": u[:400], "error": str(exc)})

        page.on("response", on_response)
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await close_common_popups(page)
        await page.wait_for_timeout(wait_ms)
        html = await page.content()
        Path(f"tmp_{out_prefix}.html").write_text(html, encoding="utf-8")
        Path(f"tmp_{out_prefix}_network.json").write_text(
            json.dumps(responses, indent=2)[:250000], encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "url": url,
                    "final": page.url,
                    "title": (await page.title())[:120],
                    "network": len(responses),
                    "p_digit": len(set(re.findall(r"/p/\d+", html))),
                    "slash_p": len(re.findall(r"/p(?:/|$|\?)", html)),
                    "rupee": len(re.findall(r"₹\s*[\d,]+", html)),
                    "next_data": "__NEXT_DATA__" in html,
                    "algolia": "algolia" in html.lower(),
                }
            )
        )
        for item in responses[:12]:
            print(json.dumps(item, ensure_ascii=False)[:450])


async def main() -> None:
    # Confirm fixed Vijay Sales search
    await capture("https://www.vijaysales.com/search?q=laptop", "vs_q_laptop", 4000)
    await capture("https://www.poorvika.com/search?q=laptop", "pv_search2", 8000)
    await capture("https://www.jiomart.com/search/smartphone", "jm_search2", 10000)


if __name__ == "__main__":
    asyncio.run(main())
