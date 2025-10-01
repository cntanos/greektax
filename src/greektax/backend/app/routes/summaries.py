"""Endpoints for persisting and exporting shareable tax summaries."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from http import HTTPStatus
from typing import Any, Mapping

from flask import Blueprint, Response, jsonify, request, url_for

from greektax.backend.app.services.share_service import (
    ExpiryFeedbackCollector,
    InMemoryShareRepository,
    SQLiteShareRepository,
    render_csv,
    render_html,
    render_pdf,
)

blueprint = Blueprint("summaries", __name__, url_prefix="/api/v1/summaries")
share_page_blueprint = Blueprint("share_page", __name__)

logger = logging.getLogger(__name__)


def _parse_positive_int(value: str | None, *, env: str) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = int(value)
    except ValueError:
        logger.warning("Ignoring invalid value for %s: %s", env, value)
        return None
    if parsed <= 0:
        logger.warning("Ignoring non-positive value for %s: %s", env, value)
        return None
    return parsed


def _build_repository() -> InMemoryShareRepository | SQLiteShareRepository:
    ttl = _parse_positive_int(os.getenv("GREEKTAX_SHARE_TTL"), env="GREEKTAX_SHARE_TTL")
    capacity = _parse_positive_int(
        os.getenv("GREEKTAX_SHARE_CAPACITY"), env="GREEKTAX_SHARE_CAPACITY"
    )

    kwargs: dict[str, Any] = {}
    if ttl is not None:
        kwargs["ttl_seconds"] = ttl
    if capacity is not None:
        kwargs["max_items"] = capacity

    db_path = os.getenv("GREEKTAX_SHARE_DB")
    if db_path:
        return SQLiteShareRepository(Path(db_path).expanduser(), **kwargs)

    return InMemoryShareRepository(**kwargs)


_REPOSITORY = _build_repository()
_FEEDBACK_COLLECTOR = ExpiryFeedbackCollector()


def _serialise_links(share_id: str) -> dict[str, str]:
    return {
        "self": url_for("summaries.get_summary", share_id=share_id),
        "html": url_for("summaries.get_summary_html", share_id=share_id),
        "share_page": url_for("share_page.view_share_page", share_id=share_id),
        "csv": url_for("summaries.download_summary_csv", share_id=share_id),
        "pdf": url_for("summaries.download_summary_pdf", share_id=share_id),
    }


@blueprint.post("")
def create_summary() -> tuple[Any, int]:
    payload = request.get_json(silent=True) or {}
    result = payload.get("result")
    if not isinstance(result, Mapping):
        return (
            jsonify(
                {
                    "error": "invalid_payload",
                    "message": "Request body must include a 'result' mapping",
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )

    record = _REPOSITORY.save(result)
    response = {
        "id": record.id,
        "links": _serialise_links(record.id),
        "meta": {
            "locale": record.locale,
            "expires_at": record.expires_at.isoformat(),
        },
    }
    return jsonify(response), HTTPStatus.CREATED


@blueprint.get("/<string:share_id>")
def get_summary(share_id: str) -> tuple[Any, int]:
    try:
        record = _REPOSITORY.get(share_id)
    except KeyError:
        return jsonify({"error": "not_found", "message": "Summary not found"}), HTTPStatus.NOT_FOUND

    return jsonify(record.payload), HTTPStatus.OK


@blueprint.get("/<string:share_id>/html")
def get_summary_html(share_id: str) -> tuple[str, int, dict[str, str]]:
    try:
        record = _REPOSITORY.get(share_id)
    except KeyError:
        return "Summary not found", HTTPStatus.NOT_FOUND, {"Content-Type": "text/plain"}

    html = render_html(record)
    return html, HTTPStatus.OK, {"Content-Type": "text/html; charset=utf-8"}


@blueprint.get("/<string:share_id>/csv")
def download_summary_csv(share_id: str) -> Response:
    try:
        record = _REPOSITORY.get(share_id)
    except KeyError:
        return Response("Summary not found", HTTPStatus.NOT_FOUND, mimetype="text/plain")

    csv_data = render_csv(record)
    response = Response(csv_data, mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f"attachment; filename=greektax-{share_id}.csv"
    return response


@blueprint.get("/<string:share_id>/pdf")
def download_summary_pdf(share_id: str) -> Response:
    try:
        record = _REPOSITORY.get(share_id)
    except KeyError:
        return Response("Summary not found", HTTPStatus.NOT_FOUND, mimetype="text/plain")

    pdf_bytes = render_pdf(record)
    response = Response(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f"attachment; filename=greektax-{share_id}.pdf"
    return response


@blueprint.post("/<string:share_id>/feedback")
def submit_feedback(share_id: str) -> tuple[Any, int]:
    try:
        record = _REPOSITORY.get(share_id)
    except KeyError:
        return jsonify({"error": "not_found", "message": "Summary not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}
    clarity = payload.get("clarity")
    notes = payload.get("notes")

    if not isinstance(clarity, str):
        return (
            jsonify({"error": "invalid_payload", "message": "Missing clarity response"}),
            HTTPStatus.BAD_REQUEST,
        )

    trimmed_notes = None
    if notes is not None:
        trimmed_notes = str(notes).strip()
        if len(trimmed_notes) > 500:
            return (
                jsonify({"error": "invalid_payload", "message": "Notes must be 500 characters or fewer"}),
                HTTPStatus.BAD_REQUEST,
            )
        if not trimmed_notes:
            trimmed_notes = None

    try:
        _FEEDBACK_COLLECTOR.submit(
            share_id=share_id,
            clarity=clarity,
            locale=record.locale,
            notes=trimmed_notes,
        )
    except ValueError as exc:
        return (
            jsonify({"error": "invalid_payload", "message": str(exc)}),
            HTTPStatus.BAD_REQUEST,
        )

    summary = _FEEDBACK_COLLECTOR.summary()
    return jsonify({"status": "received", "summary": summary}), HTTPStatus.ACCEPTED


@blueprint.get("/feedback/summary")
def feedback_summary() -> tuple[Any, int]:
    return jsonify(_FEEDBACK_COLLECTOR.summary()), HTTPStatus.OK


@share_page_blueprint.get("/share/<string:share_id>")
def view_share_page(share_id: str) -> Response:
    try:
        record = _REPOSITORY.get(share_id)
    except KeyError:
        return Response("Summary not found", HTTPStatus.NOT_FOUND, mimetype="text/plain")

    html = render_html(record)
    return Response(html, mimetype="text/html")


__all__ = ["blueprint", "share_page_blueprint"]
