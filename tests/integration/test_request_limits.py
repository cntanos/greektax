"""Integration tests for request body size limits."""

from __future__ import annotations

from http import HTTPStatus

import pytest

from greektax.backend.app import create_app


def test_calculation_endpoint_rejects_oversized_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Oversized JSON bodies should return a structured 413 response."""

    monkeypatch.setenv("GREEKTAX_MAX_REQUEST_BYTES", "200")
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    large_category = "x" * 1_000
    response = client.post(
        "/api/v1/calculations",
        json={
            "year": 2024,
            "employment": {"gross_income": 1000},
            "freelance": {"efka_category": large_category},
        },
    )

    assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    payload = response.get_json()
    assert payload["error"] == "payload_too_large"
