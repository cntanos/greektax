"""HTTP helper utilities shared across Flask blueprints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flask import jsonify


@dataclass(frozen=True)
class ProblemResponse:
    """Lightweight representation of an RFC 7807-style error payload."""

    error: str
    status: int
    message: str | None = None
    extra: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the serialisable payload for this problem response."""

        payload: dict[str, Any] = {"error": self.error}
        if self.message:
            payload["message"] = self.message
        if self.extra:
            payload.update(self.extra)
        return payload

    def to_response(self) -> tuple[Any, int]:
        """Convert the problem payload into a Flask response tuple."""

        return jsonify(self.as_dict()), self.status


def problem_response(
    error: str,
    *,
    status: int,
    message: str | None = None,
    **extra: Any,
) -> ProblemResponse:
    """Convenience factory mirroring Flask's ``jsonify`` interface."""

    additional: Mapping[str, Any] | None = extra or None
    return ProblemResponse(error=error, status=status, message=message, extra=additional)


__all__ = ["ProblemResponse", "problem_response"]
