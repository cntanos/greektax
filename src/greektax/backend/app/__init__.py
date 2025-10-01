"""Application factory for GreekTax backend services."""

from flask import Flask, jsonify
from werkzeug.exceptions import BadRequest

from .routes import register_routes


def create_app() -> Flask:
    """Create and configure the Flask application instance."""

    app = Flask(__name__)

    register_routes(app)

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
