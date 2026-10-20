"""Testes dos serviços de orçamento e clima (sem rede).

O que se testa aqui é a **regra**, não o formato da fonte: soma de repasses,
ordenação por incidência e classificação da chuva. São os números que aparecem
na tela.
"""

from __future__ import annotations

import pytest

from src import db
from src.servicos import clima, orcamento


@pytest.fixture
def banco(tmp_path):
    conexao = db.conectar(tmp_path / "servicos.db")
    db.inicializar(conexao)
    db.registrar_fonte(
        conexao,
        id_fonte="teste",
        nome="Teste",
        orgao="Teste",
        url="https://example.org",
    )
    conexao.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('SP', 'São Paulo', '35')")
    conexao.executemany(
        "INSERT INTO municipio (codigo_ibge, nome, uf, populacao) VALUES (?, ?, 'SP', ?)",
        [
            ("3550308", "São Paulo", 11_451_000),
            ("3509502", "Campinas", 1_139_000),
        ],
    )
    yield conexao
    conexao.close()


def test_resumo_de_repasses_soma_e_ordena(banco):
    """Dois repasses: total certo e o mais recente primeiro."""
    banco.executemany(
        "INSERT INTO repasse (uf, data, valor, descricao, fonte_id, url_fonte, coletado_em) "
        "VALUES ('SP', ?, ?, ?, 'teste', 'https://example.org/x', '2026-10-20T00:00:00+00:00')",
        [("2026-08-01", 1000.0, "Ação A"), ("2026-09-01", 500.0, "Ação B")],
    )

    resumo = orcamento.resumo(banco, "sp")

    assert resumo["disponivel"] is True
    assert resumo["total"] == 1500.0
    assert resumo["periodo"] == "2026-08-01 a 2026-09-01"
    assert resumo["repasses"][0]["valor"] == 500.0
    assert "causalidade" in resumo["aviso_metodologico"]


def test_repasses_mensais_agrupam_por_mes(banco):
    """Duas linhas no mesmo mês viram uma barra só no gráfico."""
    banco.executemany(
        "INSERT INTO repasse (uf, data, valor, descricao, fonte_id, url_fonte, coletado_em) "
        "VALUES ('SP', '2026-09-01', ?, 'Ação', 'teste', 'https://example.org', 'x')",
        [(100.0,), (250.0,)],
    )

    serie = orcamento.serie_mensal(banco, "SP")

    assert serie == [{"mes": "2026-09", "valor": 350.0, "quantidade": 2}]


def test_nivel_de_chuva_usa_os_limiares_documentados():
    """50 mm vira atenção; 100 mm vira alto; None não vira zero."""
    assert clima._nivel(10)[0] == "baixo"
    assert clima._nivel(50)[0] == "atencao"
    assert clima._nivel(100)[0] == "alto"
    assert clima._nivel(None)[0] == "sem_dado"


def test_alertas_ordenam_por_incidencia_e_trazem_chuva(banco):
    """Campinas tem menos casos, mas população menor: incidência maior."""
    banco.executemany(
        "INSERT INTO caso_municipio_semana (municipio_codigo, ano, semana, casos, fonte_id) "
        "VALUES (?, 2026, 41, ?, 'teste')",
        [("3550308", 100), ("3509502", 50)],
    )
    for dia in range(1, 9):
        for codigo, chuva_mm in (("3550308", 5.0), ("3509502", 20.0)):
            banco.execute(
                "INSERT INTO clima_dia (estacao, uf, municipio_codigo, data, precipitacao_mm, "
                "temp_max_c, temp_min_c, fonte_id, coletado_em) VALUES (?, 'SP', ?, ?, ?, 30, 20, "
                "'teste', 'x')",
                (f"EST-{codigo}", codigo, f"2026-10-{dia:02d}", chuva_mm),
            )
    banco.commit()

    alertas = clima.alertas_por_incidencia(banco, "SP")

    assert [alerta["municipio"] for alerta in alertas] == ["Campinas", "São Paulo"]
    assert alertas[0]["incidencia"] > alertas[1]["incidencia"]
    assert alertas[0]["chuva_7d_mm"] == pytest.approx(140.0)
    assert alertas[0]["nivel"] == "alto"


def test_sem_caso_municipal_o_fallback_mostra_chuva(banco):
    """Sem caso por município, a lista não fica vazia: mostra chuva e avisa."""
    banco.execute(
        "INSERT INTO clima_dia (estacao, uf, municipio_codigo, data, precipitacao_mm, "
        "fonte_id, coletado_em) VALUES ('A1', 'SP', '3550308', '2026-10-20', 60.0, 'teste', 'x')"
    )
    banco.commit()

    assert clima.alertas_por_incidencia(banco, "SP") == []
    fallback = clima.alertas(banco, "SP")
    assert fallback[0]["casos"] is None
    assert fallback[0]["nivel"] == "atencao"
