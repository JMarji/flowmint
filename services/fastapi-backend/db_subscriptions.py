"""Persistence for user decisions on Plaid recurring streams (cancel / keep) and still-charging detection."""
from datetime import date
from typing import Any, Dict, List, Optional

from database import get_pool

STATUSES = ("active", "cancelled", "kept")

_SELECT = """
    SELECT s.id, s.account_id, ba.id, ba.name, ba.mask, bi.institution_name,
           s.stream_id, s.merchant_name, s.frequency, s.last_amount, s.monthly_amount,
           s.next_expected_date, s.status, s.status_changed_at, s.cancelled_on, s.kept_amount,
           s.still_charging_txn_id, s.still_charging_detected_at, s.alert_dismissed,
           t.date, t.amount, COALESCE(t.merchant_name, t.name), tba.name
    FROM flowmint.subscription_tracking s
    JOIN flowmint.bank_accounts ba ON ba.account_id = s.account_id
    JOIN flowmint.bank_items bi ON bi.id = ba.item_id
    LEFT JOIN flowmint.transactions t ON t.id = s.still_charging_txn_id
    LEFT JOIN flowmint.bank_accounts tba ON tba.id = t.account_id
"""


def _f(v):
    return float(v) if v is not None else None


def _iso(v):
    return v.isoformat() if v is not None else None


def _row(r) -> Dict[str, Any]:
    still = None
    if r[16] is not None:
        still = {
            "txn_id": r[16],
            "detected_at": _iso(r[17]),
            "date": _iso(r[19]),
            "amount": _f(r[20]),
            "name": r[21],
            "account_name": r[22],
        }
    return {
        "id": r[0],
        "account_id": r[1],
        "account_db_id": r[2],
        "account_name": r[3],
        "mask": r[4],
        "institution_name": r[5],
        "stream_id": r[6],
        "merchant_name": r[7],
        "frequency": r[8],
        "last_amount": _f(r[9]),
        "monthly_amount": _f(r[10]),
        "next_expected_date": _iso(r[11]),
        "status": r[12],
        "status_changed_at": _iso(r[13]),
        "cancelled_on": _iso(r[14]),
        "kept_amount": _f(r[15]),
        "still_charging": still,
        "alert_dismissed": r[18],
    }


def match_key(merchant_name: str) -> str:
    return (merchant_name or "").strip().lower()


def get(user_id: int, sub_id: int) -> Optional[Dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SELECT + " WHERE s.user_id = %s AND s.id = %s", (user_id, sub_id))
            r = cur.fetchone()
    return _row(r) if r else None


def list_for_user(user_id: int) -> List[Dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _SELECT + " WHERE s.user_id = %s ORDER BY s.status, s.monthly_amount DESC NULLS LAST, s.merchant_name",
                (user_id,),
            )
            rows = cur.fetchall()
    return [_row(r) for r in rows]


def by_stream_for_account(account_id: str) -> Dict[str, Dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SELECT + " WHERE s.account_id = %s", (account_id,))
            rows = cur.fetchall()
    return {r[6]: _row(r) for r in rows}


def upsert(
    user_id: int,
    account_id: str,
    stream_id: str,
    merchant_name: str,
    frequency: Optional[str],
    last_amount: Optional[float],
    monthly_amount: Optional[float],
    next_expected_date: Optional[str],
    status: str,
    cancelled_on: Optional[str] = None,
) -> int:
    """Record a decision on a stream. Moving to a new status resets still-charging state."""
    if status not in STATUSES:
        raise ValueError(f"bad status {status}")
    cancelled_on = (cancelled_on or date.today().isoformat()) if status == "cancelled" else None
    kept_amount = last_amount if status == "kept" else None
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO flowmint.subscription_tracking
                    (user_id, account_id, stream_id, merchant_name, match_key, frequency,
                     last_amount, monthly_amount, next_expected_date, status, cancelled_on, kept_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (account_id, stream_id) DO UPDATE SET
                    merchant_name              = EXCLUDED.merchant_name,
                    match_key                  = EXCLUDED.match_key,
                    frequency                  = EXCLUDED.frequency,
                    last_amount                = EXCLUDED.last_amount,
                    monthly_amount             = EXCLUDED.monthly_amount,
                    next_expected_date         = EXCLUDED.next_expected_date,
                    status                     = EXCLUDED.status,
                    status_changed_at          = NOW(),
                    cancelled_on               = EXCLUDED.cancelled_on,
                    kept_amount                = EXCLUDED.kept_amount,
                    still_charging_txn_id      = NULL,
                    still_charging_detected_at = NULL,
                    alert_dismissed            = FALSE
                WHERE flowmint.subscription_tracking.user_id = EXCLUDED.user_id
                RETURNING id
                """,
                (
                    user_id, account_id, stream_id, merchant_name, match_key(merchant_name), frequency,
                    last_amount, monthly_amount, next_expected_date, status, cancelled_on, kept_amount,
                ),
            )
            row = cur.fetchone()
            conn.commit()
    if not row:
        raise PermissionError("stream tracked by another user")
    return row[0]


def set_status(user_id: int, sub_id: int, status: str, cancelled_on: Optional[str] = None) -> bool:
    """Change status on an existing row (e.g. 're-cancelled', undo, keep)."""
    if status not in STATUSES:
        raise ValueError(f"bad status {status}")
    cancelled_on = (cancelled_on or date.today().isoformat()) if status == "cancelled" else None
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE flowmint.subscription_tracking SET
                    status                     = %s,
                    status_changed_at          = NOW(),
                    cancelled_on               = %s,
                    kept_amount                = CASE WHEN %s = 'kept' THEN last_amount ELSE NULL END,
                    still_charging_txn_id      = NULL,
                    still_charging_detected_at = NULL,
                    alert_dismissed            = FALSE
                WHERE id = %s AND user_id = %s
                """,
                (status, cancelled_on, status, sub_id, user_id),
            )
            ok = cur.rowcount > 0
            conn.commit()
    return ok


def dismiss_alert(user_id: int, sub_id: int) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flowmint.subscription_tracking SET alert_dismissed = TRUE WHERE id = %s AND user_id = %s",
                (sub_id, user_id),
            )
            ok = cur.rowcount > 0
            conn.commit()
    return ok


def delete(user_id: int, sub_id: int) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.subscription_tracking WHERE id = %s AND user_id = %s",
                (sub_id, user_id),
            )
            ok = cur.rowcount > 0
            conn.commit()
    return ok


def refresh_from_streams(account_id: str, streams: List[Dict[str, Any]]):
    """Keep amounts/dates on tracked active/kept rows current with Plaid.

    Cancelled rows are left alone: their monthly_amount is what the savings figure is based on.
    """
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            for st in streams:
                cur.execute(
                    """
                    UPDATE flowmint.subscription_tracking SET
                        last_amount = %s, monthly_amount = %s, next_expected_date = %s, frequency = %s
                    WHERE account_id = %s AND stream_id = %s AND status <> 'cancelled'
                    """,
                    (st["last_amount"], st["monthly_equivalent"], st["next_date"], st["frequency"],
                     account_id, st["stream_id"]),
                )
            conn.commit()


def detect_still_charging(user_id: int) -> List[int]:
    """Flag cancelled subscriptions that charged again after the cancel date.

    Matches posted charges on any of the user's accounts (merchants sometimes move to another card)
    whose merchant name equals the tracked merchant, or whose description starts with it.
    Returns ids newly flagged.
    """
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH hits AS (
                    SELECT DISTINCT ON (s.id) s.id AS sid, t.id AS txn_id
                    FROM flowmint.subscription_tracking s
                    JOIN flowmint.bank_items bi ON bi.user_id = s.user_id
                    JOIN flowmint.bank_accounts ba ON ba.item_id = bi.id
                    JOIN flowmint.transactions t ON t.account_id = ba.id
                    WHERE s.user_id = %s
                      AND s.status = 'cancelled'
                      AND s.still_charging_txn_id IS NULL
                      AND t.pending = FALSE
                      AND t.amount > 0
                      AND t.date > s.cancelled_on
                      AND (
                        LOWER(TRIM(COALESCE(t.merchant_name, ''))) = s.match_key
                        OR POSITION(s.match_key IN LOWER(COALESCE(t.name, ''))) = 1
                      )
                    ORDER BY s.id, t.date, t.id
                )
                UPDATE flowmint.subscription_tracking s SET
                    still_charging_txn_id      = hits.txn_id,
                    still_charging_detected_at = NOW(),
                    alert_dismissed            = FALSE
                FROM hits
                WHERE s.id = hits.sid
                RETURNING s.id
                """,
                (user_id,),
            )
            ids = [r[0] for r in cur.fetchall()]
            conn.commit()
    return ids


def summarize(subs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Savings from cancellations that stuck, plus open still-charging alerts."""
    today = date.today()
    monthly = 0.0
    to_date = 0.0
    cancelled = 0
    for s in subs:
        if s["status"] != "cancelled":
            continue
        cancelled += 1
        if s["still_charging"]:
            continue  # not actually saving anything yet
        m = s["monthly_amount"] or 0.0
        monthly += m
        if s["cancelled_on"]:
            months = max(0.0, (today - date.fromisoformat(s["cancelled_on"])).days / 30.44)
            to_date += m * months
    alerts = [s["id"] for s in subs if s["still_charging"] and not s["alert_dismissed"]]
    return {
        "cancelled_count": cancelled,
        "monthly_saved": round(monthly, 2),
        "annual_saved": round(monthly * 12, 2),
        "saved_to_date": round(to_date, 2),
        "alert_ids": alerts,
    }
