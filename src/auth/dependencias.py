"""Dependências FastAPI de identidade.

O cabeçalho esperado é ``Authorization: Bearer <token>``. Sem cabeçalho, a
requisição é anônima — e as rotas públicas continuam funcionando. Rotas de
gestão exigem token.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from src.auth.modelos import Usuario
from src.auth.tokens import TokenInvalido, ler_token


def usuario_atual(
    authorization: Annotated[str | None, Header()] = None,
) -> Usuario | None:
    """Lê o token, se houver. Token inválido é erro 401, não silêncio."""
    if not authorization:
        return None
    esquema, _, token = authorization.partition(" ")
    if esquema.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="use Authorization: Bearer <token>")
    try:
        return ler_token(token)
    except TokenInvalido as erro:
        raise HTTPException(status_code=401, detail=str(erro)) from erro


def exigir_usuario(
    usuario: Annotated[Usuario | None, Depends(usuario_atual)],
) -> Usuario:
    """Exige identidade válida para rotas de gestão."""
    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail="rota de gestão exige autenticação (protótipo: /api/auth/demo-token)",
        )
    return usuario
