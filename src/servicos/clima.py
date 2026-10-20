"""Serviço climático: condições favoráveis a arboviroses, por município.

A pergunta da tela é específica: **onde a doença está mais intensa e como está
o tempo lá?** Por isso a lista é ordenada por incidência (casos por 100 mil
habitantes), não por volume de chuva. A chuva entra como contexto — e, quando
não há caso municipal, a lista cai para “maior chuva” em vez de ficar vazia.

Regra operacional do painel (não é recomendação sanitária):

- **alto**: 100 mm ou mais de chuva acumulada em 7 dias;
- **atenção**: 50 mm ou mais em 7 dias;
- **baixo**: abaixo disso.

O *Aedes aegypti* se reproduz em água parada; chuva intensa aumenta os
criadouros. A frase final é sempre “condição favorável”, nunca “surto
previsto”: previsão de epidemia exige modelo entomológico e vigilância local.
"""

from __future__ import annotations

import sqlite3

LIMIAR_ATENCAO_MM = 50.0
LIMIAR_ALTO_MM = 100.0
DIAS_JANELA = 7


def _nivel(chuva: float | None) -> tuple[str, str]:
    """Classifica a chuva acumulada e devolve (nível, explicação)."""
    if chuva is None:
        return "sem_dado", "Sem medição de chuva para este município no período."
    if chuva >= LIMIAR_ALTO_MM:
        return "alto", (
            f"{chuva:.1f} mm em {DIAS_JANELA} dias: condição favorável à proliferação "
            "do mosquito. Não é previsão de surto."
        )
    if chuva >= LIMIAR_ATENCAO_MM:
        return "atencao", (
            f"{chuva:.1f} mm em {DIAS_JANELA} dias: atenção para recipientes com água parada."
        )
    return "baixo", f"{chuva:.1f} mm em {DIAS_JANELA} dias: chuva abaixo do limiar de atenção."


def chuva_por_municipio(conexao: sqlite3.Connection, uf: str) -> dict[str, dict]:
    """Chuva acumulada e temperatura média dos últimos 7 dias por município.

    A janela é ancorada na **última data medida** (não em “hoje”): se a fonte
    atrasou, o painel mostra o período real, não um buraco de zeros.
    """
    linhas = conexao.execute(
        """
        WITH referencia AS (
            SELECT MAX(data) AS data_max FROM clima_dia WHERE uf = ?
        )
        SELECT c.municipio_codigo,
               SUM(c.precipitacao_mm) AS chuva,
               AVG(CASE WHEN c.temp_max_c IS NOT NULL AND c.temp_min_c IS NOT NULL
                        THEN (c.temp_max_c + c.temp_min_c) / 2.0
                        WHEN c.temp_max_c IS NOT NULL THEN c.temp_max_c
                        WHEN c.temp_min_c IS NOT NULL THEN c.temp_min_c
                   END) AS temp_media,
               MAX(c.data) AS data_referencia,
               MIN(c.estacao) AS estacao
        FROM clima_dia c, referencia r
        WHERE c.uf = ? AND c.municipio_codigo IS NOT NULL
          AND c.data > date(r.data_max, ?)
        GROUP BY c.municipio_codigo
        HAVING COUNT(CASE WHEN c.precipitacao_mm IS NOT NULL THEN 1 END) > 0
        """,
        (uf.upper(), uf.upper(), f"-{DIAS_JANELA} days"),
    ).fetchall()
    return {
        linha["municipio_codigo"]: {
            "chuva": linha["chuva"],
            "temp_media": linha["temp_media"],
            "data_referencia": linha["data_referencia"],
            "estacao": linha["estacao"],
        }
        for linha in linhas
    }


def _alerta(
    municipio: str, codigo: str, uf: str, casos: int, incidencia: float, clima: dict
) -> dict:
    """Monta um alerta completo (epidemiologia + clima) para a interface."""
    chuva = clima.get("chuva")
    nivel, explicacao = _nivel(chuva)
    return {
        "municipio_codigo": codigo,
        "municipio": municipio,
        "uf": uf,
        "casos": casos,
        "incidencia": round(incidencia, 1),
        "chuva_7d_mm": round(chuva, 1) if chuva is not None else None,
        "temp_media_c": (
            round(clima["temp_media"], 1) if clima.get("temp_media") is not None else None
        ),
        "nivel": nivel,
        "explicacao": explicacao,
        "estacao": clima.get("estacao") or "—",
        "data_referencia": clima.get("data_referencia") or "—",
        "url_fonte": "https://portal.inmet.gov.br/",
    }


def alertas_por_incidencia(conexao: sqlite3.Connection, uf: str, *, limite: int = 8) -> list[dict]:
    """Municípios com maior incidência na última semana, com o clima ao lado.

    Só entram municípios com população conhecida e com estação meteorológica
    mapeada. Preferimos uma lista menor e verdadeira a uma lista completa com
    incidência inventada.
    """
    uf = uf.upper()
    semana = conexao.execute(
        "SELECT MAX(cm.ano * 100 + cm.semana) AS chave "
        "FROM caso_municipio_semana cm JOIN municipio m ON m.codigo_ibge = cm.municipio_codigo "
        "WHERE m.uf = ?",
        (uf,),
    ).fetchone()
    if not semana or semana["chave"] is None:
        return []

    chave = int(semana["chave"])
    ano, numero = chave // 100, chave % 100
    casos_por_municipio = conexao.execute(
        """
        SELECT cm.municipio_codigo, m.nome, m.populacao, cm.casos
        FROM caso_municipio_semana cm
        JOIN municipio m ON m.codigo_ibge = cm.municipio_codigo
        WHERE m.uf = ? AND cm.ano = ? AND cm.semana = ? AND m.populacao > 0
        """,
        (uf, ano, numero),
    ).fetchall()

    chuva = chuva_por_municipio(conexao, uf)
    alertas = []
    for linha in casos_por_municipio:
        dados_clima = chuva.get(linha["municipio_codigo"])
        if not dados_clima:
            continue
        incidencia = linha["casos"] / linha["populacao"] * 100_000
        alertas.append(
            _alerta(
                linha["nome"],
                linha["municipio_codigo"],
                uf,
                int(linha["casos"]),
                incidencia,
                dados_clima,
            )
        )

    alertas.sort(key=lambda item: item["incidencia"], reverse=True)
    return alertas[:limite]


def alertas(conexao: sqlite3.Connection, uf: str, *, limite: int = 10) -> list[dict]:
    """Fallback: municípios com maior chuva quando não há caso municipal.

    Usado quando a fonte epidemiológica não entregou granularidade municipal —
    o painel mostra chuva (dado que existe) e avisa que a incidência não está
    disponível, em vez de esconder a seção.
    """
    uf = uf.upper()
    chuva = chuva_por_municipio(conexao, uf)
    if not chuva:
        return []

    nomes = {
        linha["codigo_ibge"]: linha["nome"]
        for linha in conexao.execute("SELECT codigo_ibge, nome FROM municipio WHERE uf = ?", (uf,))
    }
    linhas = []
    for codigo, dados in chuva.items():
        nivel, explicacao = _nivel(dados["chuva"])
        linhas.append(
            {
                "municipio_codigo": codigo,
                "municipio": nomes.get(codigo, "município não identificado"),
                "uf": uf,
                "casos": None,
                "incidencia": None,
                "chuva_7d_mm": (
                    round(dados["chuva"], 1) if dados["chuva"] is not None else None
                ),
                "temp_media_c": (
                    round(dados["temp_media"], 1) if dados["temp_media"] is not None else None
                ),
                "nivel": nivel,
                "explicacao": explicacao,
                "estacao": dados["estacao"],
                "data_referencia": dados["data_referencia"],
                "url_fonte": "https://portal.inmet.gov.br/",
            }
        )
    linhas.sort(key=lambda item: (item["chuva_7d_mm"] or 0), reverse=True)
    return linhas[:limite]
