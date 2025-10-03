"""Integration tests for application endpoints."""

from http import HTTPStatus

from flask.testing import FlaskClient


def test_health_endpoint(client: FlaskClient) -> None:
    """Ensure the health endpoint returns a successful status payload."""
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK
    assert response.json == {"status": "ok"}
    assert response.mimetype == "application/json"
