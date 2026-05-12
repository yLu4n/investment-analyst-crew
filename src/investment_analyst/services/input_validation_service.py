from __future__ import annotations

from typing import Any


def normalize_ticker(ticker: str) -> str:
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("Ticker do ativo é obrigatório.")

    normalized = ticker.strip().upper()
    return normalized[:-3] if normalized.endswith(".SA") else normalized


def normalize_positive_number(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} deve ser um número.") from exc

    if number < 0:
        raise ValueError(f"{field_name} não pode ser negativo.")

    return number


def normalize_portfolio(portfolio: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(portfolio, list) or not portfolio:
        raise ValueError("A carteira deve conter ao menos um ativo.")

    normalized_assets = []
    for asset in portfolio:
        ticker = normalize_ticker(asset.get("ticker", ""))
        transactions = asset.get("transactions") or asset.get("operations") or []

        normalized_asset = {
            **asset,
            "ticker": ticker,
            "asset_type": asset.get("asset_type", "stock"),
            "transactions": normalize_transactions(transactions),
        }

        if not normalized_asset["transactions"]:
            normalized_asset["quantity"] = normalize_positive_number(
                asset.get("quantity", 0),
                f"Quantidade de {ticker}",
            )
            normalized_asset["average_price"] = normalize_positive_number(
                asset.get("average_price", 0),
                f"Preço médio de {ticker}",
            )

        normalized_assets.append(normalized_asset)

    return normalized_assets


def normalize_transactions(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not transactions:
        return []

    normalized_transactions = []
    for transaction in transactions:
        operation_type = str(transaction.get("type", "buy")).strip().lower()
        if operation_type not in {"buy", "sell"}:
            raise ValueError("Tipo de operação deve ser 'buy' ou 'sell'.")

        normalized_transactions.append(
            {
                **transaction,
                "type": operation_type,
                "quantity": normalize_positive_number(
                    transaction.get("quantity", 0),
                    "Quantidade da operação",
                ),
                "price": normalize_positive_number(
                    transaction.get("price", 0),
                    "Preço da operação",
                ),
                "fees": normalize_positive_number(
                    transaction.get("fees", 0),
                    "Taxas da operação",
                ),
            }
        )

    return normalized_transactions


def normalize_financial_goals(goals: dict[str, Any]) -> dict[str, Any]:
    goals = goals or {}
    normalized = {**goals}
    normalized["time_horizon_months"] = int(
        normalize_positive_number(goals.get("time_horizon_months", 120), "Prazo")
    )
    normalized["monthly_contribution"] = normalize_positive_number(
        goals.get("monthly_contribution", 0),
        "Aporte mensal",
    )
    normalized["target_monthly_income"] = normalize_positive_number(
        goals.get("target_monthly_income", 0),
        "Renda mensal desejada",
    )
    normalized["expected_annual_return"] = normalize_positive_number(
        goals.get("expected_annual_return", 0.10),
        "Retorno anual esperado",
    )
    normalized["expected_annual_yield"] = normalize_positive_number(
        goals.get("expected_annual_yield", 0.08),
        "Rendimento anual esperado",
    )
    return normalized

