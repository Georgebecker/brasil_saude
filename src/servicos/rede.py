"""Estado da rede local: onde o painel está acessível e como rearmar.

Por que isso existe: o painel é visto pelo celular na mesma rede Wi-Fi. Quando o
roteador troca o IP da máquina, o endereço que estava salvo no celular deixa de
responder e parece que o painel "caiu". O indicador da tela mostra o estado real
e o endereço atual; o botão de rearme pede ao vigia (`scripts/vigia_rede.py`)
que reinicie o servidor.

Limite declarado: o navegador não pode reiniciar processo nenhum. Quem reinicia
é o vigia, que observa o arquivo-sinal em `data/rede/rearmar`. Sem o vigia
rodando, o botão apenas reconfere o estado e devolve o endereço atual.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA_REDE = RAIZ / "data" / "rede"
SINAL_REARME = PASTA_REDE / "rearmar"
ESTADO = PASTA_REDE / "vigia.json"

INICIADO_EM = time.time()
VALIDADE_BATIMENTO = 10  # segundos: batimento mais velho que isso = vigia parado


def ip_local() -> str | None:
    """IPv4 privado usado para sair da máquina (é o endereço que o celular usa).

    Abrir um socket UDP para um endereço externo não envia pacote nenhum, mas
    faz o sistema escolher a interface de saída — e é isso que queremos saber.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
            sonda.settimeout(0.5)
            sonda.connect(("8.8.8.8", 80))
            endereco = sonda.getsockname()[0]
    except OSError:
        return None
    try:
        return endereco if ipaddress.ip_address(endereco).is_private else None
    except ValueError:
        return None


def vigia_vivo() -> bool:
    """O vigia está batendo? Lê o batimento que ele grava a cada ciclo.

    Verificar processo por PID no Windows exigiria API nativa a cada requisição.
    Um arquivo com data de atualização resolve o mesmo problema sem privilégio
    especial e sem depender de plataforma.
    """
    try:
        dados = json.loads(ESTADO.read_text(encoding="utf-8"))
        quando = datetime.fromisoformat(dados["atualizado_em"])
    except (OSError, ValueError, KeyError):
        return False
    return (datetime.now(timezone.utc) - quando).total_seconds() < VALIDADE_BATIMENTO


def status(porta: int | None = None) -> dict:
    """Retrato honesto: se estamos respondendo, o serviço está no ar por definição."""
    endereco = ip_local()
    porta = porta or 8000
    return {
        "online": True,
        "ip_local": endereco,
        "porta": porta,
        "endereco_local": f"http://127.0.0.1:{porta}",
        "endereco_rede": f"http://{endereco}:{porta}" if endereco else None,
        "segundos_no_ar": int(time.time() - INICIADO_EM),
        "vigia_ativo": vigia_vivo(),
        "verificado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def gravar_batimento(pid_servidor: int | None = None) -> None:
    """Grava o batimento que a API lê para dizer se o vigia está vivo."""
    try:
        PASTA_REDE.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(
            json.dumps(
                {
                    "pid_vigia": os.getpid(),
                    "pid_servidor": pid_servidor,
                    "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def sinalizar_rearme() -> bool:
    """Cria o arquivo-sinal que o vigia observa. Sem vigia, nada acontece."""
    try:
        PASTA_REDE.mkdir(parents=True, exist_ok=True)
        SINAL_REARME.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    except OSError:
        return False
    return True
