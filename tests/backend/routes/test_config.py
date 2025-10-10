"""Regression coverage for the configuration API payloads."""

from __future__ import annotations

import json
from pathlib import Path

from flask.testing import FlaskClient

from greektax.backend.config.year_config import available_years

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "config_snapshots"


def _load_snapshot(year: int) -> dict[str, object]:
    path = SNAPSHOT_DIR / f"config_{year}.json"
    return json.loads(path.read_text())


def test_list_years_payload_matches_snapshot(client: FlaskClient) -> None:
    response = client.get("/api/v1/config/years")

    assert response.status_code == 200

    payload = response.get_json()
    years = available_years()
    expected_years = [_load_snapshot(year) for year in years]

    assert payload["years"] == expected_years

    expected_default = expected_years[-1]["year"] if expected_years else None
    assert payload["default_year"] == expected_default
