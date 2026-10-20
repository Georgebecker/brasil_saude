"""Rotas do serviço climático: condições favoráveis a arboviroses."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.modelos import AlertaClima
from src.rotas.dependencias import obter_conexao
from src.rotas.epidemiologia import _validar_uf
from src.servicos import clima

roteador = APIRouter(prefix="/api", tags=["clima"])

Conexao = Annotated[sqlite3.Connection, Depends(obter_conexao)]


@roteador.get("/estados/{uf}/clima", response_model=list[AlertaClima])
def clima_do_estado(
    uf: str,
    conexao: Conexao,
    limite: int = Query(10, ge=1, le=50),
) -> list[dict]:
    """Municípios com maior incidência, com chuva dos últimos 7 dias ao lado.

    Se não houver caso municipal, cai para a lista de maior chuva — e a
    resposta deixa `casos`/`incidencia` nulos, o que a tela mostra como
    “incidência indisponível”, nunca como zero.
    """
    validada = _validar_uf(uf)
    por_incidencia = clima.alertas_por_incidencia(conexao, validada, limite=limite)
    if por_incidencia:
        return por_incidencia
    return clima.alertas(conexao, validada, limite=limite)
