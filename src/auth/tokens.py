"""Tokens assinados do protótipo (HMAC-SHA256).

Isso **não** substitui OAuth2/OIDC do gov.br. Serve para provar a política de
acesso sem montar um servidor de identidade: o token carrega papel e UF e é
assinado com um segredo local. Quem não tem o segredo não forja um token — mas
não há login, senha, MFA nem revogação. Está documentado como protótipo.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from src import config
from src.auth.modelos import Usuario


class TokenInvalido(ValueError):
    """Token ausente, adulterado, expirado ou malformado."""


def _b64_codificar(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _b64_decodificar(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _assinar(payload: str, segredo: str) -> str:
    return _b64_codificar(hmac.new(segredo.encode(), payload.encode(), hashlib.sha256).digest())


def criar_token(
    usuario: Usuario,
    *,
    segredo: str | None = None,
    validade_segundos: int | None = None,
) -> str:
    """Emite um token com papel, UF e prazo de validade."""
    segredo = segredo or config.SEGREDO_AUTH
    validade = validade_segundos or config.VALIDADE_TOKEN_SEGUNDOS
    corpo = {
        "sub": usuario.id,
        "papel": usuario.papel,
        "uf": usuario.uf,
        "exp": int(time.time()) + validade,
    }
    payload = _b64_codificar(json.dumps(corpo, separators=(",", ":")).encode())
    return f"v1.{payload}.{_assinar(payload, segredo)}"


def ler_token(token: str, *, segredo: str | None = None) -> Usuario:
    """Valida assinatura e prazo e devolve o usuário."""
    segredo = segredo or config.SEGREDO_AUTH
    partes = token.split(".")
    if len(partes) != 3 or partes[0] != "v1":
        raise TokenInvalido("formato de token inválido")
    _, payload, assinatura = partes
    if not hmac.compare_digest(assinatura, _assinar(payload, segredo)):
        raise TokenInvalido("assinatura inválida")
    try:
        corpo = json.loads(_b64_decodificar(payload))
    except (ValueError, json.JSONDecodeError) as erro:
        raise TokenInvalido("conteúdo do token ilegível") from erro
    if int(corpo.get("exp", 0)) < int(time.time()):
        raise TokenInvalido("token expirado")
    try:
        return Usuario(id=str(corpo["sub"]), papel=corpo["papel"], uf=corpo.get("uf"))
    except (KeyError, ValueError) as erro:
        raise TokenInvalido("token sem papel válido") from erro
