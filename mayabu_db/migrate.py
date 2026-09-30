"""Deterministic PostgreSQL migration runner with schema_migrations ledger."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from psycopg import Error as PsycopgError

from mayabu_db.connection import close_connection_pool, db_connection

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schema.sql"
MIGRATIONS_DIR = ROOT / "migrations"


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _ensure_ledger(cur) -> None:
    cur.execute(
        """
        create table if not exists schema_migrations (
          version text primary key,
          applied_at timestamptz not null default now()
        )
        """
    )
    cur.execute(
        """
        alter table schema_migrations
          add column if not exists checksum text
        """
    )


def _applied_versions(cur) -> set[str]:
    cur.execute("select version from schema_migrations")
    return {str(row["version"] if isinstance(row, dict) else row[0]) for row in cur.fetchall()}


def _record(cur, version: str, checksum: str) -> None:
    cur.execute(
        """
        insert into schema_migrations(version, checksum)
        values (%s, %s)
        on conflict (version) do update set checksum = excluded.checksum
        """,
        (version, checksum),
    )


def apply_baseline_schema(*, force: bool = False) -> dict[str, object]:
    """Apply idempotent schema.sql baseline."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    digest = _checksum(sql)
    with db_connection() as conn, conn.cursor() as cur:
        _ensure_ledger(cur)
        applied = _applied_versions(cur)
        version = "baseline_schema_sql"
        if version in applied and not force:
            return {"baseline": "skipped", "checksum": digest}
        cur.execute(sql)
        _record(cur, version, digest)
        # Also record historical versions embedded in schema.sql inserts (no-op if present).
        return {"baseline": "applied", "checksum": digest}


def list_migration_files() -> list[Path]:
    if not MIGRATIONS_DIR.is_dir():
        return []
    return sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())


def apply_pending_migrations(*, dry_run: bool = False) -> dict[str, object]:
    results: list[dict[str, str]] = []
    with db_connection() as conn, conn.cursor() as cur:
        _ensure_ledger(cur)
        applied = _applied_versions(cur)
        for path in list_migration_files():
            version = path.stem
            sql = path.read_text(encoding="utf-8")
            digest = _checksum(sql)
            if version in applied:
                results.append({"version": version, "status": "already_applied"})
                continue
            if dry_run:
                results.append({"version": version, "status": "pending"})
                continue
            try:
                cur.execute(sql)
                _record(cur, version, digest)
                results.append({"version": version, "status": "applied", "checksum": digest})
            except PsycopgError as exc:
                conn.rollback()
                raise RuntimeError(f"Migration failed: {version}: {exc}") from exc
    return {"migrations": results}


def migrate(*, include_baseline: bool = True, dry_run: bool = False) -> dict[str, object]:
    report: dict[str, object] = {}
    if include_baseline and not dry_run:
        report["baseline"] = apply_baseline_schema()
    elif include_baseline and dry_run:
        report["baseline"] = {"baseline": "dry_run_skip"}
    report.update(apply_pending_migrations(dry_run=dry_run))
    return report


def status() -> dict[str, object]:
    files = [p.stem for p in list_migration_files()]
    with db_connection() as conn, conn.cursor() as cur:
        _ensure_ledger(cur)
        applied = sorted(_applied_versions(cur))
    pending = [name for name in files if name not in set(applied)]
    return {"applied": applied, "pending": pending, "migration_files": files}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Mayabu PostgreSQL migrations")
    parser.add_argument("--status", action="store_true", help="Show applied/pending migrations")
    parser.add_argument("--dry-run", action="store_true", help="List pending without applying")
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Only apply files under mayabu_db/migrations/",
    )
    args = parser.parse_args(argv)
    try:
        if args.status:
            payload = status()
            print(payload)
            return 0
        report = migrate(include_baseline=not args.skip_baseline, dry_run=args.dry_run)
        print(report)
        return 0
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        close_connection_pool(timeout=1.0)


if __name__ == "__main__":
    raise SystemExit(main())
