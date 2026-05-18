from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from investment_analyst.persistence.database_config import get_test_database_url
from investment_analyst.persistence.migrations import read_migration


pytestmark = pytest.mark.integration


def test_postgres_migration_applies_transaction_trigger_end_to_end():
    database_url = get_test_database_url()
    if not database_url:
        pytest.skip(
            "Configure INVESTMENT_ANALYST_TEST_DATABASE_URL em .env.test para rodar este teste."
        )

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        pytest.skip(f"Driver PostgreSQL indisponivel: {exc}")

    email = f"migration-{uuid4()}@example.test"
    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(read_migration("0001_create_canonical_portfolio_tables.sql"))
            try:
                cursor.execute(
                    "INSERT INTO public.users (email, display_name) VALUES (%s, %s) RETURNING id",
                    (email, "Migration Test"),
                )
                user_id = cursor.fetchone()["id"]
                cursor.execute(
                    """
                    INSERT INTO public.wallets (user_id, name)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (user_id, "Carteira Teste"),
                )
                wallet_id = cursor.fetchone()["id"]

                cursor.execute(
                    """
                    INSERT INTO public.transactions
                        (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
                    VALUES (%s, %s, %s, 'buy', 10, 20, 1)
                    """,
                    (user_id, wallet_id, "petr4"),
                )
                cursor.execute(
                    """
                    INSERT INTO public.transactions
                        (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
                    VALUES (%s, %s, %s, 'buy', 10, 30, 1)
                    """,
                    (user_id, wallet_id, "PETR4"),
                )
                cursor.execute(
                    """
                    INSERT INTO public.transactions
                        (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
                    VALUES (%s, %s, %s, 'sell', 5, 40, 0)
                    """,
                    (user_id, wallet_id, "PETR4"),
                )

                cursor.execute(
                    """
                    SELECT quantity, average_price, cost_basis
                    FROM public.assets
                    WHERE user_id = %s AND wallet_id = %s AND ticker = 'PETR4'
                    """,
                    (user_id, wallet_id),
                )
                asset = cursor.fetchone()

                assert asset["quantity"] == Decimal("15.00000000")
                assert asset["average_price"] == Decimal("25.10000000")
                assert asset["cost_basis"] == Decimal("376.50000000")

                with pytest.raises(psycopg.Error):
                    cursor.execute(
                        """
                        INSERT INTO public.transactions
                            (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
                        VALUES (%s, %s, %s, 'sell', 999, 40, 0)
                        """,
                        (user_id, wallet_id, "PETR4"),
                    )

                cursor.execute(
                    """
                    INSERT INTO public.transactions
                        (user_id, wallet_id, ticker, transaction_type, quantity, price, fees)
                    VALUES (%s, %s, %s, 'sell', 15, 40, 0)
                    """,
                    (user_id, wallet_id, "PETR4"),
                )
                cursor.execute(
                    """
                    SELECT count(*) AS asset_count
                    FROM public.assets
                    WHERE user_id = %s AND wallet_id = %s AND ticker = 'PETR4'
                    """,
                    (user_id, wallet_id),
                )

                assert cursor.fetchone()["asset_count"] == 0
            finally:
                cursor.execute("DELETE FROM public.users WHERE email = %s", (email,))

