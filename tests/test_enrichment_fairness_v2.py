"""Queue fairness: user verify_listing claims ahead of enrich_listing backlog."""

from __future__ import annotations

import os
import threading
import uuid

import pytest

pytest.importorskip("psycopg")

DATABASE_URL = os.getenv("MAYABU_TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("MAYABU_TEST_DATABASE_URL not set", allow_module_level=True)

CREATED_BY = "test-enrich-fairness-v2"


@pytest.fixture()
def conn():
    import psycopg
    from psycopg.rows import dict_row

    connection = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    yield connection
    connection.close()


def test_verify_claims_ahead_of_enrichment_backlog(conn) -> None:
    from mayabu.catalog.enrichment import ENRICH_PRIORITY
    from mayabu.core.config import get_app_settings
    from mayabu_db.tasks import claim_next_task, create_task

    settings = get_app_settings()
    verify_priority = int(settings.live_verify_priority)
    assert verify_priority < ENRICH_PRIORITY

    key = f"fairness-{os.getpid()}-{threading.get_ident()}-{uuid.uuid4().hex[:8]}"
    with conn.cursor() as cur:
        cur.execute("delete from scrape_tasks where created_by = %s", (CREATED_BY,))
    conn.commit()

    try:
        for i in range(100):
            create_task(
                conn,
                "amazon",
                "enrich_listing",
                query=f"enrich-backlog-{i}",
                priority=ENRICH_PRIORITY,
                idempotency_key=f"{key}-enrich-{i}",
                created_by=CREATED_BY,
                metadata={"purpose": "fairness_test"},
            )
        verify_id = create_task(
            conn,
            "flipkart",
            "verify_listing",
            query="user-check-latest-price",
            priority=verify_priority,
            idempotency_key=f"{key}-verify",
            created_by=CREATED_BY,
            metadata={"purpose": "fairness_test", "source": "user_verify"},
        )
        conn.commit()

        claimed = claim_next_task(conn, "fairness-worker", lease_minutes=2, created_by=CREATED_BY)
        conn.commit()
        assert claimed is not None
        assert str(claimed["id"]) == verify_id
        assert claimed["task_type"] == "verify_listing"
        assert int(claimed["priority"]) == verify_priority
    finally:
        with conn.cursor() as cur:
            cur.execute("delete from scrape_tasks where created_by = %s", (CREATED_BY,))
        conn.commit()
