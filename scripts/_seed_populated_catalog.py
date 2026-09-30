"""Seed a realistic populated catalog into MAYABU_TEST_DATABASE_URL for suggest perf."""
from __future__ import annotations

import os
import random
import uuid

import psycopg

URL = os.environ.get("MAYABU_TEST_DATABASE_URL")
if not URL or "test" not in URL.lower():
    raise SystemExit("Set MAYABU_TEST_DATABASE_URL to a disposable DB whose name contains 'test'")

BRANDS = [
    ("Samsung", "smartphone", ["Galaxy S24", "Galaxy A54", "Galaxy M34"]),
    ("Apple", "smartphone", ["iPhone 15", "iPhone 14"]),
    ("Sony", "headphones", ["WH-1000XM5", "WF-1000XM5"]),
    ("Sony", "camera", ["Alpha A7 IV", "ZV-E10"]),
    ("LG", "television", ["OLED C3", "OLED B3"]),
    ("Samsung", "television", ["QLED Q60", "Crystal UHD"]),
    ("HP", "laptop", ["Pavilion", "Victus", "OmniBook"]),
    ("Lenovo", "laptop", ["IdeaPad Slim", "ThinkPad E14"]),
    ("ASUS", "laptop", ["Vivobook", "TUF Gaming"]),
    ("Bosch", "washing_machine", ["Series 6 Front Load"]),
    ("Samsung", "refrigerator", ["Twin Cooling"]),
    ("boAt", "tws", ["Airdopes 141", "Airdopes 131"]),
]

TARGET = int(os.environ.get("MAYABU_SEED_COUNT", "1200"))


def main() -> None:
    rng = random.Random(42)
    with psycopg.connect(URL) as conn, conn.cursor() as cur:
        cur.execute("select count(*) from product_clusters where status='active'")
        existing = int(cur.fetchone()[0])
        print("existing_active", existing)
        need = max(0, TARGET - existing)
        if need == 0:
            print("already_populated", existing)
            cur.execute("select count(*) from product_search_documents")
            print("search_docs", cur.fetchone()[0])
            return

        for i in range(need):
            brand, category, families = rng.choice(BRANDS)
            family = rng.choice(families)
            ram = rng.choice([4, 8, 12, 16, 24, 32])
            storage = rng.choice([128, 256, 512, 1024])
            price = float(rng.randint(8_999, 189_999))
            pid = uuid.uuid4()
            title = f"{brand} {family} {ram}GB {storage}GB Seed-{i:04d}"
            title_norm = title.lower()
            cur.execute(
                """
                insert into product_clusters(id, category, brand, canonical_title, title_norm, status)
                values (%s, %s, %s, %s, %s, 'active')
                on conflict (id) do nothing
                """,
                (pid, category, brand.lower(), title, title_norm),
            )
            cur.execute(
                """
                insert into product_search_documents(
                  product_id, brand, category, canonical_title, title_norm,
                  family, ram_gb, storage_gb, best_price, best_platform,
                  platform_count, offer_count, search_text, search_vector, indexed_at
                )
                values (
                  %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, 'amazon',
                  1, 1, %s, to_tsvector('simple', %s), now()
                )
                on conflict (product_id) do update
                set search_text = excluded.search_text,
                    search_vector = excluded.search_vector,
                    best_price = excluded.best_price,
                    indexed_at = now()
                """,
                (
                    pid,
                    brand.lower(),
                    category,
                    title,
                    title_norm,
                    family.lower().replace(" ", "_"),
                    ram,
                    storage,
                    price,
                    title_norm,
                    title_norm,
                ),
            )
            if (i + 1) % 200 == 0:
                conn.commit()
                print("seeded", i + 1)

        conn.commit()
        cur.execute("select count(*) from product_clusters where status='active'")
        print("active_after", cur.fetchone()[0])
        cur.execute("select count(*) from product_search_documents")
        print("search_docs_after", cur.fetchone()[0])


if __name__ == "__main__":
    main()
