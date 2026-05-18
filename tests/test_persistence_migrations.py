import re

from investment_analyst.persistence.migrations import migration_files, read_migration


def normalized(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.lower()).strip()


def canonical_migration_sql() -> str:
    return read_migration("0001_create_canonical_portfolio_tables.sql")


def test_migrations_are_versioned_and_discoverable():
    files = migration_files()

    assert files
    assert [file.name for file in files] == sorted(file.name for file in files)
    assert all(re.fullmatch(r"\d{4}_[a-z0-9_]+\.sql", file.name) for file in files)


def test_canonical_tables_are_tenant_scoped_with_constraints_and_indexes():
    sql = normalized(canonical_migration_sql())

    for table_name in ("users", "wallets", "assets", "transactions"):
        assert f"create table if not exists public.{table_name}" in sql

    assert "foreign key (user_id) references public.users (id) on delete cascade" in sql
    assert (
        "foreign key (wallet_id, user_id) references public.wallets (id, user_id) "
        "on delete cascade"
    ) in sql
    assert "constraint uq_wallets_id_user_id unique (id, user_id)" in sql
    assert "constraint uq_assets_user_id_wallet_id_ticker unique (user_id, wallet_id, ticker)" in sql
    assert "constraint ck_transactions_type_buy_or_sell check (transaction_type in ('buy', 'sell'))" in sql
    assert "constraint ck_transactions_quantity_positive check (quantity > 0)" in sql
    assert "constraint ck_assets_quantity_positive check (quantity > 0)" in sql

    expected_indexes = (
        "ix_wallets_user_id",
        "ix_assets_user_id_ticker",
        "ix_assets_wallet_id_ticker",
        "ix_transactions_user_id_executed_at",
        "ix_transactions_wallet_id_ticker_executed_at",
        "ix_transactions_user_id_wallet_id_ticker",
    )
    for index_name in expected_indexes:
        assert f"create index if not exists {index_name}" in sql


def test_transaction_trigger_upserts_buys_recalculating_average_price():
    sql = normalized(canonical_migration_sql())

    assert "create or replace function public.apply_transaction_to_asset_position()" in sql
    assert "returns trigger" in sql
    assert "if new.transaction_type = 'buy' then" in sql
    assert "delta_cost_basis := (new.quantity * new.price) + new.fees" in sql
    assert "insert into public.assets" in sql
    assert "on conflict (user_id, wallet_id, ticker) do update" in sql
    assert "insert into public.assets as asset_position" in sql
    assert "quantity = asset_position.quantity + excluded.quantity" in sql
    assert "cost_basis = asset_position.cost_basis + excluded.cost_basis" in sql
    assert (
        "average_price = ( asset_position.cost_basis + excluded.cost_basis ) / "
        "( asset_position.quantity + excluded.quantity )"
    ) in sql


def test_transaction_trigger_rejects_oversell_and_deletes_zero_position():
    sql = normalized(canonical_migration_sql())

    assert "if new.transaction_type = 'sell' then" in sql
    assert "from public.assets" in sql
    assert "where user_id = new.user_id and wallet_id = new.wallet_id and ticker = new.ticker" in sql
    assert "for update" in sql
    assert "if not found or current_asset.quantity < new.quantity then" in sql
    assert "constraint = 'ck_transactions_sell_not_above_position'" in sql
    assert "new_quantity := current_asset.quantity - new.quantity" in sql
    assert "if new_quantity = 0 then delete from public.assets where id = current_asset.id" in sql
    assert "new_cost_basis := current_asset.average_price * new_quantity" in sql
    assert "average_price = current_asset.average_price" in sql


def test_transactions_trigger_is_bound_before_insert():
    sql = normalized(canonical_migration_sql())

    assert "drop trigger if exists trg_transactions_apply_asset_position on public.transactions" in sql
    assert "create trigger trg_transactions_apply_asset_position" in sql
    assert "before insert on public.transactions" in sql
    assert "for each row execute function public.apply_transaction_to_asset_position()" in sql
