"""Incremental search-document maintenance for Mayabu v5."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from typing import Any

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection

logger = logging.getLogger(__name__)


def mark_product_dirty(product_id: str, reason: str = "application_update") -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select mark_search_document_dirty(%s, %s)", (product_id, reason))


def refresh_product_search_documents(product_ids: Iterable[str], *, strict: bool = False) -> dict[str, int]:
    """Refresh a batch with one pool checkout and per-product transactions.

    Per-product transaction boundaries retain fault isolation without paying for
    hundreds of connection acquisitions during backfills.
    """
    refreshed = failed = 0
    unique_ids = list(dict.fromkeys(str(x) for x in product_ids if x))
    if not unique_ids:
        return {"refreshed": 0, "failed": 0}

    with db_connection() as conn:
        for product_id in unique_ids:
            try:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute("select refresh_product_search_document(%s)", (product_id,))
                refreshed += 1
            except Exception as exc:
                failed += 1
                logger.warning("search_document_refresh_failed", extra={"product_id": product_id, "error": str(exc)[:500]})
                try:
                    with conn.transaction():
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                update search_document_dirty
                                set attempts = attempts + 1, last_error = %s,
                                    claimed_at = null, claimed_by = null
                                where product_id = %s
                                """,
                                (str(exc)[:2000], product_id),
                            )
                except Exception:
                    logger.exception("search_document_failure_state_update_failed", extra={"product_id": product_id})
                if strict:
                    raise
    return {"refreshed": refreshed, "failed": failed}


def drain_dirty_search_documents(limit: int | None = None, *, strict: bool = False) -> dict[str, int]:
    batch = max(1, min(limit or get_app_settings().search_document_batch_size, 5000))
    claim_id = f"index-{uuid.uuid4().hex}"
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with candidates as (
                  select product_id
                  from search_document_dirty
                  where claimed_at is null or claimed_at < now() - interval '10 minutes'
                  order by dirty_at asc
                  limit %s
                  for update skip locked
                )
                update search_document_dirty d
                set claimed_at = now(), claimed_by = %s
                from candidates c
                where d.product_id = c.product_id
                returning d.product_id
                """,
                (batch, claim_id),
            )
            product_ids = [str(row["product_id"]) for row in cur.fetchall()]
    result = refresh_product_search_documents(product_ids, strict=strict)
    return {"selected": len(product_ids), **result}


def refresh_recent_search_documents(since_iso: str, limit: int = 2000) -> dict[str, int]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id from product_clusters
                where updated_at >= %s::timestamptz
                order by updated_at asc
                limit %s
                """,
                (since_iso, max(1, min(limit, 10000))),
            )
            ids = [str(row["id"]) for row in cur.fetchall()]
    return {"selected": len(ids), **refresh_product_search_documents(ids)}


def backfill_product_search_documents(batch_size: int = 500) -> dict[str, int]:
    total = selected = failed = 0
    while True:
        result = drain_dirty_search_documents(limit=batch_size)
        selected += result["selected"]
        total += result["refreshed"]
        failed += result["failed"]
        if result["selected"] == 0 or result["selected"] < batch_size:
            break
        if result["failed"] == result["selected"]:
            break
    return {"selected": selected, "refreshed": total, "failed": failed}


def refresh_product_search_index(*, strict: bool = False) -> bool:
    """Compatibility wrapper.

    v5 drains the incremental dirty queue. On pre-v5 databases it falls back to
    the legacy materialized-view refresh function.
    """
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select to_regclass('public.product_search_documents') as docs")
                docs = bool((cur.fetchone() or {}).get("docs"))
        if docs:
            backfill_product_search_documents()
        else:
            with db_connection(autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("select refresh_product_search_index_safe()")
        return True
    except Exception as exc:
        logger.warning("search_index_refresh_failed", extra={"error": str(exc)[:500]})
        if strict:
            raise
        return False


def get_search_index_stats() -> dict[str, Any]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  to_regclass('public.product_search_documents') is not null as documents_exist,
                  to_regclass('public.product_search_index') is not null as legacy_index_exists,
                  (select count(*) from product_clusters where status = 'active') as active_products,
                  case when to_regclass('public.product_search_documents') is null then null
                       else (select count(*) from product_search_documents) end as indexed_products,
                  case when to_regclass('public.search_document_dirty') is null then null
                       else (select count(*) from search_document_dirty) end as dirty_products,
                  case when to_regclass('public.product_search_documents') is null then null
                       else (select max(indexed_at) from product_search_documents) end as newest_indexed_at,
                  case when to_regclass('public.product_search_documents') is null then null
                       else (select count(*) from product_search_documents where platform_count >= 2) end as multi_platform_products
                """
            )
            return dict(cur.fetchone() or {})
