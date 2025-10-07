"""Integration tests covering CORS behaviour for API endpoints."""

import pytest
from flask.testing import FlaskClient

from greektax.backend.app import create_app

ALLOWED_ORIGIN = "https://allowed.test"
ALLOWED_EMBEDDER = "https://embedder.test"
DISALLOWED_ORIGIN = "https://blocked.test"


@pytest.fixture()
def cors_client(monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    """Return a client configured with a known CORS allow-list."""

    monkeypatch.setenv(
        "GREEKTAX_ALLOWED_ORIGINS",
        ",".join([ALLOWED_ORIGIN, ALLOWED_EMBEDDER]),
    )

    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client:
        yield client


def test_config_years_endpoint_includes_cors_headers(
    cors_client: FlaskClient,
) -> None:
    """Ensure cross-origin requests are permitted for configured origins."""

    response = cors_client.get(
        "/api/v1/config/years",
        headers={"Origin": ALLOWED_ORIGIN},
    )

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == ALLOWED_ORIGIN


def test_preflight_request_returns_success(cors_client: FlaskClient) -> None:
    """Preflight checks should succeed for allowed origins."""

    response = cors_client.options(
        "/api/v1/config/years",
        headers={
            "Origin": ALLOWED_EMBEDDER,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == ALLOWED_EMBEDDER
    assert "GET" in response.headers.get("Access-Control-Allow-Methods", "")


def test_disallowed_origin_does_not_receive_cors_headers(
    cors_client: FlaskClient,
) -> None:
    """Origins outside the allow-list should not receive CORS access."""

    response = cors_client.get(
        "/api/v1/config/years",
        headers={"Origin": DISALLOWED_ORIGIN},
    )

    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") is None


def test_disallowed_origin_preflight_is_rejected(cors_client: FlaskClient) -> None:
    """Preflight requests from disallowed origins should not succeed."""

    response = cors_client.options(
        "/api/v1/config/years",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code in (200, 403)
    assert response.headers.get("Access-Control-Allow-Origin") is None
