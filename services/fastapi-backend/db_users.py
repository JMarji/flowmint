from typing import Optional, Dict, Any
from datetime import datetime, timezone
import logging

from database import get_pool
import auth_utils

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, hashed_password, is_active FROM flowmint.users WHERE email = %s",
                (email,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "email": row[1], "hashed_password": row[2], "is_active": row[3]}


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, hashed_password, is_active FROM flowmint.users WHERE id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "email": row[1], "hashed_password": row[2], "is_active": row[3]}


def create_user(email: str, password: str) -> Dict[str, Any]:
    hashed = auth_utils.hash_password(password)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO flowmint.users (email, hashed_password) VALUES (%s, %s) RETURNING id, email, is_active",
                (email, hashed)
            )
            row = cur.fetchone()
            conn.commit()
            return {"id": row[0], "email": row[1], "is_active": row[2]}


def store_refresh_token(user_id: int, refresh_token: str, expires_at: datetime):
    token_hash = auth_utils.hash_refresh_token(refresh_token)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO flowmint.refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
                (user_id, token_hash, expires_at)
            )
            conn.commit()


def get_user_by_refresh_token(refresh_token: str) -> Optional[Dict[str, Any]]:
    token_hash = auth_utils.hash_refresh_token(refresh_token)
    now = _now_utc()
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT u.id, u.email, u.hashed_password, u.is_active
                   FROM flowmint.refresh_tokens rt
                   JOIN flowmint.users u ON rt.user_id = u.id
                   WHERE rt.token_hash = %s AND rt.expires_at > %s
                   LIMIT 1""",
                (token_hash, now)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "email": row[1], "hashed_password": row[2], "is_active": row[3]}


def revoke_refresh_token(refresh_token: str):
    token_hash = auth_utils.hash_refresh_token(refresh_token)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM flowmint.refresh_tokens WHERE token_hash = %s", (token_hash,))
            conn.commit()


def revoke_all_user_refresh_tokens(user_id: int):
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM flowmint.refresh_tokens WHERE user_id = %s", (user_id,))
            conn.commit()


def update_user_password(user_id: int, new_password: str) -> bool:
    hashed = auth_utils.hash_password(new_password)
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE flowmint.users SET hashed_password = %s WHERE id = %s",
                (hashed, user_id)
            )
            affected = cur.rowcount
            conn.commit()
            return affected > 0
