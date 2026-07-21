"""Verify a live Mayabu v5.1 PostgreSQL deployment and critical primitives."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mayabu import __version__  # noqa: E402
from mayabu.db.connection import db_connection, pool_stats  # noqa: E402
from mayabu.search.index_manager import get_search_index_stats  # noqa: E402
from mayabu.search.search_repository import warm_search_source  # noqa: E402

REQUIRED_RELATIONS = (
    "product_clusters",
    "platform_listings",
    "price_observations",
    "product_search_documents",
    "search_document_dirty",
    "variant_groups",
    "product_variant_links",
    "scrape_tasks",
    "maintenance_runs",
    "admin_audit_log",
)


def main() -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select name, to_regclass('public.' || name) is not null as present from unnest(%s::text[]) name",
                (list(REQUIRED_RELATIONS),),
            )
            relations = {row["name"]: row["present"] for row in cur.fetchall()}
            cur.execute("select to_regprocedure('refresh_product_search_document(uuid)') is not null as present")
            refresh_function = bool(cur.fetchone()["present"])
            cur.execute("select version, applied_at from schema_migrations order by applied_at desc limit 5")
            migrations = cur.fetchall()
            cur.execute(
                """
                select indexname
                from pg_indexes
                where schemaname = 'public'
                  and indexname in (
                    'idx_search_docs_vector', 'idx_search_docs_trgm',
                    'idx_search_docs_model_trgm', 'idx_scrape_tasks_claim_lease'
                  )
                """
            )
            indexes = sorted(row["indexname"] for row in cur.fetchall())
    relation, v5_search = warm_search_source()
    result = {
        "ok": all(relations.values()) and refresh_function and relation == "product_search_documents",
        "version": __version__,
        "relations": relations,
        "refresh_function": refresh_function,
        "search_relation": relation,
        "v5_search": v5_search,
        "critical_indexes": indexes,
        "search": get_search_index_stats(),
        "pool": pool_stats(),
        "recent_migrations": migrations,
    }
    print(json.dumps(result, indent=2, default=str))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
