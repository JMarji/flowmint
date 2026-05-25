import os
import logging
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)
_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    return _pool


def init_pool():
    global _pool
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    _pool = ConnectionPool(db_url, min_size=1, max_size=5, timeout=30)
    logger.info("Database pool initialized")
