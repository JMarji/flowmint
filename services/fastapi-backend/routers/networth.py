from fastapi import APIRouter, Depends
from datetime import date
from database import get_pool
from auth_routes import get_current_user

router = APIRouter(tags=["networth"])


def _compute_networth(user_id: int) -> dict:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            # Liquid assets: sum of depository/investment account balances (positive only)
            cur.execute(
                """SELECT COALESCE(SUM(ba.current_balance), 0)
                   FROM flowmint.bank_accounts ba
                   JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                   WHERE bi.user_id = %s
                     AND ba.current_balance > 0
                     AND ba.type IN ('depository', 'investment', 'brokerage')""",
                (user_id,)
            )
            liquid_assets = float(cur.fetchone()[0])

            # Liabilities: credit + loan account balances (stored as positive by Plaid)
            cur.execute(
                """SELECT COALESCE(SUM(ba.current_balance), 0)
                   FROM flowmint.bank_accounts ba
                   JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                   WHERE bi.user_id = %s
                     AND ba.type IN ('credit', 'loan')
                     AND ba.current_balance > 0""",
                (user_id,)
            )
            debt_from_accounts = float(cur.fetchone()[0])

            # Property equity
            cur.execute(
                """SELECT
                       COALESCE(SUM(current_value), 0),
                       COALESCE(SUM(mortgage_balance), 0)
                   FROM flowmint.properties WHERE user_id = %s""",
                (user_id,)
            )
            row = cur.fetchone()
            total_property_value = float(row[0])
            total_mortgage = float(row[1])
            property_equity = total_property_value - total_mortgage

    total_liabilities = debt_from_accounts + total_mortgage
    net_worth = liquid_assets + property_equity - debt_from_accounts

    return {
        "liquid_assets": round(liquid_assets, 2),
        "property_equity": round(property_equity, 2),
        "total_property_value": round(total_property_value, 2),
        "total_mortgage": round(total_mortgage, 2),
        "total_liabilities": round(total_liabilities, 2),
        "debt_from_accounts": round(debt_from_accounts, 2),
        "net_worth": round(net_worth, 2),
    }


@router.get("/networth")
def get_networth(current_user: dict = Depends(get_current_user)):
    return _compute_networth(current_user["id"])


@router.post("/networth/snapshot")
def take_snapshot(current_user: dict = Depends(get_current_user)):
    data = _compute_networth(current_user["id"])
    today = date.today()
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO flowmint.networth_snapshots
                       (user_id, snapshot_date, liquid_assets, property_equity,
                        total_liabilities, net_worth)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id, snapshot_date) DO UPDATE SET
                       liquid_assets = EXCLUDED.liquid_assets,
                       property_equity = EXCLUDED.property_equity,
                       total_liabilities = EXCLUDED.total_liabilities,
                       net_worth = EXCLUDED.net_worth
                   RETURNING id""",
                (current_user["id"], today, data["liquid_assets"],
                 data["property_equity"], data["total_liabilities"], data["net_worth"])
            )
            conn.commit()
    return {"snapshot_date": today.isoformat(), **data}


@router.get("/networth/history")
def get_networth_history(current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT snapshot_date, liquid_assets, property_equity,
                          total_liabilities, net_worth
                   FROM flowmint.networth_snapshots
                   WHERE user_id = %s
                   ORDER BY snapshot_date ASC
                   LIMIT 365""",
                (current_user["id"],)
            )
            rows = cur.fetchall()
    return [
        {
            "date": str(r[0]),
            "liquid_assets": float(r[1]) if r[1] else 0,
            "property_equity": float(r[2]) if r[2] else 0,
            "total_liabilities": float(r[3]) if r[3] else 0,
            "net_worth": float(r[4]) if r[4] else 0,
        }
        for r in rows
    ]
