"""Metadata endpoints exposing configuration primitives to the front-end."""

from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request

from greektax.backend.app.localization import get_translator, normalise_locale
from greektax.backend.config.year_config import available_years, load_year_configuration

blueprint = Blueprint("config", __name__, url_prefix="/api/v1/config")


def _serialise_year(year: int) -> Dict[str, Any]:
    config = load_year_configuration(year)
    return {"year": year, "meta": dict(config.meta)}


@blueprint.get("/years")
def list_years() -> tuple[Any, int]:
    """Return all configured years with lightweight metadata."""

    years = [_serialise_year(year) for year in available_years()]
    default_year = years[-1]["year"] if years else None
    payload = {"years": years, "default_year": default_year}
    return jsonify(payload), 200


@blueprint.get("/<int:year>/investment-categories")
def get_investment_categories(year: int) -> tuple[Any, int]:
    """Expose configured investment categories with locale-aware labels."""

    try:
        config = load_year_configuration(year)
    except FileNotFoundError as exc:  # pragma: no cover - defensive routing
        return jsonify({"error": "not_found", "message": str(exc)}), 404

    locale_hint = request.args.get("locale")
    locale = normalise_locale(locale_hint)
    translator = get_translator(locale)

    categories = []
    for key, rate in sorted(config.investment.rates.items()):
        categories.append(
            {
                "id": key,
                "label": translator(f"details.investment.{key}"),
                "rate": rate,
            }
        )

    payload = {"year": year, "locale": translator.locale, "categories": categories}
    return jsonify(payload), 200
