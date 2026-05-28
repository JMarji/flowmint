from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import os
import logging
import re
from datetime import date
from typing import Optional
from database import get_pool
from auth_routes import get_current_user

router = APIRouter(tags=["planning"])
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a thoughtful financial planning assistant embedded in Flowmint, a personal finance app.

Help the user think through their financial plans and scenarios concretely. Use their actual financial data when discussing numbers. Be direct, realistic, and specific.

When the user asks about scenarios - paying off debt early, making investments, big purchases, starting a business, agricultural or land projects - do the following:
- Calculate concrete timelines and numbers based on their actual balances and cashflow
- Identify real trade-offs (liquidity, risk, opportunity cost)
- Give honest assessments of feasibility
- Ask clarifying questions when you need more detail to give useful advice

Don't be overly cautious or hedge everything with disclaimers. This is a personal finance tool for someone who wants to think things through, not a legal document.

If the user asks to add or update plan todos, use the current todo list context and explicitly reference todo item IDs when useful.

Here is the user's current financial snapshot and current plan todo list:
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
        lines.append("\n*No financial data linked yet - advise the user to connect accounts in Flowmint for more specific guidance.*")

    return "\n".join(lines)


class PlanCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    property_id: Optional[int] = None


class PlanTodoCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class PlanTodoUpdate(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=500)
    done: Optional[bool] = None


class ChatMessage(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _verify_property_owner(property_id: int, user_id: int) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM flowmint.properties WHERE id = %s AND user_id = %s",
                (property_id, user_id),
            )
            return cur.fetchone() is not None


def _get_plan_for_user(plan_id: int, user_id: int) -> dict:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, property_id, created_at FROM flowmint.plans WHERE id = %s AND user_id = %s",
                (plan_id, user_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {
        "id": row[0],
        "title": row[1],
        "property_id": row[2],
        "created_at": row[3].isoformat(),
    }


def _list_plan_todos(plan_id: int) -> list[dict]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, content, done, position, created_at, updated_at
                FROM flowmint.plan_todos
                WHERE plan_id = %s
                ORDER BY done ASC, position ASC, id ASC
                """,
                (plan_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "content": r[1],
            "done": bool(r[2]),
            "position": r[3],
            "created_at": r[4].isoformat(),
            "updated_at": r[5].isoformat(),
        }
        for r in rows
    ]


def _format_todo_context(plan_id: int) -> str:
    todos = _list_plan_todos(plan_id)
    lines = ["## Current Plan Todos"]
    if not todos:
        lines.append("No todos yet.")
        return "\n".join(lines)

    for todo in todos:
        status = "done" if todo["done"] else "open"
        lines.append(f"- #{todo['id']} [{status}] {todo['content']}")
    return "\n".join(lines)


def _extract_new_todo_content(message: str) -> Optional[str]:
    patterns = [
        r"(?:add|create|new)\s+(?:a\s+)?(?:todo|task)(?:\s+item)?(?:\s*(?:to|:|-)\s*|\s+)(.+)",
        r"(?:add|put)\s+(.+?)\s+(?:to|on)\s+(?:my\s+)?(?:todo|task)(?:\s+list)?",
        r"(?:todo|task)\s*[:\-]\s*(.+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, message, flags=re.IGNORECASE)
        if m:
            content = re.sub(r"\s+", " ", m.group(1)).strip(" \t\n\r\"'")
            content = content.rstrip(". ")
            if content:
                return content[:500]
    return None


def _apply_todo_actions_from_user_message(plan_id: int, message: str) -> list[str]:
    text = (message or "").strip()
    if not text:
        return []

    summaries: list[str] = []
    changed = False

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            # Add todo action
            new_content = _extract_new_todo_content(text)
            if new_content:
                cur.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 FROM flowmint.plan_todos WHERE plan_id = %s",
                    (plan_id,),
                )
                next_pos = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO flowmint.plan_todos (plan_id, content, done, position)
                    VALUES (%s, %s, FALSE, %s)
                    RETURNING id
                    """,
                    (plan_id, new_content, next_pos),
                )
                todo_id = cur.fetchone()[0]
                summaries.append(f"added todo #{todo_id}: {new_content}")
                changed = True

            # Rename todo action by id
            rename_match = re.search(
                r"(?:rename|update|edit)\s+(?:todo|task)\s*#?(\d+)\s*(?:to|:)\s*(.+)",
                text,
                flags=re.IGNORECASE,
            )
            if rename_match:
                todo_id = int(rename_match.group(1))
                new_text = re.sub(r"\s+", " ", rename_match.group(2)).strip(" \t\n\r\"'")[:500]
                if new_text:
                    cur.execute(
                        """
                        UPDATE flowmint.plan_todos
                        SET content = %s, updated_at = NOW()
                        WHERE id = %s AND plan_id = %s
                        RETURNING id
                        """,
                        (new_text, todo_id, plan_id),
                    )
                    if cur.fetchone():
                        summaries.append(f"updated todo #{todo_id}")
                        changed = True

            # Status update action by id
            status_match = re.search(
                r"(?:mark|set)\s+(?:todo|task)\s*#?(\d+)\s+(?:as\s+)?(done|complete|completed|in progress|pending|open|todo)",
                text,
                flags=re.IGNORECASE,
            )
            if status_match:
                todo_id = int(status_match.group(1))
                state = status_match.group(2).lower()
                done = state in ("done", "complete", "completed")
                cur.execute(
                    """
                    UPDATE flowmint.plan_todos
                    SET done = %s, updated_at = NOW()
                    WHERE id = %s AND plan_id = %s
                    RETURNING id
                    """,
                    (done, todo_id, plan_id),
                )
                if cur.fetchone():
                    summaries.append(f"marked todo #{todo_id} as {'done' if done else 'open'}")
                    changed = True

            # Shortcut complete/reopen actions by id
            complete_match = re.search(
                r"(?:complete|finish|check\s*off|done)\s+(?:todo|task)\s*#?(\d+)",
                text,
                flags=re.IGNORECASE,
            )
            if complete_match:
                todo_id = int(complete_match.group(1))
                cur.execute(
                    """
                    UPDATE flowmint.plan_todos
                    SET done = TRUE, updated_at = NOW()
                    WHERE id = %s AND plan_id = %s
                    RETURNING id
                    """,
                    (todo_id, plan_id),
                )
                if cur.fetchone():
                    summaries.append(f"marked todo #{todo_id} as done")
                    changed = True

            reopen_match = re.search(
                r"(?:reopen|undo|uncheck)\s+(?:todo|task)\s*#?(\d+)",
                text,
                flags=re.IGNORECASE,
            )
            if reopen_match:
                todo_id = int(reopen_match.group(1))
                cur.execute(
                    """
                    UPDATE flowmint.plan_todos
                    SET done = FALSE, updated_at = NOW()
                    WHERE id = %s AND plan_id = %s
                    RETURNING id
                    """,
                    (todo_id, plan_id),
                )
                if cur.fetchone():
                    summaries.append(f"reopened todo #{todo_id}")
                    changed = True

        if changed:
            conn.commit()

    return summaries


@router.get("/plans")
def list_plans(
    property_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    if property_id is not None and not _verify_property_owner(property_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Property not found")

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            if property_id is None:
                cur.execute(
                    "SELECT id, title, property_id, created_at FROM flowmint.plans WHERE user_id = %s ORDER BY created_at DESC",
                    (current_user["id"],),
                )
            else:
                cur.execute(
                    "SELECT id, title, property_id, created_at FROM flowmint.plans WHERE user_id = %s AND property_id = %s ORDER BY created_at DESC",
                    (current_user["id"], property_id),
                )
            rows = cur.fetchall()
    return [{"id": r[0], "title": r[1], "property_id": r[2], "created_at": r[3].isoformat()} for r in rows]


@router.post("/plans", status_code=201)
def create_plan(body: PlanCreate, current_user: dict = Depends(get_current_user)):
    clean_title = body.title.strip()
    if not clean_title:
        raise HTTPException(status_code=422, detail="Plan title is required")
    if body.property_id is not None and not _verify_property_owner(body.property_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Property not found")

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO flowmint.plans (user_id, title, property_id) VALUES (%s, %s, %s) RETURNING id, title, property_id, created_at",
                (current_user["id"], clean_title, body.property_id),
            )
            r = cur.fetchone()
            conn.commit()
    return {"id": r[0], "title": r[1], "property_id": r[2], "created_at": r[3].isoformat()}


@router.get("/plans/{plan_id}/messages")
def get_messages(plan_id: int, current_user: dict = Depends(get_current_user)):
    _get_plan_for_user(plan_id, current_user["id"])
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, created_at FROM flowmint.plan_messages WHERE plan_id = %s ORDER BY created_at ASC",
                (plan_id,),
            )
            rows = cur.fetchall()
    return [{"role": r[0], "content": r[1], "created_at": r[2].isoformat()} for r in rows]


@router.get("/plans/{plan_id}/todos")
def list_plan_todos(plan_id: int, current_user: dict = Depends(get_current_user)):
    _get_plan_for_user(plan_id, current_user["id"])
    return _list_plan_todos(plan_id)


@router.post("/plans/{plan_id}/todos", status_code=201)
def create_plan_todo(plan_id: int, body: PlanTodoCreate, current_user: dict = Depends(get_current_user)):
    _get_plan_for_user(plan_id, current_user["id"])
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Todo content is required")

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM flowmint.plan_todos WHERE plan_id = %s",
                (plan_id,),
            )
            next_pos = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO flowmint.plan_todos (plan_id, content, done, position)
                VALUES (%s, %s, FALSE, %s)
                RETURNING id, content, done, position, created_at, updated_at
                """,
                (plan_id, content, next_pos),
            )
            row = cur.fetchone()
            conn.commit()

    return {
        "id": row[0],
        "content": row[1],
        "done": bool(row[2]),
        "position": row[3],
        "created_at": row[4].isoformat(),
        "updated_at": row[5].isoformat(),
    }


@router.put("/plans/{plan_id}/todos/{todo_id}")
def update_plan_todo(
    plan_id: int,
    todo_id: int,
    body: PlanTodoUpdate,
    current_user: dict = Depends(get_current_user),
):
    _get_plan_for_user(plan_id, current_user["id"])

    updates = []
    params: list = []
    if body.content is not None:
        clean_content = body.content.strip()
        if not clean_content:
            raise HTTPException(status_code=422, detail="Todo content cannot be empty")
        updates.append("content = %s")
        params.append(clean_content)
    if body.done is not None:
        updates.append("done = %s")
        params.append(body.done)

    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")

    updates.append("updated_at = NOW()")

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE flowmint.plan_todos
                SET {', '.join(updates)}
                WHERE id = %s AND plan_id = %s
                RETURNING id, content, done, position, created_at, updated_at
                """,
                params + [todo_id, plan_id],
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Todo not found")
            conn.commit()

    return {
        "id": row[0],
        "content": row[1],
        "done": bool(row[2]),
        "position": row[3],
        "created_at": row[4].isoformat(),
        "updated_at": row[5].isoformat(),
    }


@router.delete("/plans/{plan_id}/todos/{todo_id}", status_code=204)
def delete_plan_todo(plan_id: int, todo_id: int, current_user: dict = Depends(get_current_user)):
    _get_plan_for_user(plan_id, current_user["id"])
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM flowmint.plan_todos WHERE id = %s AND plan_id = %s",
                (todo_id, plan_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Todo not found")
            conn.commit()


@router.post("/plans/{plan_id}/chat")
def chat(plan_id: int, body: ChatMessage, current_user: dict = Depends(get_current_user)):
    plan = _get_plan_for_user(plan_id, current_user["id"])

    # Save user message first.
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO flowmint.plan_messages (plan_id, role, content) VALUES (%s, %s, %s)",
                (plan_id, "user", body.content)
            )
            conn.commit()

    todo_action_summaries = _apply_todo_actions_from_user_message(plan_id, body.content)

    # Fetch full conversation history (includes the just-saved user message).
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM flowmint.plan_messages WHERE plan_id = %s ORDER BY created_at ASC",
                (plan_id,)
            )
            rows = cur.fetchall()

    messages = [{"role": r[0], "content": r[1]} for r in rows]
    if todo_action_summaries:
        messages.append(
            {
                "role": "assistant",
                "content": (
                    "Flowmint system note: I already updated the todo list from the latest user request: "
                    + "; ".join(todo_action_summaries)
                    + ". Acknowledge this briefly, then continue with financial planning advice."
                ),
            }
        )

    context_parts = [_get_financial_context(current_user["id"]), _format_todo_context(plan_id)]
    if plan.get("property_id") is not None:
        context_parts.append(f"## Plan Scope\nThis plan is attached to property_id={plan['property_id']}.")
    context = "\n\n".join(context_parts)

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
    _get_plan_for_user(plan_id, current_user["id"])
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM flowmint.plans WHERE id = %s", (plan_id,))
            conn.commit()
