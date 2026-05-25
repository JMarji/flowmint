from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date, timedelta
from database import get_pool
from auth_routes import get_current_user

router = APIRouter(tags=["bills"])


class BillCreate(BaseModel):
    name: str
    amount: float
    due_day_of_month: int
    category: Optional[str] = None
    notes: Optional[str] = None


class BillUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    due_day_of_month: Optional[int] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class MarkPaidBody(BaseModel):
    paid_date: Optional[str] = None  # ISO date string; defaults to today


def _next_due(due_day: int) -> str:
    today = date.today()
    try:
        candidate = today.replace(day=due_day)
    except ValueError:
        # day > last day of month → use last day
        import calendar
        last = calendar.monthrange(today.year, today.month)[1]
        candidate = today.replace(day=last)
    if candidate < today:
        # advance to next month
        if today.month == 12:
            candidate = candidate.replace(year=today.year + 1, month=1)
        else:
            candidate = candidate.replace(month=today.month + 1)
    return candidate.isoformat()


def _row_to_bill(r) -> dict:
    return {
        "id": r[0], "name": r[1], "amount": float(r[2]),
        "due_day_of_month": r[3], "category": r[4],
        "is_active": r[5], "last_paid_date": str(r[6]) if r[6] else None,
        "notes": r[7], "created_at": r[8].isoformat(),
        "next_due": _next_due(r[3]),
    }


@router.get("/bills")
def list_bills(current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, name, amount, due_day_of_month, category, is_active,
                          last_paid_date, notes, created_at
                   FROM flowmint.bills
                   WHERE user_id = %s
                   ORDER BY due_day_of_month, name""",
                (current_user["id"],)
            )
            rows = cur.fetchall()
    return [_row_to_bill(r) for r in rows]


@router.post("/bills", status_code=201)
def create_bill(body: BillCreate, current_user: dict = Depends(get_current_user)):
    if not (1 <= body.due_day_of_month <= 31):
        raise HTTPException(status_code=422, detail="due_day_of_month must be 1–31")
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO flowmint.bills
                       (user_id, name, amount, due_day_of_month, category, notes)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id, name, amount, due_day_of_month, category,
                             is_active, last_paid_date, notes, created_at""",
                (current_user["id"], body.name, body.amount,
                 body.due_day_of_month, body.category, body.notes)
            )
            row = cur.fetchone()
            conn.commit()
    return _row_to_bill(row)


@router.put("/bills/{bill_id}")
def update_bill(bill_id: int, body: BillUpdate, current_user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")
    cols = ", ".join(f"{k} = %s" for k in updates)
    vals = list(updates.values()) + [bill_id, current_user["id"]]
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE flowmint.bills SET {cols} WHERE id = %s AND user_id = %s",
                vals
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Bill not found")
            conn.commit()
    return {"updated": bill_id}


@router.post("/bills/{bill_id}/mark-paid")
def mark_paid(bill_id: int, body: MarkPaidBody, current_user: dict = Depends(get_current_user)):
    paid_date = body.paid_date or date.today().isoformat()
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flowmint.bills SET last_paid_date = %s WHERE id = %s AND user_id = %s",
                (paid_date, bill_id, current_user["id"])
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Bill not found")
            conn.commit()
    return {"bill_id": bill_id, "paid_date": paid_date}


@router.delete("/bills/{bill_id}", status_code=204)
def delete_bill(bill_id: int, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.bills WHERE id = %s AND user_id = %s",
                (bill_id, current_user["id"])
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Bill not found")
            conn.commit()
