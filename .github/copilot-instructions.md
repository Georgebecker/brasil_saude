# Instruções do projeto para agentes

Leia e siga o [`AGENTS.md`](../AGENTS.md) na raiz — ele vence em caso de conflito.

Resumo operacional:

- Português do Brasil em resposta, código, comentário, documentação e commit.
- Loop Engineering: hipótese pequena → mudança → teste → métrica real → ACEITO/REJEITADO.
- Contrato do agente: `meu-loop-agente/program.md`; régua: `referencias_indicadores.json`.
- Nenhum valor de chave em arquivo versionado; o `.env` é local e não se altera sem pedido.
- Nenhum número de saúde sem fonte, período de referência e data de validação.
- Antes de dizer "pronto": rodar `python -m pytest -q` e `python -m ruff check .` e ler a saída.
