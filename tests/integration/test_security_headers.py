"""Integration tests for default security headers."""

from __future__ import annotations

from http import HTTPStatus

from flask.testing import FlaskClient


def test_api_responses_include_security_headers(client: FlaskClient) -> None:
    """API responses should include baseline hardening headers."""

    response = client.get("/api/v1/config/meta")

    assert response.status_code == HTTPStatus.OK
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Cache-Control") == "no-store"


def test_secure_requests_include_hsts_header(client: FlaskClient) -> None:
    """HSTS should be added when the app is behind HTTPS termination."""

    response = client.get("/health", headers={"X-Forwarded-Proto": "https"})

    assert response.status_code == HTTPStatus.OK
    assert response.headers.get("Strict-Transport-Security") == (
        "max-age=31536000; includeSubDomains"
    )
