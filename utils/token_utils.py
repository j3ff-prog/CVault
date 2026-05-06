"""
utils/token_utils.py
Password reset token generation and validation.
"""
import secrets
from datetime import datetime, timedelta, timezone
from database import get_db


def generate_reset_token(user_id: int) -> str:
    token = secrets.token_urlsafe(48)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    conn = get_db()
    conn.execute(
        "UPDATE reset_tokens SET used = 1 WHERE user_id = ? AND used = 0",
        (user_id,)
    )
    conn.execute(
        "INSERT INTO reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at)
    )
    conn.commit()
    conn.close()
    return token


def validate_reset_token(token: str):
    conn = get_db()
    row = conn.execute(
        "SELECT user_id, expires_at, used FROM reset_tokens WHERE token = ?",
        (token,)
    ).fetchone()
    conn.close()
    if not row or row["used"]:
        return None
    try:
        exp = datetime.fromisoformat(row["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            return None
    except ValueError:
        return None
    return row["user_id"]


def mark_token_used(token: str) -> None:
    conn = get_db()
    conn.execute("UPDATE reset_tokens SET used = 1 WHERE token = ?", (token,))
    conn.commit()
    conn.close()
