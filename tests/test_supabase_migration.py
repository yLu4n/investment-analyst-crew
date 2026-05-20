from __future__ import annotations

from pathlib import Path


SUPABASE_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260519193826_create_initial_schema.sql"
)


def test_supabase_migration_uses_postgres_not_sqlite_dialect():
    migration = SUPABASE_MIGRATION.read_text(encoding="utf-8").lower()

    sqlite_only_tokens = ("pragma", "randomblob", "select raise(abort")

    assert all(token not in migration for token in sqlite_only_tokens)
    assert "create extension if not exists pgcrypto" in migration
    assert "timestamptz" in migration
    assert "gen_random_uuid()" in migration


def test_supabase_migration_enables_rls_for_user_owned_tables():
    migration = SUPABASE_MIGRATION.read_text(encoding="utf-8").lower()

    for table in ("profiles", "wallets", "positions", "transactions"):
        assert f"alter table public.{table} enable row level security" in migration

    assert "using (user_id = (select auth.uid()))" in migration
    assert "with check (user_id = (select auth.uid()))" in migration


def test_supabase_migration_keeps_transaction_position_indexes():
    migration = SUPABASE_MIGRATION.read_text(encoding="utf-8").lower()

    expected_indexes = (
        "ix_transactions_user_id_executed_at",
        "ix_transactions_wallet_id_ticker_executed_at",
        "ix_transactions_user_id_wallet_id_ticker",
        "ix_positions_user_id_ticker",
    )

    for index_name in expected_indexes:
        assert index_name in migration
