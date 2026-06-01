from typing import Optional, List, Dict, Any
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
) -> Dict[str, Any]:
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

    where = " AND ".join(conditions)

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            # Total count
            cur.execute(
                f"""SELECT COUNT(*)
                    FROM flowmint.transactions t
                    JOIN flowmint.bank_accounts ba ON t.account_id = ba.id
                    JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                    WHERE {where}""",
                params
            )
            total = cur.fetchone()[0]

            # Paginated rows
            cur.execute(
                f"""
                SELECT t.id, t.txn_id, t.amount, t.date, t.name, t.merchant_name,
                       COALESCE(t.category_override, t.category_primary) AS category,
                       t.category_primary, t.category_detailed, t.category_override,
                       t.pending, t.logo_url, t.synced_at,
                       ba.name AS account_name, bi.institution_name
                FROM flowmint.transactions t
                JOIN flowmint.bank_accounts ba ON t.account_id = ba.id
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
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
        }
        for r in rows
    ]
    return {"transactions": txns, "total": total}


def override_transaction_category(txn_id: int, user_id: int, category: str) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE flowmint.transactions t
                SET category_override = %s
                FROM flowmint.bank_accounts ba
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE t.id = %s AND t.account_id = ba.id AND bi.user_id = %s
                """,
                (category, txn_id, user_id)
            )
            affected = cur.rowcount
            conn.commit()
            return affected > 0
