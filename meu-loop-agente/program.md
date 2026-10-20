# Loop Program — Brasil Saúde

> Este arquivo é o CONTRATO do agente. Só o humano altera.
> Os números ficam em `baseline.json`; comandos e medição, em `config_loop.json`.
> Mantenha os três coerentes entre si.
> Base metodológica: projeto `projeto_loop` (github.com/Georgebecker/projeto_loop).
> O projeto alvo é o próprio `brasil_saude`, na RAIZ deste repositório.

## OBJETIVO

Transformar o Brasil Saúde em um painel público confiável: cada indicador de saúde
publicado precisa ter fonte oficial, período de referência, valor validado e teste
automatizado que proteja a publicação — sem quebrar a API, a interface nem a suíte.

Em uma frase: **reduzir a dívida de rastreabilidade sem perder qualidade de código.**

## BASELINE E META

- Linha de base e melhor valor: `baseline.json` (gravados pelo verificador).
- Meta: `meta_percentual` em `baseline.json` (reduzir a dívida em 10%).
- A régua (quais indicadores o painel deve publicar) é
  `meu-loop-agente/referencias_indicadores.json` — **arquivo do humano**; o agente
  nunca o edita. Para ampliar o escopo, o humano acrescenta indicadores ali.
- Gravar a linha de base: `python meu-loop-agente/verificar_iteracao.py medir --definir-baseline`

## ARQUIVOS PERMITIDOS (o agente só mexe aqui)

- `src/**` — coleta, tratamento, banco, API e regras do painel
- `frontend/**` — interface web do painel
- `tests/**` — testes automatizados
- `sql/**` — esquema e consultas
- `scripts/**` — utilitários de linha de comando (nunca deploy)
- `data/**` — apenas artefatos gerados (nunca sobrescrever `data/raw/` original)
- `requirements.txt`, `pyproject.toml`
- `README.md` — apenas a seção `## Classificação` e a documentação de uso
- `NOTES.md`, `log_loop.md`

## ARQUIVOS PROIBIDOS

- `meu-loop-agente/**` — contrato, régua, medidor, verificador, baseline e prompts
- `.env` e `.env.*` (exceto o modelo `.env.example`) — segredos e credenciais
- `.githooks/**`, `.github/**`
- `docs/REGRAS_DE_OURO.md`, `docs/BASE_PROJETO_LOOP.md`, `LICENSE`
- Qualquer caminho fora deste repositório

## COMANDOS DE VERIFICAÇÃO (obrigatórios)

- Fonte de máquina: `config_loop.json` -> `verificacao.comandos` (não duplicar aqui,
  para não divergir).
- Conteúdo atual: `python -m pytest -q` e `python -m ruff check .`.

## MÉTRICA PRINCIPAL

- Nome: dívida de rastreabilidade dos indicadores.
- Unidade: fração de 0 a 1.
- Direção: **menor é melhor**.
- Definição: para cada indicador da régua, quatro documentos são exigidos —
  `publicado`, `fonte` (órgão + URL https), `periodo` (período de referência) e
  `validado` (valor numérico + data de validação). O medidor conta os documentos
  faltantes e divide pelo total.
- Comando e leitura do número: `config_loop.json` -> `metrica`.

## MÉTRICAS SECUNDÁRIAS (não podem piorar)

- Suíte de testes: todos passando.
- Lint: sem erros.
- Dado bruto: `data/raw/` nunca é sobrescrito nem apagado.

## CRITÉRIO DE ACEITE

- Todos os comandos de verificação passam; E
- a métrica principal fica **menor** que o melhor valor registrado.

## CRITÉRIO DE REJEIÇÃO

- Qualquer comando falha; OU
- a métrica fica igual ou pior.

## POLÍTICA DE MUDANÇA

- Uma hipótese por iteração.
- Diff pequeno (menos de 50 linhas).
- Reverter imediatamente o que for rejeitado.
- Registrar cada iteração no `log.md` (hipótese, arquivos, métricas, decisão).
- **Nunca publicar número sem fonte:** registro sem `fonte`, `url_fonte` e
  `periodo_referencia` não entra em `data/processed/indicadores.json`.

## LIMITES DE PARADA

- Máximo: 20 iterações (fonte de máquina: `config_loop.json` -> `limites`).
- Parada antecipada: meta atingida OU 5 rejeições consecutivas OU falta de
  hipóteses plausíveis.
