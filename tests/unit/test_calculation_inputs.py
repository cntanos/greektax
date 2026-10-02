"""Input handling of the reference engine, formerly covered via the HTTP API."""

from __future__ import annotations

import pytest

from greektax.backend.app.services.calculation_service import calculate_tax


def _detail(result: dict, category: str) -> dict:
    return next(item for item in result["details"] if item["category"] == category)


def test_negative_amounts_are_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_tax(
            {
                "year": 2024,
                "employment": {"gross_income": -1},
                "demographics": {"birth_year": 1985},
            }
        )


def test_mixed_annual_and_monthly_salary_inputs() -> None:
    result = calculate_tax(
        {
            "year": 2024,
            "employment": {
                "gross_income": 30_000,
                "monthly_income": 1_500,
                "payments_per_year": 14,
            },
            "demographics": {"birth_year": 1985},
        }
    )
    summary = result["summary"]
    employment = _detail(result, "employment")

    assert summary["income_total"] == pytest.approx(30_000.0)
    assert summary["taxable_income"] == pytest.approx(employment["taxable_income"])
    assert employment["gross_income"] == pytest.approx(30_000.0)
    assert employment["monthly_gross_income"] == pytest.approx(1_500.0)
    assert employment["gross_income_per_payment"] == pytest.approx(
        30_000 / 14, abs=0.01
    )


def test_employment_and_pension_combine() -> None:
    result = calculate_tax(
        {
            "year": 2024,
            "employment": {"gross_income": 18_000},
            "pension": {"gross_income": 9_000},
            "demographics": {"birth_year": 1985},
        }
    )
    assert _detail(result, "employment")["gross_income"] == pytest.approx(18_000.0)
    assert _detail(result, "pension")["gross_income"] == pytest.approx(9_000.0)


def test_tax_residency_transfer_halves_taxable_salary() -> None:
    base = calculate_tax(
        {"year": 2024, "employment": {"gross_income": 40_000}, "demographics": {}}
    )["summary"]
    transferred = calculate_tax(
        {
            "year": 2024,
            "employment": {"gross_income": 40_000},
            "demographics": {"tax_residency_transfer_to_greece": True},
        }
    )["summary"]

    assert transferred["taxable_income"] == pytest.approx(base["taxable_income"] / 2)
    assert transferred["tax_total"] < base["tax_total"]


def test_missing_demographics_default_to_empty() -> None:
    missing = calculate_tax({"year": 2024, "employment": {"gross_income": 25_000}})
    explicit = calculate_tax(
        {"year": 2024, "employment": {"gross_income": 25_000}, "demographics": {}}
    )
    assert missing["summary"] == explicit["summary"]


@pytest.mark.parametrize(
    ("section", "value", "message"),
    [
        ("toggles", ["tekmiria_reduction"], "Toggles section must be an object"),
        ("investment", 1000, "Investment section must be an object"),
    ],
)
def test_non_mapping_sections_are_validation_errors(
    section: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=f"{section}: Value error, {message}"):
        calculate_tax({"year": 2026, section: value})
