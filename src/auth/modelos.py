"""Modelos de identidade do protótipo.

Papéis previstos no contrato da Fase 2:

- ``publico`` — vê apenas dado agregado (o painel aberto);
- ``gestor_estadual`` — vê o detalhe do **seu** estado;
- ``admin`` — vê qualquer estado e administra o serviço.

O usuário guarda a UF de vínculo, não o nome da pessoa. Para o protótipo basta:
a política decide por papel + UF.
"""

from __future__ import annotations

from dataclasses import dataclass

PAPEIS = ("publico", "gestor_estadual", "admin")


@dataclass(frozen=True)
class Usuario:
    """Identidade mínima para a decisão de autorização."""

    id: str
    papel: str
    uf: str | None = None

    def __post_init__(self) -> None:
        if self.papel not in PAPEIS:
            raise ValueError(f"papel desconhecido: {self.papel}")
        if self.papel == "gestor_estadual" and not self.uf:
            raise ValueError("gestor_estadual exige UF de vínculo")
