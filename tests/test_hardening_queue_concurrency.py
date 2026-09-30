"""Concurrency and idempotency regressions for the scrape task queue."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

pytest.importorskip("psycopg")

DATABASE_URL = os.getenv("MAYABU_TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("MAYABU_TEST_DATABASE_URL not set", allow_module_level=True)

CREATED_BY = "test_hardening"


@pytest.fixture()
def conn():
    import psycopg
    from psycopg.rows import dict_row

    connection = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    yield connection
    connection.close()


def _cleanup_claim_tasks(conn, key_prefix: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "delete from scrape_tasks where idempotency_key like %s",
            (f"{key_prefix}%",),
        )
    conn.commit()


def test_claim_next_task_exclusive_under_concurrency(conn) -> None:
    from mayabu_db.tasks import claim_next_task, create_task

    key = f"hardening-claim-{os.getpid()}-{threading.get_ident()}"
    _cleanup_claim_tasks(conn, key)
    # Also clear leftover rows from earlier failed runs for this created_by prefix.
    with conn.cursor() as cur:
        cur.execute(
            "delete from scrape_tasks where created_by = %s and idempotency_key like %s",
            (CREATED_BY, "hardening-claim-%"),
        )
    conn.commit()

    task_ids: list[str] = []
    try:
        for i in range(5):
            task_ids.append(
                create_task(
                    conn,
                    "amazon",
                    "diagnostic",
                    query=f"claim-test-{i}",
                    priority=1,
                    idempotency_key=f"{key}-{i}",
                    created_by=CREATED_BY,
                )
            )
        conn.commit()

        claimed: list[str] = []
        lock = threading.Lock()

        def worker(worker_id: str) -> str | None:
            import psycopg
            from psycopg.rows import dict_row

            with psycopg.connect(DATABASE_URL, row_factory=dict_row) as local:
                with local.transaction():
                    row = claim_next_task(
                        local,
                        worker_id,
                        lease_minutes=5,
                        created_by=CREATED_BY,
                    )
                if not row:
                    return None
                tid = str(row["id"])
                with lock:
                    claimed.append(tid)
                return tid

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(worker, f"w-{i}") for i in range(8)]
            results = [f.result() for f in as_completed(futures)]

        claimed_ids = [r for r in results if r]
        assert len(claimed_ids) == len(set(claimed_ids)), claimed_ids
        assert set(claimed_ids).issubset(set(task_ids)), {
            "claimed": claimed_ids,
            "created": task_ids,
        }
        assert len(claimed_ids) == 5

        with conn.cursor() as cur:
            cur.execute(
                "select status, count(*) as n from scrape_tasks where idempotency_key like %s group by status",
                (f"{key}%",),
            )
            by_status = {row["status"]: int(row["n"]) for row in cur.fetchall()}
        assert by_status.get("running", 0) == 5
        assert by_status.get("pending", 0) == 0
    finally:
        _cleanup_claim_tasks(conn, key)


def test_create_task_idempotent_on_active_key(conn) -> None:
    from mayabu_db.tasks import create_task

    key = f"hardening-idem-{os.getpid()}-{threading.get_ident()}"
    with conn.cursor() as cur:
        cur.execute("delete from scrape_tasks where idempotency_key = %s", (key,))
    conn.commit()

    try:
        first = create_task(
            conn,
            "flipkart",
            "diagnostic",
            query="idem",
            idempotency_key=key,
            created_by=CREATED_BY,
        )
        conn.commit()
        second = create_task(
            conn,
            "flipkart",
            "diagnostic",
            query="idem",
            idempotency_key=key,
            created_by=CREATED_BY,
        )
        conn.commit()
        assert first == second

        with conn.cursor() as cur:
            cur.execute("select count(*) as n from scrape_tasks where idempotency_key = %s", (key,))
            assert int(cur.fetchone()["n"]) == 1
    finally:
        with conn.cursor() as cur:
            cur.execute("delete from scrape_tasks where idempotency_key = %s", (key,))
        conn.commit()
