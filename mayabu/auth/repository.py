"""PostgreSQL repository for Mayabu accounts, sessions, tokens, and wishlist."""

# ruff: noqa: SIM117

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from mayabu.auth.passwords import hash_password, normalize_email
from mayabu.auth.tokens import generate_token, hash_token
from mayabu.db.connection import db_connection
from mayabu.search.category_registry import get_search_category


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_user(
    *,
    email: str,
    password: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_email(email)
    display = (display_name or "").strip() or None
    if display and len(display) > 80:
        display = display[:80]
    pw_hash = hash_password(password)
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                insert into users(email, normalized_email, password_hash, display_name)
                values (%s, %s, %s, %s)
                returning id, email, normalized_email, display_name, email_verified_at,
                          status, created_at, updated_at, last_login_at
                """,
            (email.strip(), normalized, pw_hash, display),
        )
        row = cur.fetchone()
        assert row is not None
        return dict(row)


def get_user_by_normalized_email(email: str) -> dict[str, Any] | None:
    normalized = normalize_email(email)
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                select id, email, normalized_email, password_hash, display_name,
                       email_verified_at, status, created_at, updated_at, last_login_at
                from users where normalized_email = %s
                """,
            (normalized,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                select id, email, normalized_email, password_hash, display_name,
                       email_verified_at, status, created_at, updated_at, last_login_at
                from users where id = %s
                """,
            (user_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_display_name(user_id: str, display_name: str | None) -> dict[str, Any] | None:
    display = (display_name or "").strip() or None
    if display and len(display) > 80:
        display = display[:80]
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                update users
                set display_name = %s, updated_at = now()
                where id = %s
                returning id, email, normalized_email, display_name, email_verified_at,
                          status, created_at, updated_at, last_login_at
                """,
            (display, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def set_password(user_id: str, password: str) -> None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                update users
                set password_hash = %s, updated_at = now()
                where id = %s
                """,
            (hash_password(password), user_id),
        )


def mark_email_verified(user_id: str) -> None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                update users
                set email_verified_at = coalesce(email_verified_at, now()),
                    updated_at = now()
                where id = %s
                """,
            (user_id,),
        )


def touch_last_login(user_id: str) -> None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "update users set last_login_at = now(), updated_at = now() where id = %s",
            (user_id,),
        )


def create_session(
    user_id: str,
    *,
    lifetime_days: int,
    user_agent: str | None = None,
) -> tuple[str, dict[str, Any]]:
    raw = generate_token(32)
    token_digest = hash_token(raw)
    expires = _utcnow() + timedelta(days=max(1, lifetime_days))
    ua = (user_agent or "")[:240] or None
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                insert into user_sessions(user_id, token_hash, expires_at, user_agent)
                values (%s, %s, %s, %s)
                returning id, user_id, created_at, last_seen_at, expires_at, revoked_at
                """,
            (user_id, token_digest, expires, ua),
        )
        row = cur.fetchone()
        assert row is not None
        return raw, dict(row)


def get_session_by_token(raw_token: str) -> dict[str, Any] | None:
    digest = hash_token(raw_token)
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                select s.id as session_id, s.user_id, s.expires_at, s.revoked_at,
                       s.last_seen_at, u.email, u.normalized_email, u.display_name,
                       u.email_verified_at, u.status, u.created_at, u.updated_at,
                       u.last_login_at
                from user_sessions s
                join users u on u.id = s.user_id
                where s.token_hash = %s
                """,
            (digest,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def touch_session(session_id: str, *, min_interval_seconds: int = 0) -> bool:
    """Update last_seen_at. When min_interval_seconds > 0, skip if recently touched."""
    interval = max(0, int(min_interval_seconds))
    with db_connection() as conn, conn.cursor() as cur:
        if interval <= 0:
            cur.execute(
                """
                    update user_sessions
                    set last_seen_at = now()
                    where id = %s and revoked_at is null and expires_at > now()
                    """,
                (session_id,),
            )
        else:
            cur.execute(
                """
                    update user_sessions
                    set last_seen_at = now()
                    where id = %s
                      and revoked_at is null
                      and expires_at > now()
                      and last_seen_at < now() - (%s * interval '1 second')
                    """,
                (session_id, interval),
            )
        return int(cur.rowcount or 0) > 0


def list_active_sessions(user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    capped = max(1, min(50, int(limit)))
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                select id, created_at, last_seen_at, expires_at, user_agent
                from user_sessions
                where user_id = %s
                  and revoked_at is null
                  and expires_at > now()
                order by last_seen_at desc
                limit %s
                """,
            (user_id, capped),
        )
        return [dict(row) for row in cur.fetchall()]


def revoke_session(session_id: str) -> bool:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                update user_sessions
                set revoked_at = coalesce(revoked_at, now())
                where id = %s and revoked_at is null
                """,
            (session_id,),
        )
        return int(cur.rowcount or 0) > 0


def revoke_session_for_user(user_id: str, session_id: str) -> bool:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                update user_sessions
                set revoked_at = coalesce(revoked_at, now())
                where id = %s and user_id = %s and revoked_at is null
                """,
            (session_id, user_id),
        )
        return int(cur.rowcount or 0) > 0


def revoke_other_sessions(user_id: str, keep_session_id: str) -> int:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                update user_sessions
                set revoked_at = coalesce(revoked_at, now())
                where user_id = %s
                  and id <> %s
                  and revoked_at is null
                """,
            (user_id, keep_session_id),
        )
        return int(cur.rowcount or 0)


def revoke_session_by_token(raw_token: str) -> bool:
    digest = hash_token(raw_token)
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                update user_sessions
                set revoked_at = coalesce(revoked_at, now())
                where token_hash = %s and revoked_at is null
                """,
            (digest,),
        )
        return cur.rowcount > 0


def revoke_all_user_sessions(user_id: str) -> int:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                update user_sessions
                set revoked_at = coalesce(revoked_at, now())
                where user_id = %s and revoked_at is null
                """,
            (user_id,),
        )
        return int(cur.rowcount or 0)


def create_email_verification_token(user_id: str, *, hours: int) -> str:
    raw = generate_token(32)
    digest = hash_token(raw)
    expires = _utcnow() + timedelta(hours=max(1, hours))
    with db_connection() as conn, conn.cursor() as cur:
        # Invalidate older unused tokens to limit resend flood.
        cur.execute(
            """
                update email_verification_tokens
                set used_at = coalesce(used_at, now())
                where user_id = %s and used_at is null
                """,
            (user_id,),
        )
        cur.execute(
            """
                insert into email_verification_tokens(user_id, token_hash, expires_at)
                values (%s, %s, %s)
                """,
            (user_id, digest, expires),
        )
    return raw


def consume_email_verification_token(raw_token: str) -> tuple[str | None, str]:
    """Return (user_id, status) where status is ok|invalid|used|expired|already_verified."""
    digest = hash_token(raw_token)
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                select t.id, t.user_id, t.expires_at, t.used_at, u.email_verified_at
                from email_verification_tokens t
                join users u on u.id = t.user_id
                where t.token_hash = %s
                for update of t
                """,
            (digest,),
        )
        row = cur.fetchone()
        if not row:
            return None, "invalid"
        if row["email_verified_at"] is not None and row["used_at"] is not None:
            return str(row["user_id"]), "already_verified"
        if row["used_at"] is not None:
            return None, "used"
        if row["expires_at"] <= _utcnow():
            return None, "expired"
        cur.execute(
            "update email_verification_tokens set used_at = now() where id = %s",
            (row["id"],),
        )
        cur.execute(
            """
                update users
                set email_verified_at = coalesce(email_verified_at, now()),
                    updated_at = now()
                where id = %s
                """,
            (row["user_id"],),
        )
        return str(row["user_id"]), "ok"


def create_password_reset_token(user_id: str, *, hours: int) -> str:
    raw = generate_token(32)
    digest = hash_token(raw)
    expires = _utcnow() + timedelta(hours=max(1, hours))
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                update password_reset_tokens
                set used_at = coalesce(used_at, now())
                where user_id = %s and used_at is null
                """,
            (user_id,),
        )
        cur.execute(
            """
                insert into password_reset_tokens(user_id, token_hash, expires_at)
                values (%s, %s, %s)
                """,
            (user_id, digest, expires),
        )
    return raw


def consume_password_reset_token(raw_token: str, new_password: str) -> tuple[str | None, str]:
    """Return (user_id, status) where status is ok|invalid|used|expired."""
    digest = hash_token(raw_token)
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                select id, user_id, expires_at, used_at
                from password_reset_tokens
                where token_hash = %s
                for update
                """,
            (digest,),
        )
        row = cur.fetchone()
        if not row:
            return None, "invalid"
        if row["used_at"] is not None:
            return None, "used"
        if row["expires_at"] <= _utcnow():
            return None, "expired"
        cur.execute(
            "update password_reset_tokens set used_at = now() where id = %s",
            (row["id"],),
        )
        cur.execute(
            """
                update users
                set password_hash = %s, updated_at = now()
                where id = %s
                """,
            (hash_password(new_password), row["user_id"]),
        )
        cur.execute(
            """
                update user_sessions
                set revoked_at = coalesce(revoked_at, now())
                where user_id = %s and revoked_at is null
                """,
            (row["user_id"],),
        )
        return str(row["user_id"]), "ok"

def cleanup_auth_artifacts(*, session_batch: int = 500, token_batch: int = 500) -> dict[str, int]:
    """Bounded cleanup of expired/revoked auth rows."""
    deleted = {"sessions": 0, "verification": 0, "reset": 0}
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                delete from user_sessions
                where id in (
                  select id from user_sessions
                  where expires_at < now() - interval '7 days'
                     or (revoked_at is not null and revoked_at < now() - interval '7 days')
                  limit %s
                )
                """,
                (session_batch,),
            )
            deleted["sessions"] = int(cur.rowcount or 0)
            cur.execute(
                """
                delete from email_verification_tokens
                where id in (
                  select id from email_verification_tokens
                  where expires_at < now() or used_at is not null
                  limit %s
                )
                """,
                (token_batch,),
            )
            deleted["verification"] = int(cur.rowcount or 0)
            cur.execute(
                """
                delete from password_reset_tokens
                where id in (
                  select id from password_reset_tokens
                  where expires_at < now() or used_at is not null
                  limit %s
                )
                """,
                (token_batch,),
            )
            deleted["reset"] = int(cur.rowcount or 0)
    return deleted


def _public_product_ok(category: str | None, status: str | None) -> bool:
    if (status or "").lower() != "active":
        return False
    info = get_search_category((category or "").lower())
    return bool(info and info.public_search_enabled)


def wishlist_add(user_id: str, product_id: str) -> str:
    """Return added|exists|rejected."""
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, category, status from product_clusters where id = %s",
                (product_id,),
            )
            product = cur.fetchone()
            if not product or not _public_product_ok(product.get("category"), product.get("status")):
                return "rejected"
            cur.execute(
                """
                insert into user_wishlist(user_id, product_id)
                values (%s, %s)
                on conflict (user_id, product_id) do nothing
                """,
                (user_id, product_id),
            )
            return "added" if cur.rowcount else "exists"


def wishlist_remove(user_id: str, product_id: str) -> str:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "delete from user_wishlist where user_id = %s and product_id = %s",
            (user_id, product_id),
        )
        return "removed" if cur.rowcount else "absent"


def wishlist_list(user_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(200, int(limit)))
    watch_sql = """
                select p.id, p.category, p.brand, p.canonical_title as title, p.specs,
                       p.status, b.best_price, b.best_platform, b.platform_count, b.last_seen_at,
                       d.image_url, w.created_at as wishlisted_at,
                       w.target_price, w.notify_on_drop, w.last_notified_at
                from user_wishlist w
                join product_clusters p on p.id = w.product_id
                left join current_product_best_prices b on b.product_id = p.id
                left join product_search_documents d on d.product_id = p.id
                where w.user_id = %s
                order by w.created_at desc
                limit %s
                """
    base_sql = """
                select p.id, p.category, p.brand, p.canonical_title as title, p.specs,
                       p.status, b.best_price, b.best_platform, b.platform_count, b.last_seen_at,
                       d.image_url, w.created_at as wishlisted_at
                from user_wishlist w
                join product_clusters p on p.id = w.product_id
                left join current_product_best_prices b on b.product_id = p.id
                left join product_search_documents d on d.product_id = p.id
                where w.user_id = %s
                order by w.created_at desc
                limit %s
                """
    with db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(watch_sql, (user_id, limit))
            except Exception as exc:
                if "target_price" not in str(exc):
                    raise
                conn.rollback()
                cur.execute(base_sql, (user_id, limit))
            return [dict(row) for row in cur.fetchall()]


def wishlist_count(user_id: str) -> int:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select count(*) as n from user_wishlist where user_id = %s",
            (user_id,),
        )
        row = cur.fetchone() or {}
        return int(row.get("n") or 0)


def wishlist_status(user_id: str, product_ids: list[str]) -> dict[str, bool]:
    cleaned = [str(pid).strip() for pid in product_ids if str(pid).strip()][:50]
    if not cleaned:
        return {}
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                select product_id::text as product_id
                from user_wishlist
                where user_id = %s and product_id = any(%s::uuid[])
                """,
            (user_id, cleaned),
        )
        present = {str(row["product_id"]) for row in cur.fetchall()}
    return {pid: pid in present for pid in cleaned}
