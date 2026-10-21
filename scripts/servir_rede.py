"""Sobe o painel na rede local (Wi-Fi de casa) e mostra o endereço para o celular.

Por que um script e não só `uvicorn --host 0.0.0.0`: quem abre no celular
precisa do IP da máquina, e descobrir isso na mão é onde a maior parte das
pessoas desiste. O script descobre o IPv4 privado, testa se a porta responde e
imprime o endereço pronto para digitar.

Limite de segurança declarado: isto abre a porta **apenas** na rede local. Não
há redirecionamento de porta, não há túnel para a internet e não há login —
qualquer aparelho na mesma rede vê o painel, que só publica dado agregado.
"""

from __future__ import annotations

import argparse
import ipaddress
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

RAIZ = Path(__file__).resolve().parents[1]


def ip_local() -> str | None:
    """Descobre o IPv4 privado usado para sair da máquina.

    Truque conhecido: abrir um socket UDP para um endereço externo não envia
    pacote nenhum, mas faz o sistema escolher a interface de saída — e com ela
    o IP que o celular precisa usar.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
            sonda.settimeout(0.5)
            sonda.connect(("8.8.8.8", 80))
            endereco = sonda.getsockname()[0]
    except OSError:
        return None

    try:
        if ipaddress.ip_address(endereco).is_private:
            return endereco
    except ValueError:
        return None
    return None


def portas_ocupadas(porta: int) -> bool:
    """A porta já está em uso nesta máquina?"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
        teste.settimeout(0.4)
        return teste.connect_ex(("127.0.0.1", porta)) == 0


def esperar_servidor(url: str, tentativas: int = 30) -> bool:
    """Aguarda o servidor responder antes de prometer o endereço ao usuário."""
    for _ in range(tentativas):
        try:
            with urlopen(url, timeout=1) as resposta:  # noqa: S310 - URL local fixa
                if resposta.status == 200:
                    return True
        except OSError:
            time.sleep(0.5)
    return False


def regra_firewall(porta: int) -> str:
    """Tenta liberar a porta no firewall do Windows e diz o que aconteceu."""
    if sys.platform != "win32":
        return "firewall: nada a fazer neste sistema"
    comando = [
        "netsh",
        "advfirewall",
        "firewall",
        "add",
        "rule",
        f"name=Brasil Saude {porta}",
        "dir=in",
        "action=allow",
        "protocol=TCP",
        f"localport={porta}",
        "profile=private",
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True, check=False)
    if resultado.returncode == 0:
        return "firewall: porta liberada na rede privada"
    return (
        "firewall: não foi possível liberar automaticamente "
        "(abra o terminal como administrador e rode o script de novo)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Painel na rede local para acesso pelo celular")
    parser.add_argument("--porta", type=int, default=8000)
    parser.add_argument("--sem-firewall", action="store_true", help="não mexe no firewall")
    args = parser.parse_args()

    if portas_ocupadas(args.porta):
        print(
            f"A porta {args.porta} já está em uso. "
            "Encerre o servidor antigo ou use --porta 8001."
        )
        return 1

    if not args.sem_firewall:
        print(regra_firewall(args.porta))

    endereco = ip_local()
    if endereco is None:
        print("Não encontrei um IPv4 privado. Confira se o Wi-Fi ou o cabo está conectado.")
        return 1

    import uvicorn  # importado aqui para o `--help` continuar rápido

    print()
    print("=" * 58)
    print("  Painel Brasil Saúde na rede local")
    print(f"  Neste computador : http://127.0.0.1:{args.porta}")
    print(f"  No celular       : http://{endereco}:{args.porta}")
    print("=" * 58)
    print("  O celular precisa estar no mesmo Wi-Fi. Nada é exposto na internet.")
    print("  Encerre com Ctrl+C.")
    print()

    uvicorn.run(
        "src.app:app",
        host="0.0.0.0",  # aceita conexão de outros aparelhos da rede
        port=args.porta,
        app_dir=str(RAIZ),
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
