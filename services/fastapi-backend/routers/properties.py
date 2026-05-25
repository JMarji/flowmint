from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_pool
from auth_routes import get_current_user

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
        "equity": (float(r[6]) if r[6] else 0) - (float(r[8]) if r[8] else 0),
    }


@router.get("/properties")
def list_properties(current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, address, city, state, zip, purchase_price, current_value,
                          purchase_date, mortgage_balance, mortgage_rate, mortgage_payment,
                          notes, created_at
                   FROM flowmint.properties WHERE user_id = %s ORDER BY created_at DESC""",
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
                             notes, created_at""",
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
                """SELECT id, address, city, state, zip, purchase_price, current_value,
                          purchase_date, mortgage_balance, mortgage_rate, mortgage_payment,
                          notes, created_at
                   FROM flowmint.properties WHERE id = %s AND user_id = %s""",
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
