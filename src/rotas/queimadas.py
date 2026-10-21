"""Rotas de focos de queimada.

A agregação mora em `src/fontes/queimadas.py` porque ela nasce junto do parser
do arquivo do INPE; a rota só aplica o recorte de ano e devolve JSON.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.fontes import queimadas
from src.rotas.dependencias import obter_conexao

roteador = APIRouter(prefix="/api", tags=["queimadas"])

Conexao = Annotated[sqlite3.Connection, Depends(obter_conexao)]


@roteador.get("/queimadas")
def queimadas_do_ano(
    conexao: Conexao,
    ano: int = Query(2025, ge=2000, le=2100, description="Ano dos focos"),
) -> dict:
    """Focos por estado e por mês no ano pedido."""
    return queimadas.resumo(conexao, ano)
