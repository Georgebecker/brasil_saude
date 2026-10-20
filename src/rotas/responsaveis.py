"""Rotas de responsabilização: quem responde pela saúde no estado.

O painel não julga gestor nem partido. Ele apenas liga o número ao cargo que a
lei atribui àquela decisão, com link para a fonte pública onde o nome foi
verificado.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from src.modelos import Responsavel
from src.rotas.dependencias import obter_conexao
from src.rotas.epidemiologia import _validar_uf

roteador = APIRouter(prefix="/api", tags=["responsabilizacao"])

Conexao = Annotated[sqlite3.Connection, Depends(obter_conexao)]


@roteador.get("/estados/{uf}/responsaveis", response_model=list[Responsavel])
def responsaveis_do_estado(uf: str, conexao: Conexao) -> list[dict]:
    """Governador e secretário estadual de saúde, com a URL da fonte."""
    linhas = conexao.execute(
        "SELECT uf, cargo, nome, url_fonte, atualizado_em FROM responsavel "
        "WHERE uf = ? ORDER BY cargo",
        (_validar_uf(uf),),
    ).fetchall()
    return [dict(linha) for linha in linhas]
