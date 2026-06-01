from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
import db_plaid
from auth_routes import get_current_user

router = APIRouter(tags=["transactions"])


class CategoryOverride(BaseModel):
    category: str


@router.get("/transactions")
def list_transactions(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    account_id: Optional[int] = Query(None, ge=1),
    category: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Return paginated transactions with optional filters."""
    return db_plaid.get_transactions_for_user(
        user_id=current_user["id"],
        limit=limit,
        offset=offset,
        account_id=account_id,
        category=category,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/transactions/vendors-summary")
def vendor_summary(
    account_id: Optional[int] = Query(None, ge=1),
    category: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    top_n: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    """Return vendor-level spend aggregates across all filtered transactions."""
    return db_plaid.get_vendor_summary_for_user(
        user_id=current_user["id"],
        account_id=account_id,
        category=category,
        start_date=start_date,
        end_date=end_date,
        search=search,
        top_n=top_n,
    )


@router.patch("/transactions/{txn_id}/category")
def override_category(txn_id: int, body: CategoryOverride, current_user: dict = Depends(get_current_user)):
    updated = db_plaid.override_transaction_category(txn_id, current_user["id"], body.category)
    if not updated:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"updated": txn_id}
