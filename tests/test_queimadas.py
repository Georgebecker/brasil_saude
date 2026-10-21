"""Testes de queimadas (INPE) e do indicador de rede local."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from src import db
from src.app import create_app
from src.fontes import queimadas
from src.servicos import rede

CABECALHO = "id_bdq,foco_id,lat,lon,data_pas,pais,estado,municipio,bioma\n"


def _zip_com(linhas: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as pacote:
        pacote.writestr("tmp/focos_br_ref_2025.csv", CABECALHO + linhas)
    return buffer.getvalue()


def test_processar_agrega_por_uf_e_mes(tmp_path):
    """O painel publica contagem por estado e mês, nunca o ponto individual."""
    linhas = (
        "1,f1,-7.5,-37.7,2025-01-01 16:52:00,Brasil,PERNAMBUCO,SOLIDÃO,Caatinga\n"
        "2,f2,-7.6,-37.8,2025-01-31 10:00:00,Brasil,PERNAMBUCO,ARCOVERDE,Caatinga\n"
        "3,f3,-12.3,-37.9,2025-02-02 10:00:00,Brasil,BAHIA,ENTRE RIOS,Mata Atlântica\n"
        "4,f4,-15.0,-47.0,2025-02-03 10:00:00,Brasil,DISTRITO FEDERAL,BRASÍLIA,Cerrado\n"
        "5,f5,-15.0,-47.0,2025-02-04 10:00:00,Argentina,CÓRDOBA,NADA,Chaco\n"
    )
    arquivo = tmp_path / "focos_br_ref_2025.zip"
    arquivo.write_bytes(_zip_com(linhas))

    resumo = queimadas.processar(arquivo, 2025)

    por_chave = {(linha["uf"], linha["mes"]): linha["focos"] for linha in resumo}
    assert por_chave[("PE", 1)] == 2
    assert por_chave[("BA", 2)] == 1
    assert por_chave[("DF", 2)] == 1
    assert len(por_chave) == 3, "estado estrangeiro não pode entrar"


def test_processar_ignora_zip_sem_csv(tmp_path):
    """Arquivo errado vira erro explicado, não lista vazia silenciosa."""
    arquivo = tmp_path / "vazio.zip"
    with zipfile.ZipFile(arquivo, "w") as pacote:
        pacote.writestr("leiame.txt", "nada aqui")

    with pytest.raises(Exception, match="não tem CSV"):
        queimadas.processar(arquivo, 2025)


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "queimadas.db")


@pytest.fixture
def cliente(app):
    return TestClient(app)


def _semear(app) -> None:
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    db.registrar_fonte(
        conexao,
        id_fonte=queimadas.FONTE_ID,
        nome="Focos de queimada",
        orgao="INPE",
        url=queimadas.BASE,
        periodo_referencia="2025",
    )
    conexao.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('PA', 'Pará', '15')")
    conexao.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('MA', 'Maranhão', '21')")
    for uf, mes, focos in (("PA", 9, 100), ("PA", 10, 50), ("MA", 9, 30)):
        conexao.execute(
            "INSERT INTO queimada_uf_mes (uf, ano, mes, focos, fonte_id) VALUES (?, 2025, ?, ?, ?)",
            (uf, mes, focos, queimadas.FONTE_ID),
        )
    conexao.commit()
    conexao.close()


def test_rota_queimadas_devolve_totais_e_meses(app, cliente):
    """A tela precisa do total, do ranking por UF e da série mensal com nome."""
    _semear(app)

    corpo = cliente.get("/api/queimadas?ano=2025").json()

    assert corpo["total"] == 180
    assert [linha["uf"] for linha in corpo["ufs"]] == ["PA", "MA"]
    assert corpo["meses"][0]["nome"] == "setembro"
    assert corpo["fonte"].startswith("https://")


def test_rota_queimadas_ano_sem_dado_nao_inventa(app, cliente):
    """Ano não coletado devolve zero e listas vazias, nunca erro 500."""
    _semear(app)

    corpo = cliente.get("/api/queimadas?ano=2019").json()

    assert corpo["total"] == 0
    assert corpo["ufs"] == []


def test_rota_rede_informa_endereco(app, cliente):
    """O indicador da tela lê porta, endereço local e tempo no ar."""
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    conexao.close()

    corpo = cliente.get("/api/rede").json()

    assert corpo["online"] is True
    assert corpo["porta"] == 80 or corpo["porta"] > 0
    assert corpo["endereco_local"].startswith("http://127.0.0.1")
    assert corpo["segundos_no_ar"] >= 0


def test_rearmar_registra_pedido_e_devolve_endereco(app, cliente):
    """O botão grava o sinal do vigia e responde com o IP recalculado."""
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    conexao.close()

    corpo = cliente.post("/api/rede/rearmar").json()

    assert corpo["rearmado"] is True
    assert "mensagem" in corpo
    assert rede.SINAL_REARME.exists()


def test_ip_local_e_privado_ou_nulo():
    """Nunca devolver endereço público: o painel é de rede doméstica."""
    endereco = rede.ip_local()

    assert endereco is None or endereco.startswith(("10.", "192.168.", "172."))
