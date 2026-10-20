"""Coleta a divisão territorial do IBGE: UFs, municípios e a malha do mapa.

Por que o IBGE entra no MVP mesmo não sendo fonte de saúde: o painel precisa de
um denominador comum. Toda notificação do SINAN traz o código do município
IBGE; sem essa tabela, não há como somar por estado nem desenhar o mapa.

A malha usada no mapa é a de qualidade **mínima** (≈100 KB), de propósito:
o painel é sobre números, não sobre fronteiras bonitas — e um arquivo grande
travaria o navegador de quem abre a página no celular.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src import config, db
from src.rede import ClienteHTTP

URL_UFS = "https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome"
URL_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
URL_MALHA_UF = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF"
)
URL_POPULACAO = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/9514/periodos/2022/variaveis/93"
    "?localidades=N3[all]"
)
URL_POPULACAO_MUNICIPIOS = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/9514/periodos/2022/variaveis/93"
    "?localidades=N6[all]"
)
ARQUIVO_MALHA = config.RAIZ / "frontend" / "data" / "br_uf.geojson"

FONTE_ID = "ibge_localidades"


def _uf_do_municipio(item: dict[str, Any]) -> dict[str, Any] | None:
    """Extrai a UF de um município, tolerando os dois formatos do IBGE.

    O IBGE às vezes devolve `microrregiao` e às vezes só `regiao-imediata`;
    Brasília e Fernando de Noronha são exemplos de estrutura irregular. Em
    vez de assumir um caminho fixo, procuramos a UF onde ela estiver.
    """
    for chave in ("microrregiao", "regiao-imediata"):
        bloco = item.get(chave) or {}
        while isinstance(bloco, dict) and bloco:
            if "UF" in bloco and isinstance(bloco["UF"], dict):
                return bloco["UF"]
            # Desce um nível: mesorregiao -> UF, regiao-intermediaria -> ...
            proximo = next(
                (v for v in bloco.values() if isinstance(v, dict)),
                None,
            )
            bloco = proximo if proximo != bloco else None
    return None


def normalizar_ufs(bruto: Any) -> list[dict[str, Any]]:
    """Transforma a resposta do IBGE em linhas da tabela `uf`."""
    linhas = []
    for item in bruto:
        linhas.append(
            {
                "sigla": item["sigla"],
                "nome": item["nome"],
                "codigo_ibge": str(item["id"]),
                "regiao": (item.get("regiao") or {}).get("nome"),
            }
        )
    return linhas


def normalizar_municipios(bruto: Any) -> list[dict[str, Any]]:
    """Transforma a resposta do IBGE em linhas da tabela `municipio`.

    Município sem UF identificável é descartado e contado por quem chama —
    melhor perder um caso raro do que gravar UF errada.
    """
    linhas = []
    for item in bruto:
        uf = _uf_do_municipio(item)
        if not uf:
            continue
        linhas.append(
            {
                "codigo_ibge": str(item["id"]),
                "nome": item["nome"],
                "uf": uf["sigla"],
            }
        )
    return linhas


def normalizar_populacao(bruto: Any) -> tuple[dict[str, int], int | None]:
    """Extrai população residente por código de UF do agregado 9514.

    A resposta do IBGE é aninhada (`resultados[0].series[]`); o código da
    localidade é o mesmo `codigo_ibge` da tabela `uf`.
    """
    populacao: dict[str, int] = {}
    ano: int | None = None
    for agregado in bruto or []:
        for resultado in agregado.get("resultados") or []:
            for serie in resultado.get("series") or []:
                localidade = serie.get("localidade") or {}
                valores = serie.get("serie") or {}
                for chave, valor in valores.items():
                    try:
                        populacao[str(localidade.get("id"))] = int(valor)
                        ano = int(chave)
                    except (TypeError, ValueError):
                        # "-" ou ".." significam "sem dado", não zero.
                        continue
    return populacao, ano


def coletar(
    cliente: ClienteHTTP | None = None,
) -> tuple[list[dict], list[dict], dict[str, int], int | None]:
    """Baixa UFs, municípios e população (UF e município); devolve normalizado."""
    cliente = cliente or ClienteHTTP()
    ufs = normalizar_ufs(cliente.obter_json(URL_UFS))
    bruto_municipios = cliente.obter_json(URL_MUNICIPIOS)
    municipios = normalizar_municipios(bruto_municipios)
    populacao_uf, ano = normalizar_populacao(cliente.obter_json(URL_POPULACAO))
    populacao_municipios, _ = normalizar_populacao(cliente.obter_json(URL_POPULACAO_MUNICIPIOS))
    for municipio in municipios:
        municipio["populacao"] = populacao_municipios.get(municipio["codigo_ibge"])
    # A população da UF deve ser a soma dos municípios; se divergir, fica a
    # oficial do agregado N3 — e o número usado é sempre o que está gravado.
    return ufs, municipios, populacao_uf, ano


def baixar_malha(cliente: ClienteHTTP | None = None) -> Path:
    """Guarda o GeoJSON das UFs para o mapa funcionar sem depender do IBGE."""
    cliente = cliente or ClienteHTTP()
    return cliente.baixar(URL_MALHA_UF, ARQUIVO_MALHA)


def gravar(
    ufs: list[dict],
    municipios: list[dict],
    populacao: dict[str, int] | None = None,
    populacao_ano: int | None = None,
    *,
    caminho: Path | None = None,
) -> dict[str, int]:
    """Grava UFs, municípios e população em uma única transação."""
    populacao = populacao or {}
    with db.transacao(caminho) as conexao:
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID,
            nome="Divisão territorial e população (UFs e municípios)",
            orgao="IBGE",
            url=URL_UFS,
            licenca="Dados abertos do IBGE",
            periodo_referencia=f"população {populacao_ano}" if populacao_ano else "vigente",
        )
        conexao.executemany(
            """
            INSERT INTO uf (sigla, nome, codigo_ibge, regiao, populacao, populacao_ano)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(sigla) DO UPDATE SET
                nome = excluded.nome,
                codigo_ibge = excluded.codigo_ibge,
                regiao = excluded.regiao,
                populacao = COALESCE(excluded.populacao, uf.populacao),
                populacao_ano = COALESCE(excluded.populacao_ano, uf.populacao_ano)
            """,
            [
                (
                    u["sigla"],
                    u["nome"],
                    u["codigo_ibge"],
                    u["regiao"],
                    populacao.get(u["codigo_ibge"]),
                    populacao_ano,
                )
                for u in ufs
            ],
        )
        conexao.executemany(
            """
            INSERT INTO municipio (codigo_ibge, nome, uf, populacao, populacao_ano)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(codigo_ibge) DO UPDATE SET
                nome = excluded.nome,
                uf = excluded.uf,
                populacao = COALESCE(excluded.populacao, municipio.populacao),
                populacao_ano = COALESCE(excluded.populacao_ano, municipio.populacao_ano)
            """,
            [
                (
                    m["codigo_ibge"],
                    m["nome"],
                    m["uf"],
                    m.get("populacao"),
                    populacao_ano,
                )
                for m in municipios
            ],
        )
        db.registrar_log(
            conexao,
            fonte_id=FONTE_ID,
            iniciado_em=db.agora_utc(),
            status="ok",
            registros=len(municipios),
            mensagem=f"{len(ufs)} UFs e {len(municipios)} municípios",
        )
        db.definir_meta(conexao, "ibge_coletado_em", db.agora_utc())
    return {"ufs": len(ufs), "municipios": len(municipios)}


def garantir(conexao: sqlite3.Connection) -> bool:
    """Diz se a divisão territorial já está carregada (evita baixar de novo)."""
    linha = conexao.execute("SELECT COUNT(*) AS total FROM municipio").fetchone()
    return bool(linha and linha["total"] > 0)
