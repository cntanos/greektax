"""Tests for the localisation catalogue helpers."""

from __future__ import annotations

import json
from pathlib import Path

from greektax.backend.app.localization import get_translator, load_translations


def _read_backend_value(locale: str, key: str) -> str:
    root = Path("src/greektax/translations")
    payload = json.loads(root.joinpath(f"{locale}.json").read_text(encoding="utf-8"))
    return str(payload["backend"][key])


def test_get_translator_loads_shared_catalogue() -> None:
    """The translator should pull labels from the shared JSON catalogue."""

    translator = get_translator("el")

    expected = _read_backend_value("el", "summary.tax_total")
    assert translator("summary.tax_total") == expected


def test_get_translator_falls_back_to_default_locale() -> None:
    """Unknown locales should fall back to the base catalogue."""

    translator = get_translator("fr")

    assert translator.locale == "en"
    expected = _read_backend_value("en", "summary.tax_total")
    assert translator("summary.tax_total") == expected


def test_load_translations_exposes_catalogue_payload() -> None:
    """The API helper should expose both backend and frontend catalogues."""

    payload = load_translations("en")

    assert payload["locale"] == "en"
    assert "available_locales" in payload and "en" in payload["available_locales"]
    assert payload["backend"]["summary.tax_total"] == _read_backend_value("en", "summary.tax_total")
    assert isinstance(payload["frontend"], dict)
    assert payload["fallback"]["locale"] == "en"
    assert payload["fallback"]["backend"]["summary.tax_total"] == _read_backend_value(
        "en", "summary.tax_total"
    )

