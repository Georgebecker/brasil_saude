# log_loop.md — ciclos do Brasil Saúde

Registro dos ciclos do Loop (metodologia `projeto_loop`): hipótese, o que mudou,
métrica antes/depois e decisão. O detalhamento por iteração fica em
`meu-loop-agente/log.md`; aqui ficam as decisões de projeto e a reavaliação da
classificação do `README.md`.

> **Nota sobre a métrica principal.** A régua do Loop
> (`meu-loop-agente/referencias_indicadores.json`) pertence ao humano e mede 6
> indicadores nacionais que não fazem parte deste MVP. Por isso
> `divida_rastreabilidade` permanece **1.0000** do início ao fim: os ciclos
> abaixo foram medidos pelos critérios do prompt master (cobertura de UFs,
> testes verdes, integridade do backup), não por um número inventado.

## Ciclo 0 — implantação do ambiente (2026-10-20)

- **Hipótese:** a base `projeto_loop` é suficiente para começar o painel.
- **Mudança:** estrutura Python, venv, ganchos, contrato do Loop, CI.
- **Métrica:** dívida de rastreabilidade = 1.0000 (nada publicado).
- **Decisão:** ACEITO — ambiente pronto.

## Ciclo 1 — base territorial do IBGE

- **Hipótese:** com UFs, municípios e população, qualquer fonte com código IBGE
  pode ser agregada por estado.
- **Mudança:** `src/fontes/ibge.py`, tabelas `uf`/`municipio`, malha GeoJSON.
- **Medição:** 27 UFs, 5.571 municípios, 27 populações (Censo 2022); malha de
  98 KB; `test_fontes` verde.
- **Dificuldade:** `User-Agent` com acento fazia o IBGE responder 400.
- **Decisão:** ACEITO.

## Ciclo 2 — fonte epidemiológica

- **Hipótese:** é possível obter dengue por UF/semana sem microdado oficial.
- **Mudança:** `src/fontes/infodengue.py`, tabela `caso_semana`, convenção de
  semana brasileira.
- **Medição:** 27 UFs, 1.377 semanas, 0 falhas; coleta em 72,3 s.
- **Rejeições anteriores:** PySUS (não instala em 3.14); API do MS (502 acima de
  15 linhas, paginação instável).
- **Decisão:** ACEITO, com proveniência declarada.

## Ciclo 3 — EARS C1/C2

- **Hipótese:** o EARS detecta a elevação sustentada que a média simples esconde.
- **Mudança:** `src/ears.py`, tabela `alerta_ears`, serviço de cálculo.
- **Medição:** 2.322 alertas calculados; exemplo canônico do CDC reproduzido
  (C1 não alerta, C2 alerta).
- **Dificuldade:** C3 é acumulado; foi explicitamente não implementado.
- **Decisão:** ACEITO.

## Ciclo 4 — repasses federais

- **Hipótese:** o download mensal do Portal da Transparência substitui a API
  com token.
- **Mudança:** `src/fontes/transparencia.py`, tabela `repasse`.
- **Medição:** 12 meses publicados, 2.399 linhas UF×ação, 37,9 s; setembro/2025
  com R$ 14,04 bi em saúde.
- **Dificuldade:** CSV em latin-1; município é código SIAFI (não IBGE).
- **Decisão:** ACEITO.

## Ciclo 5 — clima

- **Hipótese:** o catálogo do INMET + série do Open-Meteo cobre os municípios
  com maior incidência.
- **Mudança:** `src/fontes/inmet.py`, tabela `estacao`/`clima_dia`, serviço
  climático ordenado por incidência.
- **Medição:** 275 estações, 4.125 dias, 0 falhas, 129,8 s.
- **Rejeições:** série do INMET responde 204 (exige token); `FL_CAPITAL` não é
  confiável (capital garantida por código IBGE).
- **Decisão:** ACEITO com fallback declarado.

## Ciclo 6 — autorização (Fase 2)

- **Hipótese:** dá para demonstrar RBAC/ABAC sem um provedor de identidade.
- **Mudança:** `src/auth/`, rotas de gestão, fila de e-mail.
- **Medição:** 11 testes; gestor de SP recebe **403** em RJ; admin recebe 200;
  público não vê detalhe.
- **Decisão:** ACEITO (protótipo, com limites documentados).

## Ciclo 7 — backup e restauração

- **Hipótese:** a cópia pela API do SQLite restaura byte a byte.
- **Mudança:** `src/backup.py`, `scripts/backup_sqlite.py`, testes.
- **Medição:** backup de 2.277.376 bytes; `integrity_check = ok`; SHA-256 do
  restaurado **idêntico** (`6f4151…19ed`); 4 testes verdes.
- **Decisão:** ACEITO.

## Ciclo 8 — fechamento do MVP

- **Hipótese:** os critérios de sucesso do prompt estão verificáveis item a item.
- **Mudança:** documentação (`docs/`, `DIARIO.md`), README e verificação final.
- **Medição:** 63 testes verdes; `ruff` limpo; 19 critérios conferidos.
- **Decisão:** ACEITO.
- **Classificação reavaliada:** `utilidade` · `funcional` (local) — ver README.

## Ciclo 9 — [loop] gráfico de correlação com nota metodológica

- **Hipótese:** mostrar casos e repasses no mesmo eixo mensal ajuda a Pergunta
  “houve recurso no período?”, desde que a tela recuse causalidade.
- **Mudança:** gráfico de barras mensal de repasses ao lado da série; nota fixa.
- **Medição:** 12 barras mensais renderizadas (2025-11 a 2026-10) para SP; a
  nota “não afirma causalidade” aparece no bloco; `pytest` segue verde.
- **Decisão:** **ACEITO** — o gráfico responde à pergunta sem sugerir causa.

## Ciclo 10 — [loop] alternância C1/C2 na interface

- **Hipótese:** deixar o usuário comparar as duas variantes aumenta a
  transparência metodológica sem confundir (C1 reage antes; C2 tolera atraso).
- **Mudança:** seletor de variante na tela, aproveitando `?metodo=` já existente.
- **Medição:** alternância recarrega a série; `test_serie_aceita_a_variante_c2`
  cobre `metodo=C2`; ambos os métodos mostram faixa para o mesmo ponto.
- **Decisão:** **ACEITO** — a tela deixa de esconder uma escolha metodológica.
