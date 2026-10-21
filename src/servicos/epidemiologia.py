"""Serviço epidemiológico: séries por UF, lacunas e cálculo dos alertas EARS.

Este módulo é o "cérebro" da parte de dengue. Ele não sabe de onde o caso veio
(SINAN, OpenDataSUS, InfoDengue) — só conhece a tabela `caso_semana`. Essa
separação é o que permite trocar de fonte sem reescrever a regra estatística.

Duas decisões que valem explicação:

- **Lacuna não vira zero.** Se o SINAN não publicou a semana 12, a série tem
  `None` ali. Zero seria uma afirmação ("não houve caso") que o dado não fez.
- **A grade semanal é contínua.** Para o EARS enxergar "as sete semanas
  anteriores", precisamos do calendário inteiro; por isso reconstruímos as
  semanas entre a primeira e a última, marcando as ausentes como `None`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from src import db, ears

VARIANTES = ("C1", "C2")


@dataclass(frozen=True)
class Semana:
    """Uma semana epidemiológica: ano + número + contagem (ou lacuna)."""

    ano: int
    semana: int
    casos: int | None

    @property
    def rotulo(self) -> str:
        return f"{self.ano}-SE{self.semana:02d}"


def primeiro_domingo(ano: int) -> date:
    """Domingo que abre a semana epidemiológica 1 do ano.

    A convenção brasileira (portaria do Ministério da Saúde) usa semanas de
    domingo a sábado; a semana 1 é a que contém 4 de janeiro. É parecida com a
    ISO, mas deslocada em um dia — e essa diferença muda o número da semana em
    várias datas do ano.
    """
    quarto = date(ano, 1, 4)
    return quarto - timedelta(days=(quarto.weekday() + 1) % 7)


def semana_epidemiologica(dia: date) -> tuple[int, int]:
    """Devolve (ano epidemiológico, semana) de uma data.

    O ano epidemiológico é o ano do "meio" da semana (domingo + 3 dias), o que
    resolve a virada de ano sem regra especial: a semana que começa em
    2024-12-29 pertence a 2025, porque tem quatro dias em 2025.
    """
    domingo = dia - timedelta(days=(dia.weekday() + 1) % 7)
    ano = (domingo + timedelta(days=3)).year
    return ano, (domingo - primeiro_domingo(ano)).days // 7 + 1


def semanas_no_ano(ano: int) -> int:
    """Quantas semanas epidemiológicas o ano tem (52 ou 53)."""
    return (primeiro_domingo(ano + 1) - primeiro_domingo(ano)).days // 7


def proxima_semana(ano: int, semana: int) -> tuple[int, int]:
    """Avança uma semana no calendário, virando o ano quando necessário."""
    if semana >= semanas_no_ano(ano):
        return ano + 1, 1
    return ano, semana + 1


def grade(pontos: dict[tuple[int, int], int]) -> list[Semana]:
    """Preenche as semanas ausentes com `None`, sem interpolar valores."""
    if not pontos:
        return []
    chaves = sorted(pontos)
    atual = chaves[0]
    ultima = chaves[-1]
    serie: list[Semana] = []
    while atual <= ultima:
        serie.append(Semana(atual[0], atual[1], pontos.get(atual)))
        atual = proxima_semana(*atual)
    return serie


def series_por_uf(
    conexao: sqlite3.Connection, fonte_id: str | None = None
) -> dict[str, list[Semana]]:
    """Lê `caso_semana` e devolve a grade completa por UF.

    `fonte_id` restringe a uma fonte específica; sem ele, somamos as fontes
    (o que só é seguro quando não há duas fontes para o mesmo período).
    """
    filtro = "WHERE fonte_id = ?" if fonte_id else ""
    parametros = (fonte_id,) if fonte_id else ()
    linhas = conexao.execute(
        f"SELECT uf, ano, semana, casos FROM caso_semana {filtro} ORDER BY uf, ano, semana",
        parametros,
    ).fetchall()

    bruto: dict[str, dict[tuple[int, int], int]] = {}
    for linha in linhas:
        bruto.setdefault(linha["uf"], {})[(linha["ano"], linha["semana"])] = linha["casos"]
    return {uf: grade(pontos) for uf, pontos in bruto.items()}


def calcular_alertas(
    conexao: sqlite3.Connection,
    *,
    variantes: tuple[str, ...] = VARIANTES,
    fonte_id: str | None = None,
) -> int:
    """Calcula C1/C2 para todas as UFs e grava em `alerta_ears`.

    Regrava o período inteiro a cada execução (idempotente): o alerta é
    derivado, então não há motivo para guardar versões antigas do mesmo
    cálculo. O carimbo `calculado_em` diz quando aquela faixa foi produzida.
    """
    series = series_por_uf(conexao, fonte_id)
    agora = db.agora_utc()
    gravados = 0

    for uf, semanas in series.items():
        valores: list[float | None] = [s.casos for s in semanas]
        for variante in variantes:
            for indice, resultado in enumerate(ears.detectar_serie(valores, variante=variante)):
                if resultado is None:
                    continue
                semana = semanas[indice]
                conexao.execute(
                    """
                    INSERT INTO alerta_ears
                        (uf, ano, semana, metodo, observado, esperado, limite,
                         anomalo, calculado_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(uf, ano, semana, metodo) DO UPDATE SET
                        observado = excluded.observado,
                        esperado = excluded.esperado,
                        limite = excluded.limite,
                        anomalo = excluded.anomalo,
                        calculado_em = excluded.calculado_em
                    """,
                    (
                        uf,
                        semana.ano,
                        semana.semana,
                        variante,
                        int(resultado.observado),
                        resultado.esperado,
                        resultado.limite,
                        1 if resultado.anomalo else 0,
                        agora,
                    ),
                )
                gravados += 1
    conexao.commit()
    return gravados


def ultima_semana(conexao: sqlite3.Connection) -> tuple[int, int] | None:
    """Semana de referência do mapa: a mais recente com cobertura quase total.

    Por que não usar simplesmente o `MAX`: uma UF pode publicar uma semana a
    mais que as outras (ou receber um lançamento atrasado). Escolher esse
    extremo pintaria 26 estados de cinza. A referência é a semana mais recente
    que mantém pelo menos 90% da cobertura máxima — um retrato nacional, sem
    perder a semana nova por causa de uma UF atrasada.
    """
    cobertura = conexao.execute("SELECT MAX(ufs) AS maximo FROM ("
                                "SELECT COUNT(DISTINCT uf) AS ufs FROM caso_semana "
                                "GROUP BY ano, semana)").fetchone()
    if not cobertura or not cobertura["maximo"]:
        return None
    minimo = max(1, int(cobertura["maximo"] * 0.9))
    linha = conexao.execute(
        """
        SELECT ano, semana, COUNT(DISTINCT uf) AS ufs
        FROM caso_semana
        GROUP BY ano, semana
        HAVING COUNT(DISTINCT uf) >= ?
        ORDER BY ano * 100 + semana DESC
        LIMIT 1
        """,
        (minimo,),
    ).fetchone()
    if not linha:
        return None
    return int(linha["ano"]), int(linha["semana"])


def situacao_por_uf(conexao: sqlite3.Connection, *, variante: str = "C1") -> list[dict]:
    """Uma linha por UF com o cenário da última semana disponível.

    É o que alimenta o mapa: casos, faixa esperada e se há anomalia. UF sem
    dado entra com `casos = None` e `disponivel = False` — o mapa pinta essa
    UF de cinza em vez de fingir zero.
    """
    referencia = ultima_semana(conexao)
    if referencia is None:
        return []
    ano, semana = referencia

    ufs = conexao.execute(
        "SELECT sigla, nome, codigo_ibge, regiao, populacao FROM uf ORDER BY nome"
    ).fetchall()
    linhas = []
    for uf in ufs:
        caso = conexao.execute(
            "SELECT casos FROM caso_semana WHERE uf = ? AND ano = ? AND semana = ? "
            "ORDER BY casos DESC LIMIT 1",
            (uf["sigla"], ano, semana),
        ).fetchone()
        alerta = conexao.execute(
            "SELECT esperado, limite, anomalo FROM alerta_ears "
            "WHERE uf = ? AND ano = ? AND semana = ? AND metodo = ?",
            (uf["sigla"], ano, semana, variante),
        ).fetchone()
        casos = caso["casos"] if caso else None
        populacao = uf["populacao"]
        incidencia = (
            round(casos / populacao * 100_000, 1) if casos is not None and populacao else None
        )
        linhas.append(
            {
                "uf": uf["sigla"],
                "nome": uf["nome"],
                "codigo_ibge": uf["codigo_ibge"],
                "regiao": uf["regiao"],
                "ano": ano,
                "semana": semana,
                "casos": casos,
                "populacao": populacao,
                "incidencia": incidencia,
                "disponivel": caso is not None,
                "esperado": alerta["esperado"] if alerta else None,
                "limite": alerta["limite"] if alerta else None,
                "anomalo": bool(alerta["anomalo"]) if alerta else None,
            }
        )
    return linhas


def serie_da_uf(conexao: sqlite3.Connection, uf: str, *, variante: str = "C1") -> dict:
    """Série completa + faixa esperada do EARS, ponto a ponto."""
    semanas = series_por_uf(conexao).get(uf.upper())
    if semanas is None:
        return {"uf": uf.upper(), "semanas": [], "metodo": variante}

    resultados = ears.detectar_serie([s.casos for s in semanas], variante=variante)
    referencia = ultima_semana(conexao)
    pontos = []
    for semana, resultado in zip(semanas, resultados, strict=True):
        pontos.append(
            {
                "ano": semana.ano,
                "semana": semana.semana,
                "rotulo": semana.rotulo,
                "casos": semana.casos,
                "esperado": resultado.esperado if resultado else None,
                "limite": resultado.limite if resultado else None,
                "anomalo": resultado.anomalo if resultado else None,
            }
        )
    return {
        "uf": uf.upper(),
        "metodo": variante,
        "semanas": pontos,
        "ultima": _ultima_consolidada(pontos, referencia),
    }


def _ultima_consolidada(pontos: list[dict], referencia: tuple[int, int] | None) -> dict | None:
    """Último ponto que já está consolidado na semana de referência nacional.

    A semana em curso chega parcial (às vezes só um estado publicou). Ela
    continua no gráfico, porque foi publicada, mas não pode ser o retrato do
    estado: comparar 3 dias de notificação com um limite semanal cheio faria o
    painel dizer "dentro do esperado" por um motivo falso.
    """
    if not pontos:
        return None
    if referencia is None:
        return pontos[-1]
    consolidados = [
        ponto for ponto in pontos if (ponto["ano"], ponto["semana"]) <= referencia
    ]
    return consolidados[-1] if consolidados else pontos[0]
