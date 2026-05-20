create extension if not exists pgcrypto;

create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    email text,
    display_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint ck_profiles_email_not_blank
        check (email is null or btrim(email) <> '')
);

create table if not exists public.wallets (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    name text not null,
    base_currency text not null default 'BRL',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_wallets_id_user_id unique (id, user_id),
    constraint uq_wallets_user_id_name unique (user_id, name),
    constraint ck_wallets_name_not_blank check (btrim(name) <> ''),
    constraint ck_wallets_base_currency_not_blank check (btrim(base_currency) <> '')
);

create table if not exists public.positions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    wallet_id uuid not null,
    ticker text not null,
    quantity numeric(24, 8) not null,
    average_price numeric(18, 4) not null,
    cost_basis numeric(18, 4) not null,
    currency text not null default 'BRL',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint fk_positions_wallet_id_user_id_wallets
        foreign key (wallet_id, user_id) references public.wallets (id, user_id) on delete cascade,
    constraint uq_positions_user_id_wallet_id_ticker unique (user_id, wallet_id, ticker),
    constraint ck_positions_ticker_not_blank check (btrim(ticker) <> ''),
    constraint ck_positions_quantity_positive check (quantity > 0),
    constraint ck_positions_average_price_non_negative check (average_price >= 0),
    constraint ck_positions_cost_basis_non_negative check (cost_basis >= 0),
    constraint ck_positions_currency_not_blank check (btrim(currency) <> '')
);

create table if not exists public.transactions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    wallet_id uuid not null,
    ticker text not null,
    transaction_type text not null,
    quantity numeric(24, 8) not null,
    price numeric(18, 4) not null,
    fees numeric(18, 4) not null default 0,
    currency text not null default 'BRL',
    executed_at timestamptz not null default now(),
    source text not null default 'manual',
    external_reference text,
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint fk_transactions_wallet_id_user_id_wallets
        foreign key (wallet_id, user_id) references public.wallets (id, user_id) on delete cascade,
    constraint ck_transactions_ticker_not_blank check (btrim(ticker) <> ''),
    constraint ck_transactions_type_buy_or_sell
        check (lower(btrim(transaction_type)) in ('buy', 'sell')),
    constraint ck_transactions_quantity_positive check (quantity > 0),
    constraint ck_transactions_price_non_negative check (price >= 0),
    constraint ck_transactions_fees_non_negative check (fees >= 0),
    constraint ck_transactions_currency_not_blank check (btrim(currency) <> ''),
    constraint ck_transactions_source_not_blank check (btrim(source) <> '')
);

create index if not exists ix_wallets_user_id
    on public.wallets (user_id);

create index if not exists ix_positions_user_id
    on public.positions (user_id);

create index if not exists ix_positions_user_id_ticker
    on public.positions (user_id, ticker);

create index if not exists ix_positions_wallet_id_ticker
    on public.positions (wallet_id, ticker);

create index if not exists ix_transactions_user_id_executed_at
    on public.transactions (user_id, executed_at desc);

create index if not exists ix_transactions_wallet_id_ticker_executed_at
    on public.transactions (wallet_id, ticker, executed_at desc);

create index if not exists ix_transactions_user_id_wallet_id_ticker
    on public.transactions (user_id, wallet_id, ticker);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger trg_profiles_set_updated_at
before update on public.profiles
for each row
execute function public.set_updated_at();

create trigger trg_wallets_set_updated_at
before update on public.wallets
for each row
execute function public.set_updated_at();

create trigger trg_positions_set_updated_at
before update on public.positions
for each row
execute function public.set_updated_at();

create or replace function public.normalize_transaction_fields()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.ticker = upper(btrim(new.ticker));
    new.transaction_type = lower(btrim(new.transaction_type));
    new.currency = upper(btrim(new.currency));
    new.source = lower(btrim(new.source));
    return new;
end;
$$;

create trigger trg_transactions_normalize_fields
before insert or update on public.transactions
for each row
execute function public.normalize_transaction_fields();

create or replace function public.apply_transaction_to_position()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    current_position public.positions%rowtype;
    transaction_cost numeric(18, 4);
begin
    transaction_cost := (new.quantity * new.price) + new.fees;

    if new.transaction_type = 'buy' then
        insert into public.positions (
            user_id,
            wallet_id,
            ticker,
            quantity,
            average_price,
            cost_basis,
            currency
        )
        values (
            new.user_id,
            new.wallet_id,
            new.ticker,
            new.quantity,
            transaction_cost / new.quantity,
            transaction_cost,
            new.currency
        )
        on conflict (user_id, wallet_id, ticker) do update
        set
            quantity = public.positions.quantity + excluded.quantity,
            cost_basis = public.positions.cost_basis + excluded.cost_basis,
            average_price = (
                public.positions.cost_basis + excluded.cost_basis
            ) / (
                public.positions.quantity + excluded.quantity
            ),
            currency = excluded.currency,
            updated_at = now();

        return new;
    end if;

    select *
    into current_position
    from public.positions
    where user_id = new.user_id
      and wallet_id = new.wallet_id
      and ticker = new.ticker
    for update;

    if not found or current_position.quantity < new.quantity then
        raise exception 'sell quantity exceeds current position'
            using errcode = '23514';
    end if;

    if current_position.quantity = new.quantity then
        delete from public.positions
        where id = current_position.id;
    else
        update public.positions
        set
            quantity = current_position.quantity - new.quantity,
            cost_basis = current_position.average_price * (current_position.quantity - new.quantity),
            updated_at = now()
        where id = current_position.id;
    end if;

    return new;
end;
$$;

create trigger trg_transactions_apply_position
after insert on public.transactions
for each row
execute function public.apply_transaction_to_position();

alter table public.profiles enable row level security;
alter table public.wallets enable row level security;
alter table public.positions enable row level security;
alter table public.transactions enable row level security;

create policy "Users can view own profile"
on public.profiles
for select
to authenticated
using (id = (select auth.uid()));

create policy "Users can insert own profile"
on public.profiles
for insert
to authenticated
with check (id = (select auth.uid()));

create policy "Users can update own profile"
on public.profiles
for update
to authenticated
using (id = (select auth.uid()))
with check (id = (select auth.uid()));

create policy "Users can view own wallets"
on public.wallets
for select
to authenticated
using (user_id = (select auth.uid()));

create policy "Users can insert own wallets"
on public.wallets
for insert
to authenticated
with check (user_id = (select auth.uid()));

create policy "Users can update own wallets"
on public.wallets
for update
to authenticated
using (user_id = (select auth.uid()))
with check (user_id = (select auth.uid()));

create policy "Users can delete own wallets"
on public.wallets
for delete
to authenticated
using (user_id = (select auth.uid()));

create policy "Users can view own positions"
on public.positions
for select
to authenticated
using (user_id = (select auth.uid()));

create policy "Users can insert own positions"
on public.positions
for insert
to authenticated
with check (user_id = (select auth.uid()));

create policy "Users can update own positions"
on public.positions
for update
to authenticated
using (user_id = (select auth.uid()))
with check (user_id = (select auth.uid()));

create policy "Users can delete own positions"
on public.positions
for delete
to authenticated
using (user_id = (select auth.uid()));

create policy "Users can view own transactions"
on public.transactions
for select
to authenticated
using (user_id = (select auth.uid()));

create policy "Users can insert own transactions"
on public.transactions
for insert
to authenticated
with check (user_id = (select auth.uid()));

create policy "Users can update own transactions"
on public.transactions
for update
to authenticated
using (user_id = (select auth.uid()))
with check (user_id = (select auth.uid()));

create policy "Users can delete own transactions"
on public.transactions
for delete
to authenticated
using (user_id = (select auth.uid()));

create or replace function public.create_profile_for_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, email, display_name)
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data ->> 'display_name', new.raw_user_meta_data ->> 'name')
    )
    on conflict (id) do update
    set
        email = excluded.email,
        display_name = coalesce(public.profiles.display_name, excluded.display_name),
        updated_at = now();

    return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row
execute function public.create_profile_for_new_user();
