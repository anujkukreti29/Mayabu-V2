from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from psycopg import Connection

from mayabu_common import canonical_platform, normalize_raw_listing
from mayabu_db.matching import choose_match
from mayabu_db.quality import fatal_listing_flags, validate_listing
from mayabu_db.repository import (
    add_anomaly,
    add_review_item,
    create_product,
    get_listing_by_public_id,
    insert_price_observation,
    insert_raw_item,
    list_candidate_products,
    merge_product_specs,
    refresh_daily_listing_price,
    refresh_daily_product_price,
    upsert_platform_listing,
)
from mayabu_db.variant import build_variant_key


@dataclass(slots=True)
class IngestStats:
    input: int = 0
    valid: int = 0
    invalid: int = 0
    skipped: int = 0
    products_created: int = 0
    products_matched: int = 0
    listings_created: int = 0
    listings_updated: int = 0
    observations_added: int = 0
    review_items: int = 0
    anomaly_count: int = 0
    errors: list[str] = field(default_factory=list)
    affected_product_ids: set[str] = field(default_factory=set, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "valid": self.valid,
            "invalid": self.invalid,
            "skipped": self.skipped,
            "products_created": self.products_created,
            "products_matched": self.products_matched,
            "listings_created": self.listings_created,
            "listings_updated": self.listings_updated,
            "observations_added": self.observations_added,
            "review_items": self.review_items,
            "anomaly_count": self.anomaly_count,
            "errors": self.errors[:20],
            "affected_products": len(self.affected_product_ids),
        }


def _merge_stats(total: IngestStats, stats: IngestStats) -> None:
    total.input += stats.input
    total.valid += stats.valid
    total.invalid += stats.invalid
    total.skipped += stats.skipped
    total.products_created += stats.products_created
    total.products_matched += stats.products_matched
    total.listings_created += stats.listings_created
    total.listings_updated += stats.listings_updated
    total.observations_added += stats.observations_added
    total.review_items += stats.review_items
    total.anomaly_count += stats.anomaly_count
    total.errors.extend(stats.errors)
    total.affected_product_ids.update(stats.affected_product_ids)


def _safe_raw_evidence(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_title": raw.get("title"),
        "raw_listing_id": raw.get("listing_id"),
        "raw_native_id": raw.get("native_id"),
        "raw_product_id": raw.get("productId"),
        "raw_url": raw.get("link") or raw.get("url") or raw.get("product_url"),
        "raw_price": raw.get("price") or raw.get("currentPrice"),
        "raw_mrp": raw.get("mrp") or raw.get("maxRetailPrice"),
        "raw_discount": raw.get("discount") or raw.get("discount_pct"),
    }


def ingest_listing(
    conn: Connection,
    raw: dict[str, Any],
    platform_hint: str,
    query: str | None,
    run_id: str | None = None,
    task_id: str | None = None,
    observed_at: str | None = None,
) -> tuple[bool, IngestStats]:
    """
    Ingest one normalized listing inside an active transaction.

    Important:
    Do not catch SQL exceptions here. If a DB insert/update fails, the outer
    ingest_records() transaction must roll it back first. Otherwise PostgreSQL
    keeps the transaction in an aborted state and hides the real error behind:
    "current transaction is aborted".
    """
    stats = IngestStats(input=1)
    platform = canonical_platform(platform_hint)

    listing = normalize_raw_listing(
        raw,
        platform_hint=platform,
        query=query or raw.get("query") or "",
        observed_at=observed_at,
    )

    if not listing:
        stats.invalid += 1

        insert_raw_item(
            conn,
            run_id,
            task_id,
            platform,
            query,
            raw,
            None,
            parse_status="invalid",
            parse_error="normalize_raw_listing returned None",
        )

        add_anomaly(
            conn,
            "medium",
            "invalid_raw_listing",
            "Raw listing could not be normalized",
            platform=platform,
            run_id=run_id,
            evidence=_safe_raw_evidence(raw),
        )
        stats.anomaly_count += 1
        return False, stats

    flags = validate_listing(listing)

    insert_raw_item(
        conn,
        run_id,
        task_id,
        platform,
        query,
        raw,
        listing.get("listing_id"),
        parse_status="valid",
        parse_error=None,
    )

    fatal = fatal_listing_flags(flags)
    if fatal:
        stats.invalid += 1

        add_anomaly(
            conn,
            "high",
            "fatal_listing_quality",
            "Listing failed fatal quality checks",
            platform=platform,
            run_id=run_id,
            evidence={
                "flags": fatal,
                "title": listing.get("title"),
                "listing_id": listing.get("listing_id"),
                "url": listing.get("url"),
            },
        )
        stats.anomaly_count += 1
        return False, stats

    stats.valid += 1

    existing = get_listing_by_public_id(conn, listing["listing_id"])
    product_id: str | None = (
        str(existing["product_id"])
        if existing and existing.get("product_id")
        else None
    )

    confidence = 1000.0 if product_id else 0.0
    method = "listing_id_exact" if product_id else "new_product"
    evidence: dict[str, Any] = {"listing_id": listing["listing_id"]} if product_id else {}
    needs_review = False

    if not product_id:
        candidates = list_candidate_products(conn, listing)
        product_id, confidence, method, evidence, needs_review = choose_match(
            listing,
            candidates,
        )

        if product_id and not needs_review:
            stats.products_matched += 1

        elif product_id and needs_review:
            # Keep listing unmerged until review approves. This protects trust.
            method = "needs_manual_review"

        else:
            variant_key = build_variant_key(
                listing.get("specs") or {},
                listing.get("title_norm"),
            )
            product_id = create_product(conn, listing, variant_key)
            stats.products_created += 1
            confidence = 0.0
            method = "new_product"
            evidence = {"variant_key": variant_key} if variant_key else {}

    listing_product_id = product_id if method != "needs_manual_review" else None

    listing_uuid, created = upsert_platform_listing(
        conn,
        listing,
        listing_product_id,
        confidence,
        method,
        evidence,
        flags,
    )

    if created:
        stats.listings_created += 1
    else:
        stats.listings_updated += 1

    if method == "needs_manual_review" and product_id:
        add_review_item(conn, listing_uuid, product_id, confidence, evidence)
        stats.review_items += 1

    elif listing_product_id:
        merge_product_specs(conn, listing_product_id, listing)

    if insert_price_observation(
        conn,
        listing_uuid,
        listing["listing_id"],
        listing_product_id,
        listing,
        run_id,
        flags,
    ):
        stats.observations_added += 1

        refresh_daily_listing_price(
            conn,
            listing_uuid,
            date_expr=listing.get("scraped_at"),
        )

        if listing_product_id:
            refresh_daily_product_price(
                conn,
                listing_product_id,
                date_expr=listing.get("scraped_at"),
            )

    if listing_product_id:
        stats.affected_product_ids.add(str(listing_product_id))

    for flag in flags:
        if flag.get("severity") in {"medium", "high", "critical"}:
            add_anomaly(
                conn,
                flag.get("severity", "medium"),
                flag.get("code", "quality_flag"),
                flag.get("message", "Quality issue"),
                platform=platform,
                product_id=listing_product_id,
                listing_id=listing_uuid,
                run_id=run_id,
                evidence=flag.get("evidence") or {},
            )
            stats.anomaly_count += 1

    return True, stats


def ingest_records(
    conn: Connection,
    records: list[dict[str, Any]],
    platform_hint: str,
    query: str | None,
    run_id: str | None = None,
    task_id: str | None = None,
    observed_at: str | None = None,
) -> IngestStats:
    """
    Ingest a batch safely.

    Each listing gets its own transaction. If one listing fails, that listing is
    rolled back, the real error is captured, and the remaining listings continue.
    """
    total = IngestStats()
    platform = canonical_platform(platform_hint)

    for raw in records:
        try:
            with conn.transaction():
                _, stats = ingest_listing(
                    conn,
                    raw,
                    platform,
                    query,
                    run_id=run_id,
                    task_id=task_id,
                    observed_at=observed_at,
                )

        except Exception as exc:
            real_error = repr(exc)
            stats = IngestStats(input=1, invalid=1, errors=[real_error])

            # Make sure the failed record transaction is cleared before trying
            # to write the anomaly. This avoids "current transaction is aborted".
            try:
                conn.rollback()
            except Exception:
                pass

            try:
                with conn.transaction():
                    add_anomaly(
                        conn,
                        "high",
                        "ingestion_record_rolled_back",
                        "One raw listing was rolled back without aborting the batch",
                        platform=platform,
                        run_id=run_id,
                        evidence={
                            "error": real_error,
                            **_safe_raw_evidence(raw),
                        },
                    )
                    stats.anomaly_count += 1

            except Exception as anomaly_exc:
                try:
                    conn.rollback()
                except Exception:
                    pass

                stats.errors.append(
                    f"failed_to_write_anomaly: {repr(anomaly_exc)}"
                )

        _merge_stats(total, stats)

    return total