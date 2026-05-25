from fastapi import APIRouter, Depends, HTTPException
import db_plaid
from auth_routes import get_current_user

router = APIRouter(tags=["accounts"])


@router.get("/accounts")
def list_accounts(current_user: dict = Depends(get_current_user)):
    """Return all linked bank accounts with cached balances."""
    accounts = db_plaid.get_accounts_for_user(current_user["id"])
    return accounts


@router.delete("/accounts/{item_db_id}")
def unlink_account(item_db_id: int, current_user: dict = Depends(get_current_user)):
    """Remove a linked bank institution (Plaid item) and all its accounts/transactions."""
    deleted = db_plaid.delete_bank_item(item_db_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"deleted": item_db_id}
