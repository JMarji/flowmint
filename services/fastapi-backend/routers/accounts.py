import calendar
import logging
from datetime import date, timedelta
from typing import Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import cancel_directory
import db_plaid
import db_subscriptions
import plaid_client as pc
from database import get_pool
from auth_routes import get_current_user

from plaid.model.liabilities_get_request import LiabilitiesGetRequest
from plaid.model.liabilities_get_request_options import LiabilitiesGetRequestOptions
from plaid.model.transactions_recurring_get_request import TransactionsRecurringGetRequest

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



# ---------------------------------------------------------------------------
# Credit cards
# ---------------------------------------------------------------------------

class CreditSettingsBody(BaseModel):
    network: Optional[Literal["visa", "mastercard", "amex", "discover", "other"]] = None
    product_name: Optional[str] = Field(None, max_length=80)
    annual_fee: Optional[float] = Field(None, ge=0)
    annual_fee_month: Optional[int] = Field(None, ge=1, le=12)
    reward_type: Optional[Literal["cashback", "points"]] = None
    point_value_cents: Optional[float] = Field(None, ge=0, le=100)
    base_reward_rate: Optional[float] = Field(None, ge=0, le=100)
    category_rates: Optional[Dict[str, float]] = None
    auto_bill: Optional[bool] = None
    bill_amount_mode: Optional[Literal["statement", "minimum"]] = None


def _get_credit_account(user_id: int, account_db_id: int) -> dict:
    acct = db_plaid.get_account_for_user(user_id, account_db_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    if (acct.get("type") or "").lower() != "credit":
        raise HTTPException(status_code=400, detail="Not a credit account")
    return acct


def _refresh_credit_liability(access_token: str, account_plaid_id: str):
    """Live-fetch liabilities for one account and persist them. Used when nothing is stored yet."""
    try:
        res = pc.get_plaid_client().liabilities_get(
            LiabilitiesGetRequest(
                access_token=access_token,
                options=LiabilitiesGetRequestOptions(account_ids=[account_plaid_id]),
            )
        ).to_dict()
    except Exception as e:  # Plaid API/network errors must not break the page; it renders without liability data
        logger.warning("liabilities_get failed for account %s: %s", account_plaid_id, e)
        return
    for acct_id in db_plaid.store_credit_liabilities(res):
        db_plaid.sync_credit_bill(acct_id)


def _add_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def _statement_cycle(liability: dict) -> dict:
    """Current billing cycle. Uses the last statement date when Plaid has one, else the calendar month."""
    today = date.today()
    issued = liability.get("last_statement_issue_date")
    if issued:
        last_close = date.fromisoformat(issued)
        next_close = _add_month(last_close)
        while next_close < today:  # stale statement data — roll forward
            last_close, next_close = next_close, _add_month(next_close)
        start, source = last_close + timedelta(days=1), "statement"
    else:
        start = today.replace(day=1)
        next_close = _add_month(start) - timedelta(days=1)
        source = "calendar"
    return {
        "start": start.isoformat(),
        "next_close": next_close.isoformat(),
        "days_left": (next_close - today).days,
        "days_total": (next_close - start).days + 1,
        "source": source,
    }


def _reward_rate(settings: dict, primary: Optional[str], detailed: Optional[str]) -> float:
    rates = settings.get("category_rates") or {}
    if detailed and detailed in rates:
        return rates[detailed]
    if primary and primary in rates:
        return rates[primary]
    return settings.get("base_reward_rate") or 0.0


def _estimate_rewards(settings: dict, rows: list) -> dict:
    """cashback: rate is a percent. points: rate is points per dollar, valued at point_value_cents."""
    by_cat: Dict[str, dict] = {}
    total_value = 0.0
    total_points = 0.0
    for r in rows:
        rate = _reward_rate(settings, r["primary"], r["detailed"])
        if settings["reward_type"] == "points":
            pts = r["total"] * rate
            value = pts * (settings.get("point_value_cents") or 1.0) / 100
            total_points += pts
        else:
            value = r["total"] * rate / 100
        total_value += value
        bucket = by_cat.setdefault(r["primary"], {"category": r["primary"], "spend": 0.0, "value": 0.0})
        bucket["spend"] += r["total"]
        bucket["value"] += value
    return {
        "value": round(total_value, 2),
        "points": round(total_points) if settings["reward_type"] == "points" else None,
        "by_category": sorted(by_cat.values(), key=lambda b: b["value"], reverse=True),
    }


@router.get("/accounts/{account_db_id}/credit")
def credit_account_detail(account_db_id: int, current_user: dict = Depends(get_current_user)):
    """Credit card detail: stored Plaid liability data, cycle, rewards, history, and spending."""
    acct = _get_credit_account(current_user["id"], account_db_id)
    access_token = acct.pop("access_token")
    plaid_id = acct["account_id"]

    liability = db_plaid.get_credit_liability(plaid_id)
    if liability is None:
        _refresh_credit_liability(access_token, plaid_id)
        liability = db_plaid.get_credit_liability(plaid_id)
    liability_available = liability is not None
    liability = liability or {}

    settings = db_plaid.get_credit_settings(plaid_id)
    history = db_plaid.get_balance_history(plaid_id)

    limit = liability.get("credit_limit")
    if limit is None:  # fall back to the limit captured with balance snapshots
        limit = next((h["limit"] for h in reversed(history) if h["limit"] is not None), None)
        liability["credit_limit"] = limit
    balance = acct.get("current_balance")
    utilization = (balance / limit * 100) if (limit and balance is not None) else None

    cycle = _statement_cycle(liability)
    cycle.update(db_plaid.get_cycle_activity(account_db_id, cycle["start"]))

    year_ago = (date.today() - timedelta(days=365)).isoformat()
    rewards_12m = _estimate_rewards(settings, db_plaid.get_reward_eligible_spend(account_db_id, year_ago))
    rewards_cycle = _estimate_rewards(settings, db_plaid.get_reward_eligible_spend(account_db_id, cycle["start"]))
    annual_fee = settings.get("annual_fee") or 0.0

    return {
        "account": acct,
        "liability": liability,
        "liability_available": liability_available,
        "utilization": utilization,
        "available_credit": (limit - balance) if (limit is not None and balance is not None) else None,
        "settings": settings,
        "cycle": cycle,
        "rewards": {
            "configured": bool(settings.get("base_reward_rate") or settings.get("category_rates")),
            "reward_type": settings["reward_type"],
            "cycle": rewards_cycle,
            "trailing_12m": rewards_12m,
            "annual_fee": annual_fee,
            "net_12m": round(rewards_12m["value"] - annual_fee, 2),
        },
        "balance_history": history,
        "bill_id": db_plaid.get_credit_bill_id(plaid_id),
        "spending": db_plaid.get_account_spending_summary(account_db_id),
    }


@router.put("/accounts/{account_db_id}/credit/settings")
def update_credit_settings(
    account_db_id: int, body: CreditSettingsBody, current_user: dict = Depends(get_current_user)
):
    """Save user-entered card details (network, rewards, annual fee, auto-bill preferences)."""
    acct = _get_credit_account(current_user["id"], account_db_id)
    updates = body.model_dump(exclude_unset=True)
    if "category_rates" in updates and updates["category_rates"] is not None:
        updates["category_rates"] = {
            k.strip().upper(): float(v)
            for k, v in updates["category_rates"].items()
            if k and k.strip() and v is not None and v >= 0
        }
    settings = db_plaid.upsert_credit_settings(acct["account_id"], updates)
    bill_id = db_plaid.sync_credit_bill(acct["account_id"])
    return {"settings": settings, "bill_id": bill_id}


_PER_MONTH = {
    "WEEKLY": 52 / 12, "BIWEEKLY": 26 / 12, "SEMI_MONTHLY": 2.0,
    "MONTHLY": 1.0, "ANNUALLY": 1 / 12,
}


def _fetch_recurring_streams(access_token: str, account_plaid_id: str):
    """Active outflow streams from Plaid for one account, or None if unavailable."""
    try:
        res = pc.get_plaid_client().transactions_recurring_get(
            TransactionsRecurringGetRequest(access_token=access_token, account_ids=[account_plaid_id])
        ).to_dict()
    except Exception as e:  # product not enabled, Plaid outage, etc.
        logger.warning("transactions_recurring_get failed for account %s: %s", account_plaid_id, e)
        return None

    streams = []
    for st in res.get("outflow_streams") or []:
        if not st.get("is_active", True):
            continue
        freq = _enum_str(st.get("frequency")) or "UNKNOWN"
        avg = abs(float((st.get("average_amount") or {}).get("amount") or 0))
        last = abs(float((st.get("last_amount") or {}).get("amount") or 0))
        pfc = st.get("personal_finance_category") or {}
        streams.append({
            "stream_id": st.get("stream_id"),
            "name": st.get("merchant_name") or st.get("description") or "Unknown",
            "description": st.get("description"),
            "frequency": freq,
            "average_amount": avg,
            "last_amount": last,
            "last_date": _iso_date(st.get("last_date")),
            "next_date": _iso_date(st.get("predicted_next_date")),
            "status": _enum_str(st.get("status")) or "",
            "category": pfc.get("primary"),
            "monthly_equivalent": round(last * _PER_MONTH.get(freq, 0), 2),
        })
    return streams


def _price_increase(stream: dict, tracking: Optional[dict]) -> Optional[float]:
    """For subscriptions the user chose to keep: how much the price rose since then (if noticeably)."""
    if not tracking or tracking["status"] != "kept" or not tracking["kept_amount"]:
        return None
    diff = stream["last_amount"] - tracking["kept_amount"]
    return round(diff, 2) if diff >= max(0.5, tracking["kept_amount"] * 0.02) else None


@router.get("/accounts/{account_db_id}/credit/recurring")
def credit_recurring_charges(account_db_id: int, current_user: dict = Depends(get_current_user)):
    """Recurring charges on this card (Plaid /transactions/recurring/get) merged with the user's
    cancel/keep decisions, how-to-cancel info, and price-increase flags."""
    acct = _get_credit_account(current_user["id"], account_db_id)
    plaid_id = acct["account_id"]
    streams = _fetch_recurring_streams(acct["access_token"], plaid_id)

    if streams:
        db_subscriptions.refresh_from_streams(plaid_id, streams)
    db_subscriptions.detect_still_charging(current_user["id"])
    tracked = db_subscriptions.by_stream_for_account(plaid_id)

    active, cancelled = [], []
    seen = set()
    for st in streams or []:
        t = tracked.get(st["stream_id"])
        seen.add(st["stream_id"])
        item = {
            **st,
            "tracking": t,
            "cancel_info": cancel_directory.lookup(st["name"], st["description"]),
            "price_increase": _price_increase(st, t),
        }
        (cancelled if t and t["status"] == "cancelled" else active).append(item)

    # Cancelled subscriptions Plaid no longer reports (stream went inactive) still belong in the list.
    for stream_id, t in tracked.items():
        if stream_id in seen or t["status"] != "cancelled":
            continue
        cancelled.append({
            "stream_id": stream_id,
            "name": t["merchant_name"],
            "description": None,
            "frequency": t["frequency"] or "UNKNOWN",
            "average_amount": t["last_amount"],
            "last_amount": t["last_amount"],
            "last_date": None,
            "next_date": None,
            "status": "",
            "category": None,
            "monthly_equivalent": t["monthly_amount"] or 0.0,
            "tracking": t,
            "cancel_info": cancel_directory.lookup(t["merchant_name"]),
            "price_increase": None,
        })

    active.sort(key=lambda x: x["monthly_equivalent"], reverse=True)
    cancelled.sort(key=lambda x: (x["tracking"]["still_charging"] is None, -(x["monthly_equivalent"] or 0)))
    return {
        "available": streams is not None,
        "streams": active,
        "cancelled": cancelled,
        "monthly_total": round(sum(x["monthly_equivalent"] for x in active), 2),
        "monthly_saved": round(
            sum(x["monthly_equivalent"] or 0 for x in cancelled if not x["tracking"]["still_charging"]), 2
        ),
    }


def _enum_str(v):
    v = getattr(v, "value", v)
    return str(v) if v is not None else None


def _iso_date(v):
    return v.isoformat() if isinstance(v, date) else v
