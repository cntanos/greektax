"""Integration tests for the translations API."""

from __future__ import annotations

import json
from pathlib import Path

from flask.testing import FlaskClient

TRANSLATIONS_ROOT = Path("src/greektax/translations")


def _load_backend_value(locale: str, key: str) -> str:
    payload = json.loads(TRANSLATIONS_ROOT.joinpath(f"{locale}.json").read_text(encoding="utf-8"))
    backend = payload.get("backend", {})
    return str(backend[key])


def _load_frontend_value(locale: str, *key_parts: str) -> str:
    payload = json.loads(TRANSLATIONS_ROOT.joinpath(f"{locale}.json").read_text(encoding="utf-8"))
    cursor = payload.get("frontend", {})
    for part in key_parts:
        if not isinstance(cursor, dict) or part not in cursor:
            raise AssertionError(f"Missing frontend key for locale {locale}: {'.'.join(key_parts)}")
        cursor = cursor[part]
    return str(cursor)


def test_translations_endpoint_returns_default_catalogue(client: FlaskClient) -> None:
    response = client.get("/api/v1/translations/")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["locale"] == "en"
    assert "el" in payload["available_locales"]
    assert payload["backend"]["summary.tax_total"] == _load_backend_value("en", "summary.tax_total")
    assert (
        payload["frontend"]["calculator"]["heading"]
        == _load_frontend_value("en", "calculator", "heading")
    )
    assert payload["fallback"]["locale"] == "en"


def test_translations_endpoint_respects_locale_path(client: FlaskClient) -> None:
    response = client.get("/api/v1/translations/el")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["locale"] == "el"
    assert payload["backend"]["summary.tax_total"] == _load_backend_value("el", "summary.tax_total")
    assert (
        payload["frontend"]["calculator"]["heading"]
        == _load_frontend_value("el", "calculator", "heading")
    )
    assert payload["fallback"]["locale"] == "en"
