from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from typing import Optional
from database import get_pool
from auth_routes import get_current_user
import db_plaid
import plaid_client as pc
from routers.plaid import fetch_mortgage_liability

router = APIRouter(tags=["properties"])


class PropertyCreate(BaseModel):
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    purchase_price: Optional[float] = None
    current_value: Optional[float] = None
    purchase_date: Optional[str] = None
    mortgage_balance: Optional[float] = None
    mortgage_rate: Optional[float] = None
    mortgage_payment: Optional[float] = None
    notes: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def empty_str_to_none(cls, values):
        if isinstance(values, dict):
            return {k: (None if v == '' else v) for k, v in values.items()}
        return values


class PropertyUpdate(PropertyCreate):
    address: Optional[str] = None


def _row_to_property(r) -> dict:
    return {
        "id": r[0], "address": r[1], "city": r[2], "state": r[3], "zip": r[4],
        "purchase_price": float(r[5]) if r[5] else None,
        "current_value": float(r[6]) if r[6] else None,
        "purchase_date": str(r[7]) if r[7] else None,
        "mortgage_balance": float(r[8]) if r[8] else None,
        "mortgage_rate": float(r[9]) if r[9] else None,
        "mortgage_payment": float(r[10]) if r[10] else None,
        "notes": r[11],
        "created_at": r[12].isoformat(),
        "mortgage_account_id": r[13],
        "equity": (float(r[6]) if r[6] else 0) - (float(r[8]) if r[8] else 0),
    }


_SELECT = """SELECT id, address, city, state, zip, purchase_price, current_value,
                    purchase_date, mortgage_balance, mortgage_rate, mortgage_payment,
                    notes, created_at, mortgage_account_id"""


@router.get("/properties")
def list_properties(current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"{_SELECT} FROM flowmint.properties WHERE user_id = %s ORDER BY created_at DESC",
                (current_user["id"],)
            )
            rows = cur.fetchall()
    return [_row_to_property(r) for r in rows]


@router.post("/properties", status_code=201)
def create_property(body: PropertyCreate, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO flowmint.properties
                       (user_id, address, city, state, zip, purchase_price, current_value,
                        purchase_date, mortgage_balance, mortgage_rate, mortgage_payment, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id, address, city, state, zip, purchase_price, current_value,
                             purchase_date, mortgage_balance, mortgage_rate, mortgage_payment,
                             notes, created_at, mortgage_account_id""",
                (current_user["id"], body.address, body.city, body.state, body.zip,
                 body.purchase_price, body.current_value, body.purchase_date,
                 body.mortgage_balance, body.mortgage_rate, body.mortgage_payment, body.notes)
            )
            row = cur.fetchone()
            conn.commit()
    return _row_to_property(row)


@router.get("/properties/{property_id}")
def get_property(property_id: int, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"{_SELECT} FROM flowmint.properties WHERE id = %s AND user_id = %s",
                (property_id, current_user["id"])
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Property not found")
    return _row_to_property(row)


@router.put("/properties/{property_id}")
def update_property(property_id: int, body: PropertyUpdate, current_user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")
    cols = ", ".join(f"{k} = %s" for k in updates)
    vals = list(updates.values()) + [property_id, current_user["id"]]
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE flowmint.properties SET {cols} WHERE id = %s AND user_id = %s",
                vals
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Property not found")
            conn.commit()
    return get_property(property_id, current_user)


@router.delete("/properties/{property_id}", status_code=204)
def delete_property(property_id: int, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.properties WHERE id = %s AND user_id = %s",
                (property_id, current_user["id"])
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Property not found")
            conn.commit()


# ---------------------------------------------------------------------------
# Mortgage / Plaid linking
# ---------------------------------------------------------------------------

@router.get("/properties/mortgage-accounts")
def list_mortgage_accounts(current_user: dict = Depends(get_current_user)):
    """Return the user's Plaid loan-type accounts available to link as a mortgage."""
    return db_plaid.get_loan_accounts_for_user(current_user["id"])


class LinkMortgageBody(BaseModel):
    account_id: str


@router.post("/properties/{property_id}/link-mortgage")
def link_mortgage(property_id: int, body: LinkMortgageBody, current_user: dict = Depends(get_current_user)):
    """Link a Plaid loan account to this property and sync mortgage data."""
    # Verify property belongs to user
    prop = get_property(property_id, current_user)

    # Verify the account belongs to the user
    loan_accounts = db_plaid.get_loan_accounts_for_user(current_user["id"])
    if not any(a["account_id"] == body.account_id for a in loan_accounts):
        raise HTTPException(status_code=403, detail="Account not found or not accessible")

    # Fetch liability details from Plaid
    item = db_plaid.get_item_for_account(body.account_id)
    if not item:
        raise HTTPException(status_code=404, detail="Bank item not found")

    client = pc.get_plaid_client()
    liability = fetch_mortgage_liability(client, item["access_token"], body.account_id)

    # Build update: always set the link; sync numeric fields when available
    updates: dict = {"mortgage_account_id": body.account_id}

    # Balance from the account record (current_balance = outstanding loan balance)
    acct = next(a for a in loan_accounts if a["account_id"] == body.account_id)
    if acct["current_balance"] is not None:
        updates["mortgage_balance"] = acct["current_balance"]

    if liability:
        if liability["rate"] is not None:
            updates["mortgage_rate"] = liability["rate"]
        if liability["payment"] is not None:
            updates["mortgage_payment"] = liability["payment"]

    cols = ", ".join(f"{k} = %s" for k in updates)
    vals = list(updates.values()) + [property_id, current_user["id"]]
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE flowmint.properties SET {cols} WHERE id = %s AND user_id = %s",
                vals
            )
            conn.commit()

    return get_property(property_id, current_user)


@router.delete("/properties/{property_id}/link-mortgage", status_code=200)
def unlink_mortgage(property_id: int, current_user: dict = Depends(get_current_user)):
    """Remove the Plaid mortgage link from this property (keeps manual mortgage fields)."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flowmint.properties SET mortgage_account_id = NULL WHERE id = %s AND user_id = %s",
                (property_id, current_user["id"])
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Property not found")
            conn.commit()
    return get_property(property_id, current_user)


@router.post("/properties/{property_id}/sync-mortgage")
def sync_mortgage(property_id: int, current_user: dict = Depends(get_current_user)):
    """Re-fetch live mortgage data from Plaid for a linked property."""
    prop = get_property(property_id, current_user)
    if not prop.get("mortgage_account_id"):
        raise HTTPException(status_code=400, detail="No mortgage account linked")

    account_id = prop["mortgage_account_id"]
    loan_accounts = db_plaid.get_loan_accounts_for_user(current_user["id"])
    acct = next((a for a in loan_accounts if a["account_id"] == account_id), None)
    if not acct:
        raise HTTPException(status_code=404, detail="Linked account not found")

    item = db_plaid.get_item_for_account(account_id)
    if not item:
        raise HTTPException(status_code=404, detail="Bank item not found")

    client = pc.get_plaid_client()
    liability = fetch_mortgage_liability(client, item["access_token"], account_id)

    updates: dict = {}
    if acct["current_balance"] is not None:
        updates["mortgage_balance"] = acct["current_balance"]
    if liability:
        if liability["rate"] is not None:
            updates["mortgage_rate"] = liability["rate"]
        if liability["payment"] is not None:
            updates["mortgage_payment"] = liability["payment"]

    if updates:
        cols = ", ".join(f"{k} = %s" for k in updates)
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE flowmint.properties SET {cols} WHERE id = %s AND user_id = %s",
                    list(updates.values()) + [property_id, current_user["id"]]
                )
                conn.commit()

    return get_property(property_id, current_user)
