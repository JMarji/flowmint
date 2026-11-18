"""Plaid recurring streams (/transactions/recurring/get) normalized and merged with the user's
cancel/keep decisions. Shared by the card page, the Subscriptions page, and the Bills calendar."""
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from plaid.model.transactions_recurring_get_request import TransactionsRecurringGetRequest

import cancel_directory
import plaid_client as pc

logger = logging.getLogger(__name__)

PER_MONTH = {
    "WEEKLY": 52 / 12, "BIWEEKLY": 26 / 12, "SEMI_MONTHLY": 2.0,
    "MONTHLY": 1.0, "ANNUALLY": 1 / 12,
}

# Outflows that recur but aren't cancellable subscriptions: debt payments, transfers, rent/utilities,
# fees, taxes. They're shown under "Bills & transfers" rather than as subscriptions.
_BILL_CATEGORIES = {
    "LOAN_PAYMENTS", "TRANSFER_OUT", "TRANSFER_IN", "RENT_AND_UTILITIES",
    "BANK_FEES", "GOVERNMENT_AND_NON_PROFIT", "INCOME",
}


def _enum_str(v) -> Optional[str]:
    v = getattr(v, "value", v)
    return str(v) if v is not None else None


def _iso_date(v):
    return v.isoformat() if isinstance(v, date) else v


def fetch_streams(access_token: str, account_ids: Optional[List[str]] = None) -> Optional[List[Dict[str, Any]]]:
    """Active outflow streams for an item (optionally limited to some accounts), or None if Plaid
    can't provide them (product not enabled, outage, ...)."""
    kwargs: Dict[str, Any] = {"access_token": access_token}
    if account_ids:
        kwargs["account_ids"] = account_ids
    try:
        res = pc.get_plaid_client().transactions_recurring_get(TransactionsRecurringGetRequest(**kwargs)).to_dict()
    except Exception as e:
        logger.warning("transactions_recurring_get failed (%s): %s", account_ids or "all accounts", e)
        return None

    streams = []
    for st in res.get("outflow_streams") or []:
        if not st.get("is_active", True):
            continue
        freq = _enum_str(st.get("frequency")) or "UNKNOWN"
        last = abs(float((st.get("last_amount") or {}).get("amount") or 0))
        avg = abs(float((st.get("average_amount") or {}).get("amount") or 0))
        pfc = st.get("personal_finance_category") or {}
        category = pfc.get("primary")
        streams.append({
            "stream_id": st.get("stream_id"),
            "account_id": st.get("account_id"),
            "name": st.get("merchant_name") or st.get("description") or "Unknown",
            "description": st.get("description"),
            "frequency": freq,
            "average_amount": avg,
            "last_amount": last,
            "first_date": _iso_date(st.get("first_date")),
            "last_date": _iso_date(st.get("last_date")),
            "next_date": _iso_date(st.get("predicted_next_date")),
            "status": _enum_str(st.get("status")) or "",
            "category": category,
            "kind": "bill" if category in _BILL_CATEGORIES else "subscription",
            "monthly_equivalent": round(last * PER_MONTH.get(freq, 0), 2),
        })
    return streams


def _price_increase(stream: dict, tracking: Optional[dict]) -> Optional[float]:
    """For subscriptions the user chose to keep: how much the price rose since then (if noticeably)."""
    if not tracking or tracking["status"] != "kept" or not tracking["kept_amount"]:
        return None
    diff = stream["last_amount"] - tracking["kept_amount"]
    return round(diff, 2) if diff >= max(0.5, tracking["kept_amount"] * 0.02) else None


def merge(
    streams: List[Dict[str, Any]],
    tracked: Dict[Tuple[str, str], Dict[str, Any]],
    account_info: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[List[dict], List[dict]]:
    """Attach tracking, cancel info, price-increase flags and account labels.

    `tracked` is keyed by (plaid account_id, stream_id). Returns (active, cancelled); cancelled includes
    tracked cancellations Plaid no longer reports.
    """
    account_info = account_info or {}
    active, cancelled = [], []
    seen = set()
    for st in streams:
        key = (st["account_id"], st["stream_id"])
        t = tracked.get(key)
        seen.add(key)
        item = {
            **st,
            "account": account_info.get(st["account_id"]),
            "tracking": t,
            "cancel_info": cancel_directory.lookup(st["name"], st["description"]),
            "price_increase": _price_increase(st, t),
        }
        (cancelled if t and t["status"] == "cancelled" else active).append(item)

    for key, t in tracked.items():
        if key in seen or t["status"] != "cancelled":
            continue
        cancelled.append({
            "stream_id": t["stream_id"],
            "account_id": t["account_id"],
            "name": t["merchant_name"],
            "description": None,
            "frequency": t["frequency"] or "UNKNOWN",
            "average_amount": t["last_amount"],
            "last_amount": t["last_amount"],
            "first_date": None,
            "last_date": None,
            "next_date": None,
            "status": "",
            "category": None,
            "kind": "subscription",
            "monthly_equivalent": t["monthly_amount"] or 0.0,
            "account": account_info.get(t["account_id"]),
            "tracking": t,
            "cancel_info": cancel_directory.lookup(t["merchant_name"]),
            "price_increase": None,
        })

    active.sort(key=lambda x: x["monthly_equivalent"], reverse=True)
    cancelled.sort(key=lambda x: (x["tracking"]["still_charging"] is None, -(x["monthly_equivalent"] or 0)))
    return active, cancelled


def saved_per_month(cancelled: List[dict]) -> float:
    return round(sum(x["monthly_equivalent"] or 0 for x in cancelled if not x["tracking"]["still_charging"]), 2)
