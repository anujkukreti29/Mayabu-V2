import asyncio
import json
from pathlib import Path


async def probe(name, fn, query, n=8):
    rows = await fn(query, max_products=n, max_pages=2, headless=True)
    sample = []
    for r in rows[:5]:
        sample.append(
            {
                "title": (r.get("title") or "")[:80],
                "price": r.get("price"),
                "url": (r.get("link") or r.get("url") or "")[:100],
                "image": bool(r.get("image") or r.get("image_url")),
                "native_id": r.get("native_id"),
                "category": r.get("category"),
            }
        )
    out = {"platform": name, "query": query, "count": len(rows), "sample": sample}
    print(json.dumps(out, ensure_ascii=False))
    return out


async def main():
    from vijaysales_scraper import scrape_vijaysales
    from poorvika_scraper import scrape_poorvika
    from jiomart_scraper import scrape_jiomart

    results = []
    for q in ["laptop", "smartphone", "55 inch tv"]:
        results.append(await probe("vijaysales", scrape_vijaysales, q))
    results.append(await probe("vijaysales", scrape_vijaysales, "laptop"))  # repeat
    for q in ["laptop", "smartphone"]:
        results.append(await probe("poorvika", scrape_poorvika, q))
    results.append(await probe("jiomart", scrape_jiomart, "smartphone", 4))
    Path("tmp_retail_smoke3.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
