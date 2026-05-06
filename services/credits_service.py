"""
services/credits_service.py
Credit balance logic — read, add, consume, check.
"""
from datetime import datetime, timedelta, timezone
from database import get_db


def get_credits(user_id: int) -> dict:
    conn = get_db()
    row = conn.execute(
        "SELECT single_credits, triple_credits, unlimited_until FROM credits WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {"single_credits": 0, "triple_credits": 0, "unlimited_until": None}
    return {
        "single_credits": row["single_credits"],
        "triple_credits": row["triple_credits"],
        "unlimited_until": row["unlimited_until"],
    }


def is_unlimited(user_id: int) -> bool:
    c = get_credits(user_id)
    if c["unlimited_until"]:
        try:
            exp = datetime.fromisoformat(c["unlimited_until"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return exp > datetime.now(timezone.utc)
        except ValueError:
            return False
    return False


def has_credits(user_id: int) -> bool:
    c = get_credits(user_id)
    if c["single_credits"] > 0:
        return True
    if c["triple_credits"] > 0:
        return True
    return is_unlimited(user_id)


def add_credits(user_id: int, plan_type: str) -> dict:
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO credits (user_id) VALUES (?)", (user_id,))
    if plan_type == "single":
        conn.execute(
            "UPDATE credits SET single_credits = single_credits + 1 WHERE user_id = ?",
            (user_id,)
        )
    elif plan_type == "triple":
        conn.execute(
            "UPDATE credits SET triple_credits = triple_credits + 1 WHERE user_id = ?",
            (user_id,)
        )
    elif plan_type == "unlimited":
        expires = datetime.now(timezone.utc) + timedelta(hours=24)
        conn.execute(
            "UPDATE credits SET unlimited_until = ? WHERE user_id = ?",
            (expires.isoformat(), user_id)
        )
    elif plan_type == "owner_unlimited":
        # Special plan — owner gets unlimited that never expires
        # Set expiry 100 years from now
        expires = datetime.now(timezone.utc) + timedelta(days=365 * 100)
        conn.execute(
            "UPDATE credits SET unlimited_until = ? WHERE user_id = ?",
            (expires.isoformat(), user_id)
        )
    else:
        conn.close()
        raise ValueError(f"Unknown plan type: {plan_type}")

    conn.commit()
    credits = get_credits(user_id)
    conn.close()
    return credits


def consume_credit(user_id: int) -> bool:
    """
    Deduct one use. Order: unlimited pass → single → triple.
    Returns True if deducted, False if no credits.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT single_credits, triple_credits, unlimited_until FROM credits WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    # Check unlimited
    if row["unlimited_until"]:
        try:
            exp = datetime.fromisoformat(row["unlimited_until"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > datetime.now(timezone.utc):
                conn.close()
                return True  # Active pass — no deduction needed
        except ValueError:
            pass

    # Single credits
    if row["single_credits"] > 0:
        conn.execute(
            "UPDATE credits SET single_credits = single_credits - 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()
        return True

    # Triple pack → convert 1 pack into 3 uses, use 1, keep 2
    if row["triple_credits"] > 0:
        conn.execute(
            """UPDATE credits
               SET triple_credits = triple_credits - 1,
                   single_credits = single_credits + 2
               WHERE user_id = ?""",
            (user_id,)
        )
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False
