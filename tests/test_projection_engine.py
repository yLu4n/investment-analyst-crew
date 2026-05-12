from investment_analyst.services.projection_engine import (
    calculate_required_capital,
    project_compound_growth,
)


def test_calculate_required_capital():
    assert calculate_required_capital(5000, 0.08) == 750000


def test_project_compound_growth_with_zero_return():
    result = project_compound_growth(
        initial_value=1000,
        monthly_contribution=100,
        annual_return=0,
        months=12,
    )

    assert result["final_value"] == 2200
    assert result["final_projected_monthly_income"] == 14.67

