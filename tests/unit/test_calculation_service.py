"""Unit tests for the calculation service.

TODO: Flesh out comprehensive test coverage for each income type, deductions,
credits, and localization behavior.
"""

from greektax.backend.app.services.calculation_service import calculate_tax


def test_calculate_tax_placeholder():
    """Placeholder test ensuring scaffolded response structure."""
    result = calculate_tax({})

    assert "summary" in result
    assert "details" in result
    assert result["summary"]["income_total"] == 0.0
    assert result["summary"]["tax_total"] == 0.0
    assert result["summary"]["net_income"] == 0.0
