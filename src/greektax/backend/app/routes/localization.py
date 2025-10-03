"""Expose translation catalogues to front-end consumers."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from greektax.backend.app.localization import load_translations

blueprint = Blueprint("translations", __name__, url_prefix="/api/v1/translations")


@blueprint.get("/")
def get_default_translations():
    """Return translations for the requested or default locale."""

    locale_hint = request.args.get("locale")
    payload = load_translations(locale_hint)
    return jsonify(payload), 200


@blueprint.get("/<locale>")
def get_locale_translations(locale: str):
    """Return translations for a specific locale slug."""

    payload = load_translations(locale)
    return jsonify(payload), 200
