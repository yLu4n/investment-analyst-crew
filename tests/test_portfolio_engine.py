from investment_analyst.services.portfolio_engine import (
    calculate_average_price,
    calculate_portfolio_metrics,
)


def test_calculate_average_price_with_buys_and_sell():
    result = calculate_average_price(
        [
            {"type": "buy", "quantity": 10, "price": 20, "fees": 1},
            {"type": "buy", "quantity": 10, "price": 30, "fees": 1},
            {"type": "sell", "quantity": 5, "price": 40, "fees": 0},
        ]
    )

    assert result["quantity"] == 15
    assert result["average_price"] == 25.1
    assert result["cost_basis"] == 376.5
    assert result["realized_result"] == 74.5


def test_calculate_portfolio_metrics_uses_market_price():
    result = calculate_portfolio_metrics(
        [{"ticker": "PETR4", "quantity": 100, "average_price": 32.5}],
        {"PETR4": {"preco_atual": 40}},
    )

    assert result["positions"][0]["current_value"] == 4000
    assert result["totals"]["unrealized_result"] == 750
    assert result["concentration"]["max_asset_weight"] == 100

