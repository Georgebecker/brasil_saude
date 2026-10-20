"""Backup e restauração do SQLite, com prova de que a cópia abre.

Analogia: backup sem teste de restauração é como extintor nunca conferido —
está pendurado na parede, mas ninguém sabe se funciona no dia do incêndio.

Por que a API `backup()` do SQLite e não `copy.copy` do arquivo: o banco roda
em modo WAL, com escrita em um arquivo auxiliar. Copiar só o `.db` no meio de
uma escrita pode gerar um arquivo inconsistente. A API oficial tira um
"instantâneo" coerente.

O que é verificado em toda cópia:

1. `PRAGMA integrity_check` responde `ok`;
2. a contagem das tabelas principais pode ser lida;
3. o SHA-256 do arquivo é registrado no manifesto (prova de que a cópia de
   hoje é a mesma que foi testada amanhã).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

TABELAS_PROVA = ("fonte", "uf", "caso_semana", "repasse", "clima_dia")


def _sha256(caminho: Path) -> str:
    """Hash do arquivo em blocos: não carrega o banco inteiro na memória."""
    digesto = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digesto.update(bloco)
    return digesto.hexdigest()


def verificar(caminho: Path) -> dict:
    """Abre a cópia e responde: íntegra? quantas linhas em cada tabela?"""
    if not caminho.exists():
        raise FileNotFoundError(f"backup não encontrado: {caminho}")
    conexao = sqlite3.connect(caminho)
    try:
        try:
            integridade = conexao.execute("PRAGMA integrity_check").fetchone()[0]
        except sqlite3.DatabaseError as erro:
            integridade = f"erro: {erro}"
        contagens = {}
        for tabela in TABELAS_PROVA:
            try:
                contagens[tabela] = conexao.execute(
                    f"SELECT COUNT(*) FROM {tabela}"  # noqa: S608 - nome vem de tupla fixa
                ).fetchone()[0]
            except sqlite3.DatabaseError:
                contagens[tabela] = None
    finally:
        conexao.close()

    return {
        "integridade": integridade,
        "contagens": contagens,
        "bytes": caminho.stat().st_size,
        "sha256": _sha256(caminho),
    }


def criar(origem: Path, pasta_destino: Path, *, retencao: int = 7) -> dict:
    """Cria um backup datado, confere a cópia e aplica a retenção."""
    if not origem.exists():
        raise FileNotFoundError(f"banco de origem não existe: {origem}")

    pasta_destino.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = pasta_destino / f"brasil_saude_{carimbo}.db"

    origem_conexao = sqlite3.connect(origem)
    destino_conexao = sqlite3.connect(destino)
    try:
        origem_conexao.backup(destino_conexao)
    finally:
        destino_conexao.close()
        origem_conexao.close()

    prova = verificar(destino)
    if prova["integridade"] != "ok":
        destino.unlink(missing_ok=True)
        raise RuntimeError(f"backup corrompido (integrity_check = {prova['integridade']})")

    registro = {
        "arquivo": destino.name,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "origem": str(origem),
        **prova,
    }
    _registrar_no_manifesto(pasta_destino, registro)
    removidos = _aplicar_retencao(pasta_destino, retencao)
    registro["removidos_por_retencao"] = removidos
    return registro


def _registrar_no_manifesto(pasta: Path, registro: dict) -> None:
    """Mantém um histórico legível das cópias — inclusive das já removidas."""
    manifesto = pasta / "manifesto.json"
    historico = json.loads(manifesto.read_text(encoding="utf-8")) if manifesto.exists() else []
    historico.append(registro)
    manifesto.write_text(
        json.dumps(historico[-100:], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _aplicar_retencao(pasta: Path, retencao: int) -> list[str]:
    """Apaga as cópias mais antigas, preservando as `retencao` mais recentes."""
    if retencao <= 0:
        return []
    copias = sorted(pasta.glob("brasil_saude_*.db"))
    excedentes = copias[:-retencao] if len(copias) > retencao else []
    for caminho in excedentes:
        caminho.unlink()
    return [caminho.name for caminho in excedentes]


def restaurar(backup: Path, destino: Path) -> dict:
    """Restaura a cópia em `destino` e prova que o banco restaurado abre.

    A verificação acontece **depois** da restauração, no arquivo de destino:
    é a diferença entre confiar no backup e saber que ele volta a funcionar.
    """
    prova_origem = verificar(backup)
    if prova_origem["integridade"] != "ok":
        raise RuntimeError(f"backup inválido: {backup.name}")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(backup.read_bytes())
    prova_destino = verificar(destino)
    if prova_destino["contagens"] != prova_origem["contagens"]:
        raise RuntimeError("restauração divergente: contagens diferentes do backup")

    return {
        "restaurado_em": str(destino),
        "origem": str(backup),
        **prova_destino,
    }
