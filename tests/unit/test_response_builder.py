"""Unit tests for response formatting helpers."""

from __future__ import annotations

from flask import Flask

from greektax.backend.services.response_builder import build_calculation_response


def test_build_calculation_response_returns_json(app: Flask) -> None:
    """Formatting helper should generate a JSON response tuple."""

    with app.app_context():
        response, status = build_calculation_response({"foo": "bar"})

    assert status == 200
    assert response.get_json() == {"foo": "bar"}
