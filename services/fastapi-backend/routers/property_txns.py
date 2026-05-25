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

    conditions = ["property_id = %s"]
    params: list = [property_id]
    if txn_type:
        conditions.append("type = %s")
        params.append(txn_type)

    where = " AND ".join(conditions)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT COUNT(*) FROM flowmint.property_transactions WHERE {where}""",
                params
            )
            total = cur.fetchone()[0]
            cur.execute(
                f"""SELECT id, type, amount, date, category, description, created_at
                    FROM flowmint.property_transactions
                    WHERE {where}
                    ORDER BY date DESC, id DESC
                    LIMIT %s OFFSET %s""",
                params + [limit, offset]
            )
            rows = cur.fetchall()

    txns = [
        {
            "id": r[0], "type": r[1], "amount": float(r[2]),
            "date": str(r[3]), "category": r[4], "description": r[5],
            "created_at": r[6].isoformat(),
        }
        for r in rows
    ]
    # Monthly summary
    income = sum(t["amount"] for t in txns if t["type"] == "income")
    expenses = sum(t["amount"] for t in txns if t["type"] == "expense")
    return {"transactions": txns, "total": total, "income": income, "expenses": expenses, "net": income - expenses}


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
