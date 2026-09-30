#!/usr/bin/env python3
"""Read-only staging doctor — HTTPS, live/ready, routes, SEO, metrics, worker visibility.

No destructive actions. Does not claim PASS for external gates that are unreachable.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.parse import urlparse

import httpx


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Public staging origin, e.g. https://staging.example")
    parser.add_argument("--admin-token", default="", help="Optional admin token for /api/health and /api/metrics")
    parser.add_argument("--product-path", default="", help="Optional PDP path like /product/<slug-or-id>")
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    parsed = urlparse(base)
    results: list[dict[str, Any]] = []

    results.append(_check("https_scheme", parsed.scheme == "https", parsed.scheme or "missing"))
    if parsed.scheme != "https":
        results.append(_check("tls", False, "BASE_URL is not HTTPS — REAL HTTPS STAGING blocked"))

    with httpx.Client(base_url=base, timeout=args.timeout, follow_redirects=True) as client:
        # TLS / connectivity
        try:
            live = client.get("/api/live")
            results.append(_check("api_live", live.status_code == 200, f"status={live.status_code}"))
        except httpx.HTTPError as exc:
            results.append(_check("api_live", False, str(exc)))
            if args.json:
                print(json.dumps({"base_url": base, "results": results}, default=str, indent=2))
            else:
                for row in results:
                    print(f"{'OK' if row['ok'] else 'FAIL'} {row['name']}: {row['detail']}")
            return 1

        ready = client.get("/api/ready")
        results.append(_check("api_ready", ready.status_code == 200, f"status={ready.status_code}"))

        for path, label in (
            ("/", "homepage"),
            ("/laptops", "category_laptops"),
            ("/search?q=asus", "search_asus"),
            ("/robots.txt", "robots"),
            ("/sitemap.xml", "sitemap_index"),
        ):
            response = client.get(path)
            results.append(
                _check(label, response.status_code < 500, f"status={response.status_code}")
            )

        robots = client.get("/robots.txt")
        robots_text = robots.text.lower() if robots.status_code == 200 else ""
        staging_noindex = ("disallow: /" in robots_text) or ("noindex" in robots_text)
        # Also accept X-Robots-Tag on homepage
        home = client.get("/")
        xrobots = (home.headers.get("x-robots-tag") or "").lower()
        if "noindex" in xrobots:
            staging_noindex = True
        results.append(
            _check(
                "staging_noindex_policy",
                staging_noindex,
                f"robots_hint={staging_noindex} x-robots-tag={xrobots or 'absent'}",
            )
        )

        if args.product_path:
            pdp = client.get(args.product_path)
            results.append(_check("pdp", pdp.status_code < 500, f"status={pdp.status_code}"))

        # Metrics must not be public without token
        metrics_public = client.get("/api/metrics")
        results.append(
            _check(
                "metrics_not_public",
                metrics_public.status_code in {401, 403, 404},
                f"status={metrics_public.status_code}",
            )
        )

        if args.admin_token:
            headers = {"X-Mayabu-Admin-Token": args.admin_token}
            health = client.get("/api/health", headers=headers)
            ok_health = health.status_code == 200
            detail = f"status={health.status_code}"
            if ok_health:
                body = health.json()
                detail = (
                    f"status={body.get('status')} worker_status={body.get('worker_status')} "
                    f"workers_seen_recently={body.get('workers_seen_recently')} "
                    f"pending={body.get('pending_tasks')} oldest={body.get('oldest_pending_age_seconds')}"
                )
                results.append(
                    _check(
                        "worker_visibility",
                        body.get("worker_status") in {"ok", "stale", "none"},
                        detail,
                    )
                )
            results.append(_check("admin_health", ok_health, detail))
            metrics = client.get("/api/metrics", headers=headers)
            results.append(
                _check("admin_metrics", metrics.status_code == 200, f"status={metrics.status_code}")
            )

    failed = sum(1 for row in results if not row["ok"])
    payload = {"base_url": base, "failed": failed, "results": results}
    if args.json:
        print(json.dumps(payload, default=str, indent=2))
    else:
        for row in results:
            print(f"{'OK' if row['ok'] else 'FAIL'} {row['name']}: {row['detail']}")
        print(f"summary failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
