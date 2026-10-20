"""Códigos IBGE das capitais, uma por UF.

Usado em dois lugares: a série municipal do InfoDengue (uma capital por UF) e
a escolha da estação meteorológica (a capital precisa estar sempre na amostra,
mesmo quando o INMET não a marca como capital no cadastro).
"""

from __future__ import annotations

CAPITAIS: dict[str, int] = {
    "AC": 1200401, "AL": 2704302, "AP": 1600303, "AM": 1302603, "BA": 2927408,
    "CE": 2304400, "DF": 5300108, "ES": 3205309, "GO": 5208707, "MA": 2111300,
    "MT": 5103403, "MS": 5002704, "MG": 3106200, "PA": 1501402, "PB": 2507507,
    "PR": 4106902, "PE": 2611606, "PI": 2211001, "RJ": 3304557, "RN": 2408102,
    "RS": 4314902, "RO": 1100205, "RR": 1400100, "SC": 4205407, "SP": 3550308,
    "SE": 2800308, "TO": 1721000,
}  # fmt: skip
