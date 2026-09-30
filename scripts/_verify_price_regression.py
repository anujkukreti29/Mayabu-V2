from __future__ import annotations

import time

import httpx

from mayabu_db.connection import close_connection_pool, db_connection


def pick_product() -> str:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select p.id::text
            from product_clusters p
            join current_product_best_prices b on b.product_id = p.id
            join platform_listings l on l.product_id = p.id
            where p.status = 'active'
              and b.best_price is not null
              and l.match_status = 'matched'
              and l.stock_status <> 'out_of_stock'
              and l.current_price > 0
            order by l.last_successful_refresh_at desc nulls last
            limit 1
            """
        )
        row = cur.fetchone()
        if not row:
            raise SystemExit("no in-stock product")
        product_id = row["id"]
        cur.execute(
            """
            update platform_listings
            set next_allowed_verification_at = null,
                consecutive_verification_failures = 0
            where product_id = %s::uuid
            """,
            (product_id,),
        )
        conn.commit()
        return product_id


def main() -> None:
    product_id = pick_product()
    print("product", product_id)
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
        before = client.get(f"/api/products/{product_id}").json()
        print("before_best", before["product"]["best_price"])
        posted = client.post(f"/api/products/{product_id}/verify-price", json={"mode": "best_offer"})
        print("post", posted.status_code, posted.text[:400])
        if posted.status_code != 202:
            raise SystemExit(1)
        payload = posted.json()
        task_ids = payload.get("task_ids") or []
        print("status", payload.get("status"), "task_ids", task_ids)
        if not task_ids:
            print("no_tasks_due", payload.get("status"))
            after = client.get(f"/api/products/{product_id}").json()
            print("after_best", after["product"]["best_price"])
            print("PASS verify-price regression (no due tasks)")
            return
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        worker = subprocess.run(
            [sys.executable, "-m", "mayabu.jobs.worker", "--once"],
            cwd=root,
            check=False,
        )
        print("worker_exit", worker.returncode)
        task_id = task_ids[0]
        for _ in range(40):
            time.sleep(3)
            job = client.get(f"/api/verification-jobs/{task_id}")
            body = job.json() if job.status_code == 200 else {"status": job.status_code}
            print("job", body.get("status") or body)
            if str(body.get("status") or "") in {"completed", "failed", "dead"}:
                break
        after = client.get(f"/api/products/{product_id}").json()
        print("after_best", after["product"]["best_price"], "offers", after.get("offer_count"))
        if after["product"]["best_price"] is None and any(
            (offer.get("price") or 0) > 0 for offer in after.get("offers") or []
        ):
            raise SystemExit("stale null best_price after verification")
        print("PASS verify-price regression")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_connection_pool(timeout=1.0)
