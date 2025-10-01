"""Application factory for GreekTax backend services."""

from flask import Flask


def create_app() -> Flask:
    """Create and configure the Flask application instance.

    TODO: Register blueprints, configure localization, and initialize services
    once the calculation engine and data layers are implemented.
    """
    app = Flask(__name__)

    # TODO: Load configuration dynamically based on environment variables and
    # selected tax year once the configuration management module is completed.

    @app.route("/health", methods=["GET"])
    def health_check():
        """Simple health check endpoint for infrastructure monitoring.

        TODO: Extend with dependency checks (e.g., configuration availability)
        when ancillary services are introduced.
        """
        return {"status": "ok"}

    return app
