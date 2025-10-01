"""REST endpoints for tax calculations."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest

from greektax.backend.app.localization import normalise_locale
from greektax.backend.app.services.calculation_service import calculate_tax

blueprint = Blueprint("calculations", __name__, url_prefix="/api/v1")


def _resolve_locale(payload: Dict[str, Any]) -> None:
    """Populate locale in payload using explicit or header-based hints."""

    if "locale" in payload and payload["locale"]:
        payload["locale"] = normalise_locale(str(payload["locale"]))
        return

    locale_param = request.args.get("locale")
    if locale_param:
        payload["locale"] = normalise_locale(locale_param)
        return

    accept_language = request.headers.get("Accept-Language")
    if accept_language:
        primary = accept_language.split(",")[0].strip()
        if primary:
            payload["locale"] = normalise_locale(primary)


@blueprint.post("/calculations")
def create_calculation() -> tuple[Any, int]:
    """Create a tax calculation using the submitted JSON payload."""

    data = request.get_json(silent=True)
    if data is None:
        raise BadRequest("Request body must be valid JSON")
    if not isinstance(data, Mapping):
        raise BadRequest("Request JSON must be an object")

    payload: Dict[str, Any] = dict(data)
    _resolve_locale(payload)

    result = calculate_tax(payload)

    return jsonify(result), 200
