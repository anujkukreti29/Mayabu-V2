from __future__ import annotations

import argparse
from pathlib import Path

from mayabu_db.connection import db_connection

SCHEMA_VERSION = "2026_07_15_mayabu_v5_2_live_price_verification"


def apply_schema() -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    sql = schema_path.read_text(encoding="utf-8")
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "insert into schema_migrations(version) values (%s) on conflict (version) do nothing",
                (SCHEMA_VERSION,),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Mayabu PostgreSQL schema")
    parser.parse_args()
    apply_schema()
    print(f"Applied Mayabu schema: {SCHEMA_VERSION}")


if __name__ == "__main__":
    main()
