"""Linha de comando do backup do Brasil Saúde.

Uso típico (na raiz do projeto, com o `.venv` ativo):

    python scripts/backup_sqlite.py criar
    python scripts/backup_sqlite.py verificar data/backups/brasil_saude_AAAAMMDD_HHMMSS.db
    python scripts/backup_sqlite.py restaurar data/backups/arquivo.db data/restaurado.db

O agendamento (cron ou Agendador de Tarefas do Windows) está documentado em
`docs/dba/automacao.md`; aqui fica só a ferramenta.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Permite rodar como script (`python scripts/...)` sem instalar o pacote.
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src import backup, config  # noqa: E402 - import depois do ajuste de caminho


def comando_criar(args: argparse.Namespace) -> int:
    """Cria o backup e imprime a prova (integridade, tamanho, hash)."""
    registro = backup.criar(
        Path(args.origem),
        Path(args.destino),
        retencao=args.reter,
    )
    print(json.dumps(registro, ensure_ascii=False, indent=2))
    return 0


def comando_verificar(args: argparse.Namespace) -> int:
    """Verifica um arquivo de backup já existente."""
    prova = backup.verificar(Path(args.arquivo))
    print(json.dumps(prova, ensure_ascii=False, indent=2))
    return 0 if prova["integridade"] == "ok" else 1


def comando_restaurar(args: argparse.Namespace) -> int:
    """Restaura uma cópia e imprime o resultado da verificação no destino."""
    resultado = backup.restaurar(Path(args.arquivo), Path(args.destino))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    """Monta os argumentos e despacha o subcomando."""
    parser = argparse.ArgumentParser(description="Backup e restauração do banco do Brasil Saúde")
    sub = parser.add_subparsers(dest="comando", required=True)

    criar = sub.add_parser("criar", help="cria um backup datado e verificado")
    criar.add_argument("--origem", default=str(config.CAMINHO_BANCO))
    criar.add_argument("--destino", default=str(config.RAIZ / "data" / "backups"))
    criar.add_argument("--reter", type=int, default=7, help="quantas cópias manter")
    criar.set_defaults(funcao=comando_criar)

    verificar = sub.add_parser("verificar", help="confere integridade de um backup")
    verificar.add_argument("arquivo")
    verificar.set_defaults(funcao=comando_verificar)

    restaurar = sub.add_parser("restaurar", help="restaura um backup em outro arquivo")
    restaurar.add_argument("arquivo")
    restaurar.add_argument("destino")
    restaurar.set_defaults(funcao=comando_restaurar)

    args = parser.parse_args()
    return int(args.funcao(args))


if __name__ == "__main__":
    raise SystemExit(main())
