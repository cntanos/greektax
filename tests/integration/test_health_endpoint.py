"""Integration tests for application endpoints."""

from flask.testing import FlaskClient


def test_health_endpoint(client: FlaskClient) -> None:
    """Ensure the health endpoint returns a successful status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}

    # TODO: Extend with dependency readiness assertions once services are wired.
