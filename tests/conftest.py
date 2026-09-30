"""Pytest bootstrap for disposable DB integration.

When MAYABU_TEST_DATABASE_URL is set, mirror it to DATABASE_URL and require
the database name to contain ``test``. Integration modules must gate on
MAYABU_TEST_DATABASE_URL only (not the developer .env DATABASE_URL).
"""

from __future__ import annotations

import os

_TEST_URL = os.environ.get("MAYABU_TEST_DATABASE_URL")
if _TEST_URL:
    if "test" not in _TEST_URL.lower():
        raise RuntimeError(
            "MAYABU_TEST_DATABASE_URL must point at a disposable database "
            "whose name contains 'test' (got %r)" % (_TEST_URL,)
        )
    os.environ["DATABASE_URL"] = _TEST_URL
