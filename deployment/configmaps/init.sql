CREATE SCHEMA IF NOT EXISTS flowmint;

CREATE TABLE IF NOT EXISTS flowmint.users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flowmint.refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES flowmint.users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flowmint.bank_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES flowmint.users(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL UNIQUE,
    access_token_enc TEXT NOT NULL,
    institution_name TEXT,
    institution_id TEXT,
    cursor TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flowmint.bank_accounts (
    id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES flowmint.bank_items(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    type TEXT,
    subtype TEXT,
    mask TEXT,
    current_balance NUMERIC(12,2),
    available_balance NUMERIC(12,2),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS flowmint.transactions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES flowmint.bank_accounts(id) ON DELETE CASCADE,
    txn_id TEXT NOT NULL UNIQUE,
    amount NUMERIC(12,2) NOT NULL,
    date DATE NOT NULL,
    name TEXT,
    merchant_name TEXT,
    category_primary TEXT,
    category_detailed TEXT,
    category_override TEXT,
    pending BOOLEAN DEFAULT FALSE,
    logo_url TEXT,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flowmint.budgets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES flowmint.users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    monthly_limit NUMERIC(12,2) NOT NULL,
    month_year TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, category, month_year)
);

CREATE TABLE IF NOT EXISTS flowmint.bills (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES flowmint.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    due_day_of_month INTEGER NOT NULL CHECK(due_day_of_month BETWEEN 1 AND 31),
    category TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_paid_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flowmint.properties (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES flowmint.users(id) ON DELETE CASCADE,
    address TEXT NOT NULL,
    city TEXT,
    state TEXT,
    zip TEXT,
    purchase_price NUMERIC(12,2),
    current_value NUMERIC(12,2),
    purchase_date DATE,
    mortgage_balance NUMERIC(12,2),
    mortgage_rate NUMERIC(5,3),
    mortgage_payment NUMERIC(12,2),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flowmint.property_transactions (
    id SERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL REFERENCES flowmint.properties(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
    amount NUMERIC(12,2) NOT NULL,
    date DATE NOT NULL,
    category TEXT,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flowmint.documents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES flowmint.users(id) ON DELETE CASCADE,
    property_id INTEGER REFERENCES flowmint.properties(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    content_type TEXT,
    size_bytes BIGINT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flowmint.networth_snapshots (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES flowmint.users(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    liquid_assets NUMERIC(12,2),
    property_equity NUMERIC(12,2),
    total_liabilities NUMERIC(12,2),
    net_worth NUMERIC(12,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, snapshot_date)
);
