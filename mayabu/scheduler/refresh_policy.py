"""Refresh policy for known platform listings.

HOT / NORMAL / COLD cadences come from AppSettings. Priority signals use
aggregate wishlist counts and product_activity_hourly — never individual
browsing history.
"""

from __future__ import annotations

from typing import Any

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection

TIER_PRIORITY = {"hot": 40, "normal": 80, "cold": 120}

_DUE_TAIL = """
                select *
                from (
                  select
                    ranked.*,
                    case ranked.refresh_tier
                      when 'hot' then %s
                      when 'cold' then %s
                      else %s
                    end as due_interval_minutes,
                    row_number() over (
                      partition by ranked.platform
                      order by
                        case ranked.refresh_tier
                          when 'hot' then 0
                          when 'normal' then 1
                          else 2
                        end,
                        ranked.last_successful_refresh_at asc nulls first,
                        ranked.updated_at asc
                    ) as platform_rank
                  from ranked
                ) due
                where due.last_successful_refresh_at is null
                   or due.last_successful_refresh_at
                      < now() - (due.due_interval_minutes * interval '1 minute')
                order by due.platform_rank asc,
                         case due.refresh_tier
                           when 'hot' then 0
                           when 'normal' then 1
                           else 2
                         end,
                         due.last_successful_refresh_at asc nulls first
                limit %s
"""

_DUE_FULL = """
                with activity as (
                  select product_id, sum(event_count)::int as event_count
                  from product_activity_hourly
                  where hour_bucket >= now() - interval '7 days'
                  group by product_id
                ),
                wishlist as (
                  select
                    product_id,
                    count(*)::int as wishlist_count,
                    count(*) filter (
                      where target_price is not null or notify_on_drop = true
                    )::int as watch_intent_count
                  from user_wishlist
                  group by product_id
                ),
                ranked as (
                  select
                    l.*,
                    coalesce(w.wishlist_count, 0) as wishlist_count,
                    coalesce(w.watch_intent_count, 0) as watch_intent_count,
                    coalesce(a.event_count, 0) as activity_7d,
                    case
                      -- Explicit Price Watch (target / notify) outranks bare wishlist.
                      when coalesce(w.watch_intent_count, 0) >= 1
                        or coalesce(a.event_count, 0) >= 3
                        or l.last_price_change_at >= now() - interval '7 days'
                      then 'hot'
                      when coalesce(w.wishlist_count, 0) >= 1
                      then 'normal'
                      when coalesce(w.wishlist_count, 0) = 0
                        and coalesce(a.event_count, 0) = 0
                        and (
                          l.last_price_change_at is null
                          or l.last_price_change_at < now() - interval '30 days'
                        )
                      then 'cold'
                      else 'normal'
                    end as refresh_tier
                  from platform_listings l
                  left join platform_health ph on ph.platform = l.platform
                  left join activity a on a.product_id = l.product_id
                  left join wishlist w on w.product_id = l.product_id
                  where (%s::text is null or l.platform = %s)
                    and coalesce(ph.status, 'healthy') <> 'paused'
                    and not (
                      coalesce(ph.status, 'healthy') = 'blocked'
                      and ph.circuit_open_until is null
                    )
                    and (ph.circuit_open_until is null or ph.circuit_open_until < now())
                    and l.listing_url is not null
                    -- Unmatched / needs_review stay on the refresh roster so listing
                    -- evidence can be rematched. They never become public prices.
                    and l.match_status in ('matched','unmatched','needs_review')
                    -- Same-retailer URL aliases refresh via primary only.
                    and coalesce(l.match_evidence->>'listing_role', 'primary') <> 'alias'
                    and not exists (
                      select 1 from scrape_tasks t
                      where t.status in ('pending','running')
                        and t.task_type in ('refresh_listing','verify_listing')
                        and (
                          t.metadata->>'platform_listing_id' = l.id::text
                          or t.url = l.listing_url
                        )
                    )
                )
""" + _DUE_TAIL

_DUE_BASIC = """
                with ranked as (
                  select
                    l.*,
                    0 as wishlist_count,
                    0 as activity_7d,
                    case
                      when l.last_price_change_at >= now() - interval '7 days'
                      then 'hot'
                      when l.last_price_change_at is null
                        or l.last_price_change_at < now() - interval '30 days'
                      then 'cold'
                      else 'normal'
                    end as refresh_tier
                  from platform_listings l
                  left join platform_health ph on ph.platform = l.platform
                  where (%s::text is null or l.platform = %s)
                    and coalesce(ph.status, 'healthy') <> 'paused'
                    and not (
                      coalesce(ph.status, 'healthy') = 'blocked'
                      and ph.circuit_open_until is null
                    )
                    and (ph.circuit_open_until is null or ph.circuit_open_until < now())
                    and l.listing_url is not null
                    and l.match_status in ('matched','unmatched','needs_review')
                    and coalesce(l.match_evidence->>'listing_role', 'primary') <> 'alias'
                    and not exists (
                      select 1 from scrape_tasks t
                      where t.status in ('pending','running')
                        and t.task_type in ('refresh_listing','verify_listing')
                        and (
                          t.metadata->>'platform_listing_id' = l.id::text
                          or t.url = l.listing_url
                        )
                    )
                )
""" + _DUE_TAIL


def due_refresh_candidates(limit: int = 100, platform: str | None = None) -> list[dict[str, Any]]:
    settings = get_app_settings()
    hot = max(30, int(settings.refresh_hot_minutes))
    normal = max(hot, int(settings.refresh_normal_minutes))
    cold = max(normal, int(settings.refresh_cold_minutes))
    fetch_limit = max(1, min(int(limit), 500))
    params = (platform, platform, hot, cold, normal, fetch_limit)
    with db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(_DUE_FULL, params)
            except Exception:
                conn.rollback()
                cur.execute(_DUE_BASIC, params)
            return [dict(row) for row in cur.fetchall()]


def refresh_task_priority(row: dict[str, Any]) -> int:
    tier = str(row.get("refresh_tier") or "normal")
    return TIER_PRIORITY.get(tier, TIER_PRIORITY["normal"])
