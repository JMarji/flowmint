"""Is a property's mortgage paid up or behind?

Two sources, best first:
  1. Plaid mortgage liability data (past-due amount, next due date, last payment) for linked accounts.
  2. Recorded payments — bank transactions tagged to the property or on the linked mortgage account,
     plus imported payment history — checked against a monthly due day (default the 1st) with the
     standard 15-day grace period.
"""
import calendar
import json
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from database import get_pool

GRACE_DAYS = 15
PAID_THRESHOLD = 0.9  # a payment within 10% of the expected amount counts as paid in full


def _f(v):
    return float(v) if v is not None else None


def _iso(v):
    return v.isoformat() if v is not None else None


# ---------------------------------------------------------------------------
# Plaid mortgage liabilities
# ---------------------------------------------------------------------------

def store_mortgage_liabilities(liabilities_response: Dict[str, Any]) -> int:
    """Persist mortgage liabilities from a Plaid /liabilities/get response (as a dict)."""
    mortgages = (liabilities_response.get("liabilities") or {}).get("mortgage") or []
    stored = 0
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            for m in mortgages:
                acct_id = m.get("account_id")
                if not acct_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO flowmint.mortgage_liabilities
                        (account_id, next_payment_due_date, next_monthly_payment, last_payment_date,
                         last_payment_amount, past_due_amount, current_late_fee, escrow_balance,
                         ytd_interest_paid, ytd_principal_paid, updated_at)
                    SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    WHERE EXISTS (SELECT 1 FROM flowmint.bank_accounts WHERE account_id = %s)
                    ON CONFLICT (account_id) DO UPDATE SET
                        next_payment_due_date = EXCLUDED.next_payment_due_date,
                        next_monthly_payment  = EXCLUDED.next_monthly_payment,
                        last_payment_date     = EXCLUDED.last_payment_date,
                        last_payment_amount   = EXCLUDED.last_payment_amount,
                        past_due_amount       = EXCLUDED.past_due_amount,
                        current_late_fee      = EXCLUDED.current_late_fee,
                        escrow_balance        = EXCLUDED.escrow_balance,
                        ytd_interest_paid     = EXCLUDED.ytd_interest_paid,
                        ytd_principal_paid    = EXCLUDED.ytd_principal_paid,
                        updated_at            = NOW()
                    """,
                    (
                        acct_id, m.get("next_payment_due_date"), m.get("next_monthly_payment"),
                        m.get("last_payment_date"), m.get("last_payment_amount"), m.get("past_due_amount"),
                        m.get("current_late_fee"), m.get("escrow_balance"), m.get("ytd_interest_paid"),
                        m.get("ytd_principal_paid"), acct_id,
                    ),
                )
                stored += cur.rowcount
        conn.commit()
    return stored


def _get_liability(account_id: str) -> Optional[Dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT next_payment_due_date, next_monthly_payment, last_payment_date, last_payment_amount,
                          past_due_amount, current_late_fee, escrow_balance, updated_at
                   FROM flowmint.mortgage_liabilities WHERE account_id = %s""",
                (account_id,),
            )
            r = cur.fetchone()
    if not r:
        return None
    return {
        "next_payment_due_date": r[0], "next_monthly_payment": _f(r[1]),
        "last_payment_date": r[2], "last_payment_amount": _f(r[3]),
        "past_due_amount": _f(r[4]), "current_late_fee": _f(r[5]),
        "escrow_balance": _f(r[6]), "updated_at": _iso(r[7]),
    }


# ---------------------------------------------------------------------------
# Recorded payments
# ---------------------------------------------------------------------------

def _get_payments(user_id: int, property_id: int, mortgage_account_id: Optional[str], since: date) -> List[dict]:
    """Mortgage payments from every source, de-duplicated across sources (same payment seen from the
    checking side and the mortgage side, or also present in an imported history)."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.date, t.amount,
                       CASE WHEN t.mortgage_property_id = %s
                            THEN (CASE WHEN t.tag_source = 'auto' THEN 'detected' ELSE 'tagged' END)
                            ELSE 'mortgage_account' END
                FROM flowmint.transactions t
                JOIN flowmint.bank_accounts ba ON ba.id = t.account_id
                JOIN flowmint.bank_items bi ON bi.id = ba.item_id
                WHERE bi.user_id = %s
                  AND t.date >= %s
                  AND t.amount > 0
                  AND t.pending = FALSE
                  AND (
                    t.mortgage_property_id = %s
                    OR (
                      %s::text IS NOT NULL
                      AND ba.account_id = %s::text
                      AND t.mortgage_property_id IS NULL
                      AND COALESCE(t.category_override, 'MORTGAGE_PAYMENT') = 'MORTGAGE_PAYMENT'
                    )
                  )
                UNION ALL
                SELECT pt.date, pt.amount, 'imported'
                FROM flowmint.property_transactions pt
                WHERE pt.property_id = %s AND pt.type = 'expense' AND pt.category = 'mortgage' AND pt.date >= %s
                """,
                (property_id, user_id, since, property_id, mortgage_account_id, mortgage_account_id, property_id, since),
            )
            rows = [{"date": r[0], "amount": float(r[1]), "source": r[2]} for r in cur.fetchall()]

    rows.sort(key=lambda p: (p["date"], p["source"]))
    kept: List[dict] = []
    for p in rows:
        dup = any(
            k["source"] != p["source"]
            and abs(k["amount"] - p["amount"]) <= 1.0
            and abs((k["date"] - p["date"]).days) <= 5
            for k in kept
        )
        if not dup:
            kept.append(p)
    return kept


# ---------------------------------------------------------------------------
# Due-date math
# ---------------------------------------------------------------------------

def _due_in_month(year: int, month: int, due_day: int) -> date:
    return date(year, month, min(due_day, calendar.monthrange(year, month)[1]))


def _shift_month(d: date, delta: int, due_day: int) -> date:
    m = d.month - 1 + delta
    return _due_in_month(d.year + m // 12, m % 12 + 1, due_day)


def _last_due_on_or_before(today: date, due_day: int) -> date:
    d = _due_in_month(today.year, today.month, due_day)
    return d if d <= today else _shift_month(d, -1, due_day)


def _window(due: date, due_day: int):
    """Payments are attributed to their nearest due date: [midpoint to previous, midpoint to next)."""
    prev_due, next_due = _shift_month(due, -1, due_day), _shift_month(due, 1, due_day)
    start = due - timedelta(days=(due - prev_due).days // 2)
    end = due + timedelta(days=(next_due - due).days - (next_due - due).days // 2)
    return start, end


def _paid_toward(payments: List[dict], due: date, due_day: int) -> float:
    start, end = _window(due, due_day)
    return sum(p["amount"] for p in payments if start <= p["date"] < end)


def _covered(paid: float, expected: Optional[float]) -> bool:
    return paid > 0 and (not expected or paid >= expected * PAID_THRESHOLD)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def _money(v: Optional[float]) -> str:
    return f"${v:,.2f}" if v is not None else "—"


def _fmt(d: date) -> str:
    return d.strftime("%b %-d")


def compute(user_id: int, prop: Dict[str, Any], due_day: Optional[int], today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    account_id = prop.get("mortgage_account_id")
    expected = prop.get("mortgage_payment")
    has_mortgage = bool(account_id or (prop.get("mortgage_balance") or 0) > 0 or expected)

    base = {
        "status": "none", "label": "No mortgage", "source": None, "message": None,
        "due_date": None, "next_due_date": None, "last_payment_date": None, "last_payment_amount": None,
        "past_due_amount": None, "late_fee": None, "months_behind": 0, "days_late": 0,
        "expected_amount": expected, "due_day": due_day or 1, "due_day_assumed": due_day is None,
        "grace_days": GRACE_DAYS, "recent_payments": [],
    }
    if not has_mortgage:
        return base

    payments = _get_payments(user_id, prop["id"], account_id, today - timedelta(days=400))
    base["recent_payments"] = [
        {"date": _iso(p["date"]), "amount": p["amount"], "source": p["source"]} for p in reversed(payments[-6:])
    ]
    if payments:
        base["last_payment_date"] = _iso(payments[-1]["date"])
        base["last_payment_amount"] = payments[-1]["amount"]

    liab = _get_liability(account_id) if account_id else None
    if liab and (liab["next_payment_due_date"] or liab["past_due_amount"] is not None):
        return _from_plaid(base, liab, today)
    return _from_payments(base, payments, due_day or 1, expected, today)


def _from_plaid(out: dict, liab: dict, today: date) -> dict:
    out["source"] = "plaid"
    nd: Optional[date] = liab["next_payment_due_date"]
    lpd: Optional[date] = liab["last_payment_date"]
    past_due = liab["past_due_amount"] or 0.0
    out.update({
        "next_due_date": _iso(nd),
        "last_payment_date": _iso(lpd) or out["last_payment_date"],
        "last_payment_amount": liab["last_payment_amount"] if lpd else out["last_payment_amount"],
        "past_due_amount": past_due,
        "late_fee": liab["current_late_fee"],
        "expected_amount": liab["next_monthly_payment"] or out["expected_amount"],
    })
    if nd:
        out["due_day"], out["due_day_assumed"] = nd.day, False

    if past_due > 0:
        days_late = (today - nd).days if nd and nd < today else 0
        out.update(status="behind", label="Behind", days_late=max(days_late, 0),
                   months_behind=max(1, round(past_due / out["expected_amount"])) if out["expected_amount"] else 1,
                   message=f"{_money(past_due)} past due according to your servicer"
                           + (f", plus a {_money(liab['current_late_fee'])} late fee" if liab["current_late_fee"] else "") + ".")
        return out

    if nd and nd < today and not (lpd and lpd >= nd - timedelta(days=20)):
        days_late = (today - nd).days
        late = days_late > GRACE_DAYS
        out.update(status="behind" if late else "due", label="Behind" if late else "Due",
                   due_date=_iso(nd), days_late=days_late,
                   message=(f"Payment due {_fmt(nd)} hasn't posted ({days_late} days)." if late
                            else f"Payment was due {_fmt(nd)} — still within the {GRACE_DAYS}-day grace period."))
        return out

    prev_due = nd - timedelta(days=31) if nd else None
    if lpd and (not prev_due or lpd >= prev_due - timedelta(days=20)):
        out.update(status="paid", label="Paid",
                   message=f"Last payment {_money(out['last_payment_amount'])} on {_fmt(lpd)}."
                           + (f" Next due {_fmt(nd)}." if nd else ""))
    else:
        out.update(status="due", label="Current",
                   message="Nothing past due." + (f" Next payment due {_fmt(nd)}." if nd else ""))
    return out


def _from_payments(out: dict, payments: List[dict], due_day: int, expected: Optional[float], today: date) -> dict:
    out["source"] = "payments"
    d0 = _last_due_on_or_before(today, due_day)
    d1 = _shift_month(d0, 1, due_day)
    out["due_date"], out["next_due_date"] = _iso(d0), _iso(d1)

    if not payments:
        out.update(status="unknown", label="No payment data",
                   message="No mortgage payments found. Link the mortgage account, or tag payments as "
                           "mortgage payments on the Transactions page.")
        return out

    first_seen = payments[0]["date"]
    paid_next = _paid_toward(payments, d1, due_day)
    paid_now = _paid_toward(payments, d0, due_day)

    if _covered(paid_next, expected):
        out.update(status="paid", label="Paid ahead",
                   message=f"The {_fmt(d1)} payment is already in.")
        return out
    if _covered(paid_now, expected):
        out.update(status="paid", label="Paid",
                   message=f"The {_fmt(d0)} payment is in. Next due {_fmt(d1)}.")
        return out

    days_late = (today - d0).days
    in_grace = days_late <= GRACE_DAYS

    # Count consecutive missed due dates — starting before d0 while d0 is still in its grace period —
    # but only back to when payment data starts.
    missed, owed = 0, 0.0
    due = _shift_month(d0, -1, due_day) if in_grace else d0
    while missed < 12 and _window(due, due_day)[1] > first_seen:
        paid = _paid_toward(payments, due, due_day)
        if _covered(paid, expected):
            break
        missed += 1
        owed += (expected - paid) if expected else 0.0
        due = _shift_month(due, -1, due_day)

    if missed == 0:
        shortfall = (expected - paid_now) if expected and paid_now else None
        out.update(status="due", label="Due", days_late=days_late,
                   message=(f"{_money(shortfall)} still owed on the {_fmt(d0)} payment" if shortfall
                            else f"The {_fmt(d0)} payment hasn't shown up yet")
                           + f" — late after {_fmt(d0 + timedelta(days=GRACE_DAYS))}.")
        return out

    if in_grace:
        lead = (f"Missed {missed} earlier payment{'s' if missed != 1 else ''}; "
                f"the {_fmt(d0)} payment is also due (late after {_fmt(d0 + timedelta(days=GRACE_DAYS))}).")
    elif paid_now > 0 and expected:
        lead = f"Only {_money(paid_now)} of {_money(expected)} paid toward {_fmt(d0)} ({days_late} days)."
    else:
        lead = f"No payment found for {_fmt(d0)} ({days_late} days)."
    out.update(status="behind", label="Behind", days_late=days_late if not in_grace else (today - _shift_month(d0, -1, due_day)).days,
               months_behind=missed, past_due_amount=round(owed, 2) if expected else None,
               message=lead + (f" About {_money(owed)} behind." if expected else ""))
    return out


def get_due_days(property_ids: List[int]) -> Dict[int, Optional[int]]:
    if not property_ids:
        return {}
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, mortgage_due_day FROM flowmint.properties WHERE id = ANY(%s)", (property_ids,)
            )
            return {r[0]: r[1] for r in cur.fetchall()}


def attach(user_id: int, props: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add `mortgage_due_day` and `mortgage_status` to property dicts."""
    due_days = get_due_days([p["id"] for p in props])
    for p in props:
        p["mortgage_due_day"] = due_days.get(p["id"])
        p["mortgage_status"] = compute(user_id, p, p["mortgage_due_day"])
    return props
