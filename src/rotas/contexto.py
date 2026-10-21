"""Rotas do contexto político: quem governava no período dos dados."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.servicos import contexto

roteador = APIRouter(prefix="/api", tags=["contexto"])

UF_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}  # fmt: skip


@roteador.get("/contexto")
def contexto_nacional() -> dict:
    """Presidente, ministros da Saúde e governadores do período curado."""
    return contexto.nacional()


@roteador.get("/estados/{uf}/contexto")
def contexto_do_estado(uf: str) -> dict:
    """Contexto político do estado: governador, presidente e ministros."""
    sigla = uf.upper()
    if sigla not in UF_VALIDAS:
        raise HTTPException(status_code=422, detail=f"UF inválida: {uf}")
    return contexto.para_uf(sigla)
