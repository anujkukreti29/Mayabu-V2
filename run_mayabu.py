"""One-command Mayabu scrape + merge pipeline.

Example:
  python run_mayabu.py "laptop" --platforms amazon flipkart croma reliance --max-pages 2 --catalog mayabu_catalog.json
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from amazon_scraper import scrape_amazon
from croma_scraper import scrape_croma
from flipkart_scraper import scrape_flipkart
from reliancedigital_scraper import scrape_reliancedigital
from mayabu_catalog import merge_files
from mayabu_scraper_base import default_output_path


async def run_scrapers(args: argparse.Namespace) -> dict[str, str]:
    out_dir = Path(args.raw_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    tasks = []

    async def run_one(platform: str):
        output = out_dir / default_output_path(platform, args.query)
        if platform == "amazon":
            await scrape_amazon(args.query, args.max_products, args.max_pages, str(output), args.headless)
        elif platform == "flipkart":
            await scrape_flipkart(args.query, args.max_products, args.max_pages, str(output), args.headless)
        elif platform == "croma":
            await scrape_croma(args.query, args.max_products, args.max_pages, str(output), args.headless)
        elif platform in {"reliance", "reliancedigital"}:
            await scrape_reliancedigital(args.query, args.max_products, args.max_pages, str(output), args.headless)
            platform = "reliancedigital"
        files[platform] = str(output)

    for platform in args.platforms:
        tasks.append(asyncio.create_task(run_one(platform)))
    if tasks:
        await asyncio.gather(*tasks)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu scrape + merge pipeline")
    parser.add_argument("query")
    parser.add_argument("--platforms", nargs="+", default=["amazon", "flipkart", "croma", "reliance"])
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-products", type=int)
    parser.add_argument("--raw-dir", default="raw_runs")
    parser.add_argument("--catalog", default="mayabu_catalog.json")
    parser.add_argument("--output", default="mayabu_catalog.json")
    parser.add_argument("--show-browser", action="store_true")
    args = parser.parse_args()
    args.headless = not args.show_browser

    files = asyncio.run(run_scrapers(args))
    merge_files(
        {
            "amazon": files.get("amazon"),
            "flipkart": files.get("flipkart"),
            "croma": files.get("croma"),
            "reliancedigital": files.get("reliancedigital") or files.get("reliance"),
        },
        catalog_path=args.catalog,
        output_path=args.output,
        query=args.query,
    )


if __name__ == "__main__":
    main()
