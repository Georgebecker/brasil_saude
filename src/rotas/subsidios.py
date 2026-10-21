"""Rotas de subsídios federais e do resumo nacional do painel."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.rotas.dependencias import obter_conexao
from src.servicos import epidemiologia, subsidios

roteador = APIRouter(prefix="/api", tags=["subsidios"])

Conexao = Annotated[sqlite3.Connection, Depends(obter_conexao)]


@roteador.get("/subsidios")
def subsidios_do_ano(
    conexao: Conexao,
    ano: int = Query(2026, ge=2000, le=2100, description="Ano dos programas e propostas"),
) -> dict:
    """Oferta de programas e aproveitamento por UF no ano."""
    return subsidios.resumo(conexao, ano)


@roteador.get("/resumo")
def resumo_nacional(conexao: Conexao) -> dict:
    """Números do topo da página: casos da semana, anomalias e repasses."""
    situacao = epidemiologia.situacao_por_uf(conexao)
    semana = epidemiologia.ultima_semana(conexao)

    casos = sum(linha["casos"] or 0 for linha in situacao)
    com_dado = sum(1 for linha in situacao if linha["disponivel"])
    anomalias = sum(1 for linha in situacao if linha["anomalo"])

    repasses = conexao.execute("SELECT SUM(valor) AS total FROM repasse").fetchone()
    estacoes = conexao.execute(
        "SELECT COUNT(DISTINCT estacao) AS total FROM clima_dia"
    ).fetchone()
    fontes = conexao.execute(
        "SELECT SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok, COUNT(*) AS total FROM fonte"
    ).fetchone()

    # Anomalias de uma única semana enganam: em semana de baixa transmissão o
    # número é zero e parece que o alerta nunca funcionou. A janela de 12
    # semanas mostra o método em ação sem esconder a semana atual.
    janela = conexao.execute(
        "SELECT DISTINCT ano, semana FROM caso_semana ORDER BY ano DESC, semana DESC LIMIT 12"
    ).fetchall()
    chaves = {(linha["ano"], linha["semana"]) for linha in janela}
    anomalias_12 = 0
    if chaves:
        marcados = conexao.execute(
            "SELECT uf, ano, semana FROM alerta_ears WHERE metodo = 'C1' AND anomalo = 1"
        ).fetchall()
        anomalias_12 = len(
            {linha["uf"] for linha in marcados if (linha["ano"], linha["semana"]) in chaves}
        )

    return {
        "casos_semana": casos,
        "ufs_com_dado": com_dado,
        "ufs_total": len(situacao),
        "ufs_anomalia": anomalias,
        "ufs_anomalia_12s": anomalias_12,
        "ano": semana[0] if semana else None,
        "semana": semana[1] if semana else None,
        "repasses_total": round(float(repasses["total"] or 0.0), 2),
        "estacoes": int(estacoes["total"] or 0),
        "fontes_ok": int(fontes["ok"] or 0),
        "fontes_total": int(fontes["total"] or 0),
    }
