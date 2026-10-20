"""Rotas de gestão e identidade (protótipo da Fase 2).

O painel público continua aberto e **sem login**. Estas rotas existem para
demonstrar a fronteira de acesso:

- ``POST /api/auth/demo-token`` — emite token de demonstração (só quando
  ``BRASIL_SAUDE_AUTH_DEMO=1``);
- ``GET /api/auth/quem-sou`` — devolve papel, UF e permissões;
- ``GET /api/gestao/estados/{uf}/resumo`` — detalhe protegido;
- ``POST /api/gestao/notificacoes/email`` — enfileira alerta para a própria UF.

Sem o token, as rotas de gestão respondem 401. Com token de gestor de outro
estado, respondem 403 — o teste automatizado prova esse bloqueio.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src import config
from src.auth import politicas
from src.auth.dependencias import exigir_usuario, usuario_atual
from src.auth.modelos import Usuario
from src.auth.tokens import criar_token
from src.rotas.dependencias import obter_conexao
from src.rotas.epidemiologia import _validar_uf
from src.servicos import clima, epidemiologia, orcamento

roteador = APIRouter(prefix="/api", tags=["gestao"])

Conexao = Annotated[sqlite3.Connection, Depends(obter_conexao)]
Autenticado = Annotated[Usuario, Depends(exigir_usuario)]


class PedidoToken(BaseModel):
    """Pedido de token de demonstração."""

    papel: Literal["publico", "gestor_estadual", "admin"]
    uf: str | None = Field(default=None, description="UF de vínculo (obrigatória para gestor)")


class PedidoAlerta(BaseModel):
    """Conteúdo do alerta a enfileirar."""

    assunto: str = Field(min_length=3, max_length=120)
    corpo: str = Field(min_length=3, max_length=5000)
    uf: str | None = Field(default=None, description="Só o admin escolhe UF; gestor usa a própria")


@roteador.post("/auth/demo-token", include_in_schema=False)
def demo_token(pedido: PedidoToken) -> dict:
    """Emite token assinado. Porta dos fundos **desligada** por padrão."""
    if not config.AUTH_DEMO:
        raise HTTPException(
            status_code=404,
            detail="emissão de token de demonstração desativada (BRASIL_SAUDE_AUTH_DEMO=0)",
        )
    uf = _validar_uf(pedido.uf) if pedido.uf else None
    if pedido.papel == "gestor_estadual" and not uf:
        raise HTTPException(status_code=422, detail="gestor_estadual exige UF")
    usuario = Usuario(id=f"demo-{pedido.papel}", papel=pedido.papel, uf=uf)
    return {
        "token": criar_token(usuario),
        "papel": usuario.papel,
        "uf": usuario.uf,
        "expira_em_segundos": config.VALIDADE_TOKEN_SEGUNDOS,
        "aviso": "protótipo: token local; em produção, OAuth2/OIDC gov.br com MFA",
    }


@roteador.get("/auth/quem-sou")
def quem_sou(usuario: Annotated[Usuario | None, Depends(usuario_atual)]) -> dict:
    """Identidade efetiva da requisição (anônima quando não há token)."""
    if usuario is None:
        return {"autenticado": False, "papel": "publico", "permissoes": []}
    return {
        "autenticado": True,
        "id": usuario.id,
        "papel": usuario.papel,
        "uf": usuario.uf,
        "permissoes": sorted(politicas.permissoes(usuario)),
    }


def _exigir_acesso_ao_estado(usuario: Usuario, uf: str) -> None:
    """Bloqueia gestor de outro estado com mensagem que não vaza dado."""
    if not politicas.pode_ver_detalhe(usuario, uf):
        raise HTTPException(
            status_code=403,
            detail=(
                f"papel {usuario.papel} não tem acesso ao detalhe de {uf}"
                + (f" (vínculo: {usuario.uf})" if usuario.uf else "")
            ),
        )


@roteador.get("/gestao/estados/{uf}/resumo")
def resumo_protegido(uf: str, usuario: Autenticado, conexao: Conexao) -> dict:
    """Detalhe estadual protegido: série, orçamento, clima e responsáveis."""
    validada = _validar_uf(uf)
    _exigir_acesso_ao_estado(usuario, validada)
    responsaveis = conexao.execute(
        "SELECT cargo, nome, url_fonte, atualizado_em FROM responsavel WHERE uf = ?",
        (validada,),
    ).fetchall()
    return {
        "uf": validada,
        "acesso": {
            "papel": usuario.papel,
            "vinculo": usuario.uf,
            "permissao": "ver_detalhe_do_proprio_estado"
            if usuario.papel == "gestor_estadual"
            else "ver_detalhe_de_qualquer_estado",
        },
        "serie": epidemiologia.serie_da_uf(conexao, validada),
        "repasses": orcamento.resumo(conexao, validada),
        "clima": clima.alertas_por_incidencia(conexao, validada),
        "responsaveis": [dict(linha) for linha in responsaveis],
    }


@roteador.post("/gestao/notificacoes/email", status_code=201)
def enfileirar_email(pedido: PedidoAlerta, usuario: Autenticado, conexao: Conexao) -> dict:
    """Enfileira alerta para a **própria** UF (protótipo sem envio real).

    O corpo não aceita destinatário: e-mail de terceiro é dado pessoal e o
    protótipo não o guarda. O “endereço” é o vínculo do usuário com a UF.
    """
    if usuario.papel == "publico":
        raise HTTPException(status_code=403, detail="papel público não enfileira alerta")

    uf_pedida = _validar_uf(pedido.uf) if pedido.uf else None
    if usuario.papel == "gestor_estadual":
        if uf_pedida and uf_pedida != usuario.uf:
            raise HTTPException(
                status_code=403,
                detail=f"gestor de {usuario.uf} não enfileira alerta para {uf_pedida}",
            )
        uf = usuario.uf
    else:
        if not uf_pedida:
            raise HTTPException(status_code=422, detail="admin precisa informar a UF")
        uf = uf_pedida

    if not politicas.pode_enfileirar_alerta(usuario, uf):
        raise HTTPException(status_code=403, detail="sem permissão para enfileirar alerta")

    criado = datetime.now(UTC).replace(microsecond=0).isoformat()
    cursor = conexao.execute(
        "INSERT INTO email_outbox (uf, papel, assunto, corpo, criado_em, status) "
        "VALUES (?, ?, ?, ?, ?, 'enfileirado')",
        (uf, usuario.papel, pedido.assunto, pedido.corpo, criado),
    )
    conexao.commit()
    return {
        "id": cursor.lastrowid,
        "uf": uf,
        "status": "enfileirado",
        "entrega": (
            "protótipo: nenhum e-mail é enviado; "
            "ver docs/arquitetura/integracao_servicos.md"
        ),
    }
