"""
app.py
CVault — Flask backend + static frontend served from one place.
"""
import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

from database import init_db
from routes.auth_routes import auth_bp
from routes.generate_routes import generate_bp
from routes.payment_routes import payment_bp
from routes.user_routes import user_bp

load_dotenv()

EXEMPT_EMAILS = {"jeff.006760@gmail.com"}


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")

    # ── Config ──────────────────────────────────────────────────────────
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-CHANGE-IN-PRODUCTION")
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-CHANGE-IN-PRODUCTION")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

    # ── Session config ───────────────────────────────────────────────────
    # Flask session is signed with SECRET_KEY (already set above).
    # SameSite=None + Secure required when frontend and backend are same origin
    # on Render (HTTPS). For local dev we relax this.
    is_production = os.getenv("FLASK_ENV") == "production"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = is_production    # True on Render (HTTPS), False locally
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_NAME"] = "cvault_session"

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS(app, origins=[
        os.getenv("FRONTEND_URL", ""),
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ], supports_credentials=True)

    # ── JWT ──────────────────────────────────────────────────────────────
    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def unauthorized_callback(reason):
        return jsonify({"error": "Authentication required. Please log in."}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"error": "Invalid or expired token. Please log in again."}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Your session has expired. Please log in again."}), 401

    # ── Blueprints ────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(generate_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(user_bp)

    # ── Health check ──────────────────────────────────────────────────────
    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok", "service": "CVault API", "version": "1.0.0"}), 200

    # ── Serve frontend pages ──────────────────────────────────────────────
    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        file_path = os.path.join(app.static_folder, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")

    # ── Error handlers ────────────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request."}), 400

    @app.errorhandler(404)
    def not_found(e):
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(413)
    def file_too_large(e):
        return jsonify({"error": "File too large. Maximum upload size is 10 MB."}), 413

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error. Please try again."}), 500

    return app


app = create_app()

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    init_db()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    print(f"[CVault] Running on http://localhost:{port}  (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)