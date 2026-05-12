from investment_analyst.services.analysis_preparation_service import build_analysis_inputs


def test_build_analysis_inputs_adds_deterministic_analysis():
    result = build_analysis_inputs(
        {
            "portfolio": [{"ticker": "petr4.sa", "quantity": 100, "average_price": 32.5}],
            "financial_goals": {
                "target_monthly_income": 5000,
                "monthly_contribution": 1500,
                "time_horizon_months": 120,
            },
        },
        market_data_fetcher=lambda ticker: {"ticker": ticker, "preco_atual": 40},
    )

    assert result["portfolio"][0]["ticker"] == "PETR4"
    assert result["deterministic_analysis"]["portfolio_metrics"]["totals"][
        "current_value"
    ] == 4000
    assert result["deterministic_analysis"]["required_capital_for_goal"] == 750000
