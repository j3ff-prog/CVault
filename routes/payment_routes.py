"""
routes/payment_routes.py
Payment endpoints:
  POST /api/payments/verify    — frontend calls after Paystack redirect
  POST /api/payments/webhook   — Paystack calls server-to-server
  GET  /api/payments/credits   — get current credit balance
  GET  /api/payments/history   — payment history
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import get_db
from services.paystack_service import verify_transaction, verify_webhook_signature, get_plan_from_amount
from services.credits_service import add_credits, get_credits
from flask import session
payment_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


@payment_bp.route("/verify", methods=["POST"])
@jwt_required()
def verify():
    """
    Called by the payment success page after Paystack redirects back.
    Sends { reference } → verifies with Paystack API → adds credits only if real.
    Sets session["paid"] = True on success so /generate can check it.
    """
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    reference = (data.get("reference") or "").strip()

    if not reference:
        return jsonify({"status": "failed", "error": "Payment reference is required."}), 400

    conn = get_db()

    # ── Idempotency: already verified this reference → don't double-credit ──
    existing = conn.execute(
        "SELECT status FROM payments WHERE paystack_ref = ?", (reference,)
    ).fetchone()
    if existing and existing["status"] == "success":
        conn.close()
        # Still set session so browser tab gets access even on refresh
        session["paid"] = True
        session["paid_ref"] = reference
        return jsonify({
            "status": "success",
            "message": "Already verified.",
            "credits": get_credits(user_id)
        }), 200

    # ── Call Paystack to verify the transaction ───────────────────────────
    try:
        tx = verify_transaction(reference)   # raises ValueError if not success
    except ValueError as e:
        # Payment not successful according to Paystack
        _upsert_payment(conn, user_id, reference, "unknown", 0, "failed")
        conn.close()
        session.pop("paid", None)            # make sure session is NOT set
        return jsonify({"status": "failed", "error": str(e)}), 400
    except RuntimeError as e:
        # Network / API error — don't credit, but don't block either
        conn.close()
        return jsonify({"status": "failed", "error": str(e)}), 503

    # ── Paystack confirmed success ────────────────────────────────────────
    amount_kobo = tx.get("amount", 0)
    amount_kes  = amount_kobo // 100
    plan_type   = get_plan_from_amount(amount_kobo)

    if plan_type == "unknown":
        conn.close()
        return jsonify({
            "status": "failed",
            "error": f"Unrecognised payment amount: KES {amount_kes}"
        }), 400

    # Record payment
    from datetime import datetime, timezone
    _upsert_payment(
        conn, user_id, reference, plan_type, amount_kes, "success",
        verified_at=datetime.now(timezone.utc).isoformat()
    )
    conn.close()

    # Add credits to user account
    updated_credits = add_credits(user_id, plan_type)

    # ── Set server-side session flag ──────────────────────────────────────
    # This is what /api/generate checks before allowing generation.
    session["paid"] = True
    session["paid_ref"] = reference
    session["paid_user"] = user_id

    return jsonify({
        "status": "success",
        "plan": plan_type,
        "amountKes": amount_kes,
        "credits": updated_credits
    }), 200


@payment_bp.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Paystack-Signature", "")
    if not verify_webhook_signature(request.data, signature):
        return jsonify({"error": "Invalid signature."}), 401

    event = request.get_json(silent=True) or {}
    if event.get("event") != "charge.success":
        return jsonify({"status": "ignored"}), 200

    tx = event.get("data", {})
    reference = tx.get("reference", "")
    amount_kobo = tx.get("amount", 0)
    amount_kes = amount_kobo // 100
    customer_email = (tx.get("customer") or {}).get("email", "").lower()
    plan_type = get_plan_from_amount(amount_kobo)

    if not reference or plan_type == "unknown":
        return jsonify({"status": "skipped"}), 200

    conn = get_db()
    user = conn.execute("SELECT id FROM users WHERE email = ?", (customer_email,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"status": "user_not_found"}), 200

    user_id = user["id"]
    existing = conn.execute(
        "SELECT status FROM payments WHERE paystack_ref = ?", (reference,)
    ).fetchone()

    if existing and existing["status"] == "success":
        conn.close()
        return jsonify({"status": "already_processed"}), 200

    from datetime import datetime, timezone
    _upsert_payment(conn, user_id, reference, plan_type, amount_kes, "success",
                    verified_at=datetime.now(timezone.utc).isoformat())
    conn.close()

    add_credits(user_id, plan_type)
    print(f"[WEBHOOK] Credited user {user_id} plan='{plan_type}' ref={reference}")

    return jsonify({"status": "ok"}), 200


@payment_bp.route("/credits", methods=["GET"])
@jwt_required()
def credits():
    user_id = int(get_jwt_identity())
    return jsonify(get_credits(user_id)), 200


@payment_bp.route("/history", methods=["GET"])
@jwt_required()
def payment_history():
    user_id = int(get_jwt_identity())
    conn = get_db()
    rows = conn.execute(
        """SELECT paystack_ref, plan_type, amount_kes, status, created_at
           FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 20""",
        (user_id,)
    ).fetchall()
    conn.close()
    return jsonify({"payments": [dict(r) for r in rows]}), 200


def _upsert_payment(conn, user_id, reference, plan_type, amount_kes, status, verified_at=None):
    existing = conn.execute(
        "SELECT id FROM payments WHERE paystack_ref = ?", (reference,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE payments SET status = ?, verified_at = ? WHERE paystack_ref = ?",
            (status, verified_at, reference)
        )
    else:
        conn.execute(
            """INSERT INTO payments (user_id, paystack_ref, plan_type, amount_kes, status, verified_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, reference, plan_type, amount_kes, status, verified_at)
        )
    conn.commit()




"""
Updated payment verification logic for CVault.

ADD this new route to routes/payment_routes.py
(or register it as a separate blueprint if preferred)

This replaces the redirect-only trust model with real Paystack verification.
"""

# ── ADD THIS IMPORT at the top of routes/payment_routes.py ──────────────
# from flask import session   ← add this alongside existing imports

# ════════════════════════════════════════════════════════════════════════
# UPDATED /api/payments/verify  —  replace the existing verify() function
# ════════════════════════════════════════════════════════════════════════

