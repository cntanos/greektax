"""Integration tests covering CORS behaviour for API endpoints."""

from flask.testing import FlaskClient


def test_config_years_endpoint_includes_cors_headers(client: FlaskClient) -> None:
    """Ensure cross-origin requests are permitted for public configuration data."""

    response = client.get(
        "/api/v1/config/years",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == "https://example.com"


def test_preflight_request_returns_success(client: FlaskClient) -> None:
    """Preflight checks should succeed so embedders can call the API."""

    response = client.options(
        "/api/v1/config/years",
        headers={
            "Origin": "https://embedder.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == "https://embedder.test"
    assert "GET" in response.headers.get("Access-Control-Allow-Methods", "")
