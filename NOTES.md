# NOTES — decisões do Brasil Saúde

> Decisão não trivial entra aqui, curta e datada. O detalhe de cada ciclo fica em
> `log_loop.md`; a iteração do agente, em `meu-loop-agente/log.md`.

## 2026-10-20 — criação do ambiente (Ciclo 0)

**Base.** Projeto criado com
`projeto_loop\scripts\criar_projeto_base.ps1 -Nome brasil_saude -Titulo "Brasil Saúde" -Venv`.
O script copiou a base, ajustou o nome nos textos, iniciou o git, ativou
`core.hooksPath = .githooks` e criou o `.venv`.

**Nome.** `brasil_saude` (pasta e `PROJETO_NOME`), título "Brasil Saúde". O nome é
apenas uma escolha de organização: renomear pasta + `PROJETO_NOME` não quebra nada.

**Alvo do Loop.** A raiz do repositório, e não `meu-loop-agente/workspace/`. Motivo: o
projeto é uma aplicação Python com `src/`, `tests/` e `sql/`; enclausurar tudo em uma
subpasta criaria dois lugares para o mesmo código. O contrato lista os caminhos
permitidos e proibidos, então o escopo continua fechado.

**Métrica principal.** `divida_rastreabilidade`, de 0 a 1, menor é melhor:
cada indicador da régua exige quatro documentos (publicado, fonte, período, validado).
Escolha em vez de "cobertura de testes" porque o compromisso público do painel é que
todo número tenha origem e data — e isso é verificável por máquina.

**Linha de base.** Gravada em `baseline.json` com o valor real medido na criação
(100% da régua sem publicação). Não foi inventado um número "bonito" para começar.

**Régua inicial.** Seis indicadores nacionais (mortalidade infantil, cobertura vacinal,
internações evitáveis, leitos SUS, gasto em saúde e agravos notificados). É ponto de
partida; o dono amplia ou troca itens em
`meu-loop-agente/referencias_indicadores.json` — o agente nunca edita esse arquivo.

**Stack preparada.** Python 3.14 (local) com `python-dotenv`, `requests`, `pandas`,
`fastapi`, `uvicorn`, `jinja2` para o painel, e `pytest`, `pytest-cov`, `ruff` para
qualidade. O prompt completo de desenvolvimento pode trocar peças: basta ajustar
`requirements.txt` e o contrato.

**`.env` local.** Veio da base e **não foi alterado** (regra: o `.env` pertence ao dono).
Ele contém `PROJETO_NOME=brasil_saude` e `DB_URL` apontando para `data/estudos.db`.
Se quiser alinhar ao projeto, ajuste à mão para `sqlite:///data/brasil_saude.db`; o
código lê a variável, então nada quebra enquanto não houver banco.

**Segurança.** Nenhum valor de chave foi escrito em arquivo. `.env` fora do índice do
git, `pre-commit` e `pre-push` ativos, e um teste automatizado vigia o `.env.example`.

**Pendências (próximo ciclo).** Coleta real das fontes oficiais, banco SQLite, API,
interface do painel, primeira publicação de indicadores e capturas de tela (quando a
interface existir).

## 2026-10-20 — restauração das Regras de Ouro

**Achado.** A versão mais completa das regras estava em
`selic-ipca-tracker/REGRAS_DE_OURO.md` (14/10/2026, R1–R36, 256 linhas), com cópia em
`_backup-docs-pessoais-20261015`. A base `projeto_loop` parou em **R32** (11/09) e as
cópias derivadas (`api-cep-valida`, este projeto) seguiram a base. As regras R33–R36
nunca voltaram para a base.

**Restaurado na base e neste projeto.** R33 (idioma pt-BR), R34 (`.env` em todo
projeto), R35 (saber qual modelo responde), R36 (chave só na máquina local), itens 7 e 8
da proteção em camadas e as notas de "consistência viva" e "kit de proteção global".

**Ajuste de conteúdo.** R36 foi alinhada à instrução global de 18/10: o `.env` local
**pode** guardar valor; o que nunca pode é arquivo versionado com valor de chave.

**Pendente (fora deste projeto).** `selic-ipca-tracker` ignora `REGRAS_DE_OURO.md` no
`.gitignore`, então a versão mais nova não está no histórico do git; e os projetos
`projeto_becker`, `cub-sc`, `combustivelBR` e `projeto_hostinger` têm apenas R1–R23
(sem a Parte IV do Loop, removida de propósito em 29/09).
