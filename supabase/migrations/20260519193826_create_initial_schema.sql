PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    email TEXT NOT NULL,
    display_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_email_not_blank CHECK (trim(email) <> '')
);

CREATE TABLE IF NOT EXISTS wallets (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    base_currency TEXT NOT NULL DEFAULT 'BRL',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wallets_user_id_users
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT uq_wallets_id_user_id UNIQUE (id, user_id),
    CONSTRAINT uq_wallets_user_id_name UNIQUE (user_id, name),
    CONSTRAINT ck_wallets_name_not_blank CHECK (trim(name) <> ''),
    CONSTRAINT ck_wallets_base_currency_not_blank CHECK (trim(base_currency) <> '')
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id TEXT NOT NULL,
    wallet_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    average_price NUMERIC NOT NULL,
    cost_basis NUMERIC NOT NULL,
    currency TEXT NOT NULL DEFAULT 'BRL',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_assets_user_id_users
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_assets_wallet_id_user_id_wallets
        FOREIGN KEY (wallet_id, user_id) REFERENCES wallets (id, user_id) ON DELETE CASCADE,
    CONSTRAINT uq_assets_user_id_wallet_id_ticker UNIQUE (user_id, wallet_id, ticker),
    CONSTRAINT ck_assets_ticker_not_blank CHECK (trim(ticker) <> ''),
    CONSTRAINT ck_assets_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_assets_average_price_non_negative CHECK (average_price >= 0),
    CONSTRAINT ck_assets_cost_basis_non_negative CHECK (cost_basis >= 0),
    CONSTRAINT ck_assets_currency_not_blank CHECK (trim(currency) <> '')
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id TEXT NOT NULL,
    wallet_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    fees NUMERIC NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'BRL',
    executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL DEFAULT 'manual',
    external_reference TEXT,
    raw_payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transactions_user_id_users
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_transactions_wallet_id_user_id_wallets
        FOREIGN KEY (wallet_id, user_id) REFERENCES wallets (id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_transactions_ticker_not_blank CHECK (trim(ticker) <> ''),
    CONSTRAINT ck_transactions_type_buy_or_sell CHECK (lower(trim(transaction_type)) IN ('buy', 'sell')),
    CONSTRAINT ck_transactions_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_transactions_price_non_negative CHECK (price >= 0),
    CONSTRAINT ck_transactions_fees_non_negative CHECK (fees >= 0),
    CONSTRAINT ck_transactions_currency_not_blank CHECK (trim(currency) <> ''),
    CONSTRAINT ck_transactions_source_not_blank CHECK (trim(source) <> '')
);

CREATE INDEX IF NOT EXISTS ix_wallets_user_id
    ON wallets (user_id);

CREATE INDEX IF NOT EXISTS ix_assets_user_id
    ON assets (user_id);

CREATE INDEX IF NOT EXISTS ix_assets_user_id_ticker
    ON assets (user_id, ticker);

CREATE INDEX IF NOT EXISTS ix_assets_wallet_id_ticker
    ON assets (wallet_id, ticker);

CREATE INDEX IF NOT EXISTS ix_transactions_user_id_executed_at
    ON transactions (user_id, executed_at DESC);

CREATE INDEX IF NOT EXISTS ix_transactions_wallet_id_ticker_executed_at
    ON transactions (wallet_id, ticker, executed_at DESC);

CREATE INDEX IF NOT EXISTS ix_transactions_user_id_wallet_id_ticker
    ON transactions (user_id, wallet_id, ticker);

CREATE TRIGGER IF NOT EXISTS trg_transactions_apply_asset_position_buy
AFTER INSERT ON transactions
FOR EACH ROW
WHEN lower(trim(NEW.transaction_type)) = 'buy'
BEGIN
    INSERT INTO assets (
        user_id,
        wallet_id,
        ticker,
        quantity,
        average_price,
        cost_basis,
        currency
    )
    VALUES (
        NEW.user_id,
        NEW.wallet_id,
        upper(trim(NEW.ticker)),
        NEW.quantity,
        (((NEW.quantity * NEW.price) + NEW.fees) * 1.0) / NEW.quantity,
        (NEW.quantity * NEW.price) + NEW.fees,
        upper(trim(NEW.currency))
    )
    ON CONFLICT (user_id, wallet_id, ticker) DO UPDATE
    SET
        quantity = assets.quantity + excluded.quantity,
        cost_basis = assets.cost_basis + excluded.cost_basis,
        average_price = (
            assets.cost_basis + excluded.cost_basis
        ) * 1.0 / (
            assets.quantity + excluded.quantity
        ),
        currency = excluded.currency,
        updated_at = CURRENT_TIMESTAMP;
END;

CREATE TRIGGER IF NOT EXISTS trg_transactions_reject_oversell
BEFORE INSERT ON transactions
FOR EACH ROW
WHEN lower(trim(NEW.transaction_type)) = 'sell'
 AND (
    SELECT quantity
    FROM assets
    WHERE user_id = NEW.user_id
      AND wallet_id = NEW.wallet_id
      AND ticker = upper(trim(NEW.ticker))
 ) < NEW.quantity
BEGIN
    SELECT RAISE(ABORT, 'sell quantity exceeds current position');
END;

CREATE TRIGGER IF NOT EXISTS trg_transactions_reject_sell_without_position
BEFORE INSERT ON transactions
FOR EACH ROW
WHEN lower(trim(NEW.transaction_type)) = 'sell'
 AND NOT EXISTS (
    SELECT 1
    FROM assets
    WHERE user_id = NEW.user_id
      AND wallet_id = NEW.wallet_id
      AND ticker = upper(trim(NEW.ticker))
 )
BEGIN
    SELECT RAISE(ABORT, 'sell quantity exceeds current position');
END;

CREATE TRIGGER IF NOT EXISTS trg_transactions_apply_asset_position_partial_sell
AFTER INSERT ON transactions
FOR EACH ROW
WHEN lower(trim(NEW.transaction_type)) = 'sell'
 AND (
    SELECT quantity
    FROM assets
    WHERE user_id = NEW.user_id
      AND wallet_id = NEW.wallet_id
      AND ticker = upper(trim(NEW.ticker))
 ) > NEW.quantity
BEGIN
    UPDATE assets
    SET
        quantity = quantity - NEW.quantity,
        cost_basis = average_price * (quantity - NEW.quantity),
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = NEW.user_id
      AND wallet_id = NEW.wallet_id
      AND ticker = upper(trim(NEW.ticker));
END;

CREATE TRIGGER IF NOT EXISTS trg_transactions_apply_asset_position_full_sell
AFTER INSERT ON transactions
FOR EACH ROW
WHEN lower(trim(NEW.transaction_type)) = 'sell'
 AND (
    SELECT quantity
    FROM assets
    WHERE user_id = NEW.user_id
      AND wallet_id = NEW.wallet_id
      AND ticker = upper(trim(NEW.ticker))
 ) = NEW.quantity
BEGIN
    DELETE FROM assets
    WHERE user_id = NEW.user_id
      AND wallet_id = NEW.wallet_id
      AND ticker = upper(trim(NEW.ticker));
END;
