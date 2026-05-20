# Investment Analyst Web

Front-end Next.js para a experiencia descrita em `docs/ADR/ADR.md` e
`docs/minispec/minispec-do-sistema-de-análise-de-investimentos-inteligente.md`.

## Configuracao

```bash
cp .env.example .env.local
```

Variaveis:

- `NEXT_PUBLIC_API_BASE_URL`: URL da API FastAPI. Padrao: `http://localhost:8000/api/v1`.
- `NEXT_PUBLIC_SUPABASE_URL`: URL do projeto Supabase.
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`: chave anon publica do Supabase.
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`: alternativa para projetos que ja usam
  a chave publishable nova do Supabase.

Depois de preencher `.env.local`, o middleware valida a sessao com
`supabase.auth.getUser()` e protege todas as rotas, exceto `/login` e
`/cadastro` e `/auth/callback`.

## Desenvolvimento

```bash
npm install
npm run dev
```

A tela principal inclui:

- Supabase Auth preparado via middleware e cliente browser.
- Gating por plano Free/Pro e saldo de creditos.
- Upload CSV/PDF com pre-validacao client-side.
- Preenchimento manual quando a importacao falha.
- Polling com TanStack Query para `/analysis/status/{job_id}`.
- Invalidacao de `recommendations` ao carregar resultado.
- Tabela de ativos paginada em 10 itens por pagina.
