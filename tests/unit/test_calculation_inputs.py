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


@pytest.mark.parametrize("year", [2024, 2025, 2026])
def test_tax_residency_transfer_halves_taxable_freelance_income(year: int) -> None:
    # Article 5Γ ΚΦΕ covers individual business activity as well as salaries:
    # half of the profit left after contributions is taxed.
    payload = {
        "year": year,
        "freelance": {"profit": 40_000, "mandatory_contributions": 4_000},
    }
    plain = calculate_tax(payload)
    relocated = calculate_tax(
        {**payload, "demographics": {"tax_residency_transfer_to_greece": True}}
    )
    half = calculate_tax({"year": year, "freelance": {"profit": 18_000}})

    detail = relocated["details"][0]
    assert plain["details"][0]["taxable_income"] == pytest.approx(36_000)
    assert detail["taxable_income"] == pytest.approx(18_000)
    assert detail["tax"] == pytest.approx(half["details"][0]["tax"])
    # The exempt half is still income: only the tax falls.
    assert detail["net_income"] == pytest.approx(36_000 - detail["tax"])


def test_tax_residency_transfer_leaves_other_categories_untouched() -> None:
    payload = {
        "year": 2026,
        "pension": {"gross_income": 20_000},
        "agricultural": {"gross_revenue": 15_000},
        "rental": {"gross_income": 10_000},
        "other": {"taxable_income": 5_000},
    }
    plain = calculate_tax(payload)
    relocated = calculate_tax(
        {**payload, "demographics": {"tax_residency_transfer_to_greece": True}}
    )
    assert relocated["summary"]["tax_total"] == plain["summary"]["tax_total"]


def _mixed_residency(employment_flag: bool, freelance_flag: bool, **extra) -> dict:
    result = calculate_tax(
        {
            "year": 2026,
            "employment": {
                "gross_income": 30_000,
                "include_social_contributions": False,
                "tax_residency_transfer": employment_flag,
            },
            "freelance": {"profit": 20_000, "tax_residency_transfer": freelance_flag},
            **extra,
        }
    )
    return {detail["category"]: detail["taxable_income"] for detail in result["details"]}


def test_tax_residency_transfer_is_applied_per_category() -> None:
    # AADE issues a separate Article 5Γ decision for each income category.
    assert _mixed_residency(False, False) == {"employment": 30_000, "freelance": 20_000}
    assert _mixed_residency(True, False) == {"employment": 15_000, "freelance": 20_000}
    assert _mixed_residency(False, True) == {"employment": 30_000, "freelance": 10_000}
    assert _mixed_residency(True, True) == {"employment": 15_000, "freelance": 10_000}


def test_demographics_residency_flag_still_covers_both_categories() -> None:
    flagged = _mixed_residency(
        False, False, demographics={"tax_residency_transfer_to_greece": True}
    )
    assert flagged == {"employment": 15_000, "freelance": 10_000}
    # Together with a category flag the share is applied once, not twice.
    both = _mixed_residency(
        True, False, demographics={"tax_residency_transfer_to_greece": True}
    )
    assert both == flagged
