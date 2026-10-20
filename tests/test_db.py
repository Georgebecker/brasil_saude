"""Testes do banco: esquema, proveniência e integridade referencial.

O objetivo não é testar o SQLite, e sim as regras do projeto: número sem fonte
não entra, fonte sem período não é publicada e a agregação não pode inventar
linha.
"""

from __future__ import annotations

import sqlite3

import pytest

from src import db


@pytest.fixture
def banco(tmp_path):
    """Banco temporário por teste: nada encosta no banco real."""
    caminho = tmp_path / "teste.db"
    conexao = db.conectar(caminho)
    db.inicializar(conexao)
    yield conexao
    conexao.close()


def test_inicializar_e_idempotente(tmp_path):
    """Rodar a inicialização duas vezes não pode quebrar nem duplicar tabela."""
    caminho = tmp_path / "x.db"
    db.inicializar(db.conectar(caminho))
    db.inicializar(db.conectar(caminho))

    conexao = db.conectar(caminho)
    tabelas = {
        linha["name"]
        for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    conexao.close()

    assert {"fonte", "uf", "caso_semana", "repasse", "clima_dia"} <= tabelas


def test_caso_sem_fonte_registrada_e_bloqueado(banco):
    """Sem "escritura" na tabela fonte, o caso não entra — regra do DICA."""
    banco.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('SP', 'São Paulo', '35')")

    with pytest.raises(sqlite3.IntegrityError):
        banco.execute(
            "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
            "VALUES ('SP', 2025, 10, 120, 'fonte-inexistente')"
        )


def test_caso_com_fonte_registrada_e_aceito(banco):
    """O caminho feliz precisa funcionar: UF + fonte + caso."""
    db.registrar_fonte(
        banco,
        id_fonte="sinan",
        nome="SINAN",
        orgao="Ministério da Saúde",
        url="https://example.org/sinan",
        periodo_referencia="2025",
    )
    banco.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('SP', 'São Paulo', '35')")
    banco.execute(
        "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
        "VALUES ('SP', 2025, 10, 120, 'sinan')"
    )

    total = banco.execute("SELECT SUM(casos) AS total FROM caso_semana").fetchone()["total"]
    assert total == 120


def test_casos_negativos_sao_rejeitados(banco):
    """Contagem negativa é erro de ETL, não dado: o banco recusa na entrada."""
    db.registrar_fonte(
        banco,
        id_fonte="sinan",
        nome="SINAN",
        orgao="Ministério da Saúde",
        url="https://example.org/sinan",
    )
    banco.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('SP', 'São Paulo', '35')")

    with pytest.raises(sqlite3.IntegrityError):
        banco.execute(
            "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
            "VALUES ('SP', 2025, 10, -1, 'sinan')"
        )


def test_meta_guarda_e_devolve_valor(banco):
    """`meta` é o lugar de estados simples, como a data da última coleta."""
    db.definir_meta(banco, "ultima_coleta", "2026-10-20T12:00:00+00:00")
    assert db.ler_meta(banco, "ultima_coleta") == "2026-10-20T12:00:00+00:00"
    assert db.ler_meta(banco, "nao_existe", "padrao") == "padrao"
