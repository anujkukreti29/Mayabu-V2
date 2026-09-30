"""Probe homepage product image URLs against live CDNs."""

from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError


def main() -> None:
    home = json.loads(
        urllib.request.urlopen("http://127.0.0.1:8000/api/homepage?limit=6", timeout=20).read()
    )
    urls: list[tuple[str, str | None, str | None]] = []
    for key in (
        "featured",
        "biggest_discounts",
        "recently_checked",
        "trending",
        "popular",
        "lowest_since_tracking",
        "price_drops",
    ):
        for product in home.get(key) or []:
            image = product.get("image_url")
            if image:
                urls.append((image, product.get("best_platform"), product.get("category")))

    seen: set[str] = set()
    unique: list[tuple[str, str | None, str | None]] = []
    for item in urls:
        if item[0] in seen:
            continue
        seen.add(item[0])
        unique.append(item)

    def check(item: tuple[str, str | None, str | None]) -> dict:
        url, platform, category = item
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "MayabuImageQA/1.0",
                "Referer": "https://www.mayabu.in/",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                content_type = response.headers.get("Content-Type", "")
                return {
                    "ok": True,
                    "status": response.status,
                    "ct": content_type,
                    "plat": platform,
                    "cat": category,
                    "url": url[:110],
                }
        except HTTPError as exc:
            return {
                "ok": False,
                "status": exc.code,
                "ct": "",
                "plat": platform,
                "cat": category,
                "url": url[:110],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "status": 0,
                "ct": str(exc)[:80],
                "plat": platform,
                "cat": category,
                "url": url[:110],
            }

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(check, item) for item in unique[:24]]
        for future in as_completed(futures):
            results.append(future.result())

    loaded = sum(1 for row in results if row["ok"] and "image" in (row["ct"] or "").lower())
    print(f"tested {len(results)} loaded {loaded} failed {len(results) - loaded}")
    for row in results:
        mark = "OK" if row["ok"] and "image" in (row.get("ct") or "").lower() else "FAIL"
        print(
            mark,
            row["status"],
            row["plat"],
            row["cat"],
            (row["ct"] or "")[:40],
            row["url"],
        )


if __name__ == "__main__":
    main()
