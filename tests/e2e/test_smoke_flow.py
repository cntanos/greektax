"""Smoke-level end-to-end flow checks for the hosted shell + API path."""

from __future__ import annotations

from http import HTTPStatus

from flask.testing import FlaskClient


def test_smoke_user_flow(client: FlaskClient) -> None:
    """A user can load the shell and submit a basic calculation payload."""

    shell = client.get("/")
    assert shell.status_code == HTTPStatus.OK
    html = shell.data.decode("utf-8")
    assert 'id="calculator-form"' in html
    assert 'type="module" src="./assets/scripts/main.js"' in html

    calculation = client.post(
        "/api/v1/calculations",
        json={"year": 2024, "employment": {"gross_income": 22_000}},
    )
    assert calculation.status_code == HTTPStatus.OK
    payload = calculation.get_json()
    assert "summary" in payload
    assert "details" in payload
