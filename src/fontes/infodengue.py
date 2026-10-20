"""Casos de dengue do SINAN, agregados pelo InfoDengue (Fiocruz).

Por que não ler o SINAN direto:

- o microdado do DATASUS vem em `.dbc` (274 MB só em 2024) e a biblioteca
  PySUS **não instala** no Python 3.14 deste ambiente (sem wheel para
  `pyreaddbc`/`fastparquet`);
- a API de Dados Abertos do Ministério da Saúde limita a 15 linhas por
  requisição e a paginação não tem ordenação estável (medido: 502 após 60 s
  com `limit=20`, offsets repetindo linhas).

O InfoDengue é mantido pela Fiocruz a partir do próprio SINAN. Ele oferece:

1. ``/api/notif_reduced`` — série semanal por **UF**, em uma requisição;
2. ``/api/alertcity`` — série semanal por **município**, com clima e nível
   de alerta.

O painel usa (1) para o mapa e (2) para as capitais. A proveniência exibida é
“SINAN (notificações), agregado pelo InfoDengue”, com a URL exata da consulta.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from pathlib import Path

from src import db
from src.dados.capitais import CAPITAIS
from src.rede import ClienteHTTP
from src.servicos.epidemiologia import semana_epidemiologica

URL_SERIE = "https://info.dengue.mat.br/api/notif_reduced"
URL_ALERTCITY = "https://info.dengue.mat.br/api/alertcity"
FONTE_ID = "infodengue_sinan"
FONTE_ID_MUNICIPIO = "infodengue_alertcity"


def consultar_serie(
    uf: str, cliente: ClienteHTTP, *, inicio: date, fim: date
) -> str:
    """Pede o CSV semanal de uma UF ao InfoDengue."""
    resposta = cliente.obter(
        URL_SERIE,
        params={
            "state_abv": uf.upper(),
            "chart_type": "period",
            "diseases": "dengue",
            "initial_date": inicio.isoformat(),
            "final_date": fim.isoformat(),
        },
    )
    return resposta.texto()


def normalizar_serie(texto_csv: str, uf: str) -> list[dict]:
    """Converte ``dt_week,Casos`` em linhas prontas para o banco.

    A data vem como o **domingo** que abre a semana epidemiológica. Convertemos
    para (ano, semana) com a convenção brasileira — não com a ISO, que erra o
    número em várias semanas do ano.
    """
    linhas: list[dict] = []
    leitor = csv.DictReader(io.StringIO(texto_csv))
    for registro in leitor:
        bruto = (registro.get("dt_week") or "").strip()
        if not bruto:
            continue
        try:
            ano_data, mes, dia = (int(parte) for parte in bruto.split("-"))
            casos = int(float(registro.get("Casos") or 0))
        except ValueError:
            continue
        ano, semana = semana_epidemiologica(date(ano_data, mes, dia))
        linhas.append({"uf": uf.upper(), "ano": ano, "semana": semana, "casos": casos})
    linhas.sort(key=lambda linha: (linha["ano"], linha["semana"]))
    return linhas


def remover_semana_em_curso(linhas: list[dict]) -> tuple[list[dict], bool]:
    """Descarta a última linha quando ela vem zerada.

    A semana corrente aparece no arquivo antes de as notificações serem
    digitadas — zero ali significa “ainda não chegou”, não “não houve caso”.
    Só a **última** linha é descartada: uma cauda longa de zeros é dado real
    e permanece.
    """
    if linhas and linhas[-1]["casos"] == 0:
        return linhas[:-1], True
    return linhas, False


def gravar_series(
    series: dict[str, list[dict]],
    *,
    caminho: Path | None = None,
    periodo: str | None = None,
    detalhe: str | None = None,
) -> int:
    """Grava as séries por UF em uma transação, apagando a coleta anterior."""
    total = 0
    with db.transacao(caminho) as conexao:
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID,
            nome="Dengue — notificações do SINAN agregadas por semana",
            orgao="Ministério da Saúde (SINAN) via InfoDengue/Fiocruz",
            url=URL_SERIE,
            licenca="Dados abertos; InfoDengue é projeto da Fiocruz",
            periodo_referencia=periodo,
            status="ok",
            detalhe=detalhe,
        )
        conexao.execute("DELETE FROM caso_semana WHERE fonte_id = ?", (FONTE_ID,))
        for linhas in series.values():
            conexao.executemany(
                "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (linha["uf"], linha["ano"], linha["semana"], linha["casos"], FONTE_ID)
                    for linha in linhas
                ],
            )
            total += len(linhas)
        db.registrar_log(
            conexao,
            fonte_id=FONTE_ID,
            iniciado_em=db.agora_utc(),
            status="ok",
            registros=total,
            mensagem=detalhe,
        )
        db.definir_meta(conexao, "dengue_coletado_em", db.agora_utc())
    return total


def coletar(
    *,
    ufs: list[str] | None = None,
    meses: int = 15,
    cliente: ClienteHTTP | None = None,
    caminho_banco: Path | None = None,
) -> dict[str, int]:
    """Coleta a série de cada UF e grava. Devolve contagens para o relatório."""
    cliente = cliente or ClienteHTTP()
    ufs = ufs or sorted(CAPITAIS)
    fim = date.today()
    inicio = fim - timedelta(days=30 * meses)

    series: dict[str, list[dict]] = {}
    falhas: list[str] = []
    descartadas = 0
    for uf in ufs:
        try:
            texto = consultar_serie(uf, cliente, inicio=inicio, fim=fim)
        except Exception:  # noqa: BLE001 - fonte fora do ar é caso previsto
            falhas.append(uf)
            continue
        linhas = normalizar_serie(texto, uf)
        linhas, removeu = remover_semana_em_curso(linhas)
        descartadas += int(removeu)
        if linhas:
            series[uf] = linhas

    detalhe = (
        f"{len(series)} UFs; {descartadas} semana(s) em curso descartada(s)"
        + (f"; falhas: {', '.join(falhas)}" if falhas else "")
    )
    total = gravar_series(
        series,
        caminho=caminho_banco,
        periodo=f"{series and min(s[0]['ano'] for s in series.values())} a {fim.year}",
        detalhe=detalhe,
    )
    return {
        "ufs": len(series),
        "linhas": total,
        "falhas": len(falhas),
        "semana_em_curso": descartadas,
    }


def consultar_municipio(geocode: int, cliente: ClienteHTTP, *, anos: int = 2) -> list[dict]:
    """Série semanal de um município (alertcity), com clima e nível de alerta."""
    hoje = date.today()
    resposta = cliente.obter(
        URL_ALERTCITY,
        params={
            "geocode": geocode,
            "disease": "dengue",
            "format": "json",
            "ew_start": 1,
            "ew_end": 53,
            "ey_start": hoje.year - anos,
            "ey_end": hoje.year,
        },
    )
    dados = resposta.json()
    if not isinstance(dados, list):
        raise ValueError("resposta inesperada do alertcity")
    return dados


def gravar_capitais(
    dados: dict[str, list[dict]],
    *,
    caminho: Path | None = None,
) -> int:
    """Grava casos municipais das capitais (tabela `caso_municipio_semana`)."""
    total = 0
    with db.transacao(caminho) as conexao:
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID_MUNICIPIO,
            nome="Dengue por município (capitais) — alertcity",
            orgao="InfoDengue/Fiocruz (dados do SINAN)",
            url=URL_ALERTCITY,
            licenca="Dados abertos; InfoDengue é projeto da Fiocruz",
            periodo_referencia=f"últimos 2 anos até {date.today().isoformat()}",
            status="ok",
            detalhe=f"{len(dados)} capitais",
        )
        conexao.execute(
            "DELETE FROM caso_municipio_semana WHERE fonte_id = ?", (FONTE_ID_MUNICIPIO,)
        )
        for uf, registros in dados.items():
            codigo = str(CAPITAIS[uf])
            for registro in registros:
                semana_bruta = str(registro.get("SE") or "")
                if len(semana_bruta) != 6:
                    continue
                casos = registro.get("casos")
                if casos is None:
                    continue
                conexao.execute(
                    "INSERT OR REPLACE INTO caso_municipio_semana "
                    "(municipio_codigo, ano, semana, casos, fonte_id) VALUES (?, ?, ?, ?, ?)",
                    (
                        codigo,
                        int(semana_bruta[:4]),
                        int(semana_bruta[4:]),
                        int(casos),
                        FONTE_ID_MUNICIPIO,
                    ),
                )
                total += 1
        db.definir_meta(conexao, "capitais_coletado_em", db.agora_utc())
    return total


def coletar_capitais(
    *, cliente: ClienteHTTP | None = None, caminho_banco: Path | None = None
) -> dict[str, int]:
    """Baixa a série de cada capital; falha de uma não derruba as outras."""
    cliente = cliente or ClienteHTTP()
    dados: dict[str, list[dict]] = {}
    falhas = 0
    for uf, codigo in CAPITAIS.items():
        try:
            dados[uf] = consultar_municipio(codigo, cliente)
        except Exception:  # noqa: BLE001
            falhas += 1
    total = gravar_capitais(dados, caminho=caminho_banco)
    return {"capitais": len(dados), "linhas": total, "falhas": falhas}
