from __future__ import annotations

import sqlite3
from uuid import uuid4

import pytest

from investment_analyst.persistence.migrations import read_migration


pytestmark = pytest.mark.integration


def test_sqlite_migration_applies_transaction_triggers_end_to_end():
    email = f"migration-{uuid4()}@example.test"

    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        connection.executescript(read_migration("0001_create_canonical_portfolio_tables.sql"))

        user_id = connection.execute(
            "INSERT INTO users (email, display_name) VALUES (?, ?) RETURNING id",
            (email, "Migration Test"),
        ).fetchone()["id"]
        wallet_id = connection.execute(
            """
            INSERT INTO wallets (user_id, name)
            VALUES (?, ?)
            RETURNING id
            """,
            (user_id, "Carteira Teste"),
        ).fetchone()["id"]

        connection.execute(
            """
            INSERT INTO transactions
                (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
            VALUES (?, ?, ?, 'buy', 10, 20, 1)
            """,
            (user_id, wallet_id, "petr4"),
        )
        connection.execute(
            """
            INSERT INTO transactions
                (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
            VALUES (?, ?, ?, 'buy', 10, 30, 1)
            """,
            (user_id, wallet_id, "PETR4"),
        )
        connection.execute(
            """
            INSERT INTO transactions
                (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
            VALUES (?, ?, ?, 'sell', 5, 40, 0)
            """,
            (user_id, wallet_id, "PETR4"),
        )

        asset = connection.execute(
            """
            SELECT quantity, average_price, cost_basis
            FROM assets
            WHERE user_id = ? AND wallet_id = ? AND ticker = 'PETR4'
            """,
            (user_id, wallet_id),
        ).fetchone()

        assert asset["quantity"] == 15
        assert asset["average_price"] == pytest.approx(25.1)
        assert asset["cost_basis"] == pytest.approx(376.5)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO transactions
                    (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
                VALUES (?, ?, ?, 'sell', 999, 40, 0)
                """,
                (user_id, wallet_id, "PETR4"),
            )

        connection.execute(
            """
            INSERT INTO transactions
                (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
            VALUES (?, ?, ?, 'sell', 15, 40, 0)
            """,
            (user_id, wallet_id, "PETR4"),
        )
        asset_count = connection.execute(
            """
            SELECT count(*) AS asset_count
            FROM assets
            WHERE user_id = ? AND wallet_id = ? AND ticker = 'PETR4'
            """,
            (user_id, wallet_id),
        ).fetchone()["asset_count"]

        assert asset_count == 0
