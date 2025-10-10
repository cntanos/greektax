"""REST endpoints for tax calculations."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, request

from greektax.backend.services import (
    build_calculation_response,
    calculate_tax,
    parse_calculation_payload,
)

blueprint = Blueprint("calculations", __name__, url_prefix="/api/v1")


@blueprint.post("/calculations")
def create_calculation() -> tuple[Any, int]:
    """Create a tax calculation using the submitted JSON payload."""

    payload = parse_calculation_payload(request)
    result = calculate_tax(payload)

    return build_calculation_response(result)
