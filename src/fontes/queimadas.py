"""Focos de queimada do INPE (satélite de referência).

Descoberta desta sessão: **não existe token pago nem autenticação obrigatória.**
O antigo `queimadas.dgi.inpe.br/api/focos` foi aposentado e hoje devolve a página
do portal (HTML), não JSON. O caminho aberto e estável é o servidor de
transferência do INPE, que publica um ZIP por ano com todos os focos do Brasil:

    https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_sat_ref/focos_br_ref{ano}.zip

Cada linha é um foco detectado, com data, município, estado e bioma. O painel
não publica o ponto no mapa (seria precisão que não temos como defender); agrega
por estado e por mês, que é o recorte usado para comparar com doença respiratória.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections import Counter
from pathlib import Path

from src import db
from src.rede import ClienteHTTP, FalhaDeRede

FONTE_ID = "inpe_queimadas"
BASE = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_sat_ref/"
PASTA_RAW = Path("data/raw/queimadas")

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]  # fmt: skip

# O CSV traz o nome do estado por extenso e em maiúsculas; o banco usa a sigla.
UF_POR_NOME = {
    "ACRE": "AC",
    "ALAGOAS": "AL",
    "AMAPÁ": "AP",
    "AMAZONAS": "AM",
    "BAHIA": "BA",
    "CEARÁ": "CE",
    "DISTRITO FEDERAL": "DF",
    "ESPÍRITO SANTO": "ES",
    "GOIÁS": "GO",
    "MARANHÃO": "MA",
    "MATO GROSSO": "MT",
    "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG",
    "PARÁ": "PA",
    "PARAÍBA": "PB",
    "PARANÁ": "PR",
    "PERNAMBUCO": "PE",
    "PIAUÍ": "PI",
    "RIO DE JANEIRO": "RJ",
    "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS",
    "RONDÔNIA": "RO",
    "RORAIMA": "RR",
    "SANTA CATARINA": "SC",
    "SÃO PAULO": "SP",
    "SERGIPE": "SE",
    "TOCANTINS": "TO",
}


def url_do_ano(ano: int) -> str:
    return f"{BASE}focos_br_ref_{ano}.zip"


def baixar_ano(ano: int, *, cliente: ClienteHTTP | None = None, pasta: Path = PASTA_RAW) -> Path:
    """Baixa o ZIP do ano para o disco (reaproveita o arquivo, se já existir)."""
    cliente = cliente or ClienteHTTP(tentativas=2, tempo_limite=180)
    destino = pasta / f"focos_br_ref_{ano}.zip"
    return cliente.baixar(url_do_ano(ano), destino)


def processar(arquivo: Path, ano: int) -> list[dict]:
    """Agrega os focos do ZIP por (UF, mês). Linha sem UF válida é descartada."""
    contagem: Counter[tuple[str, int]] = Counter()

    with zipfile.ZipFile(arquivo) as pacote:
        nomes = [nome for nome in pacote.namelist() if nome.lower().endswith(".csv")]
        if not nomes:
            raise FalhaDeRede(f"{arquivo.name} não tem CSV dentro")
        with pacote.open(nomes[0]) as bruto:
            # O arquivo é UTF-8 (o "Ã" no nome do município é sinal de leitura
            # errada em Latin-1, não de dado corrompido na origem).
            leitor = csv.DictReader(io.TextIOWrapper(bruto, encoding="utf-8"))
            for linha in leitor:
                uf = UF_POR_NOME.get((linha.get("estado") or "").strip().upper())
                data = (linha.get("data_pas") or "")[:10]
                if not uf or len(data) < 7:
                    continue
                contagem[(uf, int(data[5:7]))] += 1

    return [
        {"uf": uf, "ano": ano, "mes": mes, "focos": focos}
        for (uf, mes), focos in sorted(contagem.items())
    ]


def gravar(
    linhas: list[dict],
    *,
    ano: int,
    caminho: Path | None = None,
    detalhe: str | None = None,
) -> int:
    """Grava no SQLite, substituindo o ano inteiro (coleta idempotente)."""
    conexao = db.conectar(caminho)
    try:
        db.inicializar(conexao)
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID,
            nome="Focos de queimada (satélite de referência)",
            orgao="INPE — Programa Queimadas",
            url=BASE,
            periodo_referencia=str(ano),
            detalhe=detalhe,
        )
        conexao.execute("DELETE FROM queimada_uf_mes WHERE ano = ?", (ano,))
        registros = [
            (linha["uf"], linha["ano"], linha["mes"], linha["focos"], FONTE_ID)
            for linha in linhas
        ]
        conexao.executemany(
            "INSERT INTO queimada_uf_mes (uf, ano, mes, focos, fonte_id) VALUES (?, ?, ?, ?, ?)",
            registros,
        )
        total = sum(linha["focos"] for linha in linhas)
        db.definir_meta(conexao, f"queimadas_{ano}_total", str(total))
        conexao.commit()
        return len(linhas)
    finally:
        conexao.close()


def coletar(anos: list[int], *, caminho_banco: Path | None = None) -> dict:
    """Baixa, agrega e grava cada ano. Falha de um ano não derruba os outros."""
    resultado: dict[str, object] = {}
    for ano in anos:
        try:
            arquivo = baixar_ano(ano)
            linhas = processar(arquivo, ano)
            total = sum(linha["focos"] for linha in linhas)
            gravadas = gravar(
                linhas, ano=ano, caminho=caminho_banco, detalhe=f"{total} focos"
            )
            resultado[str(ano)] = {"meses_uf": gravadas, "focos": total}
        except (FalhaDeRede, zipfile.BadZipFile, OSError) as erro:
            resultado[str(ano)] = f"falhou: {erro}"
    return resultado


def resumo(conexao, ano: int) -> dict:
    """Totais do ano por UF e por mês, com o nome do mês em português."""
    por_uf = conexao.execute(
        "SELECT uf, SUM(focos) AS focos FROM queimada_uf_mes WHERE ano = ? "
        "GROUP BY uf ORDER BY focos DESC",
        (ano,),
    ).fetchall()
    por_mes = conexao.execute(
        "SELECT mes, SUM(focos) AS focos FROM queimada_uf_mes WHERE ano = ? "
        "GROUP BY mes ORDER BY mes",
        (ano,),
    ).fetchall()
    total = sum(linha["focos"] for linha in por_uf)
    return {
        "ano": ano,
        "total": total,
        "ufs": [dict(linha) for linha in por_uf],
        "meses": [{"mes": linha["mes"], "nome": MESES[linha["mes"] - 1], "focos": linha["focos"]}
                  for linha in por_mes],
        "fonte": BASE,
    }
