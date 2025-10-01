"""Integration tests for application endpoints."""

import pytest
from flask.testing import FlaskClient

from greektax.backend.app import create_app


@pytest.fixture()
def client() -> FlaskClient:
    """Create a test client for the Flask app."""
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_health_endpoint(client: FlaskClient) -> None:
    """Ensure the health endpoint returns a successful status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}

    # TODO: Extend with dependency readiness assertions once services are wired.
