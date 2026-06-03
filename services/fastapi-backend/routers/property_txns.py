from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from database import get_pool
from auth_routes import get_current_user

router = APIRouter(tags=["property-transactions"])


class PropertyTxnCreate(BaseModel):
    type: str  # "income" | "expense"
    amount: float
    date: str
    category: Optional[str] = None
    description: Optional[str] = None


def _verify_property_owner(property_id: int, user_id: int) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM flowmint.properties WHERE id = %s AND user_id = %s",
                (property_id, user_id)
            )
            return cur.fetchone() is not None


@router.get("/properties/{property_id}/transactions")
def list_property_transactions(
    property_id: int,
    txn_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    if not _verify_property_owner(property_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Property not found")

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, type, amount, date, category, description, created_at
                   FROM flowmint.property_transactions
                   WHERE property_id = %s""",
                (property_id,)
            )
            manual_rows = cur.fetchall()

            cur.execute(
                """
                SELECT t.id,
                       t.amount,
                       t.date,
                       COALESCE(NULLIF(TRIM(COALESCE(t.merchant_name, t.name, '')), ''), 'Linked mortgage payment') AS label,
                       COALESCE(t.category_override, t.category_primary) AS category,
                       t.synced_at,
                       ba.name,
                       bi.institution_name
                FROM flowmint.transactions t
                JOIN flowmint.bank_accounts ba ON t.account_id = ba.id
                JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                WHERE t.mortgage_property_id = %s
                  AND bi.user_id = %s
                ORDER BY t.date DESC, t.id DESC
                """,
                (property_id, current_user["id"])
            )
            linked_rows = cur.fetchall()

    txns = []

    for row in manual_rows:
        txns.append(
            {
                "id": row[0],
                "type": row[1],
                "amount": float(row[2]),
                "date": str(row[3]),
                "category": row[4],
                "description": row[5],
                "created_at": row[6].isoformat(),
                "source": "property_transaction",
            }
        )

    for row in linked_rows:
        amount = float(row[1]) if row[1] is not None else 0.0
        linked_type = "expense" if amount >= 0 else "income"
        txns.append(
            {
                "id": f"linked-{row[0]}",
                "type": linked_type,
                "amount": abs(amount),
                "date": str(row[2]),
                "category": row[4] or "MORTGAGE_PAYMENT",
                "description": f"{row[3]} ({row[7] or row[6] or 'Linked account'})",
                "created_at": row[5].isoformat() if row[5] else None,
                "source": "linked_transaction",
            }
        )

    if txn_type:
        txns = [t for t in txns if t["type"] == txn_type]

    txns.sort(key=lambda t: (t["date"], str(t["id"])), reverse=True)
    total = len(txns)
    paged = txns[offset:offset + limit]

    income = sum(t["amount"] for t in txns if t["type"] == "income")
    expenses = sum(t["amount"] for t in txns if t["type"] == "expense")

    return {
        "transactions": paged,
        "total": total,
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
    }


@router.post("/properties/{property_id}/transactions", status_code=201)
def create_property_transaction(
    property_id: int,
    body: PropertyTxnCreate,
    current_user: dict = Depends(get_current_user)
):
    if not _verify_property_owner(property_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Property not found")
    if body.type not in ("income", "expense"):
        raise HTTPException(status_code=422, detail="type must be 'income' or 'expense'")

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO flowmint.property_transactions
                       (property_id, type, amount, date, category, description)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id, type, amount, date, category, description, created_at""",
                (property_id, body.type, body.amount, body.date, body.category, body.description)
            )
            row = cur.fetchone()
            conn.commit()
    return {
        "id": row[0], "type": row[1], "amount": float(row[2]),
        "date": str(row[3]), "category": row[4], "description": row[5],
        "created_at": row[6].isoformat(),
    }


@router.delete("/properties/{property_id}/transactions/{txn_id}", status_code=204)
def delete_property_transaction(
    property_id: int,
    txn_id: int,
    current_user: dict = Depends(get_current_user)
):
    if not _verify_property_owner(property_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Property not found")
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.property_transactions WHERE id = %s AND property_id = %s",
                (txn_id, property_id)
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Transaction not found")
            conn.commit()
