from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import os
import logging
from datetime import date
from database import get_pool
from auth_routes import get_current_user

router = APIRouter(tags=["planning"])
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a thoughtful financial planning assistant embedded in Flowmint, a personal finance app.

Help the user think through their financial plans and scenarios concretely. Use their actual financial data when discussing numbers. Be direct, realistic, and specific.

When the user asks about scenarios — paying off debt early, making investments, big purchases, starting a business, agricultural or land projects — do the following:
- Calculate concrete timelines and numbers based on their actual balances and cashflow
- Identify real trade-offs (liquidity, risk, opportunity cost)
- Give honest assessments of feasibility
- Ask clarifying questions when you need more detail to give useful advice

Don't be overly cautious or hedge everything with disclaimers. This is a personal finance tool for someone who wants to think things through, not a legal document.

Here is the user's current financial snapshot:
{context}"""


def _get_financial_context(user_id: int) -> str:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            # Liquid assets and debt from linked accounts
            cur.execute(
                """SELECT
                    COALESCE(SUM(CASE WHEN ba.type IN ('depository','investment','brokerage') AND ba.current_balance > 0 THEN ba.current_balance ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN ba.type IN ('credit','loan') AND ba.current_balance > 0 THEN ba.current_balance ELSE 0 END), 0)
                   FROM flowmint.bank_accounts ba
                   JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                   WHERE bi.user_id = %s""",
                (user_id,)
            )
            r = cur.fetchone()
            liquid = float(r[0])
            debt = float(r[1])

            # Properties
            cur.execute(
                """SELECT address, city, state, current_value, mortgage_balance, mortgage_payment, mortgage_rate
                   FROM flowmint.properties WHERE user_id = %s""",
                (user_id,)
            )
            properties = cur.fetchall()

            # Current month budgets with spend
            month_year = date.today().strftime("%Y-%m")
            cur.execute(
                """SELECT b.category, b.monthly_limit,
                          COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0) AS spent
                   FROM flowmint.budgets b
                   LEFT JOIN flowmint.transactions t ON (
                       COALESCE(t.category_override, t.category_primary) = b.category
                       AND TO_CHAR(t.date, 'YYYY-MM') = b.month_year
                       AND t.pending = FALSE
                       AND t.account_id IN (
                           SELECT ba.id FROM flowmint.bank_accounts ba
                           JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                           WHERE bi.user_id = b.user_id
                       )
                   )
                   WHERE b.user_id = %s AND b.month_year = %s
                   GROUP BY b.category, b.monthly_limit
                   ORDER BY b.monthly_limit DESC LIMIT 15""",
                (user_id, month_year)
            )
            budgets = cur.fetchall()

            # Active bills
            cur.execute(
                """SELECT name, amount, due_day_of_month, category
                   FROM flowmint.bills WHERE user_id = %s AND is_active = TRUE
                   ORDER BY amount DESC LIMIT 15""",
                (user_id,)
            )
            bills = cur.fetchall()

            # 30-day spending total
            cur.execute(
                """SELECT COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0)
                   FROM flowmint.transactions t
                   JOIN flowmint.bank_accounts ba ON t.account_id = ba.id
                   JOIN flowmint.bank_items bi ON ba.item_id = bi.id
                   WHERE bi.user_id = %s AND t.date >= CURRENT_DATE - INTERVAL '30 days'
                     AND t.pending = FALSE""",
                (user_id,)
            )
            monthly_spend = float(cur.fetchone()[0])

    lines = [
        "## Financial Snapshot",
        f"**Liquid / Investment Assets:** ${liquid:,.2f}",
        f"**Credit / Loan Debt:** ${debt:,.2f}",
        f"**Spending (last 30 days):** ${monthly_spend:,.2f}",
    ]

    if properties:
        lines.append("\n**Properties:**")
        for p in properties:
            parts = [p[0]]
            if p[1]:
                parts.append(p[1])
            if p[2]:
                parts.append(p[2])
            addr = ", ".join(parts)
            val = f"${float(p[3]):,.0f}" if p[3] else "unknown value"
            mort_bal = f"${float(p[4]):,.0f}" if p[4] else "no mortgage"
            payment = f"${float(p[5]):,.0f}/mo" if p[5] else "N/A"
            rate = f"{float(p[6]):.3f}%" if p[6] else "N/A"
            equity = (float(p[3]) if p[3] else 0) - (float(p[4]) if p[4] else 0)
            lines.append(f"  - {addr}: value={val}, mortgage={mort_bal}, payment={payment}, rate={rate}, equity=${equity:,.0f}")
    else:
        lines.append("\n**Properties:** None linked")

    if budgets:
        lines.append(f"\n**Monthly Budgets ({month_year}):**")
        for b in budgets:
            lines.append(f"  - {b[0]}: limit=${float(b[1]):,.0f}, spent=${float(b[2]):,.0f}")

    if bills:
        total_bills = sum(float(b[1]) for b in bills)
        lines.append(f"\n**Recurring Bills (total ~${total_bills:,.0f}/mo):**")
        for b in bills:
            lines.append(f"  - {b[0]}: ${float(b[1]):,.0f}/mo (due day {b[2]})")

    if not liquid and not debt and not properties and not budgets and not bills:
        lines.append("\n*No financial data linked yet — advise the user to connect accounts in Flowmint for more specific guidance.*")

    return "\n".join(lines)


class PlanCreate(BaseModel):
    title: str


class ChatMessage(BaseModel):
    content: str


@router.get("/plans")
def list_plans(current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at FROM flowmint.plans WHERE user_id = %s ORDER BY created_at DESC",
                (current_user["id"],)
            )
            rows = cur.fetchall()
    return [{"id": r[0], "title": r[1], "created_at": r[2].isoformat()} for r in rows]


@router.post("/plans", status_code=201)
def create_plan(body: PlanCreate, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO flowmint.plans (user_id, title) VALUES (%s, %s) RETURNING id, title, created_at",
                (current_user["id"], body.title.strip())
            )
            r = cur.fetchone()
            conn.commit()
    return {"id": r[0], "title": r[1], "created_at": r[2].isoformat()}


@router.get("/plans/{plan_id}/messages")
def get_messages(plan_id: int, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM flowmint.plans WHERE id = %s AND user_id = %s",
                (plan_id, current_user["id"])
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Plan not found")
            cur.execute(
                "SELECT role, content, created_at FROM flowmint.plan_messages WHERE plan_id = %s ORDER BY created_at ASC",
                (plan_id,)
            )
            rows = cur.fetchall()
    return [{"role": r[0], "content": r[1], "created_at": r[2].isoformat()} for r in rows]


@router.post("/plans/{plan_id}/chat")
def chat(plan_id: int, body: ChatMessage, current_user: dict = Depends(get_current_user)):
    # Verify ownership
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM flowmint.plans WHERE id = %s AND user_id = %s",
                (plan_id, current_user["id"])
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Plan not found")

    # Save user message
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO flowmint.plan_messages (plan_id, role, content) VALUES (%s, %s, %s)",
                (plan_id, "user", body.content)
            )
            conn.commit()

    # Fetch full conversation history (includes the just-saved user message)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM flowmint.plan_messages WHERE plan_id = %s ORDER BY created_at ASC",
                (plan_id,)
            )
            rows = cur.fetchall()

    messages = [{"role": r[0], "content": r[1]} for r in rows]
    context = _get_financial_context(current_user["id"])

    def generate():
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        full_text = []
        try:
            with client.messages.stream(
                model=os.environ.get("AI_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=2048,
                system=SYSTEM_PROMPT.format(context=context),
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    full_text.append(text)
                    yield f"data: {json.dumps({'text': text})}\n\n"
        except Exception as e:
            logger.exception("AI stream error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if full_text:
                complete = "".join(full_text)
                try:
                    with get_pool().connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "INSERT INTO flowmint.plan_messages (plan_id, role, content) VALUES (%s, %s, %s)",
                                (plan_id, "assistant", complete)
                            )
                            conn.commit()
                except Exception:
                    logger.exception("Failed to save assistant message")
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, current_user: dict = Depends(get_current_user)):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.plans WHERE id = %s AND user_id = %s",
                (plan_id, current_user["id"])
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Plan not found")
            conn.commit()
