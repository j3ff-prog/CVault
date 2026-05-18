"""
routes/auth_routes.py
Authentication endpoints:
  POST /api/auth/signup
  POST /api/auth/login
  POST /api/auth/forgot-password
  POST /api/auth/reset-password
  GET  /api/auth/me
"""
import os
import threading
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from database import get_db
from services.auth_service import hash_password, verify_password
from services.email_service import send_welcome, send_password_reset
from services.credits_service import add_credits, get_credits
from utils.token_utils import generate_reset_token, validate_reset_token, mark_token_used

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Owner email — this account always has unlimited credits
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "Jeff.006760@gmail.com").strip().lower()


def _ensure_owner_unlimited(user_id: int) -> None:
    """
    Make sure the owner account always has an unlimited-forever credit pass.
    Called on every login so it self-heals even if the DB is wiped.
    """
    add_credits(user_id, "owner_unlimited")


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    first_name = (data.get("firstName") or "").strip()
    last_name  = (data.get("lastName") or "").strip()
    email      = (data.get("email") or "").strip().lower()
    phone      = (data.get("phone") or "").strip()
    password   = data.get("password") or ""

    if not all([first_name, last_name, email, phone, password]):
        return jsonify({"error": "All fields are required."}), 400
    if "@" not in email:
        return jsonify({"error": "Invalid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "An account with this email already exists."}), 409

    password_hash = hash_password(password)
    cur = conn.execute(
        "INSERT INTO users (first_name, last_name, email, phone, password_hash) VALUES (?, ?, ?, ?, ?)",
        (first_name, last_name, email, phone, password_hash)
    )
    user_id = cur.lastrowid
    conn.execute("INSERT INTO credits (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    # If owner is signing up, give unlimited immediately
    if email == OWNER_EMAIL:
        _ensure_owner_unlimited(user_id)

   # Send welcome email in background — never block or crash signup
    import threading
    def _send_welcome_bg():
        try:
             send_welcome(email, first_name)
        except Exception as e:
            print(f"[AUTH] Welcome email failed: {e}")
    threading.Thread(target=_send_welcome_bg, daemon=True).start()

    token = create_access_token(identity=str(user_id))
    credits = get_credits(user_id)

    return jsonify({
        "message": "Account created successfully.",
        "token": token,
        "user": {
            "id": user_id,
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
            "phone": phone,
        },
        "credits": credits,
        "isOwner": email == OWNER_EMAIL,
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT id, first_name, last_name, email, phone, password_hash, is_active FROM users WHERE email = ?",
        (email,)
    ).fetchone()
    conn.close()

    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Incorrect email or password."}), 401
    if not user["is_active"]:
        return jsonify({"error": "This account has been deactivated."}), 403

    user_id = user["id"]

    # ── OWNER PRIVILEGE ────────────────────────────────────────────────
    # Every time the owner logs in, refresh their unlimited pass.
    # This means Jeff always has unlimited access just by logging in —
    # no payment needed, no expiry, works even if DB is reset.
    is_owner = email == OWNER_EMAIL
    if is_owner:
        _ensure_owner_unlimited(user_id)
    # ──────────────────────────────────────────────────────────────────

    token = create_access_token(identity=str(user_id))
    credits = get_credits(user_id)

    return jsonify({
        "message": "Login successful.",
        "token": token,
        "user": {
            "id": user_id,
            "firstName": user["first_name"],
            "lastName": user["last_name"],
            "email": user["email"],
            "phone": user["phone"],
        },
        "credits": credits,
        "isOwner": is_owner,
    }), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    conn = get_db()
    user = conn.execute(
        "SELECT id, first_name, last_name, email, phone FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "User not found."}), 404

    is_owner = user["email"].lower() == OWNER_EMAIL
    credits = get_credits(user_id)

    # Refresh owner unlimited on /me calls too (e.g. page refresh)
    if is_owner:
        _ensure_owner_unlimited(user_id)
        credits = get_credits(user_id)

    return jsonify({
        "id": user["id"],
        "firstName": user["first_name"],
        "lastName": user["last_name"],
        "email": user["email"],
        "phone": user["phone"],
        "credits": credits,
        "isOwner": is_owner,
    }), 200


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required."}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT id, first_name FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    # Always 200 to prevent email enumeration
    if not user:
        return jsonify({"message": "If that email is registered, a reset link has been sent."}), 200

    token = generate_reset_token(user["id"])

    import threading
    def _send_reset_bg():
      try:
         send_password_reset(email, user["first_name"], token)
      except Exception as e:
        print(f"[AUTH] Reset email failed: {e}")
    threading.Thread(target=_send_reset_bg, daemon=True).start()

    return jsonify({"message": "Password reset link sent to your email."}), 200


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    token        = (data.get("token") or "").strip()
    new_password = data.get("password") or ""

    if not token or not new_password:
        return jsonify({"error": "Token and new password are required."}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    user_id = validate_reset_token(token)
    if not user_id:
        return jsonify({"error": "This reset link is invalid or has expired."}), 400

    password_hash = hash_password(new_password)
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    conn.close()
    mark_token_used(token)

    return jsonify({"message": "Password updated successfully. You can now log in."}), 200
