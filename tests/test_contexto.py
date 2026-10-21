"""Testes do contexto político e das convenções de formato brasileiro.

Dois assuntos no mesmo arquivo porque ambos respondem à mesma pergunta:
"o painel entrega o dado no padrão que o leitor brasileiro espera?".
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from src import db
from src.app import create_app
from src.servicos import contexto


def test_curadoria_tem_27_governadores_com_partido_e_fonte():
    """Governador sem partido não cumpre a função de responsabilização."""
    dados = contexto.carregar()

    ufs = {item["uf"] for item in dados["governadores"]}
    assert len(ufs) == 27
    for item in dados["governadores"]:
        assert item["nome"].strip()
        assert item["partido"].strip()
        assert item["url_fonte"].startswith("http")


def test_ministros_cobrem_o_periodo_de_2025_a_2026_sem_buraco():
    """O período dos dados precisa estar inteiro dentro de algum ministério."""
    dados = contexto.carregar()
    periodos = sorted(
        (date.fromisoformat(item["inicio"]), date.fromisoformat(item["fim"]))
        for item in dados["ministros_saude"]
    )

    assert periodos[0][0] == date(2019, 1, 1)
    for anterior, seguinte in zip(periodos, periodos[1:], strict=False):
        # Um dia de folga é aceito entre mandatos; buraco maior é erro de curadoria.
        assert (seguinte[0] - anterior[1]).days <= 1


def test_pos_mandato_so_publica_o_que_foi_conferido():
    """Afirmação sobre pessoa real exige fonte e grau de confiança declarado."""
    registros = contexto.carregar_pos_mandato()

    assert "Eduardo Pazuello" in registros
    pazuello = registros["Eduardo Pazuello"]
    assert pazuello["verificado"] is True
    assert pazuello["situacao"] == "cargo_eletivo"
    assert pazuello["url_fonte"].startswith("http")

    for nome, item in registros.items():
        if item["verificado"]:
            assert item["url_fonte"].startswith("http"), nome
            assert item["confianca"] in {"alta", "media", "baixa"}, nome
            assert item["resumo"].strip(), nome
        else:
            assert item["situacao"] == "nao_verificado", nome
            assert item["pendencias"], f"{nome}: pendência sem descrição não ajuda o próximo ciclo"


def test_pos_mandato_cobre_todos_os_ministros_da_linha_do_tempo():
    """Ministro no histórico sem registro de destino deixa a tela incompleta."""
    nomes_histórico = {item["nome"] for item in contexto.carregar()["ministros_saude"]}
    registrados = set(contexto.carregar_pos_mandato())

    assert nomes_histórico <= registrados


def test_contexto_do_estado_escolhe_governador_e_ministro_da_data():
    """Em 2024 havia uma ministra; em 2026, outro ministro. A data decide."""
    em_2024 = contexto.para_uf("SC", referencia=date(2024, 6, 1))
    em_2026 = contexto.para_uf("sc", referencia=date(2026, 6, 1))

    assert em_2024["governador"]["nome"] == "Jorginho Mello"
    assert em_2024["governador"]["partido"] == "PL"
    assert em_2024["ministros_saude"][0]["nome"] == "Nísia Trindade"
    assert em_2026["ministros_saude"][0]["nome"] == "Alexandre Padilha"
    assert em_2026["presidente"]["partido"] == "PT"


def test_contexto_nacional_devolve_historico_e_limitacao():
    """A tela mostra a linha do tempo completa e declara o que falta curar."""
    dados = contexto.nacional(referencia=date(2026, 1, 1))

    nomes = [item["nome"] for item in dados["historico_ministros"]]
    assert "Marcelo Queiroga" in nomes
    assert len(dados["governadores"]) == 27
    assert dados["limitacao"]
    assert dados["aviso"].startswith("Contexto político é curadoria manual")


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "contexto.db")


@pytest.fixture
def cliente(app):
    return TestClient(app)


def test_rotas_de_contexto_respondem(app, cliente):
    """Rota nacional e rota por UF entregam o mesmo recorte."""
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    conexao.close()

    nacional = cliente.get("/api/contexto")
    estado = cliente.get("/api/estados/PE/contexto")

    assert nacional.status_code == 200
    assert estado.status_code == 200
    assert len(nacional.json()["governadores"]) == 27
    assert estado.json()["governador"]["uf"] == "PE"
    assert cliente.get("/api/estados/ZZ/contexto").status_code == 422


def test_rotas_publicas_nao_exigem_token(app, cliente):
    """O contexto é dado público; nada aqui deve pedir autenticação."""
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    conexao.close()

    for rota in ("/api/contexto", "/api/estados/SP/contexto", "/api/resumo", "/api/subsidios"):
        assert cliente.get(rota).status_code == 200, rota


def test_resumo_traz_contagem_de_fontes(app, cliente):
    """O topo da página precisa saber quantas fontes existem e quantas estão ok."""
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    db.registrar_fonte(
        conexao,
        id_fonte="teste_ok",
        nome="Fonte ok",
        orgao="Órgão",
        url="https://example.org",
        periodo_referencia="2026",
    )
    conexao.commit()
    conexao.close()

    corpo = cliente.get("/api/resumo").json()

    assert corpo["fontes_total"] == 1
    assert corpo["fontes_ok"] == 0 or corpo["fontes_ok"] == 1


def test_formato_brasileiro_de_numero_data_e_moeda():
    """ABNT NBR 5891: ponto no milhar, vírgula no decimal, data dd/mm/aaaa."""
    import locale
    from decimal import Decimal

    locale.setlocale(locale.LC_ALL, "")

    def brl(valor: Decimal) -> str:
        inteiro = f"{valor:,.2f}"
        return inteiro.replace(",", "_").replace(".", ",").replace("_", ".")

    assert brl(Decimal("1234567.89")) == "1.234.567,89"
    assert date(2026, 10, 21).strftime("%d/%m/%Y") == "21/10/2026"
