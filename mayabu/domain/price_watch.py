"""Price Watch foundation on top of wishlist.

Stores target_price / notify_on_drop. Does not send email — Resend delivery
is blocked until staging proof.

Evaluation + durable events live in mayabu.domain.watch_events.
"""

from __future__ import annotations

from typing import Any

from mayabu.db.connection import db_connection
from mayabu.domain.watch_events import evaluate_watches as evaluate_watches

__all__ = ["evaluate_watches", "update_watch"]


def update_watch(
    user_id: str,
    product_id: str,
    *,
    target_price: float | None,
    notify_on_drop: bool,
) -> dict[str, Any] | None:
    """Upsert watch settings onto wishlist.

    Creates the wishlist row when missing (same availability gate as wishlist_add),
    then sets target_price / notify_on_drop. Returns None when the product cannot
    be saved.
    """
    if target_price is not None:
        if target_price <= 0 or target_price > 10_000_000:
            raise ValueError("target_price_out_of_range")

    from mayabu.auth.repository import _public_product_ok

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update user_wishlist
                set target_price = %s,
                    notify_on_drop = %s,
                    updated_at = now()
                where user_id = %s and product_id = %s
                returning product_id, target_price, notify_on_drop, last_notified_at
                """,
                (target_price, notify_on_drop, user_id, product_id),
            )
            row = cur.fetchone()
            if row:
                return dict(row)

            cur.execute(
                "select id, category, status from product_clusters where id = %s",
                (product_id,),
            )
            product = cur.fetchone()
            if not product or not _public_product_ok(product.get("category"), product.get("status")):
                return None

            cur.execute(
                """
                insert into user_wishlist(user_id, product_id, target_price, notify_on_drop)
                values (%s, %s, %s, %s)
                on conflict (user_id, product_id) do update
                set target_price = excluded.target_price,
                    notify_on_drop = excluded.notify_on_drop,
                    updated_at = now()
                returning product_id, target_price, notify_on_drop, last_notified_at
                """,
                (user_id, product_id, target_price, notify_on_drop),
            )
            row = cur.fetchone()
            return dict(row) if row else None
