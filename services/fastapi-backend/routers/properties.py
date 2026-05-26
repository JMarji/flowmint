from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, model_validator
from typing import Optional
from database import get_pool
from auth_routes import get_current_user
import json
import csv
import io
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


def _default_property_address_for_account(acct: dict) -> str:
    institution = (acct.get("institution_name") or "").strip()
    name = (acct.get("name") or "").strip()
    mask = (acct.get("mask") or "").strip()

    if institution and mask:
        return f"{institution} ****{mask}"
    if institution and name:
        return f"{institution} - {name}"
    if name and mask:
        return f"{name} ****{mask}"
    if name:
        return name
    if institution:
        return institution
    return "Connected Mortgage"


def _ensure_connected_mortgage_properties(user_id: int):
    loan_accounts = db_plaid.get_loan_accounts_for_user(user_id)
    if not loan_accounts:
        return

    mortgage_accounts = [a for a in loan_accounts if (a.get("subtype") or "").lower() == "mortgage"]
    non_mortgage_account_ids = [
        a.get("account_id") for a in loan_accounts
        if a.get("account_id") and (a.get("subtype") or "").lower() != "mortgage"
    ]

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            if non_mortgage_account_ids:
                cur.execute(
                    """DELETE FROM flowmint.properties
                       WHERE user_id = %s
                                                 AND mortgage_account_id = ANY(%s::text[])
                         AND notes LIKE 'Auto-created from connected mortgage account %%'""",
                    (user_id, non_mortgage_account_ids)
                )

            for acct in mortgage_accounts:
                account_id = acct.get("account_id")
                if not account_id:
                    continue

                balance = acct.get("current_balance")
                address = _default_property_address_for_account(acct)
                notes = f"Auto-created from connected mortgage account {account_id}"

                # Avoid duplicates when this account is already represented as a property.
                cur.execute(
                    """INSERT INTO flowmint.properties
                           (user_id, address, city, state, zip, purchase_price, current_value,
                            purchase_date, mortgage_balance, mortgage_rate, mortgage_payment,
                            notes, mortgage_account_id)
                       SELECT %s,%s,NULL,NULL,NULL,NULL,%s,NULL,%s,NULL,NULL,%s,%s
                       WHERE NOT EXISTS (
                           SELECT 1 FROM flowmint.properties
                           WHERE user_id = %s AND mortgage_account_id = %s
                       )""",
                    (
                        user_id,
                        address,
                        balance,
                        balance,
                        notes,
                        account_id,
                        user_id,
                        account_id,
                    )
                )
            conn.commit()


@router.get("/properties")
def list_properties(current_user: dict = Depends(get_current_user)):
    _ensure_connected_mortgage_properties(current_user["id"])

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


def _coalesce(*vals):
    for v in vals:
        if v is None:
            continue
        if isinstance(v, str):
            s = v.strip()
            if s:
                return s
            continue
        return v
    return None


def _extract_property_address(data: dict) -> dict:
    """
    Extract a property address from common servicer JSON formats.
    Supports Newrez PropertyAddress plus generic camel/snake-case keys.
    """
    addr_obj = data.get("PropertyAddress")
    if not isinstance(addr_obj, dict):
        addr_obj = data.get("propertyAddress")
    if not isinstance(addr_obj, dict):
        addr_obj = {}

    address1 = _coalesce(
        addr_obj.get("Address1"),
        addr_obj.get("address1"),
        data.get("Address1"),
        data.get("address1"),
        data.get("streetAddress"),
        data.get("street_address"),
        data.get("address"),
    )
    address2 = _coalesce(
        addr_obj.get("Address2"),
        addr_obj.get("address2"),
        data.get("Address2"),
        data.get("address2"),
    )

    address = None
    if address1 and address2:
        address = f"{address1} {address2}".strip()
    else:
        address = _coalesce(address1, address2)

    city = _coalesce(
        addr_obj.get("City"),
        addr_obj.get("city"),
        data.get("city"),
        data.get("City"),
    )
    state = _coalesce(
        addr_obj.get("StateId"),
        addr_obj.get("stateId"),
        addr_obj.get("state"),
        data.get("state"),
        data.get("State"),
        data.get("stateId"),
    )
    zip_code = _coalesce(
        addr_obj.get("ZipCode"),
        addr_obj.get("zipCode"),
        addr_obj.get("zip"),
        data.get("zip"),
        data.get("Zip"),
        data.get("postalCode"),
        data.get("postal_code"),
    )

    return {
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
    }


async def _read_json_object_upload(file: UploadFile) -> dict:
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")

    try:
        data = json.loads(contents.decode("utf-8-sig"))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse JSON: {e}")

    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Expected a JSON object, not an array")
    return data


@router.post("/properties/import-json", status_code=201)
async def create_property_from_json(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a property from a mortgage servicer JSON export.
    Address details are extracted when available; mortgage fields are mapped.
    """
    data = await _read_json_object_upload(file)
    address_data = _extract_property_address(data)

    if not address_data["address"]:
        raise HTTPException(
            status_code=422,
            detail="Could not determine property address. Expected PropertyAddress.Address1 or a top-level address field."
        )

    mapped = _map_json_to_mortgage(data)

    notes = None
    if data.get("LoanId"):
        notes = f"Imported from JSON (LoanId: {data['LoanId']})"

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
                (
                    current_user["id"],
                    address_data["address"],
                    address_data["city"],
                    address_data["state"],
                    address_data["zip"],
                    None,
                    None,
                    None,
                    mapped.get("balance"),
                    mapped.get("rate"),
                    mapped.get("payment"),
                    notes,
                )
            )
            row = cur.fetchone()
            conn.commit()

    summary = {
        "source_file": file.filename,
        "address": address_data,
        "mortgage_fields_imported": [
            k for k in ("balance", "rate", "payment") if mapped.get(k) is not None
        ],
    }

    return {"property": _row_to_property(row), "summary": summary}


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


# ---------------------------------------------------------------------------
# JSON import
# ---------------------------------------------------------------------------

def _map_json_to_mortgage(data: dict) -> dict:
    """
    Extract mortgage fields from a servicer JSON export.
    Handles Newrez format and generic camelCase / snake_case fallbacks.
    Returns a dict with keys: balance, rate, payment, and optional metadata.
    """
    result: dict = {}

    # ---- Newrez / common PascalCase servicer format ----
    if data.get("PrincipalBalance") is not None:
        result["balance"] = float(data["PrincipalBalance"])
    if data.get("InterestRate") is not None:
        r = float(data["InterestRate"])
        result["rate"] = round(r * 100, 4) if r < 1 else r
    for key in ("MonthlyPayment", "TotalPayment"):
        if data.get(key) is not None:
            result["payment"] = float(data[key])
            break

    # ---- Extra context fields (returned in summary, not persisted) ----
    for src, dst in [
        ("PIPayment", "pi_payment"),
        ("EscrowPayment", "escrow_payment"),
        ("LoanId", "loan_id"),
        ("MaturityDate", "maturity_date"),
        ("OriginalBalance", "original_balance"),
        ("LastPaymentDate", "last_payment_date"),
        ("PaymentDueDate", "payment_due_date"),
    ]:
        if data.get(src) is not None:
            result[dst] = data[src]

    # ---- Generic camelCase / snake_case fallbacks ----
    if "balance" not in result:
        for k in ("balance", "principalBalance", "principal_balance",
                  "outstandingBalance", "outstanding_balance",
                  "currentBalance", "current_balance", "loanBalance"):
            if data.get(k) is not None:
                result["balance"] = float(data[k])
                break
    if "rate" not in result:
        for k in ("interestRate", "interest_rate", "rate", "apr"):
            if data.get(k) is not None:
                r = float(data[k])
                result["rate"] = round(r * 100, 4) if r < 1 else r
                break
    if "payment" not in result:
        for k in ("monthlyPayment", "monthly_payment", "totalPayment",
                  "total_payment", "payment", "regularPayment"):
            if data.get(k) is not None:
                result["payment"] = float(data[k])
                break

    return result


@router.post("/properties/{property_id}/import-mortgage-json")
async def import_mortgage_json(
    property_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Import mortgage data from a servicer JSON export (e.g. Newrez).
    Updates mortgage_balance, mortgage_rate, and mortgage_payment.
    """
    if not _verify_property_csv_owner(property_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Property not found")

    data = await _read_json_object_upload(file)

    mapped = _map_json_to_mortgage(data)

    if not any(k in mapped for k in ("balance", "rate", "payment")):
        raise HTTPException(
            status_code=422,
            detail="No recognizable mortgage fields found. Expected keys like PrincipalBalance, InterestRate, MonthlyPayment."
        )

    prop_updates: dict = {}
    if "balance" in mapped:
        prop_updates["mortgage_balance"] = mapped["balance"]
    if "rate" in mapped:
        prop_updates["mortgage_rate"] = mapped["rate"]
    if "payment" in mapped:
        prop_updates["mortgage_payment"] = mapped["payment"]

    if prop_updates:
        cols = ", ".join(f"{k} = %s" for k in prop_updates)
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE flowmint.properties SET {cols} WHERE id = %s AND user_id = %s",
                    list(prop_updates.values()) + [property_id, current_user["id"]]
                )
                conn.commit()

    summary = {k: mapped[k] for k in (
        "balance", "rate", "payment", "pi_payment", "escrow_payment",
        "loan_id", "original_balance", "maturity_date",
        "last_payment_date", "payment_due_date",
    ) if k in mapped}

    return {
        "property": get_property(property_id, current_user),
        "fields_updated": list(prop_updates.keys()),
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

# Column aliases: map common export header names → internal field names
_COL_ALIASES = {
    "balance": "balance", "principal_balance": "balance", "outstanding_balance": "balance",
    "current_balance": "balance", "loan_balance": "balance",
    "payment": "payment", "amount": "payment", "total_payment": "payment",
    "monthly_payment": "payment", "payment_amount": "payment",
    "principal": "principal", "principal_paid": "principal",
    "interest": "interest", "interest_paid": "interest",
    "rate": "rate", "interest_rate": "rate", "apr": "rate",
    "date": "date", "payment_date": "date", "statement_date": "date",
}


def _normalize_headers(raw_headers: list) -> dict:
    """Return mapping of original CSV header → internal field name."""
    result = {}
    for h in raw_headers:
        normalized = h.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized in _COL_ALIASES:
            result[h.strip()] = _COL_ALIASES[normalized]
    return result


def _parse_float(val) -> Optional[float]:
    if not val:
        return None
    cleaned = str(val).strip().replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _verify_property_csv_owner(property_id: int, user_id: int) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM flowmint.properties WHERE id = %s AND user_id = %s",
                (property_id, user_id)
            )
            return cur.fetchone() is not None


@router.post("/properties/{property_id}/import-mortgage-csv")
async def import_mortgage_csv(
    property_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Import a mortgage statement CSV. Flexible column names are supported.

    Recognized columns: date, balance, payment, principal, interest, rate

    - Updates property mortgage_balance / mortgage_rate / mortgage_payment
      from the most recent row.
    - Creates a property_transaction (expense / mortgage) for each row that
      has a payment amount, skipping dates already recorded.
    """
    if not _verify_property_csv_owner(property_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Property not found")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")

    try:
        text = contents.decode("utf-8-sig")  # handles BOM from Excel exports
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise HTTPException(status_code=422, detail="CSV has no headers")

        col_map = _normalize_headers(list(reader.fieldnames))
        if "date" not in col_map.values():
            raise HTTPException(status_code=422, detail="CSV must have a 'date' column")
        if "balance" not in col_map.values():
            raise HTTPException(status_code=422, detail="CSV must have a 'balance' column")

        rows = []
        for raw in reader:
            mapped: dict = {}
            for raw_col, field in col_map.items():
                mapped[field] = raw.get(raw_col, "").strip()
            if mapped.get("date"):
                rows.append(mapped)

    except (UnicodeDecodeError, csv.Error) as e:
        raise HTTPException(status_code=422, detail=f"Could not parse CSV: {e}")

    if not rows:
        raise HTTPException(status_code=422, detail="CSV contains no data rows")

    rows.sort(key=lambda r: r.get("date", ""))
    latest = rows[-1]

    # Update property fields from most recent row
    prop_updates: dict = {}
    balance = _parse_float(latest.get("balance"))
    rate = _parse_float(latest.get("rate"))
    payment = _parse_float(latest.get("payment"))
    if balance is not None:
        prop_updates["mortgage_balance"] = balance
    if rate is not None:
        prop_updates["mortgage_rate"] = rate
    if payment is not None:
        prop_updates["mortgage_payment"] = payment

    if prop_updates:
        cols = ", ".join(f"{k} = %s" for k in prop_updates)
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE flowmint.properties SET {cols} WHERE id = %s AND user_id = %s",
                    list(prop_updates.values()) + [property_id, current_user["id"]]
                )
                conn.commit()

    # Import payment transactions, skipping already-recorded dates
    imported = 0
    skipped = 0

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT date FROM flowmint.property_transactions
                   WHERE property_id = %s AND category = 'mortgage' AND type = 'expense'""",
                (property_id,)
            )
            existing_dates = {str(r[0]) for r in cur.fetchall()}

            for row in rows:
                pmt = _parse_float(row.get("payment"))
                date_str = row.get("date", "").strip()
                if not pmt or not date_str:
                    continue
                if date_str in existing_dates:
                    skipped += 1
                    continue

                principal = _parse_float(row.get("principal"))
                interest = _parse_float(row.get("interest"))
                if principal is not None and interest is not None:
                    desc = f"Principal ${principal:,.2f} · Interest ${interest:,.2f}"
                else:
                    desc = None

                cur.execute(
                    """INSERT INTO flowmint.property_transactions
                           (property_id, type, amount, date, category, description)
                       VALUES (%s, 'expense', %s, %s, 'mortgage', %s)""",
                    (property_id, pmt, date_str, desc)
                )
                existing_dates.add(date_str)
                imported += 1

            conn.commit()

    return {
        "property": get_property(property_id, current_user),
        "imported": imported,
        "skipped": skipped,
        "rows_parsed": len(rows),
    }
