"""
routes/user_routes.py
  GET /api/user/history
  GET /api/user/history/<id>
  GET /api/user/stats
"""
import json
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db

user_bp = Blueprint("user", __name__, url_prefix="/api/user")


@user_bp.route("/history", methods=["GET"])
@jwt_required()
def history():
    user_id = int(get_jwt_identity())
    conn = get_db()
    rows = conn.execute(
        """SELECT id, job_title, company, match_score, matched_keywords, created_at
           FROM applications WHERE user_id = ? ORDER BY created_at DESC LIMIT 30""",
        (user_id,)
    ).fetchall()
    conn.close()

    apps = []
    for r in rows:
        try:
            keywords = json.loads(r["matched_keywords"] or "[]")
        except Exception:
            keywords = []
        apps.append({
            "id": r["id"],
            "jobTitle": r["job_title"],
            "company": r["company"],
            "matchScore": r["match_score"],
            "matchedKeywords": keywords,
            "createdAt": r["created_at"],
        })
    return jsonify({"applications": apps}), 200


@user_bp.route("/history/<int:app_id>", methods=["GET"])
@jwt_required()
def history_detail(app_id):
    user_id = int(get_jwt_identity())
    conn = get_db()
    row = conn.execute(
        """SELECT id, job_title, company, match_score, matched_keywords,
                  generated_cv, generated_cl, created_at
           FROM applications WHERE id = ? AND user_id = ?""",
        (app_id, user_id)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Application not found."}), 404

    try:
        keywords = json.loads(row["matched_keywords"] or "[]")
    except Exception:
        keywords = []

    return jsonify({
        "id": row["id"],
        "jobTitle": row["job_title"],
        "company": row["company"],
        "matchScore": row["match_score"],
        "matchedKeywords": keywords,
        "generatedCV": row["generated_cv"],
        "generatedCL": row["generated_cl"],
        "createdAt": row["created_at"],
    }), 200


@user_bp.route("/stats", methods=["GET"])
@jwt_required()
def stats():
    user_id = int(get_jwt_identity())
    conn = get_db()
    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM applications WHERE user_id = ?", (user_id,)
    ).fetchone()["cnt"]
    cl_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM applications WHERE user_id = ? AND generated_cl IS NOT NULL AND generated_cl != ''",
        (user_id,)
    ).fetchone()["cnt"]
    avg_row = conn.execute(
        "SELECT AVG(match_score) as avg FROM applications WHERE user_id = ? AND match_score IS NOT NULL",
        (user_id,)
    ).fetchone()
    conn.close()

    return jsonify({
        "totalApplications": total,
        "coverLettersGenerated": cl_count,
        "averageMatchScore": round(avg_row["avg"]) if avg_row["avg"] else None,
    }), 200
