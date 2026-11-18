from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timezone
import logging

from database import get_pool
import crypto

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bank items
# ---------------------------------------------------------------------------

def upsert_bank_item(
    user_id: int,
    item_id: str,
    access_token: str,
    institution_name: Optional[str],
    institution_id: Optional[str],
) -> int:
    """Insert or update a Plaid item. Returns the DB row id."""
    access_token_enc = crypto.encrypt(access_token)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO flowmint.bank_items
                    (user_id, item_id, access_token_enc, institution_name, institution_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (item_id) DO UPDATE SET
                    access_token_enc = EXCLUDED.access_token_enc,
                    institution_name = EXCLUDED.institution_name,
                    institution_id   = EXCLUDED.institution_id
                RETURNING id
                """,
                (user_id, item_id, access_token_enc, institution_name, institution_id)
            )
            row = cur.fetchone()
            conn.commit()
            return row[0]


def update_item_cursor(item_db_id: int, cursor: str):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flowmint.bank_items SET cursor = %s WHERE id = %s",
                (cursor, item_db_id)
            )
            conn.commit()


def get_all_items_for_user(user_id: int) -> List[Dict[str, Any]]:
    """Return all bank items with decrypted access tokens."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, item_id, access_token_enc, institution_name, institution_id, cursor
                   FROM flowmint.bank_items WHERE user_id = %s""",
                (user_id,)
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "item_id": r[1],
            "access_token": crypto.decrypt(r[2]),
            "institution_name": r[3],
            "institution_id": r[4],
            "cursor": r[5],
        }
        for r in rows
    ]


def delete_bank_item(item_db_id: int, user_id: int) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.bank_items WHERE id = %s AND user_id = %s",
                (item_db_id, user_id)
            )
            affected = cur.rowcount
            conn.commit()
            return affected > 0


# ---------------------------------------------------------------------------
# Bank accounts
# ---------------------------------------------------------------------------

def upsert_bank_account(
    item_db_id: int,
    account_id: str,
    name: str,
    acct_type: Optional[str],
    subtype: Optional[str],
    mask: Optional[str],
    current_balance: Optional[float],
    available_balance: Optional[float],
) -> int:
    """Insert or update a bank account. Returns the DB row id."""
    now = datetime.now(timezone.utc)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO flowmint.bank_accounts
                    (item_id, account_id, name, type, subtype, mask, current_balance, available_balance, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (account_id) DO UPDATE SET
                    name              = EXCLUDED.name,
                    type              = EXCLUDED.type,
                    subtype           = EXCLUDED.subtype,
                    mask              = EXCLUDED.mask,
                    current_balance   = EXCLUDED.current_balance,
                    available_balance = EXCLUDED.available_balance,
                    updated_at        = EXCLUDED.updated_at
                RETURNING id
                """,
                (item_db_id, account_id, name, acct_type, subtype, mask, current_balance, available_balance, now)
            )
            row = cur.fetchone()
            conn.commit()
            return row[0]


def get_accounts_for_user(user_id: int) -> List[Dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ba.id, ba.account_id, ba.name, ba.type, ba.subtype, ba.mask,
                       ba.current_balance, ba.available_balance, ba.updated_at,
                       bi.institution_name, bi.id as item_db_id
                FROM flowmint.bank_accounts ba
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE bi.user_id = %s
                ORDER BY bi.institution_name, ba.name
                """,
                (user_id,)
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "account_id": r[1],
            "name": r[2],
            "type": r[3],
            "subtype": r[4],
            "mask": r[5],
            "current_balance": float(r[6]) if r[6] is not None else None,
            "available_balance": float(r[7]) if r[7] is not None else None,
            "updated_at": r[8].isoformat() if r[8] else None,
            "institution_name": r[9],
            "item_db_id": r[10],
        }
        for r in rows
    ]


def get_account_for_user(user_id: int, account_db_id: int) -> Optional[Dict[str, Any]]:
    """Return a single linked account (with its item's decrypted access token) if the user owns it."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ba.id, ba.account_id, ba.name, ba.type, ba.subtype, ba.mask,
                       ba.current_balance, ba.available_balance, ba.updated_at,
                       bi.institution_name, bi.id, bi.access_token_enc
                FROM flowmint.bank_accounts ba
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE bi.user_id = %s AND ba.id = %s
                """,
                (user_id, account_db_id)
            )
            r = cur.fetchone()
    if not r:
        return None
    return {
        "id": r[0],
        "account_id": r[1],
        "name": r[2],
        "type": r[3],
        "subtype": r[4],
        "mask": r[5],
        "current_balance": float(r[6]) if r[6] is not None else None,
        "available_balance": float(r[7]) if r[7] is not None else None,
        "updated_at": r[8].isoformat() if r[8] else None,
        "institution_name": r[9],
        "item_db_id": r[10],
        "access_token": crypto.decrypt(r[11]),
    }


def get_account_spending_summary(account_db_id: int, months: int = 6) -> Dict[str, Any]:
    """Aggregate charges/payments for one account: monthly totals and top categories/merchants.

    Plaid sign convention: positive amount = charge (money out), negative = payment/credit.
    """
    category_sql = "COALESCE(t.category_override, t.category_primary, 'OTHER')"
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT to_char(date_trunc('month', t.date), 'YYYY-MM') AS month,
                       COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0) AS charges,
                       COALESCE(SUM(CASE WHEN t.amount < 0 THEN -t.amount ELSE 0 END), 0) AS payments,
                       COUNT(*) FILTER (WHERE t.amount > 0) AS charge_count
                FROM flowmint.transactions t
                WHERE t.account_id = %s
                  AND t.date >= date_trunc('month', CURRENT_DATE) - make_interval(months => %s::int)
                GROUP BY 1
                ORDER BY 1
                """,
                (account_db_id, months - 1)
            )
            monthly = [
                {"month": r[0], "charges": float(r[1]), "payments": float(r[2]), "charge_count": int(r[3])}
                for r in cur.fetchall()
            ]

            cur.execute(
                f"""
                SELECT {category_sql} AS category, SUM(t.amount) AS total, COUNT(*)
                FROM flowmint.transactions t
                WHERE t.account_id = %s AND t.amount > 0
                  AND t.date >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY 1
                ORDER BY total DESC
                LIMIT 6
                """,
                (account_db_id,)
            )
            top_categories = [
                {"category": r[0], "total": float(r[1]), "count": int(r[2])} for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(COALESCE(t.merchant_name, t.name, '')), ''), 'Unknown') AS merchant,
                       SUM(t.amount) AS total, COUNT(*), MAX(t.logo_url)
                FROM flowmint.transactions t
                WHERE t.account_id = %s AND t.amount > 0
                  AND t.date >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY 1
                ORDER BY total DESC
                LIMIT 6
                """,
                (account_db_id,)
            )
            top_merchants = [
                {"name": r[0], "total": float(r[1]), "count": int(r[2]), "logo_url": r[3]}
                for r in cur.fetchall()
            ]

    return {"monthly": monthly, "top_categories": top_categories, "top_merchants": top_merchants}


def get_loan_accounts_for_user(user_id: int) -> List[Dict[str, Any]]:
    """Return accounts with type='loan' that can be linked to properties."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ba.id, ba.account_id, ba.name, ba.type, ba.subtype, ba.mask,
                       ba.current_balance, ba.updated_at, bi.institution_name, bi.id
                FROM flowmint.bank_accounts ba
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE bi.user_id = %s AND ba.type = 'loan'
                ORDER BY bi.institution_name, ba.name
                """,
                (user_id,)
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0], "account_id": r[1], "name": r[2], "type": r[3],
            "subtype": r[4], "mask": r[5],
            "current_balance": float(r[6]) if r[6] is not None else None,
            "updated_at": r[7].isoformat() if r[7] else None,
            "institution_name": r[8], "item_db_id": r[9],
        }
        for r in rows
    ]


def get_item_for_account(account_plaid_id: str) -> Optional[Dict[str, Any]]:
    """Return the bank_item (with decrypted access token) that owns this Plaid account."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT bi.id, bi.access_token_enc, bi.institution_name
                FROM flowmint.bank_accounts ba
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE ba.account_id = %s
                """,
                (account_plaid_id,)
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "access_token": crypto.decrypt(row[1]), "institution_name": row[2]}


def get_properties_linked_to_account(account_plaid_id: str) -> List[int]:
    """Return property IDs that have this Plaid account linked as their mortgage."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM flowmint.properties WHERE mortgage_account_id = %s",
                (account_plaid_id,)
            )
            rows = cur.fetchall()
    return [r[0] for r in rows]


def get_account_db_id_by_plaid_id(account_id: str) -> Optional[int]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM flowmint.bank_accounts WHERE account_id = %s",
                (account_id,)
            )
            row = cur.fetchone()
            return row[0] if row else None


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def upsert_transactions(txns: List[Dict[str, Any]]):
    """Bulk upsert transactions from Plaid sync response."""
    if not txns:
        return
    now = datetime.now(timezone.utc)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            for txn in txns:
                account_db_id = get_account_db_id_by_plaid_id(txn["account_id"])
                if account_db_id is None:
                    logger.warning("No DB account for Plaid account_id=%s", txn["account_id"])
                    continue
                pfc = txn.get("personal_finance_category") or {}
                cur.execute(
                    """
                    INSERT INTO flowmint.transactions
                        (account_id, txn_id, amount, date, name, merchant_name,
                         category_primary, category_detailed, pending, logo_url, synced_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (txn_id) DO UPDATE SET
                        amount            = EXCLUDED.amount,
                        date              = EXCLUDED.date,
                        name              = EXCLUDED.name,
                        merchant_name     = EXCLUDED.merchant_name,
                        category_primary  = EXCLUDED.category_primary,
                        category_detailed = EXCLUDED.category_detailed,
                        pending           = EXCLUDED.pending,
                        logo_url          = EXCLUDED.logo_url,
                        synced_at         = EXCLUDED.synced_at
                    """,
                    (
                        account_db_id,
                        txn["transaction_id"],
                        txn["amount"],
                        txn["date"],
                        txn.get("name"),
                        txn.get("merchant_name"),
                        pfc.get("primary"),
                        pfc.get("detailed"),
                        txn.get("pending", False),
                        txn.get("logo_url"),
                        now,
                    )
                )
        conn.commit()


def remove_transactions(txn_ids: List[str]):
    if not txn_ids:
        return
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.transactions WHERE txn_id = ANY(%s)",
                (txn_ids,)
            )
            conn.commit()


def get_transactions_for_user(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    account_id: Optional[int] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    vendor: Optional[str] = None,
) -> Dict[str, Any]:
    effective_category_sql = """COALESCE(
        t.category_override,
        CASE
            WHEN (p.id IS NOT NULL OR LOWER(COALESCE(ba.subtype, '')) = 'mortgage')
                 AND t.amount > 0
                THEN 'MORTGAGE_PAYMENT'
            ELSE t.category_primary
        END
    )"""

    conditions = [
        "bi.user_id = %s",
    ]
    params: list = [user_id]

    if account_id:
        conditions.append("ba.id = %s")
        params.append(account_id)
    if category:
        conditions.append(f"({effective_category_sql} = %s)")
        params.append(category)
    if start_date:
        conditions.append("t.date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("t.date <= %s")
        params.append(end_date)
    if search:
        conditions.append("(LOWER(COALESCE(t.name, '')) LIKE %s OR LOWER(COALESCE(t.merchant_name, '')) LIKE %s)")
        like = f"%{search.lower()}%"
        params.extend([like, like])
    if vendor:
        conditions.append("COALESCE(NULLIF(TRIM(COALESCE(t.merchant_name, t.name, '')), ''), 'Unknown Vendor') = %s")
        params.append(vendor)

    where = " AND ".join(conditions)

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            # Total count
            cur.execute(
                f"""SELECT COUNT(*)
                    FROM flowmint.transactions t
                    JOIN flowmint.bank_accounts ba ON t.account_id = ba.id
                    JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                    LEFT JOIN flowmint.properties p
                      ON p.mortgage_account_id = ba.account_id AND p.user_id = bi.user_id
                    WHERE {where}""",
                params
            )
            total = cur.fetchone()[0]

            # Paginated rows
            cur.execute(
                f"""
                SELECT t.id, t.txn_id, t.amount, t.date, t.name, t.merchant_name,
                      {effective_category_sql} AS category,
                       t.category_primary, t.category_detailed, t.category_override,
                       t.pending, t.logo_url, t.synced_at,
                      ba.name AS account_name, bi.institution_name,
                                            CASE WHEN {effective_category_sql} = 'MORTGAGE_PAYMENT' THEN TRUE ELSE FALSE END AS is_mortgage_payment,
                                            t.mortgage_property_id,
                                            lp.address AS mortgage_property_address,
                       t.tag_source
                FROM flowmint.transactions t
                JOIN flowmint.bank_accounts ba ON t.account_id = ba.id
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                                LEFT JOIN flowmint.properties p
                                    ON p.mortgage_account_id = ba.account_id AND p.user_id = bi.user_id
                                LEFT JOIN flowmint.properties lp
                                    ON lp.id = t.mortgage_property_id AND lp.user_id = bi.user_id
                WHERE {where}
                ORDER BY t.date DESC, t.id DESC
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset]
            )
            rows = cur.fetchall()

    txns = [
        {
            "id": r[0],
            "txn_id": r[1],
            "amount": float(r[2]),
            "date": str(r[3]),
            "name": r[4],
            "merchant_name": r[5],
            "category": r[6],
            "category_primary": r[7],
            "category_detailed": r[8],
            "category_override": r[9],
            "pending": r[10],
            "logo_url": r[11],
            "synced_at": r[12].isoformat() if r[12] else None,
            "account_name": r[13],
            "institution_name": r[14],
            "is_mortgage_payment": bool(r[15]),
            "mortgage_property_id": r[16],
            "mortgage_property_address": r[17],
            "tag_source": r[18],
        }
        for r in rows
    ]
    return {"transactions": txns, "total": total}


def get_vendor_summary_for_user(
    user_id: int,
    account_id: Optional[int] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    top_n: Optional[int] = None,
) -> Dict[str, Any]:
    """Return vendor-level spend aggregates across all filtered transactions."""
    conditions = [
        "bi.user_id = %s",
    ]
    params: list = [user_id]

    if account_id:
        conditions.append("ba.id = %s")
        params.append(account_id)
    if category:
        conditions.append("(t.category_override = %s OR (t.category_override IS NULL AND t.category_primary = %s))")
        params.extend([category, category])
    if start_date:
        conditions.append("t.date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("t.date <= %s")
        params.append(end_date)
    if search:
        conditions.append("(LOWER(COALESCE(t.name, '')) LIKE %s OR LOWER(COALESCE(t.merchant_name, '')) LIKE %s)")
        like = f"%{search.lower()}%"
        params.extend([like, like])

    where = " AND ".join(conditions)
    limit_clause = ""
    query_params = list(params)
    if top_n is not None:
        limit_clause = "\n                LIMIT %s"
        query_params.append(top_n)

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COALESCE(NULLIF(TRIM(COALESCE(t.merchant_name, t.name, '')), ''), 'Unknown Vendor') AS vendor_name,
                    COUNT(*) AS txn_count,
                    COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0) AS outflow,
                    MAX(t.logo_url) FILTER (WHERE t.logo_url IS NOT NULL) AS logo_url
                FROM flowmint.transactions t
                JOIN flowmint.bank_accounts ba ON t.account_id = ba.id
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE {where}
                GROUP BY COALESCE(NULLIF(TRIM(COALESCE(t.merchant_name, t.name, '')), ''), 'Unknown Vendor')
                ORDER BY outflow DESC, txn_count DESC, vendor_name ASC
                {limit_clause}
                """,
                query_params
            )
            rows = cur.fetchall()

            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT 1
                    FROM flowmint.transactions t
                    JOIN flowmint.bank_accounts ba ON t.account_id = ba.id
                    JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                    WHERE {where}
                    GROUP BY COALESCE(NULLIF(TRIM(COALESCE(t.merchant_name, t.name, '')), ''), 'Unknown Vendor')
                ) vendor_groups
                """,
                params
            )
            vendor_count = int(cur.fetchone()[0] or 0)

            cur.execute(
                f"""
                SELECT COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0)
                FROM flowmint.transactions t
                JOIN flowmint.bank_accounts ba ON t.account_id = ba.id
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE {where}
                """,
                params
            )
            total_outflow = float(cur.fetchone()[0] or 0)

    vendors = [
        {
            "name": r[0],
            "count": int(r[1]),
            "outflow": float(r[2] or 0),
            "logo_url": r[3],
        }
        for r in rows
    ]

    return {
        "vendors": vendors,
        "vendor_count": vendor_count,
        "total_outflow": total_outflow,
    }


def override_transaction_category(txn_id: int, user_id: int, category: str) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE flowmint.transactions t
                SET category_override = %s,
                    tag_source = 'manual',
                    -- a payment that's no longer a mortgage payment can't stay linked to a property
                    mortgage_property_id = CASE WHEN %s = 'MORTGAGE_PAYMENT' THEN t.mortgage_property_id END
                FROM flowmint.bank_accounts ba
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE t.id = %s AND t.account_id = ba.id AND bi.user_id = %s
                """,
                (category, category, txn_id, user_id)
            )
            affected = cur.rowcount
            conn.commit()
            return affected > 0


def user_owns_property(user_id: int, property_id: int) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM flowmint.properties WHERE id = %s AND user_id = %s",
                (property_id, user_id)
            )
            return cur.fetchone() is not None


def override_transaction_mortgage_property(txn_id: int, user_id: int, property_id: Optional[int]) -> bool:
    effective_category_sql = """COALESCE(
        t.category_override,
        CASE
            WHEN (p.id IS NOT NULL OR LOWER(COALESCE(ba.subtype, '')) = 'mortgage')
                 AND t.amount > 0
                THEN 'MORTGAGE_PAYMENT'
            ELSE t.category_primary
        END
    )"""

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE flowmint.transactions t
                SET mortgage_property_id = %s, tag_source = 'manual'
                FROM flowmint.bank_accounts ba
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                LEFT JOIN flowmint.properties p
                  ON p.mortgage_account_id = ba.account_id AND p.user_id = bi.user_id
                WHERE t.id = %s
                  AND t.account_id = ba.id
                  AND bi.user_id = %s
                  AND ({effective_category_sql} = 'MORTGAGE_PAYMENT')
                """,
                (property_id, txn_id, user_id)
            )
            affected = cur.rowcount
            conn.commit()
            return affected > 0


# ---------------------------------------------------------------------------
# Credit cards: persisted liabilities, balance history, settings, auto-bills
# ---------------------------------------------------------------------------

# Categories that never earn rewards (fees, payments, transfers).
_NON_REWARD_CATEGORIES = ("BANK_FEES", "LOAN_PAYMENTS", "TRANSFER_IN", "TRANSFER_OUT", "INCOME")

_SETTINGS_DEFAULTS: Dict[str, Any] = {
    "network": None,
    "product_name": None,
    "annual_fee": None,
    "annual_fee_month": None,
    "reward_type": "cashback",
    "point_value_cents": 1.0,
    "base_reward_rate": 0.0,
    "category_rates": {},
    "auto_bill": True,
    "bill_amount_mode": "statement",
}
SETTINGS_FIELDS = tuple(_SETTINGS_DEFAULTS.keys())


def _f(v):
    return float(v) if v is not None else None


def _iso(v):
    return v.isoformat() if v is not None else None


def record_balance_snapshot(
    account_id: str,
    current_balance: Optional[float],
    available_balance: Optional[float],
    credit_limit: Optional[float],
):
    """One row per account per day; later syncs on the same day overwrite it."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO flowmint.account_balance_snapshots
                    (account_id, snapshot_date, current_balance, available_balance, credit_limit)
                VALUES (%s, CURRENT_DATE, %s, %s, %s)
                ON CONFLICT (account_id, snapshot_date) DO UPDATE SET
                    current_balance   = EXCLUDED.current_balance,
                    available_balance = EXCLUDED.available_balance,
                    credit_limit      = COALESCE(EXCLUDED.credit_limit, flowmint.account_balance_snapshots.credit_limit)
                """,
                (account_id, current_balance, available_balance, credit_limit)
            )
            conn.commit()


def get_balance_history(account_id: str, days: int = 365) -> List[Dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT snapshot_date, current_balance, available_balance, credit_limit
                FROM flowmint.account_balance_snapshots
                WHERE account_id = %s AND snapshot_date >= CURRENT_DATE - %s::int
                ORDER BY snapshot_date
                """,
                (account_id, days)
            )
            rows = cur.fetchall()
    return [
        {"date": _iso(r[0]), "balance": _f(r[1]), "available": _f(r[2]), "limit": _f(r[3])}
        for r in rows
    ]


def store_credit_liabilities(liabilities_response: Dict[str, Any]) -> List[str]:
    """Persist credit-card liabilities from a Plaid /liabilities/get response (as a dict).

    Returns the Plaid account_ids that were stored.
    """
    limits = {}
    currencies = {}
    for acct in liabilities_response.get("accounts") or []:
        bal = acct.get("balances") or {}
        limits[acct.get("account_id")] = bal.get("limit")
        currencies[acct.get("account_id")] = bal.get("iso_currency_code")

    stored = []
    credits = (liabilities_response.get("liabilities") or {}).get("credit") or []
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            for c in credits:
                acct_id = c.get("account_id")
                if not acct_id:
                    continue
                aprs = [
                    {
                        "apr_type": a.get("apr_type"),
                        "apr_percentage": a.get("apr_percentage"),
                        "balance_subject_to_apr": a.get("balance_subject_to_apr"),
                        "interest_charge_amount": a.get("interest_charge_amount"),
                    }
                    for a in (c.get("aprs") or [])
                ]
                cur.execute(
                    """
                    INSERT INTO flowmint.credit_liabilities
                        (account_id, credit_limit, iso_currency_code, is_overdue,
                         last_payment_amount, last_payment_date, last_statement_balance,
                         last_statement_issue_date, minimum_payment_amount, next_payment_due_date,
                         aprs, updated_at)
                    SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW()
                    WHERE EXISTS (SELECT 1 FROM flowmint.bank_accounts WHERE account_id = %s)
                    ON CONFLICT (account_id) DO UPDATE SET
                        credit_limit              = EXCLUDED.credit_limit,
                        iso_currency_code         = EXCLUDED.iso_currency_code,
                        is_overdue                = EXCLUDED.is_overdue,
                        last_payment_amount       = EXCLUDED.last_payment_amount,
                        last_payment_date         = EXCLUDED.last_payment_date,
                        last_statement_balance    = EXCLUDED.last_statement_balance,
                        last_statement_issue_date = EXCLUDED.last_statement_issue_date,
                        minimum_payment_amount    = EXCLUDED.minimum_payment_amount,
                        next_payment_due_date     = EXCLUDED.next_payment_due_date,
                        aprs                      = EXCLUDED.aprs,
                        updated_at                = NOW()
                    """,
                    (
                        acct_id, limits.get(acct_id), currencies.get(acct_id), c.get("is_overdue"),
                        c.get("last_payment_amount"), c.get("last_payment_date"),
                        c.get("last_statement_balance"), c.get("last_statement_issue_date"),
                        c.get("minimum_payment_amount"), c.get("next_payment_due_date"),
                        json.dumps(aprs), acct_id,
                    )
                )
                if cur.rowcount:
                    stored.append(acct_id)
        conn.commit()
    return stored


def get_credit_liability(account_id: str) -> Optional[Dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT credit_limit, iso_currency_code, is_overdue, last_payment_amount,
                       last_payment_date, last_statement_balance, last_statement_issue_date,
                       minimum_payment_amount, next_payment_due_date, aprs, updated_at
                FROM flowmint.credit_liabilities WHERE account_id = %s
                """,
                (account_id,)
            )
            r = cur.fetchone()
    if not r:
        return None
    return {
        "credit_limit": _f(r[0]),
        "iso_currency_code": r[1],
        "is_overdue": r[2],
        "last_payment_amount": _f(r[3]),
        "last_payment_date": _iso(r[4]),
        "last_statement_balance": _f(r[5]),
        "last_statement_issue_date": _iso(r[6]),
        "minimum_payment_amount": _f(r[7]),
        "next_payment_due_date": _iso(r[8]),
        "aprs": r[9] or [],
        "updated_at": _iso(r[10]),
    }


def get_credit_settings(account_id: str) -> Dict[str, Any]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {', '.join(SETTINGS_FIELDS)} FROM flowmint.credit_card_settings WHERE account_id = %s",
                (account_id,)
            )
            r = cur.fetchone()
    if not r:
        return dict(_SETTINGS_DEFAULTS)
    out = dict(zip(SETTINGS_FIELDS, r))
    for k in ("annual_fee", "point_value_cents", "base_reward_rate"):
        out[k] = _f(out[k])
    out["category_rates"] = {k: float(v) for k, v in (out["category_rates"] or {}).items()}
    return out


def upsert_credit_settings(account_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**get_credit_settings(account_id), **{k: v for k, v in updates.items() if k in SETTINGS_FIELDS}}
    values = [json.dumps(merged[k]) if k == "category_rates" else merged[k] for k in SETTINGS_FIELDS]
    cols = ", ".join(SETTINGS_FIELDS)
    placeholders = ", ".join("%s::jsonb" if k == "category_rates" else "%s" for k in SETTINGS_FIELDS)
    sets = ", ".join(f"{k} = EXCLUDED.{k}" for k in SETTINGS_FIELDS)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO flowmint.credit_card_settings (account_id, {cols}, updated_at)
                VALUES (%s, {placeholders}, NOW())
                ON CONFLICT (account_id) DO UPDATE SET {sets}, updated_at = NOW()
                """,
                [account_id] + values
            )
            conn.commit()
    return merged


def sync_credit_bill(account_id: str) -> Optional[int]:
    """Create/update (or remove) the auto-generated bill for a credit card.

    Amount follows the card's bill_amount_mode (statement balance or minimum payment);
    due day comes from Plaid's next_payment_due_date. The bill is marked paid when Plaid
    reports a payment on or after the last statement date. Returns the bill id, if any.
    """
    liability = get_credit_liability(account_id)
    settings = get_credit_settings(account_id)

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            if not settings["auto_bill"]:
                cur.execute("DELETE FROM flowmint.bills WHERE credit_account_id = %s", (account_id,))
                conn.commit()
                return None

            if not liability or not liability["next_payment_due_date"]:
                return None

            stmt = liability["last_statement_balance"]
            minimum = liability["minimum_payment_amount"]
            if settings["bill_amount_mode"] == "minimum":
                amount = minimum if minimum is not None else stmt
            else:
                amount = stmt if stmt is not None else minimum
            if amount is None:
                return None

            due_day = int(liability["next_payment_due_date"][8:10])
            paid = None
            if liability["last_payment_date"] and liability["last_statement_issue_date"] \
                    and liability["last_payment_date"] >= liability["last_statement_issue_date"]:
                paid = liability["last_payment_date"]

            cur.execute(
                """
                SELECT bi.user_id, bi.institution_name, ba.name, ba.mask
                FROM flowmint.bank_accounts ba
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE ba.account_id = %s
                """,
                (account_id,)
            )
            owner = cur.fetchone()
            if not owner:
                return None
            user_id, institution, acct_name, mask = owner
            label = settings.get("product_name") or acct_name
            name = f"{institution or 'Credit card'} · {label}" + (f" ••••{mask}" if mask else "")

            def money(v):
                return f"${v:,.2f}" if v is not None else "—"
            notes = (
                f"Auto-synced from Plaid. Statement {money(stmt)}, minimum {money(minimum)}, "
                f"due {liability['next_payment_due_date']}."
            )

            cur.execute(
                """
                INSERT INTO flowmint.bills
                    (user_id, name, amount, due_day_of_month, category, last_paid_date, notes, credit_account_id)
                VALUES (%s, %s, %s, %s, 'CREDIT_CARD', %s, %s, %s)
                ON CONFLICT (credit_account_id) WHERE credit_account_id IS NOT NULL DO UPDATE SET
                    amount           = EXCLUDED.amount,
                    due_day_of_month = EXCLUDED.due_day_of_month,
                    last_paid_date   = COALESCE(EXCLUDED.last_paid_date, flowmint.bills.last_paid_date),
                    notes            = EXCLUDED.notes
                RETURNING id
                """,
                (user_id, name, amount, due_day, paid, notes, account_id)
            )
            bill_id = cur.fetchone()[0]
            conn.commit()
            return bill_id


def get_credit_bill_id(account_id: str) -> Optional[int]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM flowmint.bills WHERE credit_account_id = %s", (account_id,))
            r = cur.fetchone()
    return r[0] if r else None


def get_cycle_activity(account_db_id: int, since: str) -> Dict[str, Any]:
    """Charges/payments on or after `since` (ISO date) for one account."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0),
                       COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0),
                       COUNT(*) FILTER (WHERE amount > 0)
                FROM flowmint.transactions
                WHERE account_id = %s AND date >= %s::date
                """,
                (account_db_id, since)
            )
            r = cur.fetchone()
    return {"charges": float(r[0]), "payments": float(r[1]), "charge_count": int(r[2])}


def get_reward_eligible_spend(account_db_id: int, since: str) -> List[Dict[str, Any]]:
    """Charges since `since`, grouped by (primary, detailed) category, excluding fees/payments/transfers."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(t.category_override, t.category_primary, 'OTHER') AS primary_cat,
                       t.category_detailed,
                       SUM(t.amount)
                FROM flowmint.transactions t
                WHERE t.account_id = %s AND t.amount > 0 AND t.date >= %s::date
                  AND COALESCE(t.category_override, t.category_primary, 'OTHER') <> ALL(%s)
                GROUP BY 1, 2
                """,
                (account_db_id, since, list(_NON_REWARD_CATEGORIES))
            )
            rows = cur.fetchall()
    return [{"primary": r[0], "detailed": r[1], "total": float(r[2])} for r in rows]
