"""Create disposable test DB for UX hardening verification."""
from __future__ import annotations

import psycopg

ADMIN = "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/postgres"
NAME = "mayabu_ux_harden_test"

with psycopg.connect(ADMIN, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (NAME,))
        if cur.fetchone():
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (NAME,),
            )
            cur.execute(f'DROP DATABASE "{NAME}"')
        cur.execute(f'CREATE DATABASE "{NAME}"')
        print(f"created {NAME}")
