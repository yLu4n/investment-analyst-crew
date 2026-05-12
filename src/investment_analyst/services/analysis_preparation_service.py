from __future__ import annotations

from typing import Any, Callable

from investment_analyst.services.input_validation_service import (
    normalize_financial_goals,
    normalize_portfolio,
)
from investment_analyst.services.portfolio_engine import calculate_portfolio_metrics
from investment_analyst.services.projection_engine import (
    calculate_required_capital,
    project_compound_growth,
)
from investment_analyst.tools.financial_data_tool import FinancialDataTool


MarketDataFetcher = Callable[[str], dict[str, Any]]


def build_analysis_inputs(
    raw_inputs: dict[str, Any],
    market_data_fetcher: MarketDataFetcher | None = None,
) -> dict[str, Any]:
    portfolio = normalize_portfolio(raw_inputs.get("portfolio", []))
    financial_goals = normalize_financial_goals(raw_inputs.get("financial_goals", {}))
    market_data = fetch_market_data(portfolio, market_data_fetcher)
    portfolio_metrics = calculate_portfolio_metrics(portfolio, market_data)
    required_capital = calculate_required_capital(
        financial_goals["target_monthly_income"],
        financial_goals["expected_annual_yield"],
    )
    projection = project_compound_growth(
        initial_value=portfolio_metrics["totals"]["current_value"],
        monthly_contribution=financial_goals["monthly_contribution"],
        annual_return=financial_goals["expected_annual_return"],
        months=financial_goals["time_horizon_months"],
        annual_yield=financial_goals["expected_annual_yield"],
    )

    deterministic_analysis = {
        "portfolio_metrics": portfolio_metrics,
        "required_capital_for_goal": required_capital,
        "monthly_contribution_projection": projection,
        "calculation_policy": (
            "Todos os números desta seção foram calculados por serviços "
            "determinísticos antes da execução dos agentes. Os agentes devem "
            "usar estes valores como fonte de verdade e não recalcular métricas."
        ),
    }

    return {
        **raw_inputs,
        "portfolio": portfolio,
        "financial_goals": financial_goals,
        "market_data": market_data,
        "deterministic_analysis": deterministic_analysis,
        "report_ticker": portfolio[0]["ticker"] if portfolio else "CARTEIRA",
    }


def fetch_market_data(
    portfolio: list[dict[str, Any]],
    market_data_fetcher: MarketDataFetcher | None = None,
) -> dict[str, dict[str, Any]]:
    fetcher = market_data_fetcher or FinancialDataTool()._run
    market_data = {}

    for asset in portfolio:
        ticker = asset["ticker"]
        try:
            result = fetcher(ticker)
        except Exception as exc:
            result = {"error": f"Falha ao buscar dados de mercado: {exc}"}

        market_data[ticker] = result if isinstance(result, dict) else {"raw": result}

    return market_data

