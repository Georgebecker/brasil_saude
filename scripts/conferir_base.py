#!/usr/bin/env python3
"""conferir_base.py - confere se o projeto ainda tem a base do projeto_loop.

O que este script faz, em linguagem simples: ele abre a "caixa de ferramentas"
do projeto e conta se todas as peças que vieram do modelo ainda estão lá —
ganchos de proteção, regras de ouro, contrato do Loop e pastas de dados.
Também confere se o `.env` está fora do git, que é a regra mais importante
de segurança do projeto.

Uso:
    python scripts/conferir_base.py

Código de saída: 0 = tudo certo; 1 = falta peça ou há problema de segurança.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

ARQUIVOS_ESPERADOS = [
    "README.md",
    "LICENSE",
    ".gitignore",
    ".env.example",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    "docs/REGRAS_DE_OURO.md",
    "docs/BASE_PROJETO_LOOP.md",
    "meu-loop-agente/program.md",
    "meu-loop-agente/config_loop.json",
    "meu-loop-agente/system_prompt.md",
    "meu-loop-agente/baseline.json",
    "meu-loop-agente/log.md",
    "meu-loop-agente/referencias_indicadores.json",
    "meu-loop-agente/medir_qualidade.py",
    "meu-loop-agente/verificar_iteracao.py",
]

PASTAS_ESPERADAS = [
    "data/raw",
    "data/processed",
    "data/descartados",
    "notebooks",
    "src",
    "tests",
    "sql",
    "scripts",
]


def rodar_git(*argumentos: str) -> str:
    """Roda um comando do git na raiz do projeto e devolve a saída em texto.

    Se o git não estiver instalado, devolve texto vazio em vez de quebrar:
    o conferente avisa do problema, mas continua procurando as outras peças.
    """
    try:
        resultado = subprocess.run(
            ["git", *argumentos],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return resultado.stdout.strip()


def main() -> int:
    """Confere arquivos, pastas e proteções; devolve 0 quando está tudo certo."""
    problemas = []

    for caminho in ARQUIVOS_ESPERADOS:
        if not (RAIZ / caminho).exists():
            problemas.append("arquivo ausente: " + caminho)

    for pasta in PASTAS_ESPERADAS:
        if not (RAIZ / pasta).is_dir():
            problemas.append("pasta ausente: " + pasta)

    arquivos_versionados = rodar_git("ls-files").splitlines()
    if ".env" in arquivos_versionados:
        problemas.append("SEGURANCA: o .env esta versionado; rode: git rm --cached .env")

    if rodar_git("config", "core.hooksPath") != ".githooks":
        problemas.append(
            "ganchos inativos; rode: powershell -ExecutionPolicy Bypass "
            "-File .githooks/instalar.ps1"
        )

    if problemas:
        print("Base incompleta ou insegura:")
        for problema in problemas:
            print("  - " + problema)
        return 1

    print("Base conferida: arquivos, pastas, ganchos e .env fora do git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
