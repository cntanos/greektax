"""Application factory for GreekTax backend services."""

import os
from importlib import util as importlib_util
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast
from warnings import warn

from flask import Flask, Response, jsonify, request, send_from_directory
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import BadRequest

from .routes import register_routes
from .http import problem_response
from .routes.config import get_configuration_metadata

if TYPE_CHECKING:  # pragma: no cover - only for static type checkers
    from flask import Response
else:  # pragma: no cover - runtime branch
    from flask import Response  # type: ignore

CORS: Callable[..., None] | None

if importlib_util.find_spec("flask_cors") is not None:
    from flask_cors import CORS as _cors

    CORS = cast(Callable[..., None], _cors)
else:  # pragma: no cover - executed only when optional dependency missing
    CORS = None

# Resolve the repository root so we can serve the prototype front-end directly
# from ``src/frontend`` during local development.
FRONTEND_ROOT = Path(__file__).resolve().parents[4] / "src" / "frontend"
ASSETS_ROOT = FRONTEND_ROOT / "assets"


def _parse_allowed_origins(raw: str | None) -> set[str]:
    """Convert an environment variable into a normalised set of origins."""

    if not raw:
        return set()

    return {origin.strip() for origin in raw.split(",") if origin.strip()}


def _apply_default_cors_headers(
    response: ResponseReturnValue,
    allowed_origins: set[str],
) -> ResponseReturnValue:
    """Attach CORS headers for allowed origins when Flask-Cors is unavailable."""

    if not isinstance(response, Response):
        return response

    origin = request.headers.get("Origin")
    if origin and origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers.setdefault("Vary", "Origin")
        response.headers["Access-Control-Allow-Credentials"] = "false"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "Access-Control-Request-Headers",
            "Content-Type",
        )
        response.headers["Access-Control-Allow-Methods"] = request.headers.get(
            "Access-Control-Request-Method",
            request.method,
        )
    else:
        response.headers.pop("Access-Control-Allow-Origin", None)
        response.headers.pop("Access-Control-Allow-Credentials", None)
        response.headers.pop("Access-Control-Allow-Headers", None)
        response.headers.pop("Access-Control-Allow-Methods", None)

        vary = response.headers.get("Vary")
        if vary:
            vary_values = {value.strip() for value in vary.split(",")}
            vary_values.discard("Origin")
            if vary_values:
                response.headers["Vary"] = ", ".join(sorted(vary_values))
            else:
                response.headers.pop("Vary", None)

        if origin and request.method == "OPTIONS":
            response.status_code = 403

    return response


def create_app() -> Flask:
    """Create and configure the Flask application instance."""

    app = Flask(__name__)

    allowed_origins = _parse_allowed_origins(
        os.getenv("GREEKTAX_ALLOWED_ORIGINS")
    )

    if not allowed_origins:
        warn(
            "No allowed origins configured; cross-origin requests will be rejected.",
            stacklevel=1,
        )

    if CORS is not None:
        CORS(
            app,
            resources={r"/api/*": {"origins": sorted(allowed_origins)}},
            supports_credentials=False,
            methods=["GET", "OPTIONS", "POST"],
            allow_headers=["Content-Type"],
        )
    else:
        warn(
            "Flask-Cors is not installed; falling back to a minimal CORS implementation. "
            "Install the 'Flask-Cors' extra for production use.",
            stacklevel=1,
        )

        @app.before_request
        def _handle_preflight() -> ResponseReturnValue | None:
            if request.method == "OPTIONS":
                origin = request.headers.get("Origin")
                if origin and origin not in allowed_origins:
                    response = app.make_response(("", 403))
                    return _apply_default_cors_headers(response, allowed_origins)

                response = app.make_default_options_response()
                return _apply_default_cors_headers(response, allowed_origins)
            return None

        @app.after_request
        def _attach_cors_headers(response: ResponseReturnValue) -> ResponseReturnValue:
            return _apply_default_cors_headers(response, allowed_origins)

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

        payload = {"status": "ok", **get_configuration_metadata()}
        return jsonify(payload)

    @app.errorhandler(BadRequest)
    def handle_bad_request(error: BadRequest):
        """Return consistent JSON responses for malformed payloads."""

        message = error.description or "Invalid request"
        return problem_response("bad_request", status=400, message=message).to_response()

    @app.errorhandler(ValueError)
    def handle_value_error(error: ValueError):
        """Gracefully surface domain validation errors to clients."""

        return problem_response(
            "validation_error", status=400, message=str(error)
        ).to_response()

    return app
