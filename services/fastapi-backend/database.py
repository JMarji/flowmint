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


def run_migrations():
    """Idempotent: creates any tables not yet present in the live database."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS flowmint.plans (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES flowmint.users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    property_id INTEGER REFERENCES flowmint.properties(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                ALTER TABLE flowmint.plans
                ADD COLUMN IF NOT EXISTS property_id INTEGER
            """)
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'plans_property_id_fkey'
                    ) THEN
                        ALTER TABLE flowmint.plans
                        ADD CONSTRAINT plans_property_id_fkey
                        FOREIGN KEY (property_id)
                        REFERENCES flowmint.properties(id)
                        ON DELETE SET NULL;
                    END IF;
                END $$;
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS flowmint.plan_messages (
                    id SERIAL PRIMARY KEY,
                    plan_id INTEGER NOT NULL REFERENCES flowmint.plans(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS flowmint.plan_todos (
                    id SERIAL PRIMARY KEY,
                    plan_id INTEGER NOT NULL REFERENCES flowmint.plans(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    done BOOLEAN NOT NULL DEFAULT FALSE,
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                ALTER TABLE flowmint.properties
                ADD COLUMN IF NOT EXISTS mortgage_account_id TEXT
                REFERENCES flowmint.bank_accounts(account_id) ON DELETE SET NULL
            """)
            cur.execute("""
                ALTER TABLE flowmint.transactions
                ADD COLUMN IF NOT EXISTS mortgage_property_id INTEGER
            """)
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'transactions_mortgage_property_id_fkey'
                    ) THEN
                        ALTER TABLE flowmint.transactions
                        ADD CONSTRAINT transactions_mortgage_property_id_fkey
                        FOREIGN KEY (mortgage_property_id)
                        REFERENCES flowmint.properties(id)
                        ON DELETE SET NULL;
                    END IF;
                END $$;
            """)
            conn.commit()
    logger.info("Migrations complete")
