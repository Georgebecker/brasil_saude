"""Serviço orçamentário: repasses federais de saúde por UF.

O painel **não afirma causalidade**. Ele mostra, lado a lado, o que a
epidemiologia registrou e o que o orçamento pagou. A frase que aparece na tela
é deliberadamente seca: "repasses no período", não "investimento insuficiente".

Por que isso importa: cruzar duas séries é fácil; sugerir que uma causou a
outra sem estudo adequado seria desonesto — e o contrato do projeto proíbe.
"""

from __future__ import annotations

import sqlite3

AVISO = (
    "Os repasses são mostrados ao lado dos casos, sem afirmação de causalidade. "
    "Valores e datas vêm da fonte indicada; mudanças de critério ou de empenho "
    "podem alterar a série sem relação com a doença."
)


def resumo(conexao: sqlite3.Connection, uf: str, *, limite: int = 12) -> dict:
    """Total do período e os últimos repasses da UF, do mais recente ao antigo."""
    uf = uf.upper()
    linhas = conexao.execute(
        """
        SELECT id, data, valor, descricao, url_fonte
        FROM repasse
        WHERE uf = ?
        ORDER BY data DESC, id DESC
        LIMIT ?
        """,
        (uf, limite),
    ).fetchall()

    agregado = conexao.execute(
        "SELECT SUM(valor) AS total, COUNT(*) AS quantidade, MIN(data) AS inicio, "
        "MAX(data) AS fim FROM repasse WHERE uf = ?",
        (uf,),
    ).fetchone()

    total = float(agregado["total"] or 0.0)
    quantidade = int(agregado["quantidade"] or 0)
    periodo = None
    if quantidade and agregado["inicio"]:
        periodo = f"{agregado['inicio']} a {agregado['fim']}"

    return {
        "uf": uf,
        "disponivel": quantidade > 0,
        "total": total,
        "quantidade": quantidade,
        "periodo": periodo,
        "repasses": [dict(linha) for linha in linhas],
        "aviso_metodologico": AVISO,
    }


def serie_mensal(conexao: sqlite3.Connection, uf: str) -> list[dict]:
    """Soma por mês (AAAA-MM), para o gráfico de barras ao lado da dengue."""
    linhas = conexao.execute(
        """
        SELECT substr(data, 1, 7) AS mes, SUM(valor) AS valor, COUNT(*) AS quantidade
        FROM repasse
        WHERE uf = ?
        GROUP BY mes
        ORDER BY mes
        """,
        (uf.upper(),),
    ).fetchall()
    return [dict(linha) for linha in linhas]
