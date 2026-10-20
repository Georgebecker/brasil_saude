"""Dependências compartilhadas pelas rotas: conexão por requisição.

Abrir e fechar a conexão a cada requisição é o jeito mais simples de não
vazar recurso. SQLite é rápido para isso; o custo de abrir um arquivo local é
irrelevante comparado ao de manter estado global compartilhado entre threads.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from src import db


def obter_conexao(request: Request) -> Iterator[sqlite3.Connection]:
    """Entrega uma conexão com o banco configurado no app e fecha no final."""
    conexao = db.conectar(request.app.state.caminho_banco)
    try:
        yield conexao
    finally:
        conexao.close()
