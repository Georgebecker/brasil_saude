"""Rotas do estado da rede local e do pedido de rearme."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.servicos import rede

roteador = APIRouter(prefix="/api", tags=["rede"])


@roteador.get("/rede")
def estado_da_rede(request: Request) -> dict:
    """Endereços em uso e há quanto tempo o serviço está no ar."""
    porta = request.url.port or 8000
    return rede.status(porta)


@roteador.post("/rede/rearmar")
def rearmar(request: Request) -> dict:
    """Pede ao vigia que reinicie o servidor e devolve o endereço recalculado.

    O IP é lido de novo a cada chamada: se o roteador trocou o endereço da
    máquina, a resposta já traz o novo, sem precisar reiniciar nada.
    """
    sinal = rede.sinalizar_rearme()
    estado = rede.status(request.url.port or 8000)
    return {
        **estado,
        "rearmado": sinal,
        "mensagem": (
            "Pedido de rearme registrado; o vigia reinicia o servidor em segundos."
            if estado["vigia_ativo"]
            else "Vigia não está rodando: o endereço foi reconferido, "
            "mas o processo não será reiniciado."
        ),
    }
