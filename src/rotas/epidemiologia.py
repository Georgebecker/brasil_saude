"""Rotas do serviço epidemiológico: mapa, série e EARS."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from src.modelos import SerieUF, SituacaoUF
from src.rotas.dependencias import obter_conexao
from src.servicos import epidemiologia

roteador = APIRouter(prefix="/api", tags=["epidemiologia"])

Conexao = Annotated[sqlite3.Connection, Depends(obter_conexao)]

UF_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}  # fmt: skip


def _validar_uf(uf: str) -> str:
    """Normaliza e recusa UF inexistente com 422 — em vez de devolver lista vazia."""
    normalizada = uf.upper()
    if normalizada not in UF_VALIDAS:
        raise HTTPException(status_code=422, detail=f"UF inválida: {uf}")
    return normalizada


@roteador.get("/estados", response_model=list[SituacaoUF])
def listar_estados(
    conexao: Conexao,
    metodo: str = Query("C1", pattern="^C[12]$", description="Variante do EARS"),
) -> list[dict]:
    """Situação da última semana disponível, uma linha por UF (alimenta o mapa)."""
    return epidemiologia.situacao_por_uf(conexao, variante=metodo)


@roteador.get("/estados/{uf}", response_model=SerieUF)
def serie_do_estado(
    uf: str,
    conexao: Conexao,
    metodo: str = Query("C1", pattern="^C[12]$", description="Variante do EARS"),
) -> dict:
    """Série histórica da UF com a faixa esperada do EARS."""
    return epidemiologia.serie_da_uf(conexao, _validar_uf(uf), variante=metodo)


@roteador.get("/estados/{uf}/alertas", response_model=list[dict])
def alertas_do_estado(conexao: Conexao, uf: str) -> list[dict]:
    """Semanas em que o EARS sinalizou anomalia — para a lista lateral."""
    series = epidemiologia.serie_da_uf(conexao, _validar_uf(uf))
    return [ponto for ponto in series["semanas"] if ponto.get("anomalo")]
