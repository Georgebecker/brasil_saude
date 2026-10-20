"""Meteorologia: catálogo de estações do INMET + série diária.

Duas fontes, cada uma com o seu papel — e a tela diz qual é qual:

1. **INMET** fornece o *cadastro* das estações (nome, UF, coordenadas e o
   código do município). Esse endpoint é público e respondeu normalmente.
2. **Série diária** de chuva e temperatura: a API de dados do INMET
   (`/estacao/{inicio}/{fim}/{codigo}`) devolveu **HTTP 204** em todas as
   tentativas — o serviço passou a exigir token/cadastro. Sem token, usamos o
   **Open-Meteo** (modelo meteorológico aberto, sem chave) nas coordenadas da
   estação. É um *fallback declarado*: o painel nunca escreve "INMET" no valor
   que veio do Open-Meteo.

Se um dia houver token do INMET, basta trocar `consultar_clima` — o contrato
do serviço e a tabela `clima_dia` não mudam.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from src import db
from src.dados.capitais import CAPITAIS
from src.rede import ClienteHTTP

URL_ESTACOES = "https://apitempo.inmet.gov.br/estacoes/{tipo}"
URL_CLIMA = "https://api.open-meteo.com/v1/forecast"
FONTE_ID_ESTACOES = "inmet_estacoes"
FONTE_ID_CLIMA = "open_meteo"

UF_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}  # fmt: skip


def _municipio_do_wsi(wsi: str | None) -> str | None:
    """Extrai o código IBGE do campo WSI (formato ``0-76-0-3550308000W83781``).

    O WSI carrega o código do município nos sete primeiros dígitos do último
    bloco, que pode terminar com letras (estação convencional). Por isso
    usamos expressão regular em vez de exigir número puro. Validamos contra a
    UF da estação: se não bater, é melhor ficar sem município do que apontar
    para a cidade errada.
    """
    if not wsi:
        return None
    ultimo = wsi.split("-")[-1]
    encontrado = re.search(r"\d{7}", ultimo)
    return encontrado.group(0) if encontrado else None


def normalizar_estacoes(bruto: list[dict]) -> list[dict]:
    """Transforma o JSON do INMET em linhas da tabela `estacao`."""
    linhas = []
    for item in bruto:
        uf = (item.get("SG_ESTADO") or "").upper()
        if uf not in UF_VALIDAS:
            continue
        municipio = _municipio_do_wsi(item.get("CD_WSI"))
        if municipio and municipio[:2] != _codigo_uf(uf):
            municipio = None
        try:
            latitude = float(item.get("VL_LATITUDE") or "nan")
            longitude = float(item.get("VL_LONGITUDE") or "nan")
        except ValueError:
            latitude = longitude = None
        linhas.append(
            {
                "codigo": item.get("CD_ESTACAO"),
                "nome": item.get("DC_NOME") or "estação sem nome",
                "uf": uf,
                "municipio_codigo": municipio,
                "latitude": latitude,
                "longitude": longitude,
                "tipo": item.get("TP_ESTACAO"),
                "situacao": item.get("CD_SITUACAO"),
                "capital": item.get("FL_CAPITAL") == "S",
            }
        )
    return [linha for linha in linhas if linha["codigo"]]


def _codigo_uf(uf: str) -> str:
    """Código IBGE da UF (duas primeiras posições do código de município)."""
    mapa = {
        "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
        "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
        "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
        "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53",
    }  # fmt: skip
    return mapa[uf]


def escolher_por_uf(estacoes: list[dict]) -> dict[str, dict]:
    """Escolhe a melhor estação por UF: capital, operante e com coordenadas.

    O desempate é explícito (capital primeiro). Sem isso, a primeira estação
    lida no arquivo venceria — e o painel de São Paulo acabaria mostrando
    Ariranha em vez da capital.
    """

    def nota(estacao: dict) -> tuple[int, int, int]:
        return (
            1 if estacao["capital"] else 0,
            1 if estacao["situacao"] == "Operante" else 0,
            1 if estacao["latitude"] is not None else 0,
        )

    escolhidas: dict[str, dict] = {}
    for estacao in estacoes:
        atual = escolhidas.get(estacao["uf"])
        if atual is None or nota(estacao) > nota(atual):
            escolhidas[estacao["uf"]] = estacao
    return escolhidas


def gravar_estacoes(estacoes: list[dict], *, caminho: Path | None = None) -> int:
    """Grava o catálogo (uma linha por estação) e registra a fonte.

    O código de município extraído do WSI pode não existir na tabela do IBGE
    (estação em distrito, código antigo). Nesse caso guardamos `NULL`: é
    melhor a estação sem município do que uma chave estrangeira inválida.
    """
    with db.transacao(caminho) as conexao:
        validos = {
            linha["codigo_ibge"] for linha in conexao.execute("SELECT codigo_ibge FROM municipio")
        }
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID_ESTACOES,
            nome="Cadastro de estações meteorológicas",
            orgao="INMET",
            url=URL_ESTACOES,
            licenca="Dados abertos do INMET",
            periodo_referencia="vigente na coleta",
            status="ok",
            detalhe=f"{len(estacoes)} estações",
        )
        conexao.executemany(
            """
            INSERT INTO estacao (codigo, nome, uf, municipio_codigo, latitude, longitude,
                                 tipo, situacao, fonte_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(codigo) DO UPDATE SET
                nome = excluded.nome,
                uf = excluded.uf,
                municipio_codigo = excluded.municipio_codigo,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                tipo = excluded.tipo,
                situacao = excluded.situacao
            """,
            [
                (
                    e["codigo"],
                    e["nome"],
                    e["uf"],
                    e["municipio_codigo"] if e["municipio_codigo"] in validos else None,
                    e["latitude"],
                    e["longitude"],
                    e["tipo"],
                    e["situacao"],
                    FONTE_ID_ESTACOES,
                )
                for e in estacoes
            ],
        )
        db.definir_meta(conexao, "estacoes_coletado_em", db.agora_utc())
    return len(estacoes)


def baixar_catalogo(cliente: ClienteHTTP) -> list[dict]:
    """Baixa os dois catálogos do INMET e junta sem repetir estação.

    ``T`` traz as automáticas (668) e ``M`` as convencionais (87). A capital
    de São Paulo, por exemplo, só existe no catálogo convencional — olhar
    apenas um dos dois deixaria a capital sem clima.
    """
    estacoes: list[dict] = []
    vistos: set[str] = set()
    for tipo in ("T", "M"):
        bruto = cliente.obter_json(URL_ESTACOES.format(tipo=tipo))
        if not isinstance(bruto, list):
            continue
        for estacao in normalizar_estacoes(bruto):
            if estacao["codigo"] not in vistos:
                vistos.add(estacao["codigo"])
                estacoes.append(estacao)
    return estacoes


def coletar_estacoes(
    *, cliente: ClienteHTTP | None = None, caminho_banco: Path | None = None
) -> dict[str, int]:
    """Baixa o catálogo, grava e devolve quantas estações por UF."""
    cliente = cliente or ClienteHTTP()
    estacoes = baixar_catalogo(cliente)
    total = gravar_estacoes(estacoes, caminho=caminho_banco)
    return {"estacoes": total, "ufs": len({e["uf"] for e in estacoes})}


def consultar_clima(
    estacao: dict, cliente: ClienteHTTP, *, dias: int = 14
) -> list[dict]:
    """Série diária (chuva, máxima e mínima) nas coordenadas da estação."""
    if estacao.get("latitude") is None or estacao.get("longitude") is None:
        raise ValueError(f"estação {estacao['codigo']} sem coordenadas")
    resposta = cliente.obter(
        URL_CLIMA,
        params={
            "latitude": estacao["latitude"],
            "longitude": estacao["longitude"],
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
            "past_days": dias,
            "forecast_days": 1,
            "timezone": "America/Sao_Paulo",
        },
    )
    dados = resposta.json()
    diario = (dados or {}).get("daily") or {}
    datas = diario.get("time") or []
    chuva = diario.get("precipitation_sum") or []
    maxima = diario.get("temperature_2m_max") or []
    minima = diario.get("temperature_2m_min") or []

    linhas = []
    for indice, dia in enumerate(datas):
        linhas.append(
            {
                "estacao": estacao["codigo"],
                "uf": estacao["uf"],
                "municipio_codigo": estacao.get("municipio_codigo"),
                "data": dia,
                "precipitacao_mm": chuva[indice] if indice < len(chuva) else None,
                "temp_max_c": maxima[indice] if indice < len(maxima) else None,
                "temp_min_c": minima[indice] if indice < len(minima) else None,
            }
        )
    return linhas


def gravar_clima(linhas: list[dict], *, caminho: Path | None = None) -> int:
    """Grava a série diária, substituindo o período coletado.

    O código de município vem do WSI da estação; quando ele não existe na
    tabela do IBGE (estação em distrito ou código antigo), gravamos `NULL` em
    vez de violar a chave estrangeira — a série de chuva continua válida e o
    alerta mostra a estação, ainda que sem o nome do município.
    """
    with db.transacao(caminho) as conexao:
        validos = {
            linha["codigo_ibge"] for linha in conexao.execute("SELECT codigo_ibge FROM municipio")
        }
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID_CLIMA,
            nome="Chuva e temperatura diárias (fallback declarado)",
            orgao="Open-Meteo (modelo meteorológico aberto)",
            url=URL_CLIMA,
            licenca="Uso não comercial, atribuição (Open-Meteo)",
            periodo_referencia=f"últimos 14 dias até {date.today().isoformat()}",
            status="ok",
            detalhe=(
                "Série do INMET exige token (HTTP 204 sem autenticação); "
                "estações e coordenadas são do INMET, valores são do Open-Meteo."
            ),
        )
        conexao.execute("DELETE FROM clima_dia WHERE fonte_id = ?", (FONTE_ID_CLIMA,))
        conexao.executemany(
            """
            INSERT INTO clima_dia (estacao, uf, municipio_codigo, data, precipitacao_mm,
                                   temp_max_c, temp_min_c, fonte_id, coletado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    linha["estacao"],
                    linha["uf"],
                    linha["municipio_codigo"] if linha["municipio_codigo"] in validos else None,
                    linha["data"],
                    linha["precipitacao_mm"],
                    linha["temp_max_c"],
                    linha["temp_min_c"],
                    FONTE_ID_CLIMA,
                    db.agora_utc(),
                )
                for linha in linhas
            ],
        )
        db.definir_meta(conexao, "clima_coletado_em", db.agora_utc())
    return len(linhas)


def selecionar_estacoes(estacoes: list[dict], *, por_uf: int = 12) -> list[dict]:
    """Escolhe até `por_uf` estações por UF, com a capital sempre presente.

    O INMET nem sempre marca a capital no campo `FL_CAPITAL` (Salvador, por
    exemplo, vem como “N”). Por isso a capital é garantida pelo código IBGE,
    não pelo rótulo. O resto da amostra entra por nome, para a lista cobrir
    litoral e interior.
    """
    por_estado: dict[str, list[dict]] = {}
    for estacao in estacoes:
        por_estado.setdefault(estacao["uf"], []).append(estacao)

    def ordenar(lista: list[dict]) -> list[dict]:
        return sorted(
            lista,
            key=lambda e: (
                0 if e["situacao"] == "Operante" else 1,
                0 if e["latitude"] is not None else 1,
                e["nome"],
            ),
        )

    escolhidas: list[dict] = []
    for uf, lista in por_estado.items():
        capital = str(CAPITAIS.get(uf, ""))
        da_capital = ordenar([e for e in lista if e["municipio_codigo"] == capital])
        codigos_capital = {e["codigo"] for e in da_capital}
        resto = ordenar([e for e in lista if e["codigo"] not in codigos_capital])
        escolhidas.extend((da_capital[:1] + resto)[:por_uf])
    return escolhidas


def coletar_clima(
    *,
    cliente: ClienteHTTP | None = None,
    caminho_banco: Path | None = None,
    dias: int = 14,
    por_uf: int = 12,
) -> dict[str, int]:
    """Coleta o clima de uma amostra de estações por UF e grava."""
    cliente = cliente or ClienteHTTP()
    estacoes = baixar_catalogo(cliente)
    escolhidas = selecionar_estacoes(estacoes, por_uf=por_uf)

    linhas: list[dict] = []
    falhas = 0
    for estacao in escolhidas:
        try:
            linhas.extend(consultar_clima(estacao, cliente, dias=dias))
        except Exception:  # noqa: BLE001 - fonte externa pode falhar
            falhas += 1

    total = gravar_clima(linhas, caminho=caminho_banco)
    return {"estacoes": len(escolhidas) - falhas, "linhas": total, "falhas": falhas}
