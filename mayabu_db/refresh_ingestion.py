from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from mayabu_common import canonical_platform, normalise_title
from mayabu_db.repository import add_anomaly, invalidate_price_caches, observation_hash, refresh_daily_listing_price, refresh_daily_product_price, url_hash
from mayabu_refresh.common import validate_platform_url
from mayabu_refresh.models import RefreshResult


@dataclass(slots=True)
class RefreshIngestStats:
    input: int = 1
    valid: int = 0
    invalid: int = 0
    observations_added: int = 0
    listings_updated: int = 0
    anomaly_count: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "valid": self.valid,
            "invalid": self.invalid,
            "observations_added": self.observations_added,
            "listings_updated": self.listings_updated,
            "anomaly_count": self.anomaly_count,
            "errors": self.errors[:20],
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _db_stock_status(stock_status: str | None) -> str:
    value = (stock_status or "unknown").strip().lower()
    if value in {"in_stock", "out_of_stock", "unknown", "unavailable"}:
        return value
    if value == "coming_soon":
        return "unavailable"
    return "unknown"




def find_listing_for_refresh(conn: Connection, task: dict[str, Any]) -> dict[str, Any] | None:
    """Find the platform listing targeted by a refresh task.

    Supported task shapes:
    - metadata.platform_listing_id: platform_listings.id UUID
    - metadata.listing_id: public listing_id text
    - task.url: listing_url
    - task.native_id: platform native id
    """
    platform = canonical_platform(task.get("platform") or "")
    metadata = task.get("metadata") or {}
    with conn.cursor() as cur:
        if metadata.get("platform_listing_id"):
            cur.execute("select * from platform_listings where id = %s", (metadata["platform_listing_id"],))
            row = cur.fetchone()
            if row:
                return row
        if metadata.get("listing_id"):
            cur.execute("select * from platform_listings where listing_id = %s", (metadata["listing_id"],))
            row = cur.fetchone()
            if row:
                return row
        if task.get("url"):
            cur.execute(
                "select * from platform_listings where platform = %s and listing_url_hash = %s order by updated_at desc limit 1",
                (platform, url_hash(task["url"])),
            )
            row = cur.fetchone()
            if row:
                return row
        if task.get("native_id"):
            cur.execute(
                "select * from platform_listings where platform = %s and native_id = %s order by updated_at desc limit 1",
                (platform, task["native_id"]),
            )
            row = cur.fetchone()
            if row:
                return row
    return None


def validate_refresh_result(
    listing: dict[str, Any],
    result: RefreshResult,
    *,
    allow_out_of_stock_without_price: bool = False,
) -> tuple[bool, list[dict[str, Any]]]:
    flags: list[dict[str, Any]] = []
    platform = canonical_platform(listing.get("platform") or "")
    url = listing.get("listing_url") or ""

    if not validate_platform_url(platform, url):
        flags.append({"code": "invalid_platform_url", "severity": "high", "message": "Listing URL does not match expected platform domain", "evidence": {"platform": platform, "url": url}})

    if result.page_status in {"blocked", "captcha"}:
        flags.append({"code": "blocked_or_captcha", "severity": "critical", "message": "Refresh page appears blocked or captcha protected", "evidence": {"page_status": result.page_status}})
        return False, flags

    # v4.3 refresh scrapers are price-only. Title is maintained by discovery/enrichment
    # and is not required for a valid price refresh.
    price = result.current_price
    out_of_stock_without_price = allow_out_of_stock_without_price and result.stock_status == "out_of_stock" and price is None
    if price is None and not out_of_stock_without_price:
        flags.append({"code": "missing_price", "severity": "high", "message": "Refresh result has no current price", "evidence": {"raw_price_text": result.raw_price_text}})
    elif price is not None and (listing.get("category") == "laptop" or (listing.get("category") or "unknown") == "unknown"):
        if price < 5000:
            flags.append({"code": "price_too_low", "severity": "high", "message": "Refresh price is suspiciously low for a laptop", "evidence": {"price": price}})
        if price > 600000:
            flags.append({"code": "price_too_high", "severity": "medium", "message": "Refresh price is suspiciously high for a laptop", "evidence": {"price": price}})

    if result.mrp is not None and price is not None and result.mrp < price:
        flags.append({"code": "mrp_below_price", "severity": "medium", "message": "MRP is lower than current price", "evidence": {"price": price, "mrp": result.mrp}})

    old_price = listing.get("current_price")
    try:
        old = float(old_price) if old_price is not None else None
    except Exception:
        old = None
    if old and price and price < old * 0.30:
        flags.append({"code": "suspicious_price_drop", "severity": "high", "message": "Refresh price dropped by more than 70 percent", "evidence": {"old_price": float(old), "new_price": price}})

    fatal_codes = {"invalid_platform_url", "missing_price", "price_too_low", "suspicious_price_drop"}
    ok = not any(flag["code"] in fatal_codes or flag["severity"] == "critical" for flag in flags)
    return ok, flags


def apply_refresh_result(
    conn: Connection,
    listing: dict[str, Any],
    result: RefreshResult,
    run_id: str | None,
    *,
    update_stock: bool = False,
) -> RefreshIngestStats:
    stats = RefreshIngestStats()
    ok, flags = validate_refresh_result(
        listing, result, allow_out_of_stock_without_price=update_stock
    )
    platform = canonical_platform(listing.get("platform") or "")
    listing_uuid = str(listing["id"])
    product_id = str(listing["product_id"]) if listing.get("product_id") else None

    for flag in flags:
        if flag.get("severity") in {"medium", "high", "critical"}:
            add_anomaly(
                conn,
                flag.get("severity", "medium"),
                flag.get("code", "refresh_quality_flag"),
                flag.get("message", "Refresh quality issue"),
                platform=platform,
                product_id=product_id,
                listing_id=listing_uuid,
                run_id=run_id,
                evidence=flag.get("evidence") or {},
            )
            stats.anomaly_count += 1

    if not ok:
        stats.invalid += 1
        with conn.cursor() as cur:
            cur.execute(
                """
                update platform_listings
                set last_seen_at = now(),
                    last_refresh_error = %s,
                    quality_flags = %s,
                    updated_at = now()
                where id = %s
                """,
                ("; ".join(flag["code"] for flag in flags)[:2000], Jsonb(flags), listing_uuid),
            )
        stats.errors.append("refresh_result_failed_validation")
        return stats

    observed_at = _utc_now()
    # Scheduled refresh keeps the existing stock value. Explicit live verification
    # may update it only when the verifier obtained a meaningful status.
    detected_stock = _db_stock_status(result.stock_status)
    stock_status = detected_stock if update_stock and detected_stock != "unknown" else _db_stock_status(listing.get("stock_status"))
    observed_price = result.current_price if result.current_price is not None else listing.get("current_price")
    observed_mrp = result.mrp if result.mrp is not None else listing.get("current_mrp")
    title = listing.get("title") or result.title or ""
    discount = result.discount_percent
    if discount is None and result.current_price and result.mrp and result.mrp > result.current_price:
        discount = round(((result.mrp - result.current_price) / result.mrp) * 100, 2)

    with conn.cursor() as cur:
        cur.execute(
            """
            select price from price_observations
            where listing_id = %s and price is not null
            order by observed_at desc
            limit 1
            """,
            (listing_uuid,),
        )
        prev = cur.fetchone()
        event_type = "initial"
        previous_stock = _db_stock_status(listing.get("stock_status"))
        if stock_status == "out_of_stock" and previous_stock != "out_of_stock":
            event_type = "out_of_stock"
        elif stock_status == "in_stock" and previous_stock == "out_of_stock":
            event_type = "back_in_stock"
        elif prev and result.current_price is not None:
            previous = prev.get("price")
            if previous is not None and result.current_price < previous:
                event_type = "drop"
            elif previous is not None and result.current_price > previous:
                event_type = "rise"
            elif previous is not None:
                event_type = "unchanged"

        cur.execute(
            """
            update platform_listings
            set title = %s,
                title_norm = %s,
                current_price = coalesce(%s, current_price),
                current_mrp = coalesce(%s, current_mrp),
                current_effective_price = current_effective_price,
                current_discount_pct = %s,
                currency = %s,
                stock_status = %s,
                last_seen_at = %s,
                last_successful_refresh_at = %s,
                last_refresh_error = null,
                quality_flags = %s,
                last_price_change_at = case
                  when %s is not null and current_price is distinct from %s then %s
                  else last_price_change_at end,
                updated_at = now()
            where id = %s
            """,
            (
                title,
                normalise_title(title),
                observed_price,
                observed_mrp,
                discount,
                result.currency or listing.get("currency") or "INR",
                stock_status,
                observed_at,
                observed_at,
                Jsonb(flags),
                result.current_price,
                result.current_price,
                observed_at,
                listing_uuid,
            ),
        )
        stats.listings_updated += 1

        ohash = observation_hash(listing_uuid, observed_at, observed_price, observed_mrp)
        cur.execute(
            """
            insert into price_observations(
              observation_hash, listing_id, product_id, platform, observed_at,
              price, mrp, discount_pct, currency, effective_price, raw_price_text, raw_mrp_text,
              validation_status, stock_status, source_run_id, event_type, quality_flags
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (observation_hash) do nothing
            """,
            (
                ohash,
                listing_uuid,
                product_id,
                platform,
                observed_at,
                observed_price,
                observed_mrp,
                discount,
                result.currency or listing.get("currency") or "INR",
                None,
                None,
                None,
                "valid",
                stock_status,
                run_id,
                event_type,
                Jsonb(flags),
            ),
        )
        inserted = cur.rowcount == 1
        if inserted:
            stats.observations_added += 1
            cur.execute("update platform_listings set observation_count = observation_count + 1 where id = %s", (listing_uuid,))

    if stats.observations_added:
        refresh_daily_listing_price(conn, listing_uuid, date_expr=observed_at)
        if product_id:
            refresh_daily_product_price(conn, product_id, date_expr=observed_at)
        invalidate_price_caches(product_id, category=listing.get("category"), event_type=event_type)
    stats.valid += 1
    return stats
