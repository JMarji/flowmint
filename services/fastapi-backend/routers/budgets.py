from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import date
from database import get_pool
from auth_routes import get_current_user

router = APIRouter(tags=["budgets"])


class BudgetCreate(BaseModel):
    category: str
    monthly_limit: float
    month_year: str  # "YYYY-MM"


class BudgetUpdate(BaseModel):
    monthly_limit: float


def _get_budgets_with_spend(user_id: int, month_year: str) -> list:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    b.id,
                    b.category,
                    b.monthly_limit,
                    b.month_year,
                    COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0) AS spent
                FROM flowmint.budgets b
                LEFT JOIN flowmint.transactions t ON (
                    COALESCE(t.category_override, t.category_primary) = b.category
                    AND TO_CHAR(t.date, 'YYYY-MM') = b.month_year
                    AND t.pending = FALSE
                    AND t.account_id IN (
                        SELECT ba.id FROM flowmint.bank_accounts ba
                        JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                        WHERE bi.user_id = b.user_id
                    )
                )
                WHERE b.user_id = %s AND b.month_year = %s
                GROUP BY b.id, b.category, b.monthly_limit, b.month_year
                ORDER BY b.category
                """,
                (user_id, month_year)
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "category": r[1],
            "monthly_limit": float(r[2]),
            "month_year": r[3],
            "spent": float(r[4]),
            "remaining": float(r[2]) - float(r[4]),
            "percent": round(float(r[4]) / float(r[2]) * 100, 1) if r[2] else 0,
        }
        for r in rows
    ]


@router.get("/budgets")
def list_budgets(
    month_year: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    my = month_year or date.today().strftime("%Y-%m")
    return _get_budgets_with_spend(current_user["id"], my)


@router.post("/budgets", status_code=201)
def create_budget(body: BudgetCreate, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO flowmint.budgets (user_id, category, monthly_limit, month_year)
                       VALUES (%s, %s, %s, %s) RETURNING id""",
                    (current_user["id"], body.category, body.monthly_limit, body.month_year)
                )
                budget_id = cur.fetchone()[0]
                conn.commit()
            except Exception:
                raise HTTPException(status_code=409, detail="Budget for this category/month already exists")
    return _get_budgets_with_spend(current_user["id"], body.month_year)[0] if False else {"id": budget_id, **body.model_dump()}


@router.put("/budgets/{budget_id}")
def update_budget(budget_id: int, body: BudgetUpdate, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flowmint.budgets SET monthly_limit = %s WHERE id = %s AND user_id = %s",
                (body.monthly_limit, budget_id, current_user["id"])
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Budget not found")
            conn.commit()
    return {"updated": budget_id}


@router.delete("/budgets/{budget_id}", status_code=204)
def delete_budget(budget_id: int, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.budgets WHERE id = %s AND user_id = %s",
                (budget_id, current_user["id"])
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Budget not found")
            conn.commit()
