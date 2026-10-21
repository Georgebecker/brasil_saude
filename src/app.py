"""Aplicação FastAPI do Brasil Saúde: API + painel estático.

Por que não há tela de login e por que a API é somente leitura: o painel
publica dado agregado de saúde, sem informação pessoal. Não existe usuário
para autenticar — e criar autenticação sem necessidade só aumentaria a
superfície de ataque.

Segurança aplicada (COSEGI/DICA):
- CORS restrito a origens locais (o frontend é servido pela mesma origem);
- limite de corpo por requisição (1 MB) — a API só recebe GET;
- nenhuma exceção bruta chega ao navegador: erros viram JSON com mensagem;
- cada número exibido carrega URL da fonte e data de coleta.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from src import config, db
from src.rede import FalhaDeRede
from src.rotas import (
    clima,
    contexto,
    epidemiologia,
    fontes,
    gestao,
    orcamento,
    queimadas,
    rede,
    responsaveis,
    subsidios,
)

PASTA_FRONTEND = config.RAIZ / "frontend"
LIMITE_CORPO_BYTES = 1_000_000


class LimiteDeCorpoMiddleware:
    """Recusa requisições com corpo acima do limite (proteção simples e barata)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            tamanho = dict(scope.get("headers") or []).get(b"content-length")
            if tamanho and int(tamanho) > LIMITE_CORPO_BYTES:
                resposta = JSONResponse(
                    {"detail": "corpo da requisição acima de 1 MB"}, status_code=413
                )
                await resposta(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app(caminho_banco: Path | None = None) -> FastAPI:
    """Monta a aplicação. Receber o caminho do banco facilita o teste isolado."""
    app = FastAPI(
        title="Brasil Saúde",
        version="1.0.0",
        description=(
            "Painel público de vigilância de arboviroses, repasses federais e clima. "
            "Todo número traz fonte, período e data de coleta."
        ),
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.caminho_banco = caminho_banco or db.caminho_banco()

    # Garante esquema mesmo quando alguém sobe o servidor num banco novo.
    conexao = db.conectar(app.state.caminho_banco)
    db.inicializar(conexao)
    conexao.close()

    origens = os.getenv(
        "BRASIL_SAUDE_CORS",
        "http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origem.strip() for origem in origens if origem.strip()],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_middleware(LimiteDeCorpoMiddleware)

    for roteador in (
        epidemiologia.roteador,
        orcamento.roteador,
        clima.roteador,
        responsaveis.roteador,
        gestao.roteador,
        subsidios.roteador,
        contexto.roteador,
        queimadas.roteador,
        rede.roteador,
        fontes.roteador,
    ):
        app.include_router(roteador)

    @app.exception_handler(FalhaDeRede)
    async def falha_de_rede(_: Request, erro: FalhaDeRede) -> JSONResponse:
        """Fonte fora do ar vira 503 com recado claro — nunca stack trace."""
        return JSONResponse(status_code=503, content={"detail": str(erro)})

    if PASTA_FRONTEND.exists():
        app.mount("/static", StaticFiles(directory=PASTA_FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    def inicio() -> FileResponse:
        """Entrega o painel. A tela é HTML/CSS/JS puro, sem etapa de build."""
        return FileResponse(PASTA_FRONTEND / "index.html")

    @app.get("/privacidade", include_in_schema=False)
    def privacidade() -> FileResponse:
        """Política de tratamento de dados (LGPD) — página estática."""
        return FileResponse(PASTA_FRONTEND / "privacidade.html")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        """Sem ícone próprio: devolve 204 para não poluir o log com 404."""
        return Response(status_code=204)

    return app


app = create_app()
