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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS flowmint.credit_liabilities (
                    account_id TEXT PRIMARY KEY REFERENCES flowmint.bank_accounts(account_id) ON DELETE CASCADE,
                    credit_limit NUMERIC(12,2),
                    iso_currency_code TEXT,
                    is_overdue BOOLEAN,
                    last_payment_amount NUMERIC(12,2),
                    last_payment_date DATE,
                    last_statement_balance NUMERIC(12,2),
                    last_statement_issue_date DATE,
                    minimum_payment_amount NUMERIC(12,2),
                    next_payment_due_date DATE,
                    aprs JSONB NOT NULL DEFAULT '[]'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS flowmint.account_balance_snapshots (
                    account_id TEXT NOT NULL REFERENCES flowmint.bank_accounts(account_id) ON DELETE CASCADE,
                    snapshot_date DATE NOT NULL,
                    current_balance NUMERIC(12,2),
                    available_balance NUMERIC(12,2),
                    credit_limit NUMERIC(12,2),
                    PRIMARY KEY (account_id, snapshot_date)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS flowmint.credit_card_settings (
                    account_id TEXT PRIMARY KEY REFERENCES flowmint.bank_accounts(account_id) ON DELETE CASCADE,
                    network TEXT,
                    product_name TEXT,
                    annual_fee NUMERIC(12,2),
                    annual_fee_month INTEGER CHECK (annual_fee_month BETWEEN 1 AND 12),
                    reward_type TEXT NOT NULL DEFAULT 'cashback' CHECK (reward_type IN ('cashback', 'points')),
                    point_value_cents NUMERIC(6,3) NOT NULL DEFAULT 1,
                    base_reward_rate NUMERIC(6,3) NOT NULL DEFAULT 0,
                    category_rates JSONB NOT NULL DEFAULT '{}'::jsonb,
                    auto_bill BOOLEAN NOT NULL DEFAULT TRUE,
                    bill_amount_mode TEXT NOT NULL DEFAULT 'statement' CHECK (bill_amount_mode IN ('statement', 'minimum')),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                ALTER TABLE flowmint.bills
                ADD COLUMN IF NOT EXISTS credit_account_id TEXT
                REFERENCES flowmint.bank_accounts(account_id) ON DELETE CASCADE
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS bills_credit_account_id_key
                ON flowmint.bills (credit_account_id) WHERE credit_account_id IS NOT NULL
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS flowmint.subscription_tracking (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES flowmint.users(id) ON DELETE CASCADE,
                    account_id TEXT NOT NULL REFERENCES flowmint.bank_accounts(account_id) ON DELETE CASCADE,
                    stream_id TEXT NOT NULL,
                    merchant_name TEXT NOT NULL,
                    match_key TEXT NOT NULL,
                    frequency TEXT,
                    last_amount NUMERIC(12,2),
                    monthly_amount NUMERIC(12,2),
                    next_expected_date DATE,
                    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'kept')),
                    status_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    cancelled_on DATE,
                    kept_amount NUMERIC(12,2),
                    still_charging_txn_id INTEGER REFERENCES flowmint.transactions(id) ON DELETE SET NULL,
                    still_charging_detected_at TIMESTAMPTZ,
                    alert_dismissed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (account_id, stream_id)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS subscription_tracking_user_status_idx
                ON flowmint.subscription_tracking (user_id, status)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS flowmint.mortgage_liabilities (
                    account_id TEXT PRIMARY KEY REFERENCES flowmint.bank_accounts(account_id) ON DELETE CASCADE,
                    next_payment_due_date DATE,
                    next_monthly_payment NUMERIC(12,2),
                    last_payment_date DATE,
                    last_payment_amount NUMERIC(12,2),
                    past_due_amount NUMERIC(12,2),
                    current_late_fee NUMERIC(12,2),
                    escrow_balance NUMERIC(12,2),
                    ytd_interest_paid NUMERIC(12,2),
                    ytd_principal_paid NUMERIC(12,2),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                ALTER TABLE flowmint.properties
                ADD COLUMN IF NOT EXISTS mortgage_due_day INTEGER CHECK (mortgage_due_day BETWEEN 1 AND 31)
            """)
            cur.execute("""
                ALTER TABLE flowmint.transactions
                ADD COLUMN IF NOT EXISTS tag_source TEXT CHECK (tag_source IN ('auto', 'manual'))
            """)
            cur.execute("""
                ALTER TABLE flowmint.bills
                ADD COLUMN IF NOT EXISTS match_key TEXT
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS flowmint.bill_payments (
                    id SERIAL PRIMARY KEY,
                    bill_id INTEGER NOT NULL REFERENCES flowmint.bills(id) ON DELETE CASCADE,
                    transaction_id INTEGER NOT NULL REFERENCES flowmint.transactions(id) ON DELETE CASCADE,
                    period TEXT NOT NULL,
                    source TEXT NOT NULL CHECK (source IN ('auto', 'manual')),
                    status TEXT NOT NULL DEFAULT 'matched' CHECK (status IN ('matched', 'rejected')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (bill_id, transaction_id)
                )
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS bill_payments_one_per_period
                ON flowmint.bill_payments (bill_id, period) WHERE status = 'matched'
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS bill_payments_txn_once
                ON flowmint.bill_payments (transaction_id) WHERE status = 'matched'
            """)
            cur.execute("""
                ALTER TABLE flowmint.properties
                ADD COLUMN IF NOT EXISTS mortgage_lender TEXT
            """)
            conn.commit()
    logger.info("Migrations complete")
