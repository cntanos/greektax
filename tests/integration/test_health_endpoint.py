"""Integration tests for application endpoints."""

from http import HTTPStatus

from flask.testing import FlaskClient

from greektax.backend.config import year_config
from greektax.backend.version import get_project_version


def test_health_endpoint(client: FlaskClient) -> None:
    """Ensure the health endpoint returns a successful status payload."""
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["version"] == get_project_version()
    assert payload["supported_years"] == list(year_config.available_years())
    assert payload["default_year"] == payload["supported_years"][-1]
    assert response.mimetype == "application/json"
