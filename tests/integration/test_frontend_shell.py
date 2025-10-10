"""Integration tests for the static front-end shell."""

from http import HTTPStatus

from flask.testing import FlaskClient


def test_frontend_index_is_served(client: FlaskClient) -> None:
    """The root route should serve the static UI entry point."""

    response = client.get("/")

    assert response.status_code == HTTPStatus.OK
    assert "text/html" in (response.content_type or "").lower()
    assert b"GreekTax" in response.data


def test_frontend_assets_are_available(client: FlaskClient) -> None:
    """Static assets must be accessible to hydrate the UI shell."""

    bootstrap_response = client.get("/assets/scripts/bootstrap.js")
    main_module_response = client.get("/assets/scripts/main.js")

    assert bootstrap_response.status_code == HTTPStatus.OK
    assert "javascript" in (bootstrap_response.content_type or "").lower()

    assert main_module_response.status_code == HTTPStatus.OK
    assert "javascript" in (main_module_response.content_type or "").lower()
