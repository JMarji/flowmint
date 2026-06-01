from fastapi import APIRouter, Depends, HTTPException
import db_plaid
from database import get_pool
from auth_routes import get_current_user

router = APIRouter(tags=["accounts"])


def _property_mortgage_accounts(user_id: int):
    """Project unlinked property mortgages into account-shaped rows for the Accounts UI."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, address, mortgage_balance, created_at
                   FROM flowmint.properties
                   WHERE user_id = %s
                     AND mortgage_account_id IS NULL
                     AND (
                       mortgage_balance IS NOT NULL
                       OR mortgage_payment IS NOT NULL
                       OR mortgage_rate IS NOT NULL
                     )
                   ORDER BY created_at DESC""",
                (user_id,)
            )
            rows = cur.fetchall()

    projected = []
    for r in rows:
        prop_id = r[0]
        address = r[1]
        balance = float(r[2]) if r[2] is not None else None
        created_at = r[3].isoformat() if r[3] else None
        projected.append(
            {
                "id": f"property-mortgage-{prop_id}",
                "account_id": f"property-mortgage-{prop_id}",
                "name": address or f"Property {prop_id}",
                "type": "loan",
                "subtype": "mortgage",
                "mask": str(prop_id).zfill(4)[-4:],
                "current_balance": balance,
                "available_balance": None,
                "updated_at": created_at,
                "institution_name": "Property Mortgages",
                "item_db_id": None,
            }
        )
    return projected


@router.get("/accounts")
def list_accounts(current_user: dict = Depends(get_current_user)):
    """Return all linked bank accounts with cached balances."""
    accounts = db_plaid.get_accounts_for_user(current_user["id"])
    accounts.extend(_property_mortgage_accounts(current_user["id"]))
    return accounts


@router.delete("/accounts/{item_db_id}")
def unlink_account(item_db_id: int, current_user: dict = Depends(get_current_user)):
    """Remove a linked bank institution (Plaid item) and all its accounts/transactions."""
    deleted = db_plaid.delete_bank_item(item_db_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"deleted": item_db_id}
