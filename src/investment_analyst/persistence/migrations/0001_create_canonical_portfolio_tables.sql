CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL,
    display_name text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_email_not_blank CHECK (btrim(email) <> '')
);

CREATE TABLE IF NOT EXISTS public.wallets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    name text NOT NULL,
    base_currency text NOT NULL DEFAULT 'BRL',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_wallets_user_id_users
        FOREIGN KEY (user_id) REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT uq_wallets_id_user_id UNIQUE (id, user_id),
    CONSTRAINT uq_wallets_user_id_name UNIQUE (user_id, name),
    CONSTRAINT ck_wallets_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_wallets_base_currency_not_blank CHECK (btrim(base_currency) <> '')
);

CREATE TABLE IF NOT EXISTS public.assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    wallet_id uuid NOT NULL,
    ticker text NOT NULL,
    quantity numeric(24, 8) NOT NULL,
    average_price numeric(24, 8) NOT NULL,
    cost_basis numeric(24, 8) NOT NULL,
    currency text NOT NULL DEFAULT 'BRL',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_assets_user_id_users
        FOREIGN KEY (user_id) REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_assets_wallet_id_user_id_wallets
        FOREIGN KEY (wallet_id, user_id) REFERENCES public.wallets (id, user_id) ON DELETE CASCADE,
    CONSTRAINT uq_assets_user_id_wallet_id_ticker UNIQUE (user_id, wallet_id, ticker),
    CONSTRAINT ck_assets_ticker_not_blank CHECK (btrim(ticker) <> ''),
    CONSTRAINT ck_assets_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_assets_average_price_non_negative CHECK (average_price >= 0),
    CONSTRAINT ck_assets_cost_basis_non_negative CHECK (cost_basis >= 0),
    CONSTRAINT ck_assets_currency_not_blank CHECK (btrim(currency) <> '')
);

CREATE TABLE IF NOT EXISTS public.transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    wallet_id uuid NOT NULL,
    ticker text NOT NULL,
    transaction_type text NOT NULL,
    quantity numeric(24, 8) NOT NULL,
    price numeric(24, 8) NOT NULL,
    fees numeric(24, 8) NOT NULL DEFAULT 0,
    currency text NOT NULL DEFAULT 'BRL',
    executed_at timestamptz NOT NULL DEFAULT now(),
    source text NOT NULL DEFAULT 'manual',
    external_reference text,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_transactions_user_id_users
        FOREIGN KEY (user_id) REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT fk_transactions_wallet_id_user_id_wallets
        FOREIGN KEY (wallet_id, user_id) REFERENCES public.wallets (id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_transactions_ticker_not_blank CHECK (btrim(ticker) <> ''),
    CONSTRAINT ck_transactions_type_buy_or_sell CHECK (transaction_type IN ('buy', 'sell')),
    CONSTRAINT ck_transactions_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_transactions_price_non_negative CHECK (price >= 0),
    CONSTRAINT ck_transactions_fees_non_negative CHECK (fees >= 0),
    CONSTRAINT ck_transactions_currency_not_blank CHECK (btrim(currency) <> ''),
    CONSTRAINT ck_transactions_source_not_blank CHECK (btrim(source) <> '')
);

CREATE INDEX IF NOT EXISTS ix_wallets_user_id
    ON public.wallets (user_id);

CREATE INDEX IF NOT EXISTS ix_assets_user_id
    ON public.assets (user_id);

CREATE INDEX IF NOT EXISTS ix_assets_user_id_ticker
    ON public.assets (user_id, ticker);

CREATE INDEX IF NOT EXISTS ix_assets_wallet_id_ticker
    ON public.assets (wallet_id, ticker);

CREATE INDEX IF NOT EXISTS ix_transactions_user_id_executed_at
    ON public.transactions (user_id, executed_at DESC);

CREATE INDEX IF NOT EXISTS ix_transactions_wallet_id_ticker_executed_at
    ON public.transactions (wallet_id, ticker, executed_at DESC);

CREATE INDEX IF NOT EXISTS ix_transactions_user_id_wallet_id_ticker
    ON public.transactions (user_id, wallet_id, ticker);

CREATE OR REPLACE FUNCTION public.apply_transaction_to_asset_position()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    current_asset public.assets%ROWTYPE;
    delta_cost_basis numeric(24, 8);
    new_quantity numeric(24, 8);
    new_cost_basis numeric(24, 8);
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'apply_transaction_to_asset_position only supports INSERT';
    END IF;

    NEW.ticker := upper(btrim(NEW.ticker));
    NEW.transaction_type := lower(btrim(NEW.transaction_type));
    NEW.currency := upper(btrim(NEW.currency));
    NEW.source := lower(btrim(NEW.source));

    IF NEW.transaction_type = 'buy' THEN
        delta_cost_basis := (NEW.quantity * NEW.price) + NEW.fees;

        INSERT INTO public.assets AS asset_position (
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
            NEW.ticker,
            NEW.quantity,
            delta_cost_basis / NEW.quantity,
            delta_cost_basis,
            NEW.currency
        )
        ON CONFLICT (user_id, wallet_id, ticker) DO UPDATE
        SET
            quantity = asset_position.quantity + EXCLUDED.quantity,
            cost_basis = asset_position.cost_basis + EXCLUDED.cost_basis,
            average_price = (
                asset_position.cost_basis + EXCLUDED.cost_basis
            ) / (
                asset_position.quantity + EXCLUDED.quantity
            ),
            currency = EXCLUDED.currency,
            updated_at = now();

        RETURN NEW;
    END IF;

    IF NEW.transaction_type = 'sell' THEN
        SELECT *
        INTO current_asset
        FROM public.assets
        WHERE user_id = NEW.user_id
          AND wallet_id = NEW.wallet_id
          AND ticker = NEW.ticker
        FOR UPDATE;

        IF NOT FOUND OR current_asset.quantity < NEW.quantity THEN
            RAISE EXCEPTION 'sell quantity exceeds current position for ticker %', NEW.ticker
                USING ERRCODE = '23514',
                      CONSTRAINT = 'ck_transactions_sell_not_above_position';
        END IF;

        new_quantity := current_asset.quantity - NEW.quantity;

        IF new_quantity = 0 THEN
            DELETE FROM public.assets
            WHERE id = current_asset.id;
        ELSE
            new_cost_basis := current_asset.average_price * new_quantity;

            UPDATE public.assets
            SET
                quantity = new_quantity,
                average_price = current_asset.average_price,
                cost_basis = new_cost_basis,
                currency = NEW.currency,
                updated_at = now()
            WHERE id = current_asset.id;
        END IF;

        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'unsupported transaction_type %', NEW.transaction_type
        USING ERRCODE = '23514',
              CONSTRAINT = 'ck_transactions_type_buy_or_sell';
END;
$$;

DROP TRIGGER IF EXISTS trg_transactions_apply_asset_position ON public.transactions;

CREATE TRIGGER trg_transactions_apply_asset_position
BEFORE INSERT ON public.transactions
FOR EACH ROW
EXECUTE FUNCTION public.apply_transaction_to_asset_position();
