"""Rotas do serviço orçamentário: repasses federais por UF."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.modelos import ResumoOrcamento
from src.rotas.dependencias import obter_conexao
from src.rotas.epidemiologia import _validar_uf
from src.servicos import orcamento

roteador = APIRouter(prefix="/api", tags=["orcamento"])

Conexao = Annotated[sqlite3.Connection, Depends(obter_conexao)]


@roteador.get("/estados/{uf}/repasses", response_model=ResumoOrcamento)
def repasses_do_estado(
    uf: str,
    conexao: Conexao,
    limite: int = Query(12, ge=1, le=100, description="Quantos repasses listar"),
) -> dict:
    """Total e últimos repasses federais de saúde para a UF."""
    return orcamento.resumo(conexao, _validar_uf(uf), limite=limite)


@roteador.get("/estados/{uf}/repasses/mensal", response_model=list[dict])
def repasses_mensais(uf: str, conexao: Conexao) -> list[dict]:
    """Soma mensal dos repasses, para o gráfico ao lado da série de casos."""
    return orcamento.serie_mensal(conexao, _validar_uf(uf))
