import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
import db_plaid
import plaid_client as pc
from database import get_pool
from auth_routes import get_current_user

from plaid.model.liabilities_get_request import LiabilitiesGetRequest
from plaid.model.liabilities_get_request_options import LiabilitiesGetRequestOptions
from plaid.exceptions import ApiException

logger = logging.getLogger(__name__)
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


def _jsonable(v):
    if isinstance(v, date):
        return v.isoformat()
    return v


def _fetch_credit_liability(access_token: str, account_plaid_id: str) -> dict:
    """Live-fetch Plaid credit-card liability details + credit limit for one account.

    Returns {} if the item doesn't have the liabilities product or Plaid errors.
    """
    try:
        res = pc.get_plaid_client().liabilities_get(
            LiabilitiesGetRequest(
                access_token=access_token,
                options=LiabilitiesGetRequestOptions(account_ids=[account_plaid_id]),
            )
        ).to_dict()
    except ApiException as e:
        logger.warning("liabilities_get failed for account %s: %s", account_plaid_id, e)
        return {}

    out: dict = {}
    for acct in res.get("accounts") or []:
        if acct.get("account_id") == account_plaid_id:
            balances = acct.get("balances") or {}
            out["credit_limit"] = balances.get("limit")
            out["iso_currency_code"] = balances.get("iso_currency_code")

    for c in (res.get("liabilities") or {}).get("credit") or []:
        if c.get("account_id") != account_plaid_id:
            continue
        out.update({
            "is_overdue": c.get("is_overdue"),
            "last_payment_amount": c.get("last_payment_amount"),
            "last_payment_date": _jsonable(c.get("last_payment_date")),
            "last_statement_balance": c.get("last_statement_balance"),
            "last_statement_issue_date": _jsonable(c.get("last_statement_issue_date")),
            "minimum_payment_amount": c.get("minimum_payment_amount"),
            "next_payment_due_date": _jsonable(c.get("next_payment_due_date")),
            "aprs": [
                {
                    "apr_type": a.get("apr_type"),
                    "apr_percentage": a.get("apr_percentage"),
                    "balance_subject_to_apr": a.get("balance_subject_to_apr"),
                    "interest_charge_amount": a.get("interest_charge_amount"),
                }
                for a in (c.get("aprs") or [])
            ],
        })
    return out


@router.get("/accounts/{account_db_id}/credit")
def credit_account_detail(account_db_id: int, current_user: dict = Depends(get_current_user)):
    """Credit card detail: account info, live Plaid liability data, and spending summary."""
    acct = db_plaid.get_account_for_user(current_user["id"], account_db_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")

    access_token = acct.pop("access_token")
    liability = _fetch_credit_liability(access_token, acct["account_id"])
    spending = db_plaid.get_account_spending_summary(account_db_id)

    limit = liability.get("credit_limit")
    balance = acct.get("current_balance")
    utilization = (balance / limit * 100) if (limit and balance is not None) else None

    return {
        "account": acct,
        "liability": liability,
        "liability_available": bool(liability.get("aprs") is not None or liability.get("credit_limit") is not None),
        "utilization": utilization,
        "spending": spending,
    }
