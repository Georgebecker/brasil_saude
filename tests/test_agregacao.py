"""Testes da agregação por período (semana, mês, trimestre, semestre, ano)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from src import db
from src.app import create_app
from src.servicos import agregacao, epidemiologia
from src.servicos.epidemiologia import Semana


def test_data_da_semana_segue_a_convencao_brasileira():
    """SE1 é a semana que contém 4 de janeiro, começando no domingo."""
    assert agregacao.data_da_semana(2026, 1) == date(2026, 1, 4)
    assert agregacao.data_da_semana(2026, 1).weekday() == 6  # domingo
    assert agregacao.data_da_semana(2026, 2) == date(2026, 1, 11)
    # 2025: 4 de janeiro caiu num sábado, então a semana 1 abriu em 29/12/2024
    assert agregacao.data_da_semana(2025, 1) == date(2024, 12, 29)


def test_agregar_por_mes_soma_e_conta_semanas_com_dado():
    """Média é sobre as semanas publicadas, nunca sobre as semanas do mês."""
    semanas = [
        Semana(2026, 1, 10),
        Semana(2026, 2, None),
        Semana(2026, 3, 20),
        Semana(2026, 4, 30),
        Semana(2026, 5, 40),
    ]

    baldes = agregacao.agregar(semanas, "mes")

    por_rotulo = {balde["rotulo"]: balde for balde in baldes}
    janeiro = por_rotulo["jan/2026"]  # semanas 1 a 4 começam em janeiro
    assert janeiro["casos"] == 60  # 10 + 20 + 30; a semana 2 é lacuna
    assert janeiro["semanas"] == 4
    assert janeiro["semanas_com_dado"] == 3
    assert janeiro["media"] == 20.0
    assert por_rotulo["fev/2026"]["casos"] == 40


def test_agregar_por_trimestre_e_ano():
    """O balde muda de nome, mas o total do período tem de fechar."""
    semanas = [Semana(2026, semana, semana * 10) for semana in range(1, 13)]

    trimestres = agregacao.agregar(semanas, "trimestre")
    anos = agregacao.agregar(semanas, "ano")

    assert len(trimestres) >= 1
    assert sum(balde["casos"] for balde in trimestres) == sum(balde["casos"] for balde in anos)
    assert anos[-1]["rotulo"] == "2026"


def test_recortar_inclui_as_duas_pontas():
    """'de tal a tal' é intervalo fechado; perder a última semana engana o leitor."""
    semanas = [Semana(2026, semana, 1) for semana in range(1, 11)]

    janela = agregacao.recortar(semanas, de=(2026, 3), ate=(2026, 5))

    assert [semana.semana for semana in janela] == [3, 4, 5]


def test_granularidade_invalida_falha_alto():
    """Erro de programação não pode virar resposta silenciosa."""
    with pytest.raises(ValueError, match="granularidade inválida"):
        agregacao.agregar([Semana(2026, 1, 1)], "decada")


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "agregado.db")


@pytest.fixture
def cliente(app):
    return TestClient(app)


def _semear(app) -> None:
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    db.registrar_fonte(
        conexao,
        id_fonte="teste",
        nome="Fonte de teste",
        orgao="Órgão",
        url="https://example.org",
        periodo_referencia="2026",
    )
    conexao.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('SP', 'São Paulo', '35')")
    for semana, casos in zip(range(1, 9), [10, 20, 30, 40, 50, 60, 70, 80], strict=True):
        conexao.execute(
            "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
            "VALUES ('SP', 2026, ?, ?, 'teste')",
            (semana, casos),
        )
    conexao.commit()
    conexao.close()


def test_rota_agregado_por_mes(app, cliente):
    """A rota devolve baldes com rótulo em português e totais conferidos."""
    _semear(app)

    corpo = cliente.get("/api/estados/SP/agregado?granularidade=mes").json()

    assert corpo["uf"] == "SP"
    assert corpo["total"] == 360
    assert corpo["semanas"] == 8
    assert all("rotulo" in periodo for periodo in corpo["periodos"])


def test_rota_agregado_com_janela(app, cliente):
    """Recorte por semana: 3 a 5 devolve só as semanas do intervalo."""
    _semear(app)

    corpo = cliente.get(
        "/api/estados/SP/agregado?granularidade=semana&de=2026-SE3&ate=2026-SE5"
    ).json()

    assert corpo["total"] == 120  # 30 + 40 + 50
    assert corpo["semanas"] == 3


def test_rota_agregado_recusa_granularidade_estranha(app, cliente):
    """Parâmetro fora da lista vira 422, não lista vazia."""
    _semear(app)

    resposta = cliente.get("/api/estados/SP/agregado?granularidade=semestre_estranho")

    assert resposta.status_code == 422


def test_series_por_uf_nao_inventa_semana_faltante():
    """A grade preenche buraco com None — a agregação conta isso como ausência."""
    conexao = db.conectar(":memory:")
    db.inicializar(conexao)
    conexao.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('SP', 'São Paulo', '35')")
    db.registrar_fonte(
        conexao,
        id_fonte="teste",
        nome="Fonte",
        orgao="Órgão",
        url="https://example.org",
        periodo_referencia="2026",
    )
    for semana in (10, 12):
        conexao.execute(
            "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
            "VALUES ('SP', 2026, ?, 5, 'teste')",
            (semana,),
        )

    series = epidemiologia.series_por_uf(conexao)

    assert [semana.semana for semana in series["SP"]] == [10, 11, 12]
    assert series["SP"][1].casos is None
    conexao.close()
