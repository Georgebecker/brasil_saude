"""Testes da API: o contrato que o frontend consome.

Cada teste sobe a aplicação com um banco temporário e confere o JSON que o
JavaScript vai ler. Isso substitui "abrir o navegador e olhar" no que diz
respeito aos dados; a aparência é conferida à parte.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src import db
from src.app import create_app
from src.servicos import epidemiologia


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "api.db")


@pytest.fixture
def cliente(app):
    return TestClient(app)


def semear(app) -> None:
    """Cria o mínimo de dado real para o mapa ter o que mostrar."""
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    db.registrar_fonte(
        conexao,
        id_fonte="teste",
        nome="Fonte de teste",
        orgao="Órgão de teste",
        url="https://example.org/fonte",
        periodo_referencia="2025",
    )
    conexao.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('SP', 'São Paulo', '35')")
    for semana, casos in enumerate([10, 12, 11, 13, 12, 10, 11, 12, 40], start=1):
        conexao.execute(
            "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
            "VALUES ('SP', 2025, ?, ?, 'teste')",
            (semana, casos),
        )
    conexao.commit()
    epidemiologia.calcular_alertas(conexao)
    conexao.close()


def test_saude_responde_mesmo_sem_dado(cliente):
    """O painel precisa subir vazio e dizer que está vazio (status sem_dados)."""
    resposta = cliente.get("/api/saude")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "sem_dados"
    assert corpo["ufs"] == 0


def test_lista_de_estados_vazia_nao_e_erro(cliente):
    """Sem coleta, o mapa recebe lista vazia — e o frontend mostra o aviso."""
    assert cliente.get("/api/estados").json() == []


def test_estados_trazem_casos_e_alerta(app, cliente):
    """Depois da semeadura, o mapa tem SP com casos e anomalia calculada."""
    semear(app)

    corpo = cliente.get("/api/estados").json()

    assert len(corpo) == 1
    linha = corpo[0]
    assert linha["uf"] == "SP"
    assert linha["casos"] == 40
    assert linha["disponivel"] is True
    assert linha["anomalo"] is True


def test_serie_da_uf_tem_faixa_esperada(app, cliente):
    """A série consumida pelo Chart.js precisa de esperado e limite por ponto."""
    semear(app)

    corpo = cliente.get("/api/estados/sp").json()

    assert corpo["uf"] == "SP"
    assert len(corpo["semanas"]) == 9
    assert corpo["ultima"]["casos"] == 40
    assert corpo["ultima"]["limite"] is not None


def test_serie_aceita_a_variante_c2(app, cliente):
    """A alternância C1/C2 da tela usa o mesmo contrato, com `metodo`."""
    semear(app)
    conexao = db.conectar(app.state.caminho_banco)
    conexao.execute(
        "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
        "VALUES ('SP', 2025, 10, 41, 'teste')"
    )
    conexao.commit()
    conexao.close()

    corpo = cliente.get("/api/estados/SP?metodo=C2").json()

    assert corpo["metodo"] == "C2"
    assert corpo["ultima"]["limite"] is not None


def test_uf_invalida_responde_422(cliente):
    """UF digitada errada precisa de erro explícito, não de série vazia."""
    assert cliente.get("/api/estados/XX").status_code == 422


def test_metodo_invalido_responde_422(cliente):
    """Variante do EARS fora de C1..C3 é erro do cliente, não do servidor."""
    assert cliente.get("/api/estados?metodo=C9").status_code == 422


def test_repasses_sem_dado_avisa_em_vez_de_inventar(app, cliente):
    """Aba de orçamento sem coleta devolve disponivel=False e aviso metodológico."""
    semear(app)

    corpo = cliente.get("/api/estados/SP/repasses").json()

    assert corpo["disponivel"] is False
    assert corpo["total"] == 0
    assert "causalidade" in corpo["aviso_metodologico"]


def test_clima_sem_dado_devolve_lista_vazia(app, cliente):
    """Sem estação coletada, a aba de clima não inventa alerta."""
    semear(app)
    assert cliente.get("/api/estados/SP/clima").json() == []


def test_fontes_lista_a_proveniencia(app, cliente):
    """A seção Fontes e Metodologia lê a tabela `fonte`, não texto fixo."""
    semear(app)

    corpo = cliente.get("/api/fontes").json()

    assert corpo[0]["id"] == "teste"
    assert corpo[0]["orgao"] == "Órgão de teste"
    assert corpo[0]["coletado_em"]
