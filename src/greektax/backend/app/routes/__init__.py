"""Blueprint registrations for application routes."""

from flask import Flask

from .calculations import blueprint as calculations_blueprint


def register_routes(app: Flask) -> None:
    """Register all Flask blueprints with the provided application."""

    app.register_blueprint(calculations_blueprint)
