"""Blueprint registrations for application routes."""

from flask import Blueprint

api_blueprint = Blueprint("api", __name__)

# TODO: Implement endpoints for tax calculation, configuration metadata, and
# localization resources. They should delegate heavy-lifting to dedicated
# service modules within ``greektax.backend.app.services``.
