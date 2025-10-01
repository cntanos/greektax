"""Integration tests for the static front-end preview."""

from flask.testing import FlaskClient


def test_frontend_index_is_served(client: FlaskClient) -> None:
    """The root route should serve the static UI entry point."""

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in (response.content_type or "").lower()
    assert b"GreekTax" in response.data


def test_frontend_assets_are_available(client: FlaskClient) -> None:
    """Static assets must be accessible to hydrate the preview UI."""

    response = client.get("/assets/scripts/main.js")

    assert response.status_code == 200
    assert "javascript" in (response.content_type or "").lower()
