"""Unit tests for the calculation service."""

from __future__ import annotations

import pytest

from greektax.backend.app.services.calculation_service import calculate_tax


def test_calculate_tax_defaults_to_zero_summary() -> None:
    """An empty payload (besides year) should produce zeroed totals."""

    result = calculate_tax({"year": 2024})

    assert result["summary"]["income_total"] == 0.0
    assert result["summary"]["tax_total"] == 0.0
    assert result["summary"]["net_income"] == 0.0
    assert result["details"] == []
    assert result["meta"] == {"year": 2024, "locale": "en"}


def test_calculate_tax_employment_only() -> None:
    """Employment income uses progressive rates and tax credit."""

    payload = {
        "year": 2024,
        "locale": "en",
        "dependents": {"children": 1},
        "employment": {"gross_income": 30_000},
    }

    result = calculate_tax(payload)

    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(30_000.0)
    assert summary["tax_total"] == pytest.approx(5_090.0)
    assert summary["net_income"] == pytest.approx(24_910.0)

    assert len(result["details"]) == 1
    employment_detail = result["details"][0]
    assert employment_detail["category"] == "employment"
    assert employment_detail["gross_income"] == pytest.approx(30_000.0)
    assert employment_detail["tax_before_credits"] == pytest.approx(5_900.0)
    assert employment_detail["credits"] == pytest.approx(810.0)
    assert employment_detail["total_tax"] == pytest.approx(5_090.0)


def test_calculate_tax_with_freelance_income() -> None:
    """Freelance profit combines progressive tax and trade fee."""

    payload = {
        "year": 2024,
        "locale": "en",
        "dependents": {"children": 0},
        "employment": {"gross_income": 20_000},
        "freelance": {
            "gross_revenue": 18_000,
            "deductible_expenses": 4_000,
            "mandatory_contributions": 3_000,
        },
    }

    result = calculate_tax(payload)

    assert result["summary"]["income_total"] == pytest.approx(34_000.0)
    assert result["summary"]["tax_total"] == pytest.approx(4_093.0)
    assert result["summary"]["net_income"] == pytest.approx(26_907.0)

    assert len(result["details"]) == 2
    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )
    freelance_detail = next(
        detail for detail in result["details"] if detail["category"] == "freelance"
    )

    assert employment_detail["total_tax"] == pytest.approx(2_323.0)
    assert freelance_detail["taxable_income"] == pytest.approx(11_000.0)
    assert freelance_detail["tax"] == pytest.approx(1_120.0)
    assert freelance_detail["trade_fee"] == pytest.approx(650.0)
    assert freelance_detail["total_tax"] == pytest.approx(1_770.0)
    assert freelance_detail["net_income"] == pytest.approx(9_230.0)


def test_calculate_tax_respects_locale_toggle() -> None:
    """Locale toggle switches translation catalogue."""

    payload = {"year": 2024, "locale": "el", "employment": {"gross_income": 10_000}}

    result = calculate_tax(payload)

    assert result["meta"]["locale"] == "el"
    assert result["details"][0]["label"] == "Εισόδημα μισθωτών"
    assert result["summary"]["labels"]["income_total"] == "Συνολικό εισόδημα"
