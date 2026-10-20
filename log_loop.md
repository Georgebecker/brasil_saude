# log_loop.md — ciclos do Brasil Saúde

Registro dos ciclos do Loop (metodologia `projeto_loop`): hipótese, o que mudou,
métrica antes/depois e decisão. O detalhamento por iteração fica em
`meu-loop-agente/log.md`; aqui ficam as decisões de projeto e a reavaliação da
classificação do `README.md`.

## Ciclo 0 — implantação do ambiente (2026-10-20)

- **Objetivo do ciclo**: entregar o ambiente pronto para o desenvolvimento — base do
  `projeto_loop`, proteções de git ativas, `.venv`, estrutura Python, contrato do Loop e
  medidor funcionando.
- **O que foi feito**: projeto criado pelo script da base; `meu-loop-agente/` adaptado
  (contrato, régua de indicadores, medidor, baseline); `src/`, `tests/`, `sql/`,
  `scripts/`, `frontend/`; `pyproject.toml`; CI; `docs/BASE_PROJETO_LOOP.md`;
  `NOTES.md`; este log.
- **Métrica**: dívida de rastreabilidade = 1.0000 (nada publicado ainda; valor real,
  sem dado de saúde inventado). Linha de base gravada pelo verificador.
- **Verificação**: `pytest` e `ruff` verdes antes do commit.
- **Classificação reavaliada**: `estudo` · `utilidade` / `rascunho`.
- **Decisão**: ACEITO — ambiente pronto; desenvolvimento do painel começa no Ciclo 1.

## Ciclo 1 — (aguardando o prompt de desenvolvimento)

- **Hipótese**: a ser definida com o escopo completo do painel.
