"""Watchlist event engine — durable, idempotent user-facing watch events.

Events are derived from authoritative price/stock observations only.
Delivery (email/push) remains deferred; events surface on the Watchlist Dashboard.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from psycopg import Connection
from psycopg.errors import UndefinedTable
from psycopg.types.json import Jsonb

from mayabu.db.connection import db_connection

logger = logging.getLogger(__name__)

# Meaningful drop: matches homepage price-drop semantics.
DROP_MIN_PERCENT = 2.0
DROP_MIN_AMOUNT = 100.0

# Near tracked low: within 5% above Mayabu tracked minimum (and not already AT low).
NEAR_LOW_PERCENT = 5.0

EVENT_PRICE_DROP = "price_drop"
EVENT_TARGET_REACHED = "target_reached"
EVENT_BACK_IN_STOCK = "back_in_stock"
EVENT_OUT_OF_STOCK = "out_of_stock"
EVENT_NEW_TRACKED_LOW = "new_tracked_low"

WATCH_STATE_PRICE_DROPPED = "PRICE_DROPPED"
WATCH_STATE_AT_TARGET = "AT_TARGET"
WATCH_STATE_NEAR_TRACKED_LOW = "NEAR_TRACKED_LOW"
WATCH_STATE_BACK_IN_STOCK = "BACK_IN_STOCK"
WATCH_STATE_OUT_OF_STOCK = "OUT_OF_STOCK"
WATCH_STATE_NO_CHANGE = "NO_MEANINGFUL_CHANGE"
WATCH_STATE_INSUFFICIENT = "INSUFFICIENT_DATA"


def _fingerprint(
    user_id: str,
    product_id: str,
    event_type: str,
    *,
    price: float | None,
    prior_price: float | None,
    stock: str | None,
) -> str:
    raw = (
        f"{user_id}|{product_id}|{event_type}|"
        f"{price if price is not None else ''}|{prior_price if prior_price is not None else ''}|"
        f"{stock or ''}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_meaningful_drop(previous: float, current: float) -> bool:
    if previous <= 0 or current <= 0 or current >= previous:
        return False
    amount = previous - current
    percent = (amount / previous) * 100.0
    return percent >= DROP_MIN_PERCENT or amount >= DROP_MIN_AMOUNT


def is_purchasable_stock(stock_status: str | None) -> bool:
    return (stock_status or "").strip().lower() == "in_stock"


def insert_watch_event(
    conn: Connection,
    *,
    user_id: str,
    product_id: str,
    event_type: str,
    current_price: float | None,
    previous_price: float | None = None,
    target_price: float | None = None,
    stock_status: str | None = None,
    tracked_low: float | None = None,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Insert one event if fingerprint is new. Returns True when inserted."""
    fp = _fingerprint(
        user_id,
        product_id,
        event_type,
        price=current_price,
        prior_price=previous_price,
        stock=stock_status,
    )
    facts = {
        "current_price": current_price,
        "previous_price": previous_price,
        "target_price": target_price,
        "stock_status": stock_status,
        "tracked_low": tracked_low,
        **(payload or {}),
    }
    with conn.cursor() as cur:
        cur.execute("savepoint watch_event_insert")
        try:
            cur.execute(
                """
                insert into watch_events(
                  user_id, product_id, event_type, fingerprint,
                  current_price, previous_price, target_price, stock_status, payload
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (fingerprint) do nothing
                """,
                (
                    user_id,
                    product_id,
                    event_type,
                    fp,
                    current_price,
                    previous_price,
                    target_price,
                    stock_status,
                    Jsonb(facts),
                ),
            )
            inserted = cur.rowcount == 1
            cur.execute("release savepoint watch_event_insert")
            return inserted
        except UndefinedTable:
            cur.execute("rollback to savepoint watch_event_insert")
            logger.warning("watch_events missing; skipping event insert")
            return False


def evaluate_watches(
    conn: Connection,
    product_id: str,
    current_price: float | None,
    event_type: str,
    *,
    previous_price: float | None = None,
    stock_status: str | None = None,
    purchasable: bool | None = None,
) -> int:
    """Evaluate wishlist watches for a product after an authoritative observation.

    OOS / non-purchasable prices never create target_reached.
    Unchanged prices never create duplicate drop events (fingerprint + last_notified).
    """
    buyable = purchasable if purchasable is not None else is_purchasable_stock(stock_status)
    price = float(current_price) if current_price is not None and current_price > 0 else None

    with conn.cursor() as cur:
        cur.execute("savepoint price_watch_eval")
        try:
            cur.execute(
                """
                select user_id, target_price, notify_on_drop, last_notified_price
                from user_wishlist
                where product_id = %s
                  and (notify_on_drop = true or target_price is not null)
                """,
                (product_id,),
            )
            watches = [dict(r) for r in cur.fetchall()]
        except UndefinedTable:
            cur.execute("rollback to savepoint price_watch_eval")
            logger.warning("user_wishlist missing; skipping watch evaluation")
            return 0
        cur.execute("release savepoint price_watch_eval")

    fired = 0
    for watch in watches:
        user_id = str(watch["user_id"])
        target = watch.get("target_price")
        target_f = float(target) if target is not None else None
        notify_drop = bool(watch.get("notify_on_drop"))
        last_notified = watch.get("last_notified_price")
        last_f = float(last_notified) if last_notified is not None else None

        events: list[tuple[str, float | None, float | None]] = []

        if event_type == "back_in_stock" and buyable:
            events.append((EVENT_BACK_IN_STOCK, price, previous_price))

        if event_type == "out_of_stock":
            events.append((EVENT_OUT_OF_STOCK, price, previous_price))

        if (
            event_type == "drop"
            and price is not None
            and previous_price is not None
            and is_meaningful_drop(previous_price, price)
            and notify_drop
        ):
            events.append((EVENT_PRICE_DROP, price, previous_price))

        if (
            event_type == "new_tracked_low"
            and price is not None
            and buyable
            and previous_price is not None
            and price < previous_price
        ):
            events.append((EVENT_NEW_TRACKED_LOW, price, previous_price))

        # Target reached: requires buyable current public price.
        if (
            target_f is not None
            and price is not None
            and buyable
            and price <= target_f
            and (last_f is None or last_f > target_f or last_f != price)
        ):
            # Only fire when newly at/below target or price changed while still at target
            # after having risen above (last_f > target) or first time.
            if last_f is None or last_f > target_f:
                events.append((EVENT_TARGET_REACHED, price, previous_price))

        for etype, cur_p, prev_p in events:
            if insert_watch_event(
                conn,
                user_id=user_id,
                product_id=product_id,
                event_type=etype,
                current_price=cur_p,
                previous_price=prev_p,
                target_price=target_f,
                stock_status=stock_status,
            ):
                fired += 1
                if cur_p is not None:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            update user_wishlist
                            set last_notified_price = %s,
                                last_notified_at = now(),
                                updated_at = now()
                            where user_id = %s and product_id = %s
                            """,
                            (cur_p, user_id, product_id),
                        )
    return fired


def derive_watch_state(
    *,
    target_price: float | None,
    notify_on_drop: bool,
    current_price: float | None,
    purchasable: bool,
    latest_event_type: str | None,
    tracked_low: float | None = None,
) -> str:
    """Deterministic dashboard state for one wishlist row."""
    if not purchasable:
        if latest_event_type == EVENT_OUT_OF_STOCK:
            return WATCH_STATE_OUT_OF_STOCK
        if current_price is None:
            return WATCH_STATE_INSUFFICIENT
        return WATCH_STATE_OUT_OF_STOCK

    if current_price is None or current_price <= 0:
        return WATCH_STATE_INSUFFICIENT

    if target_price is not None and current_price <= float(target_price):
        return WATCH_STATE_AT_TARGET

    if latest_event_type == EVENT_BACK_IN_STOCK:
        return WATCH_STATE_BACK_IN_STOCK

    if latest_event_type == EVENT_PRICE_DROP:
        return WATCH_STATE_PRICE_DROPPED

    if (
        tracked_low is not None
        and tracked_low > 0
        and current_price > tracked_low
        and current_price <= tracked_low * (1 + NEAR_LOW_PERCENT / 100.0)
    ):
        return WATCH_STATE_NEAR_TRACKED_LOW

    if notify_on_drop or target_price is not None:
        return WATCH_STATE_NO_CHANGE
    return WATCH_STATE_NO_CHANGE


def list_watch_events(
    user_id: str,
    *,
    limit: int = 20,
    unread_only: bool = False,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 50))
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("savepoint watch_events_list")
        try:
            cur.execute(
                """
                select e.id, e.product_id, e.event_type, e.current_price, e.previous_price,
                       e.target_price, e.stock_status, e.payload, e.created_at, e.seen_at,
                       d.canonical_title as title, d.brand, d.category, d.image_url
                from watch_events e
                left join product_search_documents d on d.product_id = e.product_id
                where e.user_id = %s
                  and (%s = false or e.seen_at is null)
                order by e.created_at desc
                limit %s
                """,
                (user_id, unread_only, limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.execute("release savepoint watch_events_list")
            return rows
        except UndefinedTable:
            cur.execute("rollback to savepoint watch_events_list")
            return []


def mark_watch_events_seen(user_id: str, event_ids: list[str] | None = None) -> int:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("savepoint watch_events_seen")
        try:
            if event_ids:
                cur.execute(
                    """
                    update watch_events
                    set seen_at = now()
                    where user_id = %s and id = any(%s::uuid[]) and seen_at is null
                    """,
                    (user_id, event_ids),
                )
            else:
                cur.execute(
                    """
                    update watch_events
                    set seen_at = now()
                    where user_id = %s and seen_at is null
                    """,
                    (user_id,),
                )
            n = int(cur.rowcount or 0)
            cur.execute("release savepoint watch_events_seen")
            return n
        except UndefinedTable:
            cur.execute("rollback to savepoint watch_events_seen")
            return 0


def latest_events_by_product(user_id: str, product_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batched latest event per product for wishlist dashboard (no N+1)."""
    if not product_ids:
        return {}
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("savepoint watch_events_latest")
        try:
            cur.execute(
                """
                select distinct on (product_id)
                       product_id, id, event_type, current_price, previous_price,
                       target_price, stock_status, created_at, seen_at
                from watch_events
                where user_id = %s and product_id = any(%s::uuid[])
                order by product_id, created_at desc
                """,
                (user_id, product_ids),
            )
            rows = {str(r["product_id"]): dict(r) for r in cur.fetchall()}
            cur.execute("release savepoint watch_events_latest")
            return rows
        except UndefinedTable:
            cur.execute("rollback to savepoint watch_events_latest")
            return {}

