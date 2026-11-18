"""Find mortgage, auto-loan, and bill payments in synced transactions so they don't need manual tagging.

Rules of engagement:
  * Anything the user set by hand (tag_source = 'manual') is never touched.
  * Auto-tags are marked tag_source = 'auto' so the UI can show them and the user can override them.
  * A bill match the user rejects is remembered (bill_payments.status = 'rejected') and never re-made.
"""
import calendar
import logging
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from database import get_pool

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 730

# Plaid personal_finance_category.detailed values
_PFC_MORTGAGE = "LOAN_PAYMENTS_MORTGAGE_PAYMENT"
_PFC_CAR = "LOAN_PAYMENTS_CAR_PAYMENT"

# Generic mortgage wording plus large US servicers whose names don't say "mortgage".
_MORTGAGE_RE = re.compile(
    r"(?<![a-z0-9])(mortgage|mortg|mtg|mtge|home ?loans?|mr\.? ?cooper|newrez|pennymac|"
    r"loan ?depot|shellpoint|lakeview loan|cenlar|nationstar|flagstar|dovenmuehle)(?![a-z0-9])"
)

_STOPWORDS = {
    "the", "and", "for", "bill", "bills", "payment", "payments", "pmt", "pymt", "monthly", "online",
    "autopay", "auto", "pay", "ach", "debit", "web", "inc", "llc", "co", "corp", "company", "service",
    "services", "my", "of", "to", "recurring", "purchase", "pos",
}


def merchant_key(merchant_name: Optional[str], name: Optional[str]) -> str:
    """Stable key for 'who was paid': the merchant name if Plaid has one, else the first words of the
    description with reference numbers stripped (e.g. 'ROCKET MORTGAGE PMT 88231' -> 'rocket mortgage pmt')."""
    if merchant_name and merchant_name.strip():
        return merchant_name.strip().lower()
    words = re.findall(r"[a-z][a-z&'.]*", (name or "").lower())
    return " ".join(words[:3])


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 3 and w not in _STOPWORDS}


def _looks_like_mortgage(t: dict) -> bool:
    if t["category_detailed"] == _PFC_MORTGAGE:
        return True
    return bool(_MORTGAGE_RE.search(f"{t['merchant_name'] or ''} {t['name'] or ''}".lower()))


def _close(amount: float, expected: Optional[float], tolerance: float) -> bool:
    return bool(expected) and abs(amount - expected) <= max(expected * tolerance, 5.0)


# ---------------------------------------------------------------------------
# Mortgage + auto loan
# ---------------------------------------------------------------------------

def detect_loan_payments(user_id: int) -> Dict[str, int]:
    """Tag mortgage (and link to a property) and auto-loan payments. Returns counts."""
    since = date.today() - timedelta(days=LOOKBACK_DAYS)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, mortgage_payment FROM flowmint.properties
                   WHERE user_id = %s
                     AND (mortgage_account_id IS NOT NULL OR mortgage_payment IS NOT NULL
                          OR COALESCE(mortgage_balance, 0) > 0)""",
                (user_id,),
            )
            props = [{"id": r[0], "payment": float(r[1]) if r[1] is not None else None} for r in cur.fetchall()]

            # Learn from existing links: payee -> property, and payees the user called a car payment.
            cur.execute(
                """SELECT t.merchant_name, t.name, t.mortgage_property_id, t.category_override
                   FROM flowmint.transactions t
                   JOIN flowmint.bank_accounts ba ON ba.id = t.account_id
                   JOIN flowmint.bank_items bi ON bi.id = ba.item_id
                   WHERE bi.user_id = %s
                     AND (t.mortgage_property_id IS NOT NULL OR t.category_override = 'AUTO_LOAN_PAYMENT')""",
                (user_id,),
            )
            payee_props: Dict[str, set] = defaultdict(set)
            car_payees: set = set()
            for m, n, pid, cat in cur.fetchall():
                k = merchant_key(m, n)
                if pid:
                    payee_props[k].add(pid)
                if cat == "AUTO_LOAN_PAYMENT":
                    car_payees.add(k)
            learned = {k: next(iter(v)) for k, v in payee_props.items() if len(v) == 1}

            # Candidates: posted outflows from cash accounts that nobody has decided about yet.
            cur.execute(
                """SELECT t.id, t.amount, t.date, t.name, t.merchant_name, t.category_detailed, t.category_override
                   FROM flowmint.transactions t
                   JOIN flowmint.bank_accounts ba ON ba.id = t.account_id
                   JOIN flowmint.bank_items bi ON bi.id = ba.item_id
                   WHERE bi.user_id = %s
                     AND ba.type = 'depository'
                     AND t.amount > 0
                     AND t.pending = FALSE
                     AND t.date >= %s
                     AND t.tag_source IS NULL
                     AND t.mortgage_property_id IS NULL
                     AND (t.category_override IS NULL OR t.category_override = 'MORTGAGE_PAYMENT')""",
                (user_id, since),
            )
            cols = ["id", "amount", "date", "name", "merchant_name", "category_detailed", "category_override"]
            candidates = [dict(zip(cols, r)) for r in cur.fetchall()]

            counts = {"mortgage_tagged": 0, "mortgage_linked": 0, "auto_loan_tagged": 0}
            for t in candidates:
                t["amount"] = float(t["amount"])
                key = merchant_key(t["merchant_name"], t["name"])
                is_mortgage = key in learned or _looks_like_mortgage(t)

                if is_mortgage:
                    prop_id = _pick_property(t, key, learned, props)
                    # Don't guess on stray servicer charges (fees, escrow refunds) that aren't payment-sized.
                    if prop_id is None and t["category_detailed"] != _PFC_MORTGAGE and key not in learned:
                        if not any(_close(t["amount"], p["payment"], 0.25) for p in props):
                            continue
                    cur.execute(
                        """UPDATE flowmint.transactions
                           SET category_override = 'MORTGAGE_PAYMENT', mortgage_property_id = %s, tag_source = 'auto'
                           WHERE id = %s AND tag_source IS NULL""",
                        (prop_id, t["id"]),
                    )
                    counts["mortgage_tagged"] += 1
                    counts["mortgage_linked"] += 1 if prop_id else 0
                    continue

                if t["category_override"] is None and (t["category_detailed"] == _PFC_CAR or key in car_payees):
                    cur.execute(
                        """UPDATE flowmint.transactions
                           SET category_override = 'AUTO_LOAN_PAYMENT', tag_source = 'auto'
                           WHERE id = %s AND tag_source IS NULL""",
                        (t["id"],),
                    )
                    counts["auto_loan_tagged"] += 1
        conn.commit()
    return counts


def _pick_property(t: dict, key: str, learned: Dict[str, int], props: List[dict]) -> Optional[int]:
    """Which property a mortgage payment belongs to, or None if it can't be decided safely."""
    if key in learned:
        return learned[key]
    if len(props) == 1:
        p = props[0]
        # One mortgage: link unless we know the payment amount and this is nowhere near it.
        return p["id"] if (p["payment"] is None or _close(t["amount"], p["payment"], 0.25)) else None
    matches = [p for p in props if _close(t["amount"], p["payment"], 0.03)]
    return matches[0]["id"] if len(matches) == 1 else None


def unassigned_mortgage_payments(user_id: int) -> int:
    """Mortgage payments (any source) not linked to a property — the user needs to pick one."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM flowmint.transactions t
                   JOIN flowmint.bank_accounts ba ON ba.id = t.account_id
                   JOIN flowmint.bank_items bi ON bi.id = ba.item_id
                   WHERE bi.user_id = %s AND ba.type = 'depository'
                     AND t.category_override = 'MORTGAGE_PAYMENT' AND t.mortgage_property_id IS NULL
                     AND t.date >= %s""",
                (user_id, date.today() - timedelta(days=LOOKBACK_DAYS)),
            )
            return int(cur.fetchone()[0])


# ---------------------------------------------------------------------------
# Bills
# ---------------------------------------------------------------------------

BILL_LOOKBACK_MONTHS = 6
DATE_WINDOW_DAYS = 10


def _due(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _recent_due_dates(due_day: int, months: int) -> List[date]:
    today = date.today()
    out = []
    y, m = today.year, today.month
    for _ in range(months + 1):
        d = _due(y, m, due_day)
        if d - timedelta(days=DATE_WINDOW_DAYS) <= today:
            out.append(d)
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out


def match_bill_payments(user_id: int) -> int:
    """Link bills (except card bills, which Plaid tracks) to the transactions that paid them."""
    today = date.today()
    matched = 0
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, name, amount, due_day_of_month, match_key
                   FROM flowmint.bills
                   WHERE user_id = %s AND is_active AND credit_account_id IS NULL""",
                (user_id,),
            )
            bills = [
                {"id": r[0], "name": r[1], "amount": float(r[2]), "due_day": r[3], "key": r[4]}
                for r in cur.fetchall()
            ]
            if not bills:
                return 0

            earliest = today - timedelta(days=31 * (BILL_LOOKBACK_MONTHS + 1))
            cur.execute(
                """SELECT t.id, t.amount, t.date, t.name, t.merchant_name
                   FROM flowmint.transactions t
                   JOIN flowmint.bank_accounts ba ON ba.id = t.account_id
                   JOIN flowmint.bank_items bi ON bi.id = ba.item_id
                   WHERE bi.user_id = %s AND t.amount > 0 AND t.pending = FALSE AND t.date >= %s
                     AND ba.type IN ('depository', 'credit')
                     AND NOT EXISTS (SELECT 1 FROM flowmint.bill_payments bp
                                     WHERE bp.transaction_id = t.id AND bp.status = 'matched')""",
                (user_id, earliest),
            )
            txns = [
                {"id": r[0], "amount": float(r[1]), "date": r[2], "name": r[3], "merchant_name": r[4],
                 "key": merchant_key(r[4], r[3])}
                for r in cur.fetchall()
            ]

            cur.execute(
                """SELECT bp.bill_id, bp.period, bp.transaction_id, bp.status
                   FROM flowmint.bill_payments bp JOIN flowmint.bills b ON b.id = bp.bill_id
                   WHERE b.user_id = %s""",
                (user_id,),
            )
            done_periods, rejected = set(), set()
            for bill_id, period, txn_id, status in cur.fetchall():
                if status == "matched":
                    done_periods.add((bill_id, period))
                else:
                    rejected.add((bill_id, txn_id))

            used = set()
            # Two passes: a bill's payee is learned from its first name/amount match, and the second pass
            # then picks up months whose amount was too far off to match by name alone.
            for _pass in range(2):
                matched += _match_pass(cur, bills, txns, done_periods, rejected, used)

            # last_paid_date follows the latest matched payment (never moves backwards).
            cur.execute(
                """UPDATE flowmint.bills b SET last_paid_date = x.last_date
                   FROM (SELECT bp.bill_id, MAX(t.date) AS last_date
                         FROM flowmint.bill_payments bp JOIN flowmint.transactions t ON t.id = bp.transaction_id
                         WHERE bp.status = 'matched' GROUP BY bp.bill_id) x
                   WHERE b.id = x.bill_id AND b.user_id = %s
                     AND (b.last_paid_date IS NULL OR b.last_paid_date < x.last_date)""",
                (user_id,),
            )
        conn.commit()
    return matched


def _match_pass(cur, bills: List[dict], txns: List[dict], done_periods: set, rejected: set, used: set) -> int:
    """Best transaction per (bill, unmatched due date). Returns how many were linked."""
    matched = 0
    for b in bills:
        name_tokens = _tokens(b["name"])
        for due in _recent_due_dates(b["due_day"], BILL_LOOKBACK_MONTHS):
            period = due.strftime("%Y-%m")
            if (b["id"], period) in done_periods:
                continue
            best = None
            for t in txns:
                if t["id"] in used or (b["id"], t["id"]) in rejected:
                    continue
                gap = abs((t["date"] - due).days)
                if gap > DATE_WINDOW_DAYS:
                    continue
                score = _bill_score(b, name_tokens, t, gap)
                if score and (best is None or score > best[0]):
                    best = (score, t)
            if not best:
                continue
            t = best[1]
            cur.execute(
                """INSERT INTO flowmint.bill_payments (bill_id, transaction_id, period, source)
                   VALUES (%s, %s, %s, 'auto') ON CONFLICT DO NOTHING""",
                (b["id"], t["id"], period),
            )
            if cur.rowcount:
                matched += 1
                used.add(t["id"])
                done_periods.add((b["id"], period))
                if not b["key"]:
                    b["key"] = t["key"]
                    cur.execute("UPDATE flowmint.bills SET match_key = %s WHERE id = %s AND match_key IS NULL",
                                (t["key"], b["id"]))
    return matched


def _bill_score(bill: dict, name_tokens: set, t: dict, gap: int) -> float:
    """0 = not this bill. Higher is better; closeness to the due date breaks ties."""
    amount, expected = t["amount"], bill["amount"]
    nearness = (DATE_WINDOW_DAYS - gap) / 100
    if bill["key"] and t["key"] == bill["key"]:
        # Known payee: amounts on variable bills (utilities) can swing a lot.
        return 3 + nearness if 0.5 * expected <= amount <= 1.5 * expected else 0
    if name_tokens & _tokens(f"{t['merchant_name'] or ''} {t['name'] or ''}"):
        return 2 + nearness if _close(amount, expected, 0.15) else 0
    # Same amount to the cent, right around the due date — only for non-round amounts ($15.49, not $40.00),
    # where a coincidental match with an unrelated purchase is unlikely.
    if abs(amount - expected) < 0.005 and gap <= 3 and abs(expected - round(expected)) >= 0.01:
        return 1 + nearness
    return 0


# ---------------------------------------------------------------------------

def run_all(user_id: int) -> Dict[str, Any]:
    loans = detect_loan_payments(user_id)
    bills = match_bill_payments(user_id)
    return {**loans, "bill_payments_matched": bills, "unassigned_mortgage_payments": unassigned_mortgage_payments(user_id)}
