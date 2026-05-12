from __future__ import annotations

from typing import Any


def calculate_average_price(transactions: list[dict[str, Any]]) -> dict[str, float]:
    quantity = 0.0
    cost_basis = 0.0
    realized_result = 0.0

    for transaction in transactions:
        transaction_quantity = float(transaction["quantity"])
        price = float(transaction["price"])
        fees = float(transaction.get("fees", 0))

        if transaction["type"] == "buy":
            quantity += transaction_quantity
            cost_basis += transaction_quantity * price + fees
            continue

        if transaction_quantity > quantity:
            raise ValueError("Venda maior que a posição disponível.")

        average_price = cost_basis / quantity if quantity else 0.0
        realized_result += transaction_quantity * (price - average_price) - fees
        cost_basis -= average_price * transaction_quantity
        quantity -= transaction_quantity

    average_price = cost_basis / quantity if quantity else 0.0
    return {
        "quantity": round(quantity, 8),
        "average_price": round(average_price, 8),
        "cost_basis": round(cost_basis, 2),
        "realized_result": round(realized_result, 2),
    }


def calculate_portfolio_metrics(
    portfolio: list[dict[str, Any]],
    market_data: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    market_data = market_data or {}
    positions = []

    for asset in portfolio:
        ticker = asset["ticker"]
        if asset.get("transactions"):
            position = calculate_average_price(asset["transactions"])
            quantity = position["quantity"]
            average_price = position["average_price"]
            invested_value = position["cost_basis"]
            realized_result = position["realized_result"]
        else:
            quantity = float(asset.get("quantity", 0))
            average_price = float(asset.get("average_price", 0))
            invested_value = quantity * average_price
            realized_result = 0.0

        ticker_market_data = market_data.get(ticker, {})
        current_price = _first_number(
            ticker_market_data.get("preco_atual"),
            ticker_market_data.get("regularMarketPrice"),
            average_price,
        )
        current_value = quantity * current_price
        unrealized_result = current_value - invested_value
        return_percentage = (
            unrealized_result / invested_value * 100 if invested_value else 0.0
        )

        positions.append(
            {
                "ticker": ticker,
                "asset_type": asset.get("asset_type", "stock"),
                "quantity": round(quantity, 8),
                "average_price": round(average_price, 2),
                "invested_value": round(invested_value, 2),
                "current_price": round(current_price, 2),
                "current_value": round(current_value, 2),
                "unrealized_result": round(unrealized_result, 2),
                "return_percentage": round(return_percentage, 2),
                "realized_result": round(realized_result, 2),
                "market_data": ticker_market_data,
            }
        )

    total_invested = sum(position["invested_value"] for position in positions)
    total_current_value = sum(position["current_value"] for position in positions)
    total_unrealized_result = total_current_value - total_invested

    for position in positions:
        position["portfolio_weight"] = round(
            position["current_value"] / total_current_value * 100
            if total_current_value
            else 0,
            2,
        )

    return {
        "positions": positions,
        "totals": {
            "invested_value": round(total_invested, 2),
            "current_value": round(total_current_value, 2),
            "unrealized_result": round(total_unrealized_result, 2),
            "return_percentage": round(
                total_unrealized_result / total_invested * 100 if total_invested else 0,
                2,
            ),
        },
        "concentration": calculate_concentration(positions),
    }


def calculate_concentration(positions: list[dict[str, Any]]) -> dict[str, Any]:
    by_asset = {
        position["ticker"]: position["portfolio_weight"] for position in positions
    }
    by_class: dict[str, float] = {}

    for position in positions:
        asset_type = position.get("asset_type", "stock")
        by_class[asset_type] = round(
            by_class.get(asset_type, 0) + position["portfolio_weight"],
            2,
        )

    return {
        "by_asset": by_asset,
        "by_class": by_class,
        "max_asset_weight": max(by_asset.values(), default=0),
        "asset_count": len(positions),
    }


def _first_number(*values: Any) -> float:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0

