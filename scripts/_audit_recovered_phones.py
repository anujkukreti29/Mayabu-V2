"""Stratified audit of smartphones recovered from unknown listings."""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from mayabu.domain.phone_recovery import phone_recovery_verdict
from mayabu_db.connection import db_connection


def main() -> None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select c.id, c.brand, c.canonical_title, d.best_price, l.platform
            from platform_listings l
            join product_clusters c on c.id = l.product_id
            left join product_search_documents d on d.product_id = c.id
            where coalesce(l.match_evidence->>'auto_resolution','') = 'unknown_recovered'
              and l.category = 'smartphone'
              and c.status = 'active'
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    by_product: dict[str, dict] = {}
    for row in rows:
        by_product[str(row["id"])] = row
    products = list(by_product.values())
    buckets: dict[str, list] = defaultdict(list)
    for row in products:
        price = float(row["best_price"] or 0)
        if price <= 0:
            band = "no_price"
        elif price < 15000:
            band = "under_15k"
        elif price < 30000:
            band = "15_30k"
        elif price < 60000:
            band = "30_60k"
        else:
            band = "over_60k"
        brand = str(row["brand"] or "unknown").lower()
        buckets[f"{brand}|{band}|{row['platform']}"].append(row)
    sample: list[dict] = []
    # Round-robin so the sample is not one brand.
    keys = sorted(buckets)
    while len(sample) < 100 and any(buckets.values()):
        for key in keys:
            if buckets[key] and len(sample) < 100:
                sample.append(buckets[key].pop())
    verdicts = Counter()
    wrong = []
    for row in sample:
        verdict = phone_recovery_verdict(row["canonical_title"] or "")
        verdicts[verdict] += 1
        if verdict != "correct_smartphone":
            wrong.append({"title": row["canonical_title"], "verdict": verdict, "brand": row["brand"], "platform": row["platform"]})
    # Full-set scan, not just the sample, so a systematic miss is visible.
    full = Counter(phone_recovery_verdict(row["canonical_title"] or "") for row in products)
    precision = (verdicts["correct_smartphone"] / len(sample)) if sample else 0
    report = {
        "recovered_products": len(products),
        "sample": len(sample),
        "sample_verdicts": dict(verdicts),
        "sample_precision": round(precision, 4),
        "full_verdicts": dict(full),
        "sample_not_phone": wrong[:30],
        "sample_rows": [
            {
                "product_id": str(row["id"]),
                "brand": row["brand"],
                "title": row["canonical_title"],
                "platform": row["platform"],
                "price": float(row["best_price"] or 0),
                "verdict": phone_recovery_verdict(row["canonical_title"] or ""),
            }
            for row in sample
        ],
    }
    from pathlib import Path
    path = Path("artifacts/catalog_depth_v2_completion/recovered_phone_audit.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "sample_rows"}, indent=2))


if __name__ == "__main__":
    main()
