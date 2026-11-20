"""Article 16 ΚΦΕ tax reduction and its phase-out above 12,000.

The phase-out is 20 per 1,000 of *taxable* salary and pension income (after
employee contributions and any Article 5Γ exemption), not of gross income.
Employment cases were cross-checked against aftertax.gr (which rounds to whole
euros) and match to within 1 euro; the 5+ children cases follow the statutory
exemption from the phase-out.
"""

from __future__ import annotations

import pytest

from greektax.backend.app.services.calculation_service import calculate_tax

TOGGLES = {"presumptive_relief": True, "tekmiria_reduction": True}

# year, birth year, children, gross, residency transfer,
# taxable income, tax before credits, credits, total tax
EMPLOYMENT_CASES = [
    (2026, 1980, 0, 12_000, False, 10_395.60, 979.12, 777.00, 202.12),
    (2026, 1980, 0, 15_000, False, 12_994.50, 1_498.90, 757.11, 741.79),
    (2026, 1980, 0, 20_000, False, 17_326.00, 2_365.20, 670.48, 1_694.72),
    (2026, 1980, 0, 45_000, False, 38_983.50, 8_554.39, 237.33, 8_317.06),
    (2026, 1980, 0, 60_000, False, 51_978.00, 13_571.42, 0.00, 13_571.42),
    (2026, 1980, 1, 60_000, False, 51_978.00, 13_171.42, 100.44, 13_070.98),
    (2026, 1980, 2, 60_000, False, 51_978.00, 12_771.42, 320.44, 12_450.98),
    (2026, 1980, 3, 90_000, False, 77_967.00, 22_905.48, 20.66, 22_884.82),
    (2026, 1980, 4, 90_000, False, 77_967.00, 20_905.48, 260.66, 20_644.82),
    (2026, 1998, 2, 30_000, False, 25_989.00, 3_117.58, 840.22, 2_277.36),
    (2026, 2003, 1, 30_000, False, 25_989.00, 1_437.36, 620.22, 817.14),
    (2025, 1979, 0, 20_000, False, 17_326.00, 2_511.72, 670.48, 1_841.24),
    (2025, 1979, 4, 15_000, False, 12_994.50, 1_558.79, 1_558.79, 0.00),
    (2026, 1980, 0, 40_000, True, 17_326.00, 2_365.20, 670.48, 1_694.72),
    (2026, 1980, 0, 40_000, False, 34_652.00, 7_081.68, 323.96, 6_757.72),
    (2026, 1980, 5, 45_000, False, 38_983.50, 4_654.39, 1_780.00, 2_874.39),
    (2026, 1980, 6, 90_000, False, 77_967.00, 20_505.48, 2_000.00, 18_505.48),
]


def _employment(case: tuple, payments: int = 14) -> dict:
    year, birth_year, children, gross, transfer = case
    demographics: dict[str, object] = {"birth_year": birth_year}
    if transfer:
        demographics["tax_residency_transfer_to_greece"] = True
    result = calculate_tax(
        {
            "year": year,
            "toggles": TOGGLES,
            "dependents": {"children": children},
            "demographics": demographics,
            "employment": {"gross_income": gross, "payments_per_year": payments},
        }
    )
    return next(d for d in result["details"] if d["category"] == "employment")


@pytest.mark.parametrize("case", EMPLOYMENT_CASES)
def test_employment_phase_out_uses_taxable_income(case: tuple) -> None:
    taxable, before, credits, total = case[5:]
    detail = _employment(case[:5])
    assert detail["taxable_income"] == pytest.approx(taxable, abs=0.01)
    assert detail["tax_before_credits"] == pytest.approx(before, abs=0.01)
    assert detail["credits"] == pytest.approx(credits, abs=0.01)
    assert detail["total_tax"] == pytest.approx(total, abs=0.01)


def test_payment_frequency_does_not_change_annual_figures() -> None:
    twelve = _employment((2026, 1980, 0, 20_000, False), payments=12)
    fourteen = _employment((2026, 1980, 0, 20_000, False), payments=14)
    for field in ("taxable_income", "credits", "total_tax", "net_income"):
        assert twelve[field] == pytest.approx(fourteen[field], abs=0.01)
    assert twelve["net_income_per_payment"] == pytest.approx(
        twelve["net_income"] / 12, abs=0.01
    )


def test_pension_only_gets_the_reduction() -> None:
    # 2026: 9% of 10,000 + 20% of 5,000 = 1,900; credit 777 - 3 x 20 = 717.
    result = calculate_tax(
        {"year": 2026, "pension": {"gross_income": 15_000}, "demographics": {"birth_year": 1960}}
    )
    pension = result["details"][0]
    assert pension["credits"] == pytest.approx(717.0, abs=0.01)
    assert result["summary"]["tax_total"] == pytest.approx(1_183.0, abs=0.01)


def test_salary_and_pension_share_one_reduction_on_combined_taxable_income() -> None:
    # Taxable salary 10,000 x (1 - 13.37%) = 8,663 plus pension 10,000 = 18,663.
    # Tax: 900 + 20% of 8,663 = 2,632.60; credit 777 - 6.663 x 20 = 643.74.
    result = calculate_tax(
        {
            "year": 2026,
            "employment": {"gross_income": 10_000},
            "pension": {"gross_income": 10_000},
            "demographics": {"birth_year": 1960},
        }
    )
    credits = sum(d["credits"] for d in result["details"])
    assert credits == pytest.approx(643.74, abs=0.01)
    assert result["summary"]["tax_total"] == pytest.approx(1_988.86, abs=0.01)


def _farm_tax(year: int, revenue: float, **extra) -> float:
    payload = {
        "year": year,
        "agricultural": {"gross_revenue": revenue, "professional_farmer": True},
    }
    payload.update(extra)
    return calculate_tax(payload)["summary"]["tax_total"]


def test_professional_farmer_zero_rate_matches_published_examples() -> None:
    # Law 5355/2026, Article 4: 0% on the first two brackets from tax year 2026.
    # Published examples: no children, 30,000 -> 2,183 (5,083 before the law);
    # two children, 20,000 -> 0; aged 28 with one child, 19,000 -> 0; and the
    # tax-free amount without children rises to 22,204.
    assert _farm_tax(2026, 30_000) == pytest.approx(2_183.0, abs=0.01)
    assert _farm_tax(2026, 20_000, dependents={"children": 2}) == 0.0
    assert (
        _farm_tax(
            2026,
            19_000,
            dependents={"children": 1},
            demographics={"birth_year": 1998},
        )
        == 0.0
    )
    assert _farm_tax(2026, 22_203) == 0.0
    assert 0 < _farm_tax(2026, 22_205) < 1


def test_professional_farmer_zero_rate_starts_in_2026() -> None:
    # 2025: 900 + 2,200 + 2,800 scale tax, less the reduction of 777 - 360.
    assert _farm_tax(2025, 30_000) == pytest.approx(5_483.0, abs=0.01)


def test_zero_rate_needs_professional_farmer_status() -> None:
    result = calculate_tax(
        {"year": 2026, "agricultural": {"gross_revenue": 30_000}}
    )
    assert result["summary"]["tax_total"] == pytest.approx(5_500.0, abs=0.01)


@pytest.mark.parametrize("year", [2024, 2025, 2026])
def test_agricultural_profit_is_taxed_separately_from_salary(year: int) -> None:
    # Article 29(3) ΚΦΕ: 10,000 of farm profit pays 9% whatever the salary is.
    result = calculate_tax(
        {
            "year": year,
            "employment": {
                "gross_income": 20_000,
                "include_social_contributions": False,
            },
            "agricultural": {"gross_revenue": 10_000},
        }
    )
    details = {detail["category"]: detail for detail in result["details"]}
    alone = calculate_tax(
        {
            "year": year,
            "employment": {
                "gross_income": 20_000,
                "include_social_contributions": False,
            },
        }
    )
    assert details["agricultural"]["total_tax"] == pytest.approx(900.0)
    assert details["employment"]["total_tax"] == pytest.approx(
        alone["summary"]["tax_total"]
    )


def test_farm_zero_rate_does_not_reach_salary_taxed_beside_it() -> None:
    # Salary 20,000 and professional farm profit 10,000 in 2026: the farm profit
    # is free of tax; the salary pays 2,900 less the reduction, which is sized
    # on both incomes together (777 - 360).
    result = calculate_tax(
        {
            "year": 2026,
            "employment": {
                "gross_income": 20_000,
                "include_social_contributions": False,
            },
            "agricultural": {"gross_revenue": 10_000, "professional_farmer": True},
        }
    )
    details = {detail["category"]: detail for detail in result["details"]}
    assert details["agricultural"]["total_tax"] == 0.0
    assert details["employment"]["total_tax"] == pytest.approx(2_483.0, abs=0.01)


def test_reduction_does_not_offset_freelance_tax() -> None:
    # Salary 5,000 alongside freelance profit 20,000: the reduction is capped by
    # the tax attributable to the salary, so it cannot reduce the freelance tax.
    result = calculate_tax(
        {
            "year": 2026,
            "employment": {"gross_income": 5_000},
            "freelance": {"profit": 20_000},
            "demographics": {"birth_year": 1980},
        }
    )
    details = {d["category"]: d for d in result["details"]}
    assert details["freelance"]["credits"] == pytest.approx(0.0)
    assert details["employment"]["credits"] <= details["employment"]["tax_before_credits"]


@pytest.mark.parametrize(
    ("children", "expected"),
    [
        # 40,000 of taxable salary: 0% up to 20,000 (4+ children), the
        # 20,000-30,000 rate for the child count, 34% on the rest, less the
        # Article 16 reduction (no phase-out from five children on).
        (6, 1_400 + 3_400 - 2_000),
        (7, 1_200 + 3_400 - 2_220),
        (11, 400 + 3_400 - 3_100),
        (13, 0 + 3_400 - 3_540),
    ],
)
def test_third_band_keeps_falling_by_two_points_per_child_above_four(
    children: int, expected: float
) -> None:
    # Art. 15(1)(δε) ΚΦΕ: 18% with four children, two points less for each
    # further child.
    result = calculate_tax(
        {
            "year": 2026,
            "dependents": {"children": children},
            "employment": {
                "gross_income": 40_000,
                "include_social_contributions": False,
            },
        }
    )
    assert result["summary"]["tax_total"] == pytest.approx(max(expected, 0.0), abs=0.01)
