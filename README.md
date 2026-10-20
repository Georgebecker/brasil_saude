# Brasil Saúde

**Aqui vive um agente de Loop Engineering** (DeepSeek Flash): ele melhora sistemas em
**ciclos contínuos e verificáveis** — lê o objetivo, propõe UMA mudança pequena, testa,
mede, decide (mantém ou reverte) e registra. Sem intervenção humana a cada passo.

Este repositório **é o modelo em si** — o Loop Engineer completo (contrato, regras de ouro,
ferramentas de verificação e agente), pronto para receber um sistema alvo e rodar ciclos.

---

**Autor:** George Herman Becker
**Gestão em Tecnologia da Informação**


**Apoie o autor:**
- **PIX:** `a8b68e14-edfe-4450-88f2-c2af4aca2a6c`
- **Buy Me a Coffee:** <https://buymeacoffee.com/georgehbecker>
- **LinkedIn:** <https://www.linkedin.com/in/georgehbecker/>

---

## Loop Engineering — o coração do projeto

Um agente opera em ciclos: lê o contrato (`program.md`), propõe **UMA** hipótese pequena,
aplica a mudança, roda a verificação, **mede a métrica principal** e decide —
**ACEITO** (mantém e atualiza a linha de base) ou **REJEITADO** (reverte na hora) —
registrando tudo no log. O ciclo repete até a meta, dentro de limites definidos.

**Um ciclo de verdade, do começo ao fim (exemplo):**

```
Iteração 1
- Hipótese: trocar a biblioteca moment.js por date-fns
- Arquivos: workspace/lib/date.ts, workspace/package.json
- Métrica antes: 312 kB  →  depois: 298 kB  (melhoria de 4,49%)
- Comandos de verificação: todos passaram
- Decisão: ACEITO — a linha de base vira 298 kB; o próximo ciclo parte daqui

Iteração 2
- Hipótese: remover um import não utilizado de lodash
- Métrica antes: 298 kB  →  depois: 298 kB  (não melhorou)
- Decisão: REJEITADO — a mudança é revertida e nada entra na linha de base
```

**As vantagens na prática:**

- **Melhoria medida, não "achada":** cada iteração tem número antes/depois; o que não melhora é revertido.
- **Zero regressão silenciosa:** a linha de base só avança quando a métrica melhora de verdade.
- **Rede de segurança total:** hipótese pequena + ponto de retorno antes de cada ciclo — reverter é um comando só.
- **Decisão objetiva:** critérios de aceite/rejeição escritos no contrato — não é opinião nem promessa da IA.
- **Conhecimento que não se perde:** o `log.md` guarda cada tentativa (hipótese, arquivos, métricas, decisão).
- **Autonomia sem risco:** o agente só mexe no que o contrato permite (dentro de `workspace/`); o resto é proibido e bloqueado.
- **Ganho acumulado:** melhorias aceitas se somam — o avanço compõe a cada ciclo.
- **Custo controlado:** limites de parada (meta, iterações, rejeições seguidas) e temperatura baixa (consistência).
- **Um contrato, dois "cérebros":** funciona hoje com o agente do chat e amanhã com o runner autônomo (API DeepSeek).

**Onde está:** `meu-loop-agente/` — contrato (`program.md`), configuração de máquina
(`config_loop.json`), linha de base (`baseline.json`), log (`log.md`), comportamento do
agente (`system_prompt.md`) e o verificador (`verificar_iteracao.py`).
Guia de uso: [`meu-loop-agente/README.md`](meu-loop-agente/README.md).

---

## O que tem aqui (por enquanto)

- `docs/REGRAS_DE_OURO.md` — as melhores regras, sintetizadas, para todo projeto de dados (Python + SQL + arquitetura moderna).
- `meu-loop-agente/` — **o coração do projeto:** o agente de Loop Engineering (contrato, métrica, log e verificador para ciclos de melhoria contínua; ele só mexe em `meu-loop-agente/workspace/`).
- `.env` / `.env.example` — configuração pronta (caminhos, banco de dados, APIs), sem segredo no repositório.
- `.githooks/` — ganchos de proteção do git: bloqueiam o `.env` no commit **e** no envio ao remoto (ativar em um clone novo: `git config core.hooksPath .githooks` ou `.githooks\instalar.ps1`).
- Pastas-base prontas para crescer: `data/raw`, `data/processed`, `data/descartados`, `notebooks`.

## Estrutura prevista (vai evoluir com o projeto)

```
brasil_saude/
├── .env / .env.example        # configuração (nunca commitar o .env)
├── .githooks/                 # ganchos de proteção (bloqueiam .env no commit e no envio)
├── README.md                  # este arquivo
├── docs/                      # documentação e regras de ouro
├── meu-loop-agente/           # agente de Loop Engineering (contrato, log, workspace, verificador)
├── data/
│   ├── raw/                   # dados brutos (nunca alterar)
│   ├── processed/             # dados tratados/limpos
│   └── descartados/           # fora de circulação (nunca apagar)
├── notebooks/                 # análises exploratórias (.ipynb)
├── src/                       # código reutilizável (cresce depois)
└── sql/                       # consultas e schemas SQL (cresce depois)
```

## Requisitos

- **Python 3.8+** — o verificador do agente usa somente a biblioteca padrão (sem dependências externas por enquanto; veja `requirements.txt`).
- **Git** — com os ganchos de proteção ativos (`git config core.hooksPath .githooks`).
- **Node.js** — opcional; necessário apenas se o projeto alvo for o exemplo Next.js do `program.md`.

## Comece por aqui

1. Leia [`docs/REGRAS_DE_OURO.md`](docs/REGRAS_DE_OURO.md) — é o contrato do projeto (a **Parte IV** é o guia do agente de Loop Engineering).
2. Para operar o agente: leia [`meu-loop-agente/README.md`](meu-loop-agente/README.md) — contrato, comandos e como rodar um ciclo.
3. O `.env` já está criado neste projeto (e nunca vai ao git); em um clone novo, copie `.env.example` para `.env` e ajuste os valores (caminhos, banco, chaves).
4. Use `data/raw` para o que vier bruto e `data/processed` só para o que for tratado e validado.
5. Nunca apague dado: se não servir mais, mova para uma pasta de descarte (ex.: `data/descartados/`).

---
