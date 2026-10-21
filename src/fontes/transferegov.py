"""Subsídios federais: oferta de programas e aproveitamento por estado.

Fonte: **API Pública do Transferegov** (Ministério da Gestão e da Inovação).
O host antigo (`api.transferegov.gestao.gov.br`) foi desativado em julho de
2026; o novo é `api-publica.transferegov.gestao.gov.br`, aberto, sem token.

O que este módulo mede — e o que ele **não** mede:

- **Oferta:** programas de 2026 disponibilizados pelo Ministério da Saúde e
  pelo Ministério das Cidades (habitação, mobilidade, saneamento).
- **Aproveitamento:** propostas apresentadas pelos entes por UF, quantas foram
  aprovadas e quanto foi planejado/repactuado.
- **Não mede** execução física nem se o recurso chegou ao cidadão. Proposta
  aprovada ≠ obra entregue. A tela diz isso.

Dois eixos, porque são sistemas diferentes:

1. ``saude_fundo_a_fundo`` — parcerias do SUS (``/parcerias/proposta``), valor
   em ``vl_total_planejamento_gastos``;
2. ``cidades_discricionaria`` — transferências discricionárias do Ministério
   das Cidades (``/discricionarias/propostas``), valor em ``vl_repasse_prop``.
"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from src import db
from src.dados.capitais import CAPITAIS
from src.rede import ClienteHTTP, FalhaDeRede

URL_BASE = "https://api-publica.transferegov.gestao.gov.br"
FONTE_ID = "transferegov_subsidios"
EIXO_SAUDE = "saude_fundo_a_fundo"
EIXO_CIDADES = "cidades_discricionaria"
ORGAOS = ("MINISTERIO DA SAUDE", "MINISTERIO DAS CIDADES")
TAMANHO_PAGINA = 200
MAX_PAGINAS_UF = 40


def _numero(valor: Any) -> float:
    """Converte '850093.0', 850093 ou None em float — sem inventar zero falso.

    A API mistura string e número. Campo ausente vira 0 **apenas** para soma,
    e a contagem de propostas continua sendo a prova de que houve registro.
    """
    if valor in (None, ""):
        return 0.0
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return 0.0


def obter_paginado(
    cliente: ClienteHTTP,
    caminho: str,
    params: dict,
    *,
    max_paginas: int = MAX_PAGINAS_UF,
) -> tuple[list[dict], bool]:
    """Percorre as páginas até o fim (ou até o teto). Devolve (dados, completo)."""
    dados: list[dict] = []
    pagina = 1
    while pagina <= max_paginas:
        consulta = {**params, "pagina": pagina, "tamanho_da_pagina": TAMANHO_PAGINA}
        resposta = cliente.obter(URL_BASE + caminho, params=consulta).json()
        if not isinstance(resposta, dict) or "data" not in resposta:
            break
        lote = resposta.get("data") or []
        dados.extend(lote)
        total_paginas = int(resposta.get("total_pages") or 1)
        if pagina >= total_paginas or not lote:
            return dados, True
        pagina += 1
    return dados, False


def coletar_programas(cliente: ClienteHTTP, ano: int) -> list[dict]:
    """Programas disponibilizados no ano, para Saúde e Cidades."""
    programas: dict[int, dict] = {}
    for orgao in ORGAOS:
        itens, _ = obter_paginado(
            cliente,
            "/discricionarias/todos-programas",
            {"ano_programa": ano, "desc_orgao_sup_programa": orgao},
            max_paginas=20,
        )
        for item in itens:
            chave = int(item.get("id_programa") or 0)
            if not chave:
                continue
            programas[chave] = {
                "id_programa": chave,
                "orgao": item.get("desc_orgao_sup_programa") or orgao,
                "nome": item.get("nome_programa") or "programa sem nome",
                "situacao": item.get("sit_programa"),
                "modalidade": item.get("modalidade_programa"),
                "data_disponibilizacao": item.get("data_disponibilizacao"),
                "inicio_recebimento": item.get("dt_prog_ini_receb_prop"),
                "fim_recebimento": item.get("dt_prog_fim_receb_prop"),
            }
    return sorted(programas.values(), key=lambda p: (p["orgao"], p["nome"]))


def _resumir_saude(itens: list[dict]) -> dict:
    """Agrega propostas de parceria (fundo a fundo) de uma UF."""
    aprovadas = sum(
        1 for item in itens if str(item.get("situacao_proposta") or "").lower().startswith("aprov")
    )
    return {
        "propostas": len(itens),
        "aprovadas": aprovadas,
        "valor_planejado": sum(_numero(item.get("vl_total_planejamento_gastos")) for item in itens),
        "valor_repasse": 0.0,
        "programas": len({item.get("id_programa") for item in itens if item.get("id_programa")}),
    }


def _resumir_cidades(itens: list[dict]) -> dict:
    """Agrega propostas discricionárias do Ministério das Cidades de uma UF."""
    aprovadas = sum(
        1 for item in itens if "aprovad" in str(item.get("sit_proposta") or "").lower()
    )
    return {
        "propostas": len(itens),
        "aprovadas": aprovadas,
        "valor_planejado": sum(_numero(item.get("vl_global_prop")) for item in itens),
        "valor_repasse": sum(_numero(item.get("vl_repasse_prop")) for item in itens),
        "programas": 0,
    }


def coletar_uf(cliente: ClienteHTTP, uf: str, ano: int) -> dict[str, dict]:
    """Coleta os dois eixos de uma UF; falha de um não apaga o outro."""
    resultado: dict[str, dict] = {}

    try:
        itens, completo = obter_paginado(
            cliente, "/parcerias/proposta", {"sg_uf_recebedor": uf, "ano_proposta": ano}
        )
        resultado[EIXO_SAUDE] = {**_resumir_saude(itens), "completo": completo}
    except FalhaDeRede:
        pass

    try:
        itens, completo = obter_paginado(
            cliente,
            "/discricionarias/propostas",
            {"uf_proponente": uf, "ano_prop": ano, "desc_orgao_sup": "MINISTERIO DAS CIDADES"},
        )
        resultado[EIXO_CIDADES] = {**_resumir_cidades(itens), "completo": completo}
    except FalhaDeRede:
        pass

    return resultado


def gravar(
    programas: list[dict],
    por_uf: dict[str, dict[str, dict]],
    ano: int,
    *,
    caminho: Path | None = None,
    detalhe: str | None = None,
) -> dict[str, int]:
    """Substitui programas e agregados do ano em uma transação."""
    with db.transacao(caminho) as conexao:
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID,
            nome="Subsídios federais — programas e propostas por UF",
            orgao="Ministério da Gestão e da Inovação (Transferegov)",
            url=URL_BASE,
            licenca="Dados abertos do Governo Federal",
            periodo_referencia=str(ano),
            status="ok",
            detalhe=detalhe,
        )
        conexao.execute("DELETE FROM subsidio_programa")
        conexao.executemany(
            """
            INSERT INTO subsidio_programa
                (id_programa, orgao, nome, situacao, modalidade, data_disponibilizacao,
                 inicio_recebimento, fim_recebimento, fonte_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    p["id_programa"], p["orgao"], p["nome"], p["situacao"], p["modalidade"],
                    p["data_disponibilizacao"], p["inicio_recebimento"], p["fim_recebimento"],
                    FONTE_ID,
                )
                for p in programas
            ],
        )
        conexao.execute("DELETE FROM subsidio_uf WHERE ano = ?", (ano,))
        linhas = []
        for uf, eixos in por_uf.items():
            for eixo, resumo in eixos.items():
                linhas.append(
                    (
                        uf, ano, eixo, resumo["propostas"], resumo["aprovadas"],
                        round(resumo["valor_planejado"], 2), round(resumo["valor_repasse"], 2),
                        resumo["programas"], FONTE_ID,
                    )
                )
        conexao.executemany(
            """
            INSERT INTO subsidio_uf
                (uf, ano, eixo, propostas, aprovadas, valor_planejado, valor_repasse,
                 programas, fonte_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            linhas,
        )
        db.definir_meta(conexao, f"subsidios_{ano}_coletado_em", db.agora_utc())
    return {"programas": len(programas), "linhas_uf": len(linhas)}


def coletar(
    ano: int,
    *,
    cliente: ClienteHTTP | None = None,
    caminho_banco: Path | None = None,
    ufs: list[str] | None = None,
    trabalhadores: int = 6,
) -> dict[str, int]:
    """Coleta programas e agregados de todas as UFs (paralelo moderado)."""
    cliente = cliente or ClienteHTTP(tentativas=3)
    ufs = ufs or sorted(CAPITAIS)
    programas = coletar_programas(cliente, ano)

    por_uf: dict[str, dict[str, dict]] = {}
    incompletos = 0
    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        futuros = {uf: executor.submit(coletar_uf, cliente, uf, ano) for uf in ufs}
        for uf, futuro in futuros.items():
            try:
                resultado = futuro.result()
            except Exception:  # noqa: BLE001 - fonte externa
                continue
            if resultado:
                por_uf[uf] = resultado
                incompletos += sum(1 for r in resultado.values() if not r.get("completo", True))

    detalhe = f"{len(programas)} programas; {len(por_uf)} UFs; {incompletos} coleta(s) parcial(is)"
    contagem = gravar(programas, por_uf, ano, caminho=caminho_banco, detalhe=detalhe)
    return {**contagem, "ufs": len(por_uf), "parciais": incompletos}


def ofertas(conexao: sqlite3.Connection, *, orgao: str | None = None) -> list[dict]:
    """Programas disponibilizados, do mais recente ao mais antigo."""
    filtro = "WHERE orgao = ?" if orgao else ""
    parametros = (orgao,) if orgao else ()
    linhas = conexao.execute(
        f"SELECT * FROM subsidio_programa {filtro} "
        "ORDER BY data_disponibilizacao DESC, nome",
        parametros,
    ).fetchall()
    return [dict(linha) for linha in linhas]


def por_uf(conexao: sqlite3.Connection, ano: int, eixo: str | None = None) -> list[dict]:
    """Aproveitamento por UF, ordenado pelo valor planejado."""
    filtro = "AND eixo = ?" if eixo else ""
    parametros = (ano, eixo) if eixo else (ano,)
    linhas = conexao.execute(
        f"SELECT * FROM subsidio_uf WHERE ano = ? {filtro} ORDER BY valor_planejado DESC",
        parametros,
    ).fetchall()
    return [dict(linha) for linha in linhas]
