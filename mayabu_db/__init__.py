"""Database-first backend layer for Mayabu.

The package keeps scrapers independent from storage while making PostgreSQL the
source of truth for listings, products, price history, task execution, review
queue, diagnostics, and anomalies.
"""

__all__ = ["__version__"]
__version__ = "3.1.0"
