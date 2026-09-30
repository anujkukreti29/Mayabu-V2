"""Bootstrap disposable mayabu_test database and apply schema twice."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ADMIN_URL = os.getenv(
    "MAYABU_ADMIN_DATABASE_URL",
    "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu",
)
TEST_URL = os.getenv(
    "MAYABU_TEST_DATABASE_URL",
    "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test",
)


def ensure_database() -> None:
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from pg_database where datname = 'mayabu_test'")
            if cur.fetchone() is None:
                cur.execute("create database mayabu_test")
                print("created database mayabu_test")
            else:
                print("database mayabu_test already exists")


def apply_schema(label: str) -> None:
    schema = Path("mayabu_db/schema.sql").read_text(encoding="utf-8")
    with psycopg.connect(TEST_URL, autocommit=True, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(schema, prepare=False)
            cur.execute(
                "select count(*) as n from information_schema.tables "
                "where table_schema = 'public'"
            )
            tables = cur.fetchone()["n"]
            cur.execute(
                "select to_regclass('public.platform_registry') as pr, "
                "to_regclass('public.daily_product_platform_prices') as dppp, "
                "to_regclass('public.product_search_documents') as psd, "
                "to_regclass('public.product_clusters') as pc"
            )
            regs = cur.fetchone()
            print(f"{label}: tables={tables} registry={regs}")


def main() -> int:
    ensure_database()
    apply_schema("fresh_or_first_apply")
    # Insert a marker row then re-apply to verify idempotency / no data wipe.
    with psycopg.connect(TEST_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into product_clusters(category, brand, canonical_title, title_norm, specs)
                values ('laptop','idempotency','Idempotency Marker','idempotency marker','{}'::jsonb)
                on conflict do nothing
                returning id
                """
            )
            row = cur.fetchone()
            conn.commit()
            marker = row["id"] if row else None
            if marker is None:
                cur.execute(
                    "select id from product_clusters where canonical_title = 'Idempotency Marker' limit 1"
                )
                marker = cur.fetchone()["id"]
            print(f"marker_product_id={marker}")
    apply_schema("second_apply")
    with psycopg.connect(TEST_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) as n from product_clusters where canonical_title = 'Idempotency Marker'"
            )
            print(f"marker_preserved={cur.fetchone()['n']}")
    print(f"MAYABU_TEST_DATABASE_URL={TEST_URL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
