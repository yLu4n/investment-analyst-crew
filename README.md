# Investment Analyst Crew

Backend Python para análise inteligente de carteiras com CrewAI, cálculos
determinísticos e uma API assíncrona compatível com o contrato descrito em
`docs/SDD/sdd-do-sistema-de-análise-de-investimentos-inteligente.md`.

## API local

Instale as dependências e rode a API:

```bash
UV_CACHE_DIR=.uv-cache uv run uvicorn investment_analyst.api:app --reload
```

Endpoints disponíveis:

- `POST /api/v1/analysis`: cria um job de análise e retorna `202 Accepted` com
  `{"job_id": "..."}`.
- `GET /api/v1/analysis/status/{job_id}`: retorna `status`, `current_step` e
  `error_message`.
- `GET /api/v1/analysis/result/{job_id}`: retorna `result_payload`,
  `report_markdown` e `pdf_path` quando o job estiver `completed`.

Payload mínimo:

```json
{
  "assets": [
    {"ticker": "PETR4", "quantity": 100, "average_price": 32.5}
  ],
  "risk_profile": "moderate",
  "monthly_contribution": 1000
}
```

Quando a autenticação estiver habilitada, a API deriva o usuário do token
Supabase (`sub`). O cliente não deve enviar `user_id` no payload.

## Supabase

O frontend usa Supabase Auth e envia o access token para a API. A API valida
esse token com `SUPABASE_JWT_SECRET`; copie o valor em Supabase Dashboard >
Project Settings > API > JWT Settings.

Crie os arquivos de ambiente:

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env.local
```

Preencha:

```env
# .env
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_JWT_SECRET=<jwt-secret>
INVESTMENT_ANALYST_REQUIRE_AUTH=true

# apps/web/.env.local
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-or-publishable-key>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

Para aplicar a schema no Supabase:

```bash
supabase link --project-ref <project-ref>
supabase db push
```

A migration em `supabase/migrations` usa Postgres nativo, RLS por
`auth.uid()`, chaves estrangeiras para `auth.users`, índices nos filtros por
usuário/carteira/ticker e trigger para atualizar posições a partir de compras e
vendas.

Nesta rodada, o job store e os caches de requisição/ativo usam implementação em
memória com TTL de 24 horas. Eles foram isolados para troca posterior por
servicos persistentes dedicados, conforme ADR/SDD.

## Banco de dados para testes

Os testes de integração de banco usam SQLite em memoria por padrao. Use
`.env.test` apenas se quiser apontar para outro arquivo SQLite local. O arquivo
real fica ignorado pelo Git.

```bash
cp .env.test.example .env.test
```

Edite `.env.test` e preencha:

```env
INVESTMENT_ANALYST_TEST_DATABASE_URL=sqlite:///investment_analyst_test.sqlite3
```

Esse banco deve ser exclusivo para testes. O teste
`tests/test_sqlite_migration_integration.py` aplica a migration versionada e
valida as triggers de preco medio/hard delete no SQLite.

## Validação

```bash
UV_CACHE_DIR=.uv-cache uv run pytest
UV_CACHE_DIR=.uv-cache uv run ruff check .
```
