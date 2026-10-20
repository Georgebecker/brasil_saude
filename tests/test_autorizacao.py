"""Testes do protótipo de autorização (Fase 2).

O critério de sucesso é literal: **um `gestor_estadual` não pode acessar dados
de outro estado**. O teste prova o 403 e também que o `admin` e o público se
comportam como a matriz manda.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src import config, db
from src.app import create_app
from src.auth import politicas
from src.auth.modelos import Usuario
from src.auth.tokens import TokenInvalido, criar_token, ler_token

SEGREDO = "segredo-de-teste-nao-usar-em-producao"


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / "auth.db")
    conexao = db.conectar(app.state.caminho_banco)
    for sigla, nome, codigo in (("SP", "São Paulo", "35"), ("RJ", "Rio de Janeiro", "33")):
        conexao.execute(
            "INSERT INTO uf (sigla, nome, codigo_ibge) VALUES (?, ?, ?)", (sigla, nome, codigo)
        )
    conexao.commit()
    conexao.close()
    return app


@pytest.fixture
def cliente(app):
    return TestClient(app)


def cabecalho(usuario: Usuario) -> dict[str, str]:
    return {"Authorization": f"Bearer {criar_token(usuario, segredo=SEGREDO)}"}


@pytest.fixture(autouse=True)
def segredo_fixo(monkeypatch):
    """Usa um segredo conhecido no teste — nunca o arquivo local do projeto."""
    monkeypatch.setattr(config, "SEGREDO_AUTH", SEGREDO)


def test_token_adulterado_e_recusado():
    """Trocar um caractere da assinatura invalida o token."""
    token = criar_token(Usuario(id="x", papel="admin"), segredo=SEGREDO)
    with pytest.raises(TokenInvalido):
        ler_token(token[:-2] + "xx", segredo=SEGREDO)


def test_gestor_sem_uf_e_rejeitado_no_modelo():
    """Gestor sem vínculo é erro de cadastro, não usuário válido."""
    with pytest.raises(ValueError, match="UF de vínculo"):
        Usuario(id="x", papel="gestor_estadual")


def test_rota_de_gestao_exige_autenticacao(cliente):
    """Sem token, 401 — o painel público não expõe detalhe protegido."""
    assert cliente.get("/api/gestao/estados/SP/resumo").status_code == 401


def test_gestor_ve_o_proprio_estado(cliente):
    """SP pode abrir SP."""
    resposta = cliente.get("/api/gestao/estados/SP/resumo", headers=cabecalho(
        Usuario(id="g-sp", papel="gestor_estadual", uf="SP")
    ))
    assert resposta.status_code == 200
    assert resposta.json()["acesso"]["papel"] == "gestor_estadual"


def test_gestor_nao_ve_outro_estado(cliente):
    """O critério de sucesso da Fase 2: gestor de SP recebe 403 em RJ."""
    resposta = cliente.get("/api/gestao/estados/RJ/resumo", headers=cabecalho(
        Usuario(id="g-sp", papel="gestor_estadual", uf="SP")
    ))
    assert resposta.status_code == 403
    assert "não tem acesso" in resposta.json()["detail"]


def test_admin_ve_qualquer_estado(cliente):
    """Admin atravessa a fronteira territorial de propósito."""
    resposta = cliente.get("/api/gestao/estados/RJ/resumo", headers=cabecalho(
        Usuario(id="a", papel="admin")
    ))
    assert resposta.status_code == 200


def test_publico_nao_ve_detalhe(cliente):
    """Papel público fica no agregado; detalhe é 403."""
    resposta = cliente.get("/api/gestao/estados/SP/resumo", headers=cabecalho(
        Usuario(id="p", papel="publico")
    ))
    assert resposta.status_code == 403


def test_email_do_gestor_usa_a_propria_uf(app, cliente):
    """Sem UF no corpo, o alerta vai para o vínculo do gestor."""
    resposta = cliente.post(
        "/api/gestao/notificacoes/email",
        headers=cabecalho(Usuario(id="g-sp", papel="gestor_estadual", uf="SP")),
        json={"assunto": "Alerta semanal", "corpo": "Resumo da semana."},
    )
    assert resposta.status_code == 201
    assert resposta.json()["uf"] == "SP"

    conexao = db.conectar(app.state.caminho_banco)
    linha = conexao.execute("SELECT uf, status FROM email_outbox").fetchone()
    conexao.close()
    assert dict(linha) == {"uf": "SP", "status": "enfileirado"}


def test_email_para_outro_estado_e_bloqueado(app, cliente):
    """Gestor de SP não enfileira alerta para RJ."""
    resposta = cliente.post(
        "/api/gestao/notificacoes/email",
        headers=cabecalho(Usuario(id="g-sp", papel="gestor_estadual", uf="SP")),
        json={"assunto": "Alerta", "corpo": "Conteúdo", "uf": "RJ"},
    )
    assert resposta.status_code == 403

    conexao = db.conectar(app.state.caminho_banco)
    total = conexao.execute("SELECT COUNT(*) AS total FROM email_outbox").fetchone()["total"]
    conexao.close()
    assert total == 0


def test_demo_token_desligado_por_padrao(cliente, monkeypatch):
    """Sem a variável de ambiente, a emissão de token responde 404."""
    monkeypatch.setattr(config, "AUTH_DEMO", False)
    resposta = cliente.post("/api/auth/demo-token", json={"papel": "admin"})
    assert resposta.status_code == 404


def test_matriz_de_permissoes_do_documento_bate_com_o_codigo():
    """Se a matriz mudar no código, este teste obriga a revisar a documentação."""
    assert politicas.PERMISSOES["publico"] == {"ver_agregado"}
    assert "ver_detalhe_do_proprio_estado" in politicas.PERMISSOES["gestor_estadual"]
    assert "ver_detalhe_de_qualquer_estado" in politicas.PERMISSOES["admin"]
    assert not politicas.tem_permissao(
        Usuario(id="p", papel="publico"), "ver_detalhe_do_proprio_estado"
    )
