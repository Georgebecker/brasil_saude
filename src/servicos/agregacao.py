"""Agregação da série semanal em períodos maiores (mês, trimestre, semestre, ano).

Por que existe: o contrato do painel é semanal, mas ninguém compara "semana 12 com
semana 40" para falar de tendência. O leitor quer mês, trimestre, semestre, ano —
e também quer recortar "de tal semana a tal semana".

Regra que não se negocia: agregar **não** é interpolar. Um mês com duas semanas
sem publicação tem `semanas_com_dado = 2` e a média é calculada sobre essas duas,
nunca sobre quatro. O total continua sendo a soma do que foi publicado.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from src.servicos.epidemiologia import Semana, primeiro_domingo

GRANULARIDADES = ("semana", "mes", "trimestre", "semestre", "ano")

MESES_CURTOS = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]  # fmt: skip


def data_da_semana(ano: int, semana: int) -> date:
    """Domingo que abre a semana epidemiológica (convenção brasileira)."""
    return primeiro_domingo(ano) + timedelta(days=(semana - 1) * 7)


def chave_do_periodo(ano: int, semana: int, granularidade: str) -> tuple[str, str]:
    """Devolve (chave, rótulo) do balde ao qual a semana pertence."""
    if granularidade == "semana":
        return f"{ano}-SE{semana:02d}", f"SE {semana:02d}/{ano}"

    dia = data_da_semana(ano, semana)
    if granularidade == "mes":
        return f"{dia.year}-{dia.month:02d}", f"{MESES_CURTOS[dia.month - 1]}/{dia.year}"
    if granularidade == "trimestre":
        trimestre = (dia.month - 1) // 3 + 1
        return f"{dia.year}-T{trimestre}", f"{trimestre}º tri/{dia.year}"
    if granularidade == "semestre":
        semestre = (dia.month - 1) // 6 + 1
        return f"{dia.year}-S{semestre}", f"{semestre}º sem/{dia.year}"
    if granularidade == "ano":
        return str(dia.year), str(dia.year)
    raise ValueError(f"granularidade inválida: {granularidade}")


def recortar(
    semanas: Iterable[Semana],
    *,
    de: tuple[int, int] | None = None,
    ate: tuple[int, int] | None = None,
) -> list[Semana]:
    """Filtra pela janela pedida, incluindo as duas pontas."""
    lista = list(semanas)
    if de is not None:
        lista = [semana for semana in lista if (semana.ano, semana.semana) >= de]
    if ate is not None:
        lista = [semana for semana in lista if (semana.ano, semana.semana) <= ate]
    return lista


def agregar(semanas: Iterable[Semana], granularidade: str) -> list[dict]:
    """Agrupa a série no período pedido, preservando a ordem cronológica."""
    if granularidade not in GRANULARIDADES:
        raise ValueError(f"granularidade inválida: {granularidade}")

    baldes: dict[str, dict] = {}
    ordem: list[str] = []

    for semana in semanas:
        chave, rotulo = chave_do_periodo(semana.ano, semana.semana, granularidade)
        if chave not in baldes:
            baldes[chave] = {
                "chave": chave,
                "rotulo": rotulo,
                "casos": 0,
                "semanas": 0,
                "semanas_com_dado": 0,
                "primeira": semana.rotulo,
                "ultima": semana.rotulo,
            }
            ordem.append(chave)
        balde = baldes[chave]
        balde["semanas"] += 1
        balde["ultima"] = semana.rotulo
        if semana.casos is None:
            continue
        balde["casos"] += semana.casos
        balde["semanas_com_dado"] += 1

    for chave in ordem:
        balde = baldes[chave]
        balde["media"] = (
            round(balde["casos"] / balde["semanas_com_dado"], 1)
            if balde["semanas_com_dado"]
            else None
        )

    return [baldes[chave] for chave in ordem]


def resumo(semanas: list[Semana], granularidade: str) -> dict:
    """Baldes + totais da janela, prontos para o JSON da API."""
    baldes = agregar(semanas, granularidade)
    com_dado = [semana for semana in semanas if semana.casos is not None]
    total = sum(semana.casos for semana in com_dado)
    return {
        "granularidade": granularidade,
        "de": semanas[0].rotulo if semanas else None,
        "ate": semanas[-1].rotulo if semanas else None,
        "semanas": len(semanas),
        "semanas_com_dado": len(com_dado),
        "total": total,
        "media_semanal": round(total / len(com_dado), 1) if com_dado else None,
        "periodos": baldes,
    }
