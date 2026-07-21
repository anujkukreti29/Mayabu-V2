"""Persist deterministic family/variant groups for one or more products."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from mayabu.db.connection import db_connection
from mayabu.domain.product_identity import build_identity

logger = logging.getLogger(__name__)


def _refresh_variant_group(conn: Connection, product_id: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("select id, category, brand, canonical_title, specs from product_clusters where id = %s", (product_id,))
        product = cur.fetchone()
        if not product:
            raise ValueError(f"Product not found: {product_id}")
        identity = build_identity(product["canonical_title"], product.get("specs") or {}, product.get("category") or "laptop")
        cur.execute(
            """
            update product_clusters
            set exact_fingerprint = %s,
                family_fingerprint = %s,
                updated_at = now()
            where id = %s
              and (exact_fingerprint is distinct from %s or family_fingerprint is distinct from %s)
            """,
            (
                identity.exact_fingerprint,
                identity.family_fingerprint,
                product_id,
                identity.exact_fingerprint,
                identity.family_fingerprint,
            ),
        )
        if not identity.family_fingerprint:
            cur.execute("delete from product_variant_links where product_id = %s", (product_id,))
            return {"product_id": product_id, "grouped": False}

        display_name = " ".join(x for x in (identity.brand, identity.family) if x) or product["canonical_title"][:120]
        cur.execute(
            """
            insert into variant_groups(category, brand, family_key, display_name, metadata)
            values (%s,%s,%s,%s,%s)
            on conflict (category, brand, family_key) do update set
              display_name = excluded.display_name,
              metadata = variant_groups.metadata || excluded.metadata,
              updated_at = now()
            returning id
            """,
            (
                identity.category,
                identity.brand,
                identity.family_fingerprint,
                display_name,
                Jsonb({"family": identity.family}),
            ),
        )
        group_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            insert into product_variant_links(group_id, product_id, exact_fingerprint, relation_confidence, metadata)
            values (%s,%s,%s,100,%s)
            on conflict (product_id) do update set
              group_id = excluded.group_id,
              exact_fingerprint = excluded.exact_fingerprint,
              relation_confidence = excluded.relation_confidence,
              metadata = excluded.metadata,
              updated_at = now()
            """,
            (
                group_id,
                product_id,
                identity.exact_fingerprint,
                Jsonb({
                    "model_codes": identity.model_codes,
                    "ram_gb": identity.ram_gb,
                    "storage_gb": identity.storage_gb,
                    "cpu_models": identity.cpu_models,
                    "screen_inch": identity.screen_inch,
                }),
            ),
        )
    return {"product_id": product_id, "group_id": group_id, "grouped": True}


def refresh_variant_group(product_id: str) -> dict[str, Any]:
    with db_connection() as conn:
        return _refresh_variant_group(conn, product_id)


def refresh_variant_groups(product_ids: Iterable[str]) -> dict[str, int]:
    """Refresh a batch with one pool checkout and per-product transactions."""
    updated = skipped = failed = 0
    unique_ids = list(dict.fromkeys(str(x) for x in product_ids if x))
    if not unique_ids:
        return {"updated": 0, "skipped": 0, "failed": 0}

    with db_connection() as conn:
        for product_id in unique_ids:
            try:
                with conn.transaction():
                    result = _refresh_variant_group(conn, product_id)
                updated += int(bool(result.get("grouped")))
                skipped += int(not result.get("grouped"))
            except Exception as exc:
                failed += 1
                logger.warning("variant_group_refresh_failed", extra={"product_id": product_id, "error": str(exc)[:500]})
    return {"updated": updated, "skipped": skipped, "failed": failed}
