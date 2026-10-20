"""Matriz de permissões em código — a mesma que está em `docs/arquitetura`.

Por que a matriz vive no código **e** na documentação: o documento explica, o
código decide. Um teste (`tests/test_autorizacao.py`) garante que os dois não
divergem nos casos que importam.

Analogia: é o crachá do prédio. O papel `publico` entra no saguão (dados
agregados); o `gestor_estadual` abre a sala do seu estado; o `admin` abre
qualquer sala. Ninguém abre a sala do outro por engano.
"""

from __future__ import annotations

from src.auth.modelos import Usuario

# Cada permissão é uma frase curta que dá para citar na tela de auditoria.
PERMISSOES: dict[str, frozenset[str]] = {
    "publico": frozenset({"ver_agregado"}),
    "gestor_estadual": frozenset(
        {"ver_agregado", "ver_detalhe_do_proprio_estado", "enfileirar_alerta"}
    ),
    "admin": frozenset(
        {
            "ver_agregado",
            "ver_detalhe_do_proprio_estado",
            "ver_detalhe_de_qualquer_estado",
            "enfileirar_alerta",
            "administrar_usuarios",
            "ver_logs",
        }
    ),
}


def permissoes(usuario: Usuario) -> frozenset[str]:
    """Permissões efetivas do usuário."""
    return PERMISSOES.get(usuario.papel, frozenset())


def tem_permissao(usuario: Usuario, permissao: str) -> bool:
    """Pergunta simples: este usuário tem esta permissão?"""
    return permissao in permissoes(usuario)


def pode_ver_detalhe(usuario: Usuario, uf: str) -> bool:
    """Decide se o usuário pode abrir o detalhe de uma UF.

    Regra de ouro: **gestor só vê o próprio estado**. O `admin` vê todos; o
    público não vê detalhe (só o agregado que já está no painel aberto).
    """
    uf = uf.upper()
    if usuario.papel == "admin":
        return True
    if usuario.papel == "gestor_estadual":
        return usuario.uf == uf
    return False


def pode_enfileirar_alerta(usuario: Usuario, uf: str) -> bool:
    """Alerta por e-mail segue a mesma fronteira territorial do detalhe."""
    return pode_ver_detalhe(usuario, uf)
