"""Helpers for normalising incoming calculation requests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Request
from werkzeug.exceptions import BadRequest

from greektax.backend.app.localization import normalise_locale


def _resolve_locale(req: Request, payload: dict[str, Any]) -> None:
    """Populate the locale field in ``payload`` based on hints in ``req``."""

    locale = payload.get("locale")
    if isinstance(locale, str) and locale.strip():
        payload["locale"] = normalise_locale(locale)
        return

    locale_param = req.args.get("locale")
    if locale_param:
        payload["locale"] = normalise_locale(locale_param)
        return

    accept_language = req.headers.get("Accept-Language")
    if accept_language:
        primary = accept_language.split(",")[0].strip()
        if primary:
            payload["locale"] = normalise_locale(primary)


def parse_calculation_payload(req: Request) -> dict[str, Any]:
    """Extract and validate a JSON payload from ``req``."""

    data = req.get_json(silent=True)
    if data is None:
        raise BadRequest("Request body must be valid JSON")
    if not isinstance(data, Mapping):
        raise BadRequest("Request JSON must be an object")

    payload = dict(data)
    _resolve_locale(req, payload)

    return payload
