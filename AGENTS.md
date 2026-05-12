# AGENTS.md

## Workflow principal

Use os subagents em `.codex/agents/`.

Fluxo obrigatório:

1. `workflow-orchestrator` planeja.
2. `task-distributor` divide tarefas.
3. `backend-developer`, `frontend-developer` ou `fullstack-developer` implementam.
4. `reviewer` revisa código.
5. `architect-reviewer` revisa arquitetura.
6. `qa-expert` valida funcionalmente.
7. `devops-engineer` valida build, Docker e deploy.
8. Se houver erro, `error-coordinator` analisa o log e devolve ao responsável.
9. O responsável corrige, adiciona teste de regressão e devolve para revisão.

## Regra de self-correction

Sempre que QA, reviewer ou architect-reviewer reprovar:

- Ler o log completo.
- Identificar causa raiz.
- Corrigir o menor escopo possível.
- Adicionar ou ajustar teste de regressão.
- Rodar lint, testes e build.
- Retornar para nova revisão.

## Critério de DONE

Uma tarefa só é concluída quando:

- implementação finalizada
- testes passando
- review aprovado
- tech review aprovado
- QA aprovado
- build/deploy validado quando aplicável