"""Safe rematch of fragmented same-identity products onto the strongest cluster.

Used after targeted discovery creates parallel one-store clones that share
family + storage (or model codes) across retailers.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mayabu.db.connection import db_connection
from mayabu.domain.matching import assess_product_match
from mayabu.search.index_manager import refresh_product_search_documents

logger = logging.getLogger(__name__)


def _product_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_id": str(row["id"]),
        "id": str(row["id"]),
        "category": row.get("category"),
        "canonical_title": row.get("canonical_title"),
        "title_norm": row.get("title_norm"),
        "brand": row.get("brand"),
        "specs": row.get("specs") if isinstance(row.get("specs"), dict) else {},
    }


def consolidate_same_identity(
    *, category: str = "smartphone", limit: int = 80
) -> dict[str, int]:
    """Attach listings from weaker single-store clones onto stronger canonicals.

    Smartphones/audio: brand + family + storage.
    Televisions/appliances/cameras: brand + primary model code + size/capacity when present.
    Only moves when assess_product_match allows exact merge. Never deletes clusters.
    """
    moved = 0
    considered = 0
    blocked = 0
    affected: set[str] = set()

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select pc.id, pc.category, pc.brand, pc.canonical_title, pc.title_norm, pc.specs,
                       coalesce(pc.specs->>'family','') as family,
                       coalesce(pc.specs->>'storage_gb','') as storage,
                       coalesce(pc.specs->>'screen_size_inch','') as screen_size,
                       coalesce(pc.specs->>'capacity_l','') as capacity_l,
                       coalesce(pc.specs->>'capacity_kg','') as capacity_kg,
                       coalesce(pc.specs->'model_codes'->>0, '') as model0,
                       (
                         select count(distinct pl.platform)
                         from platform_listings pl
                         where pl.product_id = pc.id and pl.match_status = 'matched'
                       ) as stores,
                       (
                         select count(*)
                         from platform_listings pl
                         where pl.product_id = pc.id and pl.match_status = 'matched'
                       ) as listing_n
                from product_clusters pc
                where pc.category = %s
                """,
                (category,),
            )
            rows = [dict(r) for r in cur.fetchall()]

        groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for row in rows:
            brand = str(row.get("brand") or "").lower()
            if category == "smartphone":
                family = str(row.get("family") or "")
                storage = str(row.get("storage") or "")
                if not family or not storage:
                    continue
                key: tuple[str, ...] = (brand, family, storage)
            elif category == "television":
                from mayabu.catalog.tv_aliases import primary_tv_model_key

                specs = row.get("specs") if isinstance(row.get("specs"), dict) else {}
                codes = specs.get("model_codes") if isinstance(specs.get("model_codes"), list) else []
                model = primary_tv_model_key(codes) or str(row.get("model0") or "").upper()
                size = str(row.get("screen_size") or "")
                if not model or len(model) < 3 or not size:
                    continue
                key = (brand, model, size)
            elif category in {"tws", "headphones"}:
                family = str(row.get("family") or "").lower().replace("-", "").replace(" ", "_")
                if family:
                    key = (brand, family, "")
                else:
                    model = str(row.get("model0") or "").upper()
                    if model and len(model) >= 4:
                        key = (brand, model, "")
                    else:
                        continue
            else:
                model = str(row.get("model0") or "").upper()
                if not model or len(model) < 4:
                    continue
                key = (brand, model, str(row.get("capacity_l") or row.get("capacity_kg") or ""))
            groups.setdefault(key, []).append(row)

        for _key, members in groups.items():
            if len(members) < 2:
                continue
            members = sorted(
                members,
                key=lambda r: (int(r.get("stores") or 0), int(r.get("listing_n") or 0)),
                reverse=True,
            )
            destination = members[0]
            dest_dict = _product_dict(destination)
            for source in members[1:]:
                if considered >= limit:
                    break
                considered += 1
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select id, platform, title, title_norm, category, specs, listing_id,
                               current_price, listing_url, image_url, match_status
                        from platform_listings
                        where product_id = %s::uuid
                          and match_status = 'matched'
                        """,
                        (str(source["id"]),),
                    )
                    listings = [dict(r) for r in cur.fetchall()]
                for listing in listings:
                    listing_payload = {
                        "title": listing.get("title"),
                        "title_norm": listing.get("title_norm"),
                        "category": listing.get("category") or category,
                        "specs": listing.get("specs")
                        if isinstance(listing.get("specs"), dict)
                        else {},
                    }
                    assessment = assess_product_match(listing_payload, dest_dict)
                    if not assessment.merge_allowed:
                        blocked += 1
                        continue
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            update platform_listings
                            set product_id = %s::uuid,
                                match_status = 'matched',
                                match_method = 'consolidate_same_identity',
                                match_evidence = coalesce(match_evidence, '{}'::jsonb)
                                  || %s::jsonb,
                                updated_at = now()
                            where id = %s::uuid
                              and product_id = %s::uuid
                            """,
                            (
                                str(destination["id"]),
                                json.dumps(
                                    {
                                        "from_product_id": str(source["id"]),
                                        "relation": assessment.relation,
                                        "reason": "same_identity_key",
                                    }
                                ),
                                str(listing["id"]),
                                str(source["id"]),
                            ),
                        )
                        if cur.rowcount:
                            moved += 1
                            affected.add(str(destination["id"]))
                            affected.add(str(source["id"]))
            if considered >= limit:
                break
        conn.commit()

    if affected:
        try:
            refresh_product_search_documents(list(affected), strict=False)
        except Exception:
            logger.exception("consolidate_reindex_failed")

    return {
        "groups_considered": considered,
        "listings_moved": moved,
        "blocked": blocked,
        "products_touched": len(affected),
    }


__all__ = ["consolidate_same_identity"]
