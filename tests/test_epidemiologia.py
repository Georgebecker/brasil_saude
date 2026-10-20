"""Testes do serviço epidemiológico: grade semanal, lacunas e alertas.

Os testes usam um banco temporário e dados montados à mão. É de propósito:
testar com o SINAN real tornaria o teste lento e dependente da internet, e um
teste que falha quando o governo muda o site não protege nada.
"""

from __future__ import annotations

import pytest

from src import db
from src.servicos import epidemiologia


@pytest.fixture
def banco(tmp_path):
    conexao = db.conectar(tmp_path / "epidemiologia.db")
    db.inicializar(conexao)
    db.registrar_fonte(
        conexao,
        id_fonte="teste",
        nome="Fonte de teste",
        orgao="Teste",
        url="https://example.org/teste",
    )
    for sigla, nome, codigo in (("SP", "São Paulo", "35"), ("RJ", "Rio de Janeiro", "33")):
        conexao.execute(
            "INSERT INTO uf (sigla, nome, codigo_ibge) VALUES (?, ?, ?)", (sigla, nome, codigo)
        )
    yield conexao
    conexao.close()


def inserir_semana(conexao, uf, ano, semana, casos):
    conexao.execute(
        "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) VALUES (?, ?, ?, ?, 'teste')",
        (uf, ano, semana, casos),
    )


def test_grade_completa_as_semanas_ausentes_com_none(banco):
    """A semana 11 não existe no banco; a grade precisa mostrar o buraco."""
    inserir_semana(banco, "SP", 2025, 10, 100)
    inserir_semana(banco, "SP", 2025, 12, 140)

    serie = epidemiologia.series_por_uf(banco)["SP"]

    assert [(s.ano, s.semana, s.casos) for s in serie] == [
        (2025, 10, 100),
        (2025, 11, None),
        (2025, 12, 140),
    ]


def test_calcular_alertas_grava_c1_e_c2(banco):
    """Com oito semanas de histórico, C1 e C2 produzem alertas avaliáveis."""
    for semana, casos in enumerate([10, 12, 11, 13, 12, 10, 11, 12, 40], start=1):
        inserir_semana(banco, "SP", 2025, semana, casos)

    gravados = epidemiologia.calcular_alertas(banco)

    # 9 semanas x 2 variantes, menos as semanas sem sete pontos de histórico.
    assert gravados > 0
    linha = banco.execute(
        "SELECT * FROM alerta_ears WHERE uf = 'SP' AND ano = 2025 AND semana = 9 AND metodo = 'C1'"
    ).fetchone()
    assert linha is not None
    assert linha["observado"] == 40
    assert linha["anomalo"] == 1


def test_lacuna_impede_alerta_em_vez_de_inventar_queda(banco):
    """Semana ausente dentro da janela: o EARS não avalia (não vira zero)."""
    for semana in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11):
        inserir_semana(banco, "SP", 2025, semana, 10)

    epidemiologia.calcular_alertas(banco)

    linha = banco.execute(
        "SELECT COUNT(*) AS total FROM alerta_ears WHERE uf = 'SP' AND semana = 11"
    ).fetchone()
    assert linha["total"] == 0


def test_situacao_por_uf_marca_uf_sem_dado_como_indisponivel(banco):
    """RJ não tem caso; o mapa precisa saber a diferença entre zero e ausência."""
    for semana in range(1, 10):
        inserir_semana(banco, "SP", 2025, semana, 10)
    epidemiologia.calcular_alertas(banco)

    situacao = {linha["uf"]: linha for linha in epidemiologia.situacao_por_uf(banco)}

    assert situacao["SP"]["disponivel"] is True
    assert situacao["RJ"]["disponivel"] is False
    assert situacao["RJ"]["casos"] is None


def test_serie_da_uf_traz_a_faixa_esperada(banco):
    """A série devolvida para o gráfico precisa ter esperado e limite por ponto."""
    for semana, casos in enumerate([10, 12, 11, 13, 12, 10, 11, 12, 40], start=1):
        inserir_semana(banco, "SP", 2025, semana, casos)

    serie = epidemiologia.serie_da_uf(banco, "sp")

    assert serie["uf"] == "SP"
    assert serie["ultima"]["casos"] == 40
    assert serie["ultima"]["limite"] is not None
    assert serie["ultima"]["anomalo"] is True
