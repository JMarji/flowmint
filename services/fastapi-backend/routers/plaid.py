import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db_plaid
import plaid_client as pc
from auth_routes import get_current_user

from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.liabilities_get_request import LiabilitiesGetRequest
from plaid.exceptions import ApiException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["plaid"])


class ExchangeBody(BaseModel):
    public_token: str


@router.get("/plaid/link-token")
def create_link_token(current_user: dict = Depends(get_current_user)):
    """Create a Plaid Link token to initialize the Link flow in the browser."""
    client = pc.get_plaid_client()
    try:
        request = LinkTokenCreateRequest(
            products=[Products("transactions"), Products("liabilities")],
            client_name="Flowmint",
            country_codes=[CountryCode("US")],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=str(current_user["id"]))
        )
        response = client.link_token_create(request)
        return {"link_token": response["link_token"]}
    except ApiException as e:
        logger.error("Plaid link_token_create error: %s", e)
        raise HTTPException(status_code=502, detail="Failed to create Plaid link token")


@router.post("/plaid/exchange")
def exchange_public_token(body: ExchangeBody, current_user: dict = Depends(get_current_user)):
    """Exchange a public_token for a permanent access_token, then seed accounts and transactions."""
    client = pc.get_plaid_client()
    user_id = current_user["id"]

    try:
        # Exchange
        exchange_req = ItemPublicTokenExchangeRequest(public_token=body.public_token)
        exchange_res = client.item_public_token_exchange(exchange_req)
        access_token = exchange_res["access_token"]
        item_id = exchange_res["item_id"]

        # Fetch institution name
        institution_name, institution_id = None, None
        try:
            item_res = client.item_get(ItemGetRequest(access_token=access_token))
            institution_id = item_res["item"]["institution_id"]
            if institution_id:
                inst_res = client.institutions_get_by_id(
                    InstitutionsGetByIdRequest(
                        institution_id=institution_id,
                        country_codes=[CountryCode("US")]
                    )
                )
                institution_name = inst_res["institution"]["name"]
        except ApiException:
            pass  # institution name is optional

        # Persist item
        item_db_id = db_plaid.upsert_bank_item(
            user_id, item_id, access_token, institution_name, institution_id
        )

        # Seed accounts with real-time balances
        _sync_accounts(client, access_token, item_db_id)

        # Seed initial transactions
        _sync_transactions(client, access_token, item_db_id)

        # Sync liabilities for any properties already linked to accounts from this item
        _sync_liabilities_for_item(client, access_token)

        return {"status": "linked", "institution": institution_name}

    except ApiException as e:
        logger.error("Plaid exchange error: %s", e)
        raise HTTPException(status_code=502, detail="Failed to link bank account")


@router.post("/plaid/sync")
def sync(current_user: dict = Depends(get_current_user)):
    """Sync all linked accounts and pull new/modified/removed transactions."""
    client = pc.get_plaid_client()
    user_id = current_user["id"]
    items = db_plaid.get_all_items_for_user(user_id)
    if not items:
        return {"synced": 0, "items": 0}

    total_added = 0
    for item in items:
        try:
            _sync_accounts(client, item["access_token"], item["id"])
            added = _sync_transactions(client, item["access_token"], item["id"], cursor=item["cursor"])
            _sync_liabilities_for_item(client, item["access_token"])
            total_added += added
        except ApiException as e:
            logger.error("Sync failed for item %s: %s", item["item_id"], e)

    return {"synced": total_added, "items": len(items)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sync_accounts(client, access_token: str, item_db_id: int):
    """Refresh account balances from Plaid and upsert into DB."""
    balance_res = client.accounts_balance_get(AccountsBalanceGetRequest(access_token=access_token))
    for acct in balance_res["accounts"]:
        balances = acct.get("balances", {})
        db_plaid.upsert_bank_account(
            item_db_id=item_db_id,
            account_id=acct["account_id"],
            name=acct["name"],
            acct_type=str(acct.get("type", "")),
            subtype=str(acct.get("subtype", "")),
            mask=acct.get("mask"),
            current_balance=balances.get("current"),
            available_balance=balances.get("available"),
        )


def _sync_transactions(client, access_token: str, item_db_id: int, cursor: str = None) -> int:
    """Pull all new/modified/removed transactions using /transactions/sync. Returns added count."""
    added_total = 0
    current_cursor = cursor

    while True:
        kwargs = {"access_token": access_token}
        if current_cursor:
            kwargs["cursor"] = current_cursor

        response = client.transactions_sync(TransactionsSyncRequest(**kwargs))

        added = [_plaid_txn_to_dict(t) for t in (response.get("added") or [])]
        modified = [_plaid_txn_to_dict(t) for t in (response.get("modified") or [])]
        removed_ids = [r["transaction_id"] for r in (response.get("removed") or [])]

        db_plaid.upsert_transactions(added + modified)
        db_plaid.remove_transactions(removed_ids)

        added_total += len(added)
        current_cursor = response.get("next_cursor", "")

        if not response.get("has_more"):
            break

    if current_cursor:
        db_plaid.update_item_cursor(item_db_id, current_cursor)

    return added_total


def fetch_mortgage_liability(client, access_token: str, account_plaid_id: str) -> dict | None:
    """Return rate/payment/balance for a specific mortgage account, or None if unavailable."""
    try:
        res = client.liabilities_get(LiabilitiesGetRequest(access_token=access_token))
        mortgages = res.liabilities.mortgage or []
        for m in mortgages:
            if m.account_id == account_plaid_id:
                rate = None
                if m.interest_rate and m.interest_rate.percentage is not None:
                    rate = float(m.interest_rate.percentage)
                payment = float(m.next_monthly_payment) if m.next_monthly_payment is not None else None
                balance = float(m.origination_principal_amount) if m.origination_principal_amount is not None else None
                return {"rate": rate, "payment": payment, "balance": balance}
    except ApiException as e:
        logger.warning("liabilities_get failed for account %s: %s", account_plaid_id, e)
    return None


def _sync_liabilities_for_item(client, access_token: str):
    """Update mortgage fields on any properties linked to accounts from this item."""
    from database import get_pool
    try:
        res = client.liabilities_get(LiabilitiesGetRequest(access_token=access_token))
        mortgages = res.liabilities.mortgage or []
    except ApiException:
        return  # item may not have liabilities product enabled

    for m in mortgages:
        property_ids = db_plaid.get_properties_linked_to_account(m.account_id)
        if not property_ids:
            continue
        rate = float(m.interest_rate.percentage) if (m.interest_rate and m.interest_rate.percentage is not None) else None
        payment = float(m.next_monthly_payment) if m.next_monthly_payment is not None else None
        # Balance comes from the account's current_balance (updated by _sync_accounts)
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT current_balance FROM flowmint.bank_accounts WHERE account_id = %s",
                    (m.account_id,)
                )
                row = cur.fetchone()
                balance = float(row[0]) if row and row[0] is not None else None

                for prop_id in property_ids:
                    updates = {}
                    if balance is not None:
                        updates["mortgage_balance"] = balance
                    if rate is not None:
                        updates["mortgage_rate"] = rate
                    if payment is not None:
                        updates["mortgage_payment"] = payment
                    if updates:
                        cols = ", ".join(f"{k} = %s" for k in updates)
                        cur.execute(
                            f"UPDATE flowmint.properties SET {cols} WHERE id = %s",
                            list(updates.values()) + [prop_id]
                        )
            conn.commit()


def _plaid_txn_to_dict(t) -> dict:
    """Normalize a Plaid Transaction object to a plain dict for db_plaid."""
    pfc = getattr(t, "personal_finance_category", None) or {}
    if hasattr(pfc, "primary"):
        pfc = {"primary": pfc.primary, "detailed": pfc.detailed}
    return {
        "transaction_id": t["transaction_id"],
        "account_id": t["account_id"],
        "amount": t["amount"],
        "date": t["date"],
        "name": t.get("name"),
        "merchant_name": t.get("merchant_name"),
        "personal_finance_category": pfc,
        "pending": t.get("pending", False),
        "logo_url": t.get("logo_url"),
    }
