"""Utilities for serialising calculation responses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Tuple

from flask import jsonify

ResponseTuple = Tuple[Any, int]


def build_calculation_response(payload: Mapping[str, Any]) -> ResponseTuple:
    """Return a Flask JSON response for the calculation ``payload``."""

    return jsonify(payload), 200
