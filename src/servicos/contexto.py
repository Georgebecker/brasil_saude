"""Contexto político: quem ocupava os cargos no período dos dados.

Por que este módulo existe: um painel que mostra repasse e caso sem dizer quem
governava deixa o leitor sem a informação principal — a de responsabilização.
O módulo não opina: entrega nome, cargo, partido, período e a fonte.

O dado é **curadoria manual** versionada em `src/dados/mandatos.json`, não
coleta automática. Isso está declarado na resposta (`aviso`) porque o leitor
precisa saber que esse bloco tem a data de validação da curadoria, e não a
data de uma coleta de API.
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parents[1] / "dados" / "mandatos.json"
ARQUIVO_POS = Path(__file__).resolve().parents[1] / "dados" / "pos_mandato.json"

AVISO = (
    "Contexto político é curadoria manual revisada em 21/10/2026, não coleta automática. "
    "Partido é a legenda de eleição ou de filiação no início do mandato. "
    "Situação pós-mandato só aparece quando foi conferida em fonte pública."
)


@lru_cache(maxsize=1)
def carregar() -> dict:
    """Lê a curadoria uma vez por processo (o arquivo é pequeno e não muda em execução)."""
    with ARQUIVO.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


@lru_cache(maxsize=1)
def carregar_pos_mandato() -> dict[str, dict]:
    """Índice por nome com a situação posterior ao cargo."""
    with ARQUIVO_POS.open(encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    return {registro["nome"]: registro for registro in dados["registros"]}


def _dentro(item: dict, referencia: date) -> bool:
    """O cargo estava ocupado na data de referência?"""
    inicio = date.fromisoformat(item["inicio"])
    fim = date.fromisoformat(item["fim"])
    return inicio <= referencia <= fim


def _item_publico(item: dict) -> dict:
    """Remove as datas ISO internas e mantém o que a tela mostra."""
    pos = carregar_pos_mandato().get(item["nome"])
    return {
        "nome": item["nome"],
        "partido": item["partido"],
        "periodo": item["periodo"],
        "url_fonte": item["url_fonte"],
        "pos_mandato": (
            {
                "situacao": pos["situacao"],
                "resumo": pos["resumo"],
                "verificado": pos["verificado"],
                "confianca": pos["confianca"],
                "url_fonte": pos["url_fonte"],
            }
            if pos
            else None
        ),
    }


def referencia_do_painel() -> date:
    """Data usada como referência: hoje, limitada ao fim do último mandato curado."""
    dados = carregar()
    fim_mandato = max(date.fromisoformat(item["fim"]) for item in dados["presidentes"])
    return min(date.today(), fim_mandato)


def nacional(referencia: date | None = None) -> dict:
    """Presidente, ministros da Saúde do período e a lista completa de ministros."""
    dados = carregar()
    quando = referencia or referencia_do_painel()

    presidente = next((item for item in dados["presidentes"] if _dentro(item, quando)), None)
    ministros = [item for item in dados["ministros_saude"] if _dentro(item, quando)]

    return {
        "referencia": quando.isoformat(),
        "presidente": _item_publico(presidente) if presidente else None,
        "ministros_saude": [_item_publico(item) for item in ministros],
        "historico_ministros": [_item_publico(item) for item in dados["ministros_saude"]],
        "historico_presidentes": [_item_publico(item) for item in dados["presidentes"]],
        "governadores": [
            {"uf": item["uf"], **_item_publico(item)} for item in dados["governadores"]
        ],
        "aviso": AVISO,
        "limitacao": dados.get("_limitacao"),
        "fontes": dados.get("_fontes", []),
    }


def para_uf(uf: str, referencia: date | None = None) -> dict:
    """Mesmo recorte do nacional, com o governador da UF."""
    dados = carregar()
    quando = referencia or referencia_do_painel()
    sigla = uf.upper()

    governador = next(
        (item for item in dados["governadores"] if item["uf"] == sigla),
        None,
    )
    presidente = next((item for item in dados["presidentes"] if _dentro(item, quando)), None)
    ministros = [item for item in dados["ministros_saude"] if _dentro(item, quando)]

    return {
        "uf": sigla,
        "referencia": quando.isoformat(),
        "governador": (
            {
                "uf": governador["uf"],
                "cargo_inicio": "Governador(a) 2023-2026",
                **_item_publico(governador),
            }
            if governador
            else None
        ),
        "presidente": _item_publico(presidente) if presidente else None,
        "ministros_saude": [_item_publico(item) for item in ministros],
        "aviso": AVISO,
    }
