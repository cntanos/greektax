#!/usr/bin/env python3
"""Generate calculation fixtures from the Python engine.

The fixtures pin the exact output of ``calculate_tax`` for a broad, deterministic
set of payloads. They serve two purposes:

* any change in calculation behaviour shows up as a fixture diff in review;
* a second implementation of the engine (the planned client-side port) can be
  checked against them for exact parity.

Usage::

    python scripts/generate_parity_fixtures.py          # rewrite fixtures
    python scripts/generate_parity_fixtures.py --check  # fail if stale
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from greektax.backend.app.services.calculation_service import (  # noqa: E402
    calculate_tax,
)
from greektax.backend.config.year_config import (  # noqa: E402
    available_years,
    load_year_configuration,
)

OUTPUT_DIR = ROOT / "tests" / "data" / "parity"
REGRESSION_PATH = ROOT / "tests" / "data" / "regression_scenarios.json"
SEED = 20261002

# Amounts around every bracket edge and the salary-credit reduction threshold.
EDGE_AMOUNTS = (
    0.0,
    4_999.99,
    9_999.99,
    10_000.0,
    10_000.01,
    12_000.0,
    12_000.01,
    15_000.0,
    19_999.99,
    20_000.0,
    20_000.01,
    25_000.0,
    30_000.0,
    30_000.01,
    40_000.0,
    40_000.01,
    50_000.0,
    60_000.0,
    60_000.01,
    85_000.0,
    150_000.0,
)
CHILDREN = (0, 1, 2, 3, 4, 5, 7)
# No birth year (no youth relief), then one birth year in each youth band
# (age 26 to 30, and 25 or under) for every year's age reference year.
BIRTH_YEARS = (None, 1998, 2004)


def _year_fields(year: int) -> dict[str, Any]:
    config = load_year_configuration(year)
    return {
        "employment_payments": list(config.employment.payroll.allowed_payments_per_year),
        "pension_payments": list(config.pension.payroll.allowed_payments_per_year),
        "efka_categories": [category.id for category in config.freelance.efka_categories],
        "investment_categories": list(config.investment.rates),
    }


def _demographics(birth_year: int | None) -> dict[str, Any]:
    return {} if birth_year is None else {"demographics": {"birth_year": birth_year}}


def _regression_cases() -> list[dict[str, Any]]:
    scenarios = json.loads(REGRESSION_PATH.read_text("utf-8"))
    return [
        {"name": f"regression/{item['name']}", "payload": item["payload"]}
        for item in scenarios
    ]


def _grid_cases(year: int) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    for amount in EDGE_AMOUNTS:
        for children in CHILDREN:
            for birth_year in BIRTH_YEARS:
                cases.append(
                    {
                        "name": f"grid/employment/{amount}/{children}/{birth_year}",
                        "payload": {
                            "year": year,
                            "dependents": {"children": children},
                            "employment": {"gross_income": amount},
                            **_demographics(birth_year),
                        },
                    }
                )

    for category in ("pension", "freelance", "agricultural", "other"):
        for amount in EDGE_AMOUNTS:
            for children in (0, 4):
                for birth_year in (None, 2004):
                    if category == "pension":
                        section = {"pension": {"gross_income": amount}}
                    elif category == "freelance":
                        section = {"freelance": {"profit": amount}}
                    elif category == "agricultural":
                        section = {
                            "agricultural": {
                                "gross_revenue": amount,
                                "professional_farmer": children % 4 == 0,
                            }
                        }
                    else:
                        section = {"other": {"taxable_income": amount}}
                    cases.append(
                        {
                            "name": f"grid/{category}/{amount}/{children}/{birth_year}",
                            "payload": {
                                "year": year,
                                "dependents": {"children": children},
                                **section,
                                **_demographics(birth_year),
                            },
                        }
                    )

    for amount in EDGE_AMOUNTS:
        cases.append(
            {
                "name": f"grid/rental/{amount}",
                "payload": {
                    "year": year,
                    "rental": {"gross_income": amount, "deductible_expenses": amount / 10},
                },
            }
        )

    return cases


def _random_amount(rng: random.Random, high: float) -> float:
    if rng.random() < 0.3:
        return 0.0
    return round(rng.uniform(0, high), 2)


def _random_cases(year: int, count: int, rng: random.Random) -> list[dict[str, Any]]:
    fields = _year_fields(year)
    cases: list[dict[str, Any]] = []

    for index in range(count):
        payload: dict[str, Any] = {
            "year": year,
            "locale": rng.choice(("en", "en", "el")),
            "dependents": {"children": rng.choice(CHILDREN)},
        }
        birth_year = rng.choice(BIRTH_YEARS)
        demographics: dict[str, Any] = {}
        if birth_year is not None:
            demographics["birth_year"] = birth_year
        if rng.random() < 0.1:
            demographics["tax_residency_transfer_to_greece"] = True
        if demographics:
            payload["demographics"] = demographics

        if rng.random() < 0.7:
            employment: dict[str, Any] = {}
            if rng.random() < 0.5:
                employment["gross_income"] = _random_amount(rng, 90_000)
            else:
                employment["monthly_income"] = _random_amount(rng, 5_000)
            employment["payments_per_year"] = rng.choice(fields["employment_payments"])
            if rng.random() < 0.3:
                employment["employee_contributions"] = _random_amount(rng, 6_000)
            if rng.random() < 0.2:
                employment["include_social_contributions"] = False
            payload["employment"] = employment

        if rng.random() < 0.3:
            pension: dict[str, Any] = {"gross_income": _random_amount(rng, 40_000)}
            pension["payments_per_year"] = rng.choice(fields["pension_payments"])
            payload["pension"] = pension

        if rng.random() < 0.4:
            freelance: dict[str, Any] = {}
            if rng.random() < 0.5:
                freelance["profit"] = _random_amount(rng, 80_000)
            else:
                freelance["gross_revenue"] = _random_amount(rng, 120_000)
                freelance["deductible_expenses"] = _random_amount(rng, 40_000)
            if fields["efka_categories"] and rng.random() < 0.6:
                freelance["efka_category"] = rng.choice(fields["efka_categories"])
                freelance["efka_months"] = rng.choice((0, 1, 6, 12))
            for key in ("mandatory", "auxiliary", "lump_sum"):
                if rng.random() < 0.3:
                    freelance[f"{key}_contributions"] = _random_amount(rng, 4_000)
            freelance["include_trade_fee"] = rng.random() < 0.7
            freelance["trade_fee_location"] = rng.choice(("standard", "reduced"))
            if rng.random() < 0.3:
                freelance["newly_self_employed"] = True
                freelance["years_active"] = rng.choice((0, 1, 2, 3, 6))
            payload["freelance"] = freelance

        if rng.random() < 0.25:
            payload["agricultural"] = {
                "gross_revenue": _random_amount(rng, 60_000),
                "deductible_expenses": _random_amount(rng, 15_000),
                "professional_farmer": rng.random() < 0.5,
            }
        if rng.random() < 0.25:
            payload["rental"] = {
                "gross_income": _random_amount(rng, 50_000),
                "deductible_expenses": _random_amount(rng, 8_000),
            }
        if rng.random() < 0.25:
            payload["investment"] = {
                category: _random_amount(rng, 20_000)
                for category in fields["investment_categories"]
                if rng.random() < 0.6
            }
        if rng.random() < 0.15:
            payload["other"] = {"taxable_income": _random_amount(rng, 30_000)}
        if rng.random() < 0.3:
            payload["obligations"] = {
                "enfia": _random_amount(rng, 2_000),
                "luxury": _random_amount(rng, 1_500),
            }
        if rng.random() < 0.4:
            payload["deductions"] = {
                key: _random_amount(rng, 8_000)
                for key in ("donations", "medical", "education", "insurance")
            }
        if rng.random() < 0.3:
            payload["withholding_tax"] = _random_amount(rng, 15_000)

        cases.append({"name": f"random/{index:03d}", "payload": payload})

    return cases


def _invalid_cases(year: int) -> list[dict[str, Any]]:
    return [
        {"name": "invalid/unknown_field", "payload": {"year": year, "bogus": 1}},
        {
            "name": "invalid/negative_income",
            "payload": {"year": year, "employment": {"gross_income": -1}},
        },
        {
            "name": "invalid/net_income_input",
            "payload": {"year": year, "employment": {"net_income": 1000}},
        },
        {
            "name": "invalid/too_many_children",
            "payload": {"year": year, "dependents": {"children": 16}},
        },
        {
            "name": "invalid/birth_year_mismatch",
            "payload": {
                "year": year,
                "demographics": {"birth_year": 1990, "taxpayer_birth_year": 1991},
            },
        },
        {
            "name": "invalid/payments_per_year",
            "payload": {
                "year": year,
                "employment": {"gross_income": 1000, "payments_per_year": 13},
            },
        },
        {
            "name": "invalid/efka_category",
            "payload": {
                "year": year,
                "freelance": {"profit": 1000, "efka_category": "no_such_category"},
            },
        },
        {
            "name": "invalid/trade_fee_location",
            "payload": {
                "year": year,
                "freelance": {"profit": 1000, "trade_fee_location": "elsewhere"},
            },
        },
        {
            "name": "invalid/negative_investment",
            "payload": {"year": year, "investment": {"dividends": -5}},
        },
        {
            "name": "invalid/toggles_not_mapping",
            "payload": {"year": year, "toggles": ["tekmiria_reduction"]},
        },
        {
            "name": "invalid/investment_not_mapping",
            "payload": {"year": year, "investment": 1000},
        },
        {
            "name": "invalid/future_birth_year_with_income",
            "payload": {
                "year": year,
                "employment": {"gross_income": 1000},
                "demographics": {"birth_year": year + 1},
            },
        },
    ]


def _evaluate(case: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": case["name"], "payload": case["payload"]}
    try:
        entry["expected"] = calculate_tax(case["payload"])
    except ValueError as error:
        entry["error"] = str(error)
    return entry


def build_fixtures() -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(SEED)
    fixtures: dict[str, list[dict[str, Any]]] = {}

    regression = _regression_cases()
    for year in available_years():
        cases = [case for case in regression if case["payload"]["year"] == year]
        cases += _grid_cases(year)
        cases += _random_cases(year, 120, rng)
        cases += _invalid_cases(year)
        fixtures[f"{year}.json"] = [_evaluate(case) for case in cases]

    return fixtures


def _serialise(entries: list[dict[str, Any]]) -> str:
    """Write one case per line so fixture diffs point at the changed cases."""

    lines = [
        json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for entry in entries
    ]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the committed fixtures differ from the engine output",
    )
    args = parser.parse_args(argv)

    fixtures = build_fixtures()
    stale: list[str] = []

    if not args.check:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    expected_files = set(fixtures)
    existing_files = (
        {path.name for path in OUTPUT_DIR.glob("*.json")} if OUTPUT_DIR.exists() else set()
    )

    for filename, entries in fixtures.items():
        path = OUTPUT_DIR / filename
        content = _serialise(entries)
        if args.check:
            if not path.exists() or path.read_text("utf-8") != content:
                stale.append(filename)
        else:
            path.write_text(content, "utf-8")

    for filename in sorted(existing_files - expected_files):
        if args.check:
            stale.append(filename)
        else:
            (OUTPUT_DIR / filename).unlink()

    if stale:
        print(
            "Parity fixtures are stale: "
            + ", ".join(sorted(stale))
            + ". Run python scripts/generate_parity_fixtures.py and review the diff."
        )
        return 1

    total = sum(len(entries) for entries in fixtures.values())
    print(f"{'Checked' if args.check else 'Wrote'} {total} fixtures in {len(fixtures)} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
