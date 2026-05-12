from __future__ import annotations


def project_compound_growth(
    initial_value: float,
    monthly_contribution: float,
    annual_return: float,
    months: int,
    annual_yield: float = 0.08,
) -> dict:
    monthly_return = (1 + annual_return) ** (1 / 12) - 1 if annual_return else 0
    timeline = []

    for month in range(0, months + 1):
        future_value = _future_value(
            initial_value=initial_value,
            monthly_contribution=monthly_contribution,
            monthly_return=monthly_return,
            months=month,
        )
        if month % 12 == 0 or month == months:
            timeline.append(
                {
                    "month": month,
                    "year": round(month / 12, 2),
                    "projected_value": round(future_value, 2),
                    "projected_monthly_income": round(
                        future_value * annual_yield / 12,
                        2,
                    ),
                }
            )

    final_value = timeline[-1]["projected_value"] if timeline else round(initial_value, 2)
    return {
        "assumptions": {
            "initial_value": round(initial_value, 2),
            "monthly_contribution": round(monthly_contribution, 2),
            "annual_return": annual_return,
            "annual_yield": annual_yield,
            "months": months,
        },
        "timeline": timeline,
        "final_value": final_value,
        "final_projected_monthly_income": round(final_value * annual_yield / 12, 2),
    }


def calculate_required_capital(target_monthly_income: float, annual_yield: float) -> float:
    if annual_yield <= 0:
        return 0.0
    return round(target_monthly_income * 12 / annual_yield, 2)


def _future_value(
    initial_value: float,
    monthly_contribution: float,
    monthly_return: float,
    months: int,
) -> float:
    if months <= 0:
        return initial_value

    accumulated_initial = initial_value * ((1 + monthly_return) ** months)
    if monthly_return == 0:
        accumulated_contributions = monthly_contribution * months
    else:
        accumulated_contributions = (
            monthly_contribution * (((1 + monthly_return) ** months - 1) / monthly_return)
        )
    return accumulated_initial + accumulated_contributions

