"""Test configuration utilities and shared fixtures."""

import sys
from pathlib import Path

# Ensure the ``src`` directory is importable when tests are executed without an
# editable install. This keeps developer experience smooth for first-time
# contributors running ``pytest`` directly in VS Code.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest
from flask import Flask
from flask.testing import FlaskClient

from greektax.backend.app import create_app
from greektax.backend.app.routes import summaries
from greektax.backend.app.services.share_service import InMemoryShareRepository


@pytest.fixture()
def app() -> Flask:
    """Return a configured Flask application for integration tests."""

    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """Provide a test client bound to the configured Flask app."""

    return app.test_client()


@pytest.fixture(autouse=True)
def reset_share_repository() -> None:
    """Ensure each test case operates with a fresh share repository."""

    summaries._REPOSITORY = InMemoryShareRepository()
