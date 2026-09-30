#!/usr/bin/env python3
"""Create a PostgreSQL logical backup (custom format) for Mayabu."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


def _parse_dsn(dsn: str) -> dict[str, str]:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise SystemExit("DATABASE_URL must be postgresql://")
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": str(parsed.port or 5432),
        "user": unquote(parsed.username or "mayabu"),
        "password": unquote(parsed.password or ""),
        "dbname": (parsed.path or "/mayabu").lstrip("/") or "mayabu",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--out-dir", default="artifacts/backups")
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    if not args.database_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 2
    cfg = _parse_dsn(args.database_url)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = f"-{args.label}" if args.label else ""
    out_path = out_dir / f"mayabu{label}-{stamp}.dump"
    env = os.environ.copy()
    if cfg["password"]:
        env["PGPASSWORD"] = cfg["password"]
    cmd = [
        "pg_dump",
        "-Fc",
        "-h",
        cfg["host"],
        "-p",
        cfg["port"],
        "-U",
        cfg["user"],
        "-d",
        cfg["dbname"],
        "-f",
        str(out_path),
    ]
    print("running", " ".join(cmd[:-2] + ["-f", str(out_path)]))
    completed = subprocess.run(cmd, env=env, check=False)
    if completed.returncode != 0:
        print("pg_dump failed", file=sys.stderr)
        return completed.returncode
    print(f"backup_ok path={out_path} bytes={out_path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
