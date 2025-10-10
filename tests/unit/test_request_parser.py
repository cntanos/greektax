"""Unit tests for calculation request parsing helpers."""

from __future__ import annotations

import pytest
from flask import Flask, request
from werkzeug.exceptions import BadRequest

from greektax.backend.services.request_parser import parse_calculation_payload


def test_parse_payload_uses_accept_language(app: Flask) -> None:
    """Accept-Language header should supply the locale when absent."""

    with app.test_request_context(
        "/api/v1/calculations",
        method="POST",
        json={"year": 2024, "demographics": {"birth_year": 1985}},
        headers={"Accept-Language": "el"},
    ):
        payload = parse_calculation_payload(request)

    assert payload["locale"] == "el"


def test_parse_payload_preserves_explicit_locale(app: Flask) -> None:
    """Explicit locale fields should be normalised without overrides."""

    with app.test_request_context(
        "/api/v1/calculations",
        method="POST",
        json={"year": 2024, "locale": "el", "demographics": {"birth_year": 1985}},
    ):
        payload = parse_calculation_payload(request)

    assert payload["locale"] == "el"


def test_parse_payload_rejects_non_object(app: Flask) -> None:
    """Non-object JSON payloads should trigger BadRequest responses."""

    with app.test_request_context(
        "/api/v1/calculations",
        method="POST",
        json=["not", "an", "object"],
    ):
        with pytest.raises(BadRequest):
            parse_calculation_payload(request)
