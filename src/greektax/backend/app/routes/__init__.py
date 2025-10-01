"""Blueprint registrations for application routes."""

from flask import Flask

from .calculations import blueprint as calculations_blueprint
from .config import blueprint as config_blueprint
from .summaries import blueprint as summaries_blueprint
from .summaries import share_page_blueprint


def register_routes(app: Flask) -> None:
    """Register all Flask blueprints with the provided application."""

    app.register_blueprint(calculations_blueprint)
    app.register_blueprint(config_blueprint)
    app.register_blueprint(summaries_blueprint)
    app.register_blueprint(share_page_blueprint)
