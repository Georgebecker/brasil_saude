"""Rotas de proveniência e de diagnóstico do painel.

"Fontes e Metodologia" não é enfeite: é o critério 6 do contrato. A rota
`/api/fontes` devolve exatamente o que está gravado na tabela `fonte`, com a
data de coleta — sem texto inventado no frontend.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from src.modelos import FonteInfo, Saude
from src.rotas.dependencias import obter_conexao
from src.servicos import epidemiologia

roteador = APIRouter(prefix="/api", tags=["proveniencia"])

Conexao = Annotated[sqlite3.Connection, Depends(obter_conexao)]


@roteador.get("/fontes", response_model=list[FonteInfo])
def listar_fontes(conexao: Conexao) -> list[dict]:
    """Todas as fontes já coletadas, com órgão, URL, licença e data."""
    linhas = conexao.execute("SELECT * FROM fonte ORDER BY nome").fetchall()
    return [dict(linha) for linha in linhas]


@roteador.get("/saude", response_model=Saude)
def saude(conexao: Conexao) -> dict:
    """Diagnóstico rápido: o painel tem dado? até quando? alguma fonte falhou?"""

    def contar(tabela: str) -> int:
        return int(conexao.execute(f"SELECT COUNT(*) AS total FROM {tabela}").fetchone()["total"])

    semana = epidemiologia.ultima_semana(conexao)
    fontes_ok = conexao.execute(
        "SELECT COUNT(*) AS total FROM fonte WHERE status = 'ok'"
    ).fetchone()["total"]
    fontes_ruins = conexao.execute(
        "SELECT COUNT(*) AS total FROM fonte WHERE status = 'falhou'"
    ).fetchone()["total"]

    return {
        "status": "ok" if contar("caso_semana") else "sem_dados",
        "banco": str(conexao.execute("PRAGMA database_list").fetchone()["file"]),
        "ufs": contar("uf"),
        "municipios": contar("municipio"),
        "casos": contar("caso_semana"),
        "repasses": contar("repasse"),
        "clima": contar("clima_dia"),
        "ultima_semana": f"{semana[0]}-SE{semana[1]:02d}" if semana else None,
        "fontes_ok": int(fontes_ok),
        "fontes_com_problema": int(fontes_ruins),
    }


@roteador.get("/meta")
def metas(conexao: Conexao) -> dict[str, str]:
    """Pares chave/valor de operação (última coleta etc.), sem dado sensível."""
    linhas = conexao.execute("SELECT chave, valor FROM meta ORDER BY chave").fetchall()
    return {linha["chave"]: linha["valor"] for linha in linhas}


@roteador.get("/log-coletas")
def log_coletas(conexao: Conexao, limite: int = 20) -> list[dict]:
    """Histórico de execuções de coleta — a "caixa-preta" do ETL."""
    linhas = conexao.execute(
        "SELECT * FROM log_coleta ORDER BY id DESC LIMIT ?", (max(1, min(limite, 100)),)
    ).fetchall()
    return [dict(linha) for linha in linhas]
