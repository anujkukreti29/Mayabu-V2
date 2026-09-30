#!/usr/bin/env python3
"""Restore a Mayabu pg_dump custom-format backup into a SEPARATE database."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from urllib.parse import unquote, urlparse


def _parse_dsn(dsn: str) -> dict[str, str]:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise SystemExit("Target DATABASE_URL must be postgresql://")
    dbname = (parsed.path or "").lstrip("/")
    if not dbname:
        raise SystemExit("Target URL must include a database name")
    if dbname in {"mayabu", "postgres"} and not os.getenv("MAYABU_ALLOW_PRIMARY_RESTORE"):
        raise SystemExit(
            "Refusing to restore into primary-looking DB name without MAYABU_ALLOW_PRIMARY_RESTORE=1"
        )
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": str(parsed.port or 5432),
        "user": unquote(parsed.username or "mayabu"),
        "password": unquote(parsed.password or ""),
        "dbname": dbname,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", required=True, help="Path to .dump from backup_postgres.py")
    parser.add_argument(
        "--target-url",
        default=os.getenv("MAYABU_RESTORE_DATABASE_URL", ""),
        help="Restore target DSN (must be a separate DB)",
    )
    parser.add_argument("--create-db", action="store_true", help="CREATE DATABASE if missing")
    args = parser.parse_args()
    if not args.target_url:
        print("MAYABU_RESTORE_DATABASE_URL / --target-url required", file=sys.stderr)
        return 2
    cfg = _parse_dsn(args.target_url)
    env = os.environ.copy()
    if cfg["password"]:
        env["PGPASSWORD"] = cfg["password"]
    if args.create_db:
        admin = [
            "psql",
            "-h",
            cfg["host"],
            "-p",
            cfg["port"],
            "-U",
            cfg["user"],
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f"CREATE DATABASE \"{cfg['dbname']}\"",
        ]
        subprocess.run(admin, env=env, check=False)
    cmd = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "-h",
        cfg["host"],
        "-p",
        cfg["port"],
        "-U",
        cfg["user"],
        "-d",
        cfg["dbname"],
        args.dump,
    ]
    print("running pg_restore into", cfg["dbname"])
    completed = subprocess.run(cmd, env=env, check=False)
    if completed.returncode not in {0, 1}:
        # pg_restore uses 1 for some non-fatal warnings
        print("pg_restore failed", completed.returncode, file=sys.stderr)
        return completed.returncode
    verify = [
        "psql",
        "-h",
        cfg["host"],
        "-p",
        cfg["port"],
        "-U",
        cfg["user"],
        "-d",
        cfg["dbname"],
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        (
            "select count(*) as migrations from schema_migrations; "
            "select count(*) as users from users; "
            "select count(*) as products from product_clusters;"
        ),
    ]
    verify_result = subprocess.run(verify, env=env, check=False)
    if verify_result.returncode != 0:
        print("restore verification queries failed", file=sys.stderr)
        return verify_result.returncode
    print("restore_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
