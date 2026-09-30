#!/usr/bin/env python3
"""Post-deploy release smoke checks (safe, read-mostly).

Optional --enqueue-verify creates a Check-latest-price job only (does not wait
for expensive retailer completion). Use --product-id to target a known listing.
"""

from __future__ import annotations

import argparse
import time

import httpx

CHECKS = [
    ("/api/live", 200),
    ("/api/ready", 200),
    ("/api/homepage?limit=1", 200),
    ("/api/search?q=asus&limit=1", 200),
    ("/api/categories/laptop/landing", 200),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url", default="")
    parser.add_argument("--admin-token", default="")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--product-id", default="", help="Optional product UUID for PDP/verify smoke")
    parser.add_argument(
        "--enqueue-verify",
        action="store_true",
        help="POST verify-price once (job creation only; does not poll retailer completion)",
    )
    args = parser.parse_args()
    failed = 0
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout) as client:
        for path, expected in CHECKS:
            started = time.perf_counter()
            try:
                response = client.get(path)
                ms = (time.perf_counter() - started) * 1000
                ok = response.status_code == expected
                print(f"{'OK' if ok else 'FAIL'} {response.status_code} {path} {ms:.0f}ms")
                if not ok:
                    failed += 1
            except httpx.HTTPError as exc:
                print(f"FAIL {path} {exc}")
                failed += 1

        if args.product_id:
            pdp = client.get(f"/api/products/{args.product_id}")
            ok = pdp.status_code == 200
            print(f"{'OK' if ok else 'FAIL'} {pdp.status_code} /api/products/{{id}}")
            if not ok:
                failed += 1
            if args.enqueue_verify and ok:
                verify = client.post(f"/api/products/{args.product_id}/verify-price")
                # 202 queued/joined, 200 already-fresh are acceptable
                ok_v = verify.status_code in {200, 202}
                print(f"{'OK' if ok_v else 'FAIL'} {verify.status_code} verify-price enqueue")
                if not ok_v:
                    failed += 1

        # Protected health/metrics when token provided
        if args.admin_token:
            headers = {"X-Mayabu-Admin-Token": args.admin_token}
            for path in ("/api/health", "/api/metrics"):
                response = client.get(path, headers=headers)
                ok = response.status_code == 200
                print(f"{'OK' if ok else 'FAIL'} {response.status_code} {path} (admin)")
                if not ok:
                    failed += 1
                if path == "/api/health" and ok:
                    body = response.json()
                    print(
                        "INFO worker_status="
                        f"{body.get('worker_status')} "
                        f"workers_seen_recently={body.get('workers_seen_recently')} "
                        f"pending={body.get('pending_tasks')} "
                        f"oldest_pending_age_seconds={body.get('oldest_pending_age_seconds')}"
                    )
            # Without token should fail in deployed mode if admin required
            denied = client.get("/api/metrics")
            print(f"INFO metrics_without_token {denied.status_code}")

    if args.frontend_url:
        with httpx.Client(base_url=args.frontend_url.rstrip("/"), timeout=args.timeout, follow_redirects=True) as fe:
            for path in ("/", "/laptops", "/robots.txt", "/sitemap.xml", "/search?q=asus"):
                try:
                    response = fe.get(path)
                    print(f"{'OK' if response.status_code < 500 else 'FAIL'} {response.status_code} FE {path}")
                    if response.status_code >= 500:
                        failed += 1
                except httpx.HTTPError as exc:
                    print(f"FAIL FE {path} {exc}")
                    failed += 1
            if args.product_id:
                try:
                    response = fe.get(f"/product/{args.product_id}")
                    print(f"{'OK' if response.status_code < 500 else 'FAIL'} {response.status_code} FE /product/{{id}}")
                    if response.status_code >= 500:
                        failed += 1
                except httpx.HTTPError as exc:
                    print(f"FAIL FE product {exc}")
                    failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
