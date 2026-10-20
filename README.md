# Brasil Saúde

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-green)
![Status](https://img.shields.io/badge/status-rascunho%20(em%20constru%C3%A7%C3%A3o)-orange)

Este repositório prepara um **painel público de vigilância e responsabilização em saúde**:
todo número publicado precisa dizer de onde veio, a que período se refere e quando foi
validado. A pergunta que o painel responde é simples — *o que está acontecendo na saúde
do Brasil, e quem responde por isso?* — mas a resposta só vale se for rastreável.

## Classificação

| Dimensão | Valor |
|----------|-------|
| **Propósito** | `estudo` · `utilidade` |
| **Maturidade** | `rascunho` |
| **O que estou treinando** | dados públicos de saúde, rastreabilidade de fontes, painel web, Loop Engineering |
| **Quem usaria** | conselhos de saúde, gestores municipais, jornalistas de dados, cidadãos |

> A maturidade é `rascunho` de propósito: este é o **ambiente preparado**. Coleta, banco,
> API e interface entram nos próximos ciclos, com evidência no [`log_loop.md`](log_loop.md).

## Metodologia Loop

Este projeto nasce do repositório base [`projeto_loop`](https://github.com/Georgebecker/projeto_loop)
e é desenvolvido com **Loop Engineering**: uma hipótese pequena por ciclo → mudança →
teste → métrica real → decisão **ACEITO** (fica) ou **REJEITADO** (reverte).

*Este projeto não foi feito no "achismo". Cada decisão foi medida e testada.* O histórico
fica em [`log_loop.md`](log_loop.md) e o detalhe por iteração em
[`meu-loop-agente/log.md`](meu-loop-agente/log.md).

## O que tem aqui

Ambiente pronto — sem painel inventado:

- `meu-loop-agente/` — contrato (`program.md`), régua de indicadores, medidor, verificador e log do Loop.
- `src/` — configuração central do projeto (`src/config.py`).
- `tests/` — suíte que protege a base, os segredos e o formato da métrica.
- `sql/`, `data/{raw,processed,descartados}`, `notebooks/` — fluxo bruto → validado → usado.
- `.githooks/` — bloqueiam `.env` e chave no commit **e** no envio ao remoto.
- `docs/REGRAS_DE_OURO.md` — o contrato de método (dados, processo, técnica e Loop).
- `.github/workflows/ci.yml` — lint e testes em cada push.

```
brasil_saude/
├── meu-loop-agente/     # o cérebro do Loop (contrato, régua, medidor, verificador)
├── src/                 # código do painel (cresce nos próximos ciclos)
├── tests/               # testes automatizados
├── sql/                 # esquema e consultas
├── data/{raw,processed,descartados}
├── docs/                # regras de ouro e origem da base
└── scripts/             # utilitários de linha de comando
```

## Como rodar

Requisitos: Python 3.10+ (testado no 3.14) e Git.

```powershell
cd D:\Projetos\brasil_saude
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Repositório ainda local (sem remoto publicado). Quando for a hora de publicar:
> `gh repo create brasil_saude --private --source=. --remote=origin --push`.

Verificação do ambiente e do Loop:

```powershell
python -m pytest -q                        # testes do ambiente
python -m ruff check .                     # estilo e erros óbvios
python meu-loop-agente/verificar_iteracao.py estado
python meu-loop-agente/medir_qualidade.py --detalhe
```

O `.env` é local e nunca vai ao git; o modelo versionado é `.env.example`.

## 🚀 Convite à interação

**Iniciantes:** este repositório é um bom lugar para o primeiro Pull Request. As tarefas
marcadas com `good first issue` são pequenas de propósito — melhorar uma mensagem de erro,
escrever um teste, corrigir uma explicação. Eu reviso e ajudo; errar faz parte.

**Colegas de programação e dados:** abra uma Issue ou PR se encontrar gargalo, brecha de
segurança, número sem fonte ou dúvida de modelagem. Discussão técnica é bem-vinda, inclusive
quando discorda de uma decisão registrada.

**Recrutadores e visitantes:** não é tutorial copiado. É um projeto real, com histórico de
decisões, testes e um agente que mede o próprio avanço. O código está em [`src/`](src) e o
raciocínio em [`log_loop.md`](log_loop.md).

## Transparência e limitações

- **Sem dados ainda:** o painel não publica nenhum indicador; a dívida de rastreabilidade
  começa em 100%. Nada de número inventado para "encher" a tela.
- **Ambiente local:** sem deploy, sem autenticação e sem banco compartilhado.
- **Régua inicial:** os seis indicadores em `meu-loop-agente/referencias_indicadores.json`
  são ponto de partida; o dono do projeto ajusta a lista.
- **Dados públicos mudam de formato:** cada fonte precisa de coletor e de teste de
  contrato antes de entrar no painel.
- **Capturas de tela:** pendentes — a interface ainda não existe (ambiente sem tela).

## Apoio

Se este trabalho te ajudar, o autor agradece (sem compromisso):

- **PIX:** `a8b68e14-edfe-4450-88f2-c2af4aca2a6c`
- **Buy Me a Coffee:** <https://buymeacoffee.com/georgehbecker>
- **LinkedIn:** <https://www.linkedin.com/in/georgehbecker/>

## Topics sugeridos

```text
python fastapi sqlite dados-publicos saude-sus data-quality loop-engineering transparencia
```