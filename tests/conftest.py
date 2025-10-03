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

import pytest  # noqa: E402
from flask import Flask  # noqa: E402
from flask.testing import FlaskClient  # noqa: E402

from greektax.backend.app import create_app  # noqa: E402


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


