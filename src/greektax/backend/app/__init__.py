"""Application factory for GreekTax backend services."""

from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import BadRequest

from .routes import register_routes

# Resolve the repository root so we can serve the prototype front-end directly
# from ``src/frontend`` during local development.
FRONTEND_ROOT = Path(__file__).resolve().parents[4] / "src" / "frontend"
ASSETS_ROOT = FRONTEND_ROOT / "assets"


def create_app() -> Flask:
    """Create and configure the Flask application instance."""

    app = Flask(__name__)

    register_routes(app)

    @app.route("/", methods=["GET"])
    def serve_frontend():
        """Return the static UI entry point for the local shell."""

        return send_from_directory(FRONTEND_ROOT, "index.html")

    @app.route("/assets/<path:filename>", methods=["GET"])
    def serve_frontend_assets(filename: str):
        """Expose static assets (CSS/JS) used by the prototype UI shell."""

        return send_from_directory(ASSETS_ROOT, filename)

    @app.route("/health", methods=["GET"])
    def health_check():
        """Simple health check endpoint for infrastructure monitoring."""

        return {"status": "ok"}

    @app.errorhandler(BadRequest)
    def handle_bad_request(error: BadRequest):
        """Return consistent JSON responses for malformed payloads."""

        message = error.description or "Invalid request"
        return jsonify({"error": "bad_request", "message": message}), 400

    @app.errorhandler(ValueError)
    def handle_value_error(error: ValueError):
        """Gracefully surface domain validation errors to clients."""

        return jsonify({"error": "validation_error", "message": str(error)}), 400

    return app
