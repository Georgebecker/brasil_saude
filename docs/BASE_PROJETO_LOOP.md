# Base do projeto — `projeto_loop`

Este projeto nasceu do modelo **`projeto_loop`**
(<https://github.com/Georgebecker/projeto_loop>), clonado na máquina em
`D:\Projetos\projeto_loop`.

A conferência rápida de que a base continua inteira:

```powershell
python scripts/conferir_base.py
```

## O que veio da base, sem mudança de conteúdo

| Item | Observação |
|------|------------|
| `.githooks/` (`pre-commit`, `pre-push`, `instalar.ps1`, `README.md`) | Barreira que bloqueia `.env` e chave no commit e no push. |
| `docs/REGRAS_DE_OURO.md` | Método do projeto (Parte IV = Loop Engineering). |
| `.gitattributes` | Força LF nos ganchos (shell do git). |
| `.gitignore` | Ignora `.env`, dados, saídas, caches e `.venv`. |
| `LICENSE` | Licença MIT. |
| `data/{raw,processed,descartados}` e `notebooks/` | Fluxo bruto → validado → descartado, com `.gitkeep`. |
| `meu-loop-agente/verificar_iteracao.py` | Verificador de iteração (comandos + métrica + baseline). |
| `meu-loop-agente/system_prompt.md` | Comportamento do agente (adaptado ao objetivo deste projeto). |

## O que difere de propósito

| Item | Mudança | Motivo |
|------|---------|--------|
| `README.md` | Reescrito para o Brasil Saúde | O da base descreve o próprio modelo, não o painel. |
| `meu-loop-agente/program.md` | Contrato novo (dívida de rastreabilidade) | O contrato da base mede bundle de um exemplo Next.js. |
| `meu-loop-agente/config_loop.json` | Métrica e comandos deste projeto | O verificador lê daqui. |
| `meu-loop-agente/baseline.json` | Números do Brasil Saúde | Linha de base gravada com o medidor real. |
| `meu-loop-agente/workspace/` | **Não existe** | O alvo do Loop é a raiz do projeto (como no `selic-ipca-tracker`), não uma subpasta. |
| `meu-loop-agente/referencias_indicadores.json` | Novo | A base não traz régua de indicadores; cada projeto define a sua. |
| `meu-loop-agente/medir_qualidade.py` | Novo | Mede a métrica principal com biblioteca padrão (sem dependências). |
| `src/`, `tests/`, `sql/`, `scripts/`, `frontend/` | Novos | Estrutura de aplicação Python; a base só cria `data/` e `notebooks/`. |
| `pyproject.toml`, `.github/workflows/ci.yml` | Novos | Configuração de pytest/ruff e verificação contínua. |
| `NOTES.md`, `log_loop.md` | Novos | Decisões e ciclos, conforme as Regras de Ouro. |
| `docs/GUIA_NOVO_PROJETO.md` | **Não copiado** | É documentação de como criar projetos a partir da base; mora na base, não nos projetos derivados. |
| `scripts/criar_projeto_base.ps1` | **Não copiado** | Mesmo motivo: criar novos projetos é papel do `projeto_loop`. |
| `.env` | Copiado e mantido como veio | O `.env` pertence ao dono; nenhum valor de chave foi adicionado. |

## Como re-sincronizar com a base

Quando a base evoluir (gancho novo, regra nova, correção no verificador):

```powershell
# 1. veja o que mudou na base
cd D:\Projetos\projeto_loop
git pull

# 2. copie só o arquivo que mudou, por exemplo:
Copy-Item .githooks\pre-commit D:\Projetos\brasil_saude\.githooks\pre-commit -Force

# 3. confira a base e o git neste projeto
cd D:\Projetos\brasil_saude
python scripts/conferir_base.py
git status
```

Não copie `README.md`, `program.md` nem `baseline.json` da base: esses arquivos são
deste projeto e seriam sobrescritos por conteúdo de outro contexto.
