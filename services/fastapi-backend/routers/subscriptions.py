from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import cancel_directory
import db_plaid
import db_subscriptions
from auth_routes import get_current_user

router = APIRouter(tags=["subscriptions"])

Status = Literal["active", "cancelled", "kept"]


class TrackBody(BaseModel):
    account_db_id: int
    stream_id: str = Field(..., min_length=1, max_length=200)
    merchant_name: str = Field(..., min_length=1, max_length=200)
    frequency: Optional[str] = None
    last_amount: Optional[float] = None
    monthly_amount: Optional[float] = None
    next_date: Optional[date] = None
    status: Status
    cancelled_on: Optional[date] = None


class UpdateBody(BaseModel):
    status: Optional[Status] = None
    cancelled_on: Optional[date] = None
    alert_dismissed: Optional[bool] = None


def _check_cancel_date(d: Optional[date]):
    if d and d > date.today():
        raise HTTPException(status_code=422, detail="cancelled_on can't be in the future")


def _with_cancel_info(sub: dict) -> dict:
    return {**sub, "cancel_info": cancel_directory.lookup(sub["merchant_name"])}


@router.get("/subscriptions")
def list_subscriptions(current_user: dict = Depends(get_current_user)):
    """All tracked subscriptions with savings summary and still-charging alerts."""
    db_subscriptions.detect_still_charging(current_user["id"])
    subs = db_subscriptions.list_for_user(current_user["id"])
    return {
        "subscriptions": [_with_cancel_info(s) for s in subs],
        "summary": db_subscriptions.summarize(subs),
    }


@router.post("/subscriptions", status_code=201)
def track_subscription(body: TrackBody, current_user: dict = Depends(get_current_user)):
    """Record a decision (cancelled / kept / active) on a Plaid recurring stream."""
    _check_cancel_date(body.cancelled_on)
    acct = db_plaid.get_account_for_user(current_user["id"], body.account_db_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    try:
        sub_id = db_subscriptions.upsert(
            user_id=current_user["id"],
            account_id=acct["account_id"],
            stream_id=body.stream_id,
            merchant_name=body.merchant_name.strip(),
            frequency=body.frequency,
            last_amount=body.last_amount,
            monthly_amount=body.monthly_amount,
            next_expected_date=body.next_date.isoformat() if body.next_date else None,
            status=body.status,
            cancelled_on=body.cancelled_on.isoformat() if body.cancelled_on else None,
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Account not found")
    # A back-dated cancellation may already have a charge after it.
    db_subscriptions.detect_still_charging(current_user["id"])
    return _with_cancel_info(db_subscriptions.get(current_user["id"], sub_id))


@router.patch("/subscriptions/{sub_id}")
def update_subscription(sub_id: int, body: UpdateBody, current_user: dict = Depends(get_current_user)):
    """Change status (re-cancel, undo, keep) or dismiss a still-charging alert."""
    uid = current_user["id"]
    if not db_subscriptions.get(uid, sub_id):
        raise HTTPException(status_code=404, detail="Subscription not found")
    if body.status is not None:
        _check_cancel_date(body.cancelled_on)
        db_subscriptions.set_status(
            uid, sub_id, body.status, body.cancelled_on.isoformat() if body.cancelled_on else None
        )
        db_subscriptions.detect_still_charging(uid)
    if body.alert_dismissed:
        db_subscriptions.dismiss_alert(uid, sub_id)
    return _with_cancel_info(db_subscriptions.get(uid, sub_id))


@router.delete("/subscriptions/{sub_id}", status_code=204)
def forget_subscription(sub_id: int, current_user: dict = Depends(get_current_user)):
    """Stop tracking — the stream goes back to an undecided active subscription."""
    if not db_subscriptions.delete(current_user["id"], sub_id):
        raise HTTPException(status_code=404, detail="Subscription not found")


@router.get("/subscriptions/cancel-info")
def cancel_info(
    merchant: str = Query(..., min_length=1, max_length=200),
    description: Optional[str] = Query(None, max_length=300),
    current_user: dict = Depends(get_current_user),
):
    return cancel_directory.lookup(merchant, description)
