"""
routes/generate_routes.py
CV tailoring endpoint — protected by real payment verification.

Protection order:
  1. JWT must be valid (user is logged in)
  2. session["paid"] must be True (real Paystack verification happened)
  3. User must have credits remaining
"""
import json
from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import get_db
from services.cv_extractor import extract_text
from services.gemini_service import tailor_cv
from services.credits_service import has_credits, consume_credit


from flask import session, jsonify


EXEMPT_USER_IDS = {1}  # replace 1 with YOUR actual user_id

def is_exempt_user(user_id):
    return user_id in EXEMPT_USER_IDS

generate_bp = Blueprint("generate", __name__, url_prefix="/api")


@generate_bp.route("/generate", methods=["POST"])
@jwt_required()
def generate():
    user_id = int(get_jwt_identity())

    # ── GATE 1: Real payment must have been verified this session ─────────
    # session["paid"] is only set by /api/payments/verify after Paystack
    # confirms the transaction. A redirect alone does NOT set this.

    

    if not session.get("paid") and user_id not in EXEMPT_USER_IDS:

        return jsonify({
            "error": "payment_required",
            "message": "Payment verification required. Please complete payment before generating."
        }), 403

    # Extra safety: make sure the session belongs to this user
    if session.get("paid_user") and session.get("paid_user") != user_id:
        return jsonify({
            "error": "payment_required",
            "message": "Session mismatch. Please log in again."
        }), 403

    # ── GATE 2: User must have credits in the database ────────────────────
    if not has_credits(user_id):
        # Clear the paid flag — they need to top up
        session.pop("paid", None)
        return jsonify({
            "error": "no_credits",
            "message": "You have no credits. Please top up to continue."
        }), 402

    # ── Get CV text ───────────────────────────────────────────────────────
    cv_text = ""

    if "cvFile" in request.files:
        cv_file = request.files["cvFile"]
        if cv_file and cv_file.filename:
            try:
                cv_text = extract_text(cv_file)
            except (ValueError, RuntimeError) as e:
                return jsonify({"error": str(e)}), 400

    if not cv_text:
        cv_text = (
            request.form.get("cvText")
            or (request.get_json(silent=True) or {}).get("cvText")
            or ""
        ).strip()

    if not cv_text:
        return jsonify({"error": "Please upload your CV or paste it as text."}), 400
    if len(cv_text) < 100:
        return jsonify({"error": "Your CV is too short. Please provide the full CV text."}), 400

    # ── Get job description ───────────────────────────────────────────────
    job_description = (
        request.form.get("jobDescription")
        or (request.get_json(silent=True) or {}).get("jobDescription")
        or ""
    ).strip()

    if not job_description:
        return jsonify({"error": "Please paste the job description."}), 400
    if len(job_description) < 80:
        return jsonify({"error": "The job description is too short. Please paste the full posting."}), 400

    # ── Call Gemini ───────────────────────────────────────────────────────
    try:
        result = tailor_cv(cv_text, job_description)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    # ── Consume one credit ────────────────────────────────────────────────
    consumed = consume_credit(user_id)
    if not consumed:
        session.pop("paid", None)
        return jsonify({
            "error": "no_credits",
            "message": "Credit could not be deducted. Please top up and try again."
        }), 402

    # ── If user now has 0 credits remaining, clear the paid session ───────
    # This forces re-verification on the next payment before generating again.
    if not has_credits(user_id):
        session.pop("paid", None)
        session.pop("paid_ref", None)
        session.pop("paid_user", None)

    # ── Save to application history ───────────────────────────────────────
    try:
        plain_cv = _build_plain_cv(result)
        cover_letter = result.get("coverLetter", "")
        jd_lines = [l.strip() for l in job_description.split("\n") if l.strip()]
        job_title = jd_lines[0][:100] if jd_lines else "Job Application"

        conn = get_db()
        conn.execute(
            """INSERT INTO applications
               (user_id, job_title, match_score, matched_keywords, generated_cv, generated_cl)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                job_title,
                result.get("matchScore"),
                json.dumps(result.get("matchedKeywords", [])),
                plain_cv,
                cover_letter,
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[GENERATE] History save failed: {e}")

    return jsonify(result), 200


def _build_plain_cv(p: dict) -> str:
    cv = p.get("tailoredCV") or {}
    out = ""
    if p.get("candidateName"): out += p["candidateName"] + "\n"
    if p.get("contactInfo"):   out += p["contactInfo"] + "\n"
    out += "\n"
    if cv.get("summary"):
        out += "PROFESSIONAL SUMMARY\n" + cv["summary"] + "\n\n"
    if cv.get("experience"):
        out += "WORK EXPERIENCE\n"
        for e in cv["experience"]:
            out += f"{e.get('title','')} — {e.get('company','')} ({e.get('period','')})\n"
            for b in e.get("bullets", []):
                out += f"• {b}\n"
            out += "\n"
    if cv.get("education"):
        out += "EDUCATION\n"
        for e in cv["education"]:
            line = e.get("degree", "")
            if e.get("institution"): line += f", {e['institution']}"
            if e.get("year"):        line += f" ({e['year']})"
            out += line + "\n"
        out += "\n"
    if cv.get("skills"):
        out += "SKILLS\n" + " · ".join(cv["skills"]) + "\n"
    return out
