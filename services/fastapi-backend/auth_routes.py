import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
import logging

import auth_utils
import db_users
from schemas import UserCreate, UserOut, TokenResponse, LoginRequest, PasswordRecoverRequest, PasswordResetRequest

logger = logging.getLogger(__name__)
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


@router.post("/auth/register", response_model=UserOut)
def register(payload: UserCreate):
    if not payload.password or len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password too long")
    try:
        if db_users.get_user_by_email(payload.email.lower()):
            raise HTTPException(status_code=400, detail="Email already registered")
        created = db_users.create_user(payload.email.lower(), payload.password)
        return UserOut(**created)
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.exception("Registration failed: %s", exc)
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/auth/token", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response):
    user = db_users.get_user_by_email(payload.email.lower())
    if not user or not auth_utils.verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = auth_utils.create_access_token({"sub": str(user["id"]), "email": user["email"]})
    refresh_token, expires_at = auth_utils.create_refresh_token()
    db_users.store_refresh_token(user["id"], refresh_token, expires_at)
    auth_utils.set_refresh_cookie(response, refresh_token, expires_at)

    include_refresh = os.environ.get("DEV_INSECURE_REFRESH") == "1"
    return TokenResponse(
        access_token=access_token,
        expires_in=int(auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES * 60),
        refresh_token=refresh_token if include_refresh else None
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token and os.environ.get("DEV_INSECURE_REFRESH") == "1":
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
        except Exception:
            pass

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    user = db_users.get_user_by_refresh_token(refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    db_users.revoke_refresh_token(refresh_token)
    new_refresh_token, expires_at = auth_utils.create_refresh_token()
    db_users.store_refresh_token(user["id"], new_refresh_token, expires_at)
    auth_utils.set_refresh_cookie(response, new_refresh_token, expires_at)

    access_token = auth_utils.create_access_token({"sub": str(user["id"]), "email": user["email"]})
    include_refresh = os.environ.get("DEV_INSECURE_REFRESH") == "1"
    return TokenResponse(
        access_token=access_token,
        expires_in=int(auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES * 60),
        refresh_token=new_refresh_token if include_refresh else None
    )


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        db_users.revoke_refresh_token(refresh_token)
    auth_utils.delete_refresh_cookie(response)
    return Response(status_code=204)


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = auth_utils.decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid access token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    try:
        user_id = int(sub)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    user = db_users.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/auth/me", response_model=UserOut)
def me(current_user: dict = Depends(get_current_user)):
    return UserOut(**current_user)
