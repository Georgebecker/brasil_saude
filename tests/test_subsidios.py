"""Testes do módulo de subsídios e da decodificação de JSON em Latin-1.

Dois assuntos moram juntos aqui porque nasceram do mesmo defeito real: a API
do Transferegov devolve JSON em Latin-1 sem declarar o charset, e o nome do
programa chegava ao banco como "Processo n�". O teste da rede garante que a
leitura corrige; os testes do serviço garantem que a soma não mente.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src import db
from src.app import create_app
from src.fontes import transferegov
from src.rede import FalhaDeRede, Resposta
from src.servicos import epidemiologia, subsidios


def test_json_latin1_sem_charset_e_lido_corretamente():
    """Acento em Latin-1 não pode virar caractere de substituição."""
    corpo = json.dumps({"nome": "Processo nº 12"}, ensure_ascii=False).encode("latin-1")
    resposta = Resposta(conteudo=corpo, url="https://exemplo", status=200, tipo="application/json")

    assert resposta.json() == {"nome": "Processo nº 12"}


def test_json_invalido_levanta_falha_de_rede_explicada():
    """Texto que não é JSON vira erro em português, não exceção crua."""
    resposta = Resposta(
        conteudo=b"<html>manutencao</html>", url="https://exemplo", status=200, tipo=""
    )

    with pytest.raises(FalhaDeRede, match="não é JSON válido"):
        resposta.json()


def test_texto_cai_para_latin1_quando_utf8_falha():
    """CSV antigo do governo continua legível para o parser."""
    resposta = Resposta(
        conteudo="Ação".encode("latin-1"), url="https://exemplo", status=200, tipo=""
    )

    assert resposta.texto() == "Ação"


def test_numero_aceita_string_com_ponto_e_devolve_zero_quando_vazio():
    """A API mistura tipos; campo vazio não pode derrubar a soma."""
    assert transferegov._numero("850093.0") == 850093.0
    assert transferegov._numero(12) == 12.0
    assert transferegov._numero(None) == 0.0
    assert transferegov._numero("texto") == 0.0


def test_resumir_saude_conta_aprovadas_e_soma_planejamento():
    """Só situação que começa com "aprov" conta como aprovada."""
    itens = [
        {
            "situacao_proposta": "Aprovada",
            "vl_total_planejamento_gastos": "100.50",
            "id_programa": 1,
        },
        {
            "situacao_proposta": "APROVADO",
            "vl_total_planejamento_gastos": "50",
            "id_programa": 2,
        },
        {"situacao_proposta": "Em análise", "vl_total_planejamento_gastos": "10", "id_programa": 1},
    ]

    resumo = transferegov._resumir_saude(itens)

    assert resumo["propostas"] == 3
    assert resumo["aprovadas"] == 2
    assert resumo["valor_planejado"] == 160.5
    assert resumo["programas"] == 2


def test_resumir_cidades_usa_global_e_repasse():
    """Proposta discricionária tem valor global e valor de repasse separados."""
    itens = [
        {
            "sit_proposta": "Proposta Aprovada",
            "vl_global_prop": "1000.00",
            "vl_repasse_prop": "900.00",
        },
        {"sit_proposta": "Em Análise", "vl_global_prop": "500.00", "vl_repasse_prop": None},
    ]

    resumo = transferegov._resumir_cidades(itens)

    assert resumo["propostas"] == 2
    assert resumo["aprovadas"] == 1
    assert resumo["valor_planejado"] == 1500.0
    assert resumo["valor_repasse"] == 900.0


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "subsidios.db")


@pytest.fixture
def cliente(app):
    return TestClient(app)


def semear(app) -> None:
    """Banco pequeno com programas, propostas por UF e uma semana de dengue."""
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    db.registrar_fonte(
        conexao,
        id_fonte="transferegov_subsidios",
        nome="Transferegov",
        orgao="Ministério da Gestão",
        url="https://api-publica.transferegov.gestao.gov.br",
        periodo_referencia="2026",
    )
    conexao.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('SP', 'São Paulo', '35')")
    conexao.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('PE', 'Pernambuco', '26')")
    for semana, casos in enumerate([8, 9, 10, 9, 11, 10, 9, 12, 30], start=1):
        conexao.execute(
            "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
            "VALUES ('SP', 2026, ?, ?, 'transferegov_subsidios')",
            (semana, casos),
        )
    conexao.execute(
        "INSERT INTO subsidio_programa (id_programa, orgao, nome, situacao, modalidade, "
        "data_disponibilizacao, fonte_id) VALUES (1, 'MINISTERIO DAS CIDADES', "
        "'Novo PAC - Drenagem', 'DISPONIBILIZADO', 'TERMO DE COMPROMISSO', '2026-01-02', "
        "'transferegov_subsidios')"
    )
    conexao.execute(
        "INSERT INTO subsidio_uf (uf, ano, eixo, propostas, aprovadas, valor_planejado, "
        "valor_repasse, programas, fonte_id) VALUES ('SP', 2026, 'saude_fundo_a_fundo', "
        "10, 9, 1500000.0, 0.0, 2, 'transferegov_subsidios')"
    )
    conexao.execute(
        "INSERT INTO subsidio_uf (uf, ano, eixo, propostas, aprovadas, valor_planejado, "
        "valor_repasse, programas, fonte_id) VALUES ('PE', 2026, 'cidades_discricionaria', "
        "3, 1, 500000.0, 400000.0, 1, 'transferegov_subsidios')"
    )
    conexao.commit()
    epidemiologia.calcular_alertas(conexao)
    conexao.close()


def test_rota_subsidios_soma_por_eixo_e_uf(app, cliente):
    """A tela precisa dos totais e da lista por UF no mesmo JSON."""
    semear(app)

    corpo = cliente.get("/api/subsidios?ano=2026").json()

    assert corpo["ano"] == 2026
    assert corpo["totais"]["programas"] == 1
    assert corpo["totais"]["propostas"] == 13
    assert corpo["totais"]["aprovadas"] == 10
    assert corpo["totais"]["valor_planejado"] == 2000000.0
    assert corpo["totais"]["ufs_com_proposta"] == 2
    assert [linha["uf"] for linha in corpo["ufs"]][0] == "SP"
    assert corpo["aviso_metodologico"].startswith("Propostas apresentadas")


def test_rota_subsidios_vazia_nao_inventa_zero(app, cliente):
    """Ano sem coleta devolve listas vazias e totais zerados — sem erro 500."""
    semear(app)

    corpo = cliente.get("/api/subsidios?ano=2019").json()

    assert corpo["ufs"] == []
    assert corpo["totais"]["propostas"] == 0


def test_servico_resumo_le_o_que_esta_no_banco(app):
    """O serviço é a camada que a rota usa; conferir direto isola a query."""
    semear(app)
    conexao = db.conectar(app.state.caminho_banco)

    resumo = subsidios.resumo(conexao, 2026)

    assert resumo["totais"]["valor_repasse"] == 400000.0
    assert {programa["nome"] for programa in resumo["programas"]} == {"Novo PAC - Drenagem"}
    conexao.close()


def test_rota_resumo_nacional_conta_casos_e_anomalias(app, cliente):
    """O topo da página mostra casos da semana, UFs com dado e anomalias."""
    semear(app)

    corpo = cliente.get("/api/resumo").json()

    assert corpo["casos_semana"] == 30
    assert corpo["ufs_com_dado"] == 1
    assert corpo["ufs_total"] == 2
    assert corpo["ufs_anomalia"] == 1
    assert corpo["ufs_anomalia_12s"] == 1
    assert corpo["semana"] == 9
