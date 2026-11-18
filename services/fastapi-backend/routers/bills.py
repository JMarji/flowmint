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
        # Set when the bill is auto-generated from a Plaid credit card (bank_accounts.id).
        "credit_account_db_id": r[9] if len(r) > 9 else None,
    }


@router.get("/bills")
def list_bills(current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT b.id, b.name, b.amount, b.due_day_of_month, b.category, b.is_active,
                          b.last_paid_date, b.notes, b.created_at, ba.id
                   FROM flowmint.bills b
                   LEFT JOIN flowmint.bank_accounts ba ON ba.account_id = b.credit_account_id
                   WHERE b.user_id = %s
                   ORDER BY b.due_day_of_month, b.name""",
                (current_user["id"],)
            )
            rows = cur.fetchall()
            cur.execute(
                """SELECT bp.id, bp.bill_id, bp.period, bp.source, t.id, t.date, t.amount,
                          COALESCE(t.merchant_name, t.name)
                   FROM flowmint.bill_payments bp
                   JOIN flowmint.bills b ON b.id = bp.bill_id
                   JOIN flowmint.transactions t ON t.id = bp.transaction_id
                   WHERE b.user_id = %s AND bp.status = 'matched' AND t.date >= %s
                   ORDER BY t.date DESC""",
                (current_user["id"], date.today() - timedelta(days=400))
            )
            payments: dict = {}
            for pid, bill_id, period, source, txn_id, d, amount, name in cur.fetchall():
                payments.setdefault(bill_id, []).append({
                    "id": pid, "period": period, "source": source, "transaction_id": txn_id,
                    "date": d.isoformat(), "amount": float(amount), "name": name,
                })
    bills = [_row_to_bill(r) for r in rows]
    for b in bills:
        b["payments"] = payments.get(b["id"], [])
    return bills


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


@router.delete("/bills/{bill_id}/payments/{payment_id}", status_code=204)
def reject_bill_payment(bill_id: int, payment_id: int, current_user: dict = Depends(get_current_user)):
    """'That transaction wasn't this bill' — unlink it and never auto-match that pair again."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE flowmint.bill_payments bp SET status = 'rejected'
                   FROM flowmint.bills b
                   WHERE bp.id = %s AND bp.bill_id = %s AND b.id = bp.bill_id AND b.user_id = %s
                     AND bp.status = 'matched'
                   RETURNING bp.transaction_id""",
                (payment_id, bill_id, current_user["id"])
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Payment not found")
            # If last_paid_date came from this transaction, fall back to the latest remaining match.
            cur.execute(
                """UPDATE flowmint.bills b SET last_paid_date = (
                       SELECT MAX(t.date) FROM flowmint.bill_payments bp
                       JOIN flowmint.transactions t ON t.id = bp.transaction_id
                       WHERE bp.bill_id = b.id AND bp.status = 'matched')
                   WHERE b.id = %s
                     AND b.last_paid_date = (SELECT date FROM flowmint.transactions WHERE id = %s)""",
                (bill_id, row[0])
            )
            conn.commit()


@router.delete("/bills/{bill_id}", status_code=204)
def delete_bill(bill_id: int, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.bills WHERE id = %s AND user_id = %s RETURNING credit_account_id",
                (bill_id, current_user["id"])
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Bill not found")
            if row[0]:
                # Deleting a card's auto-bill opts that card out, so the next sync doesn't recreate it.
                cur.execute(
                    """INSERT INTO flowmint.credit_card_settings (account_id, auto_bill)
                       VALUES (%s, FALSE)
                       ON CONFLICT (account_id) DO UPDATE SET auto_bill = FALSE, updated_at = NOW()""",
                    (row[0],)
                )
            conn.commit()
