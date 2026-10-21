"""Vigia da rede local: mantém o painel no ar e honra o pedido de rearme da tela.

Por que um processo separado: o servidor não consegue reiniciar a si mesmo com
segurança. O vigia roda o servidor como filho, observa o arquivo-sinal
`data/rede/rearmar` e reinicia o filho quando a tela pede — ou quando ele morre.

Uso:
    python scripts/vigia_rede.py              # porta 8000
    python scripts/vigia_rede.py --porta 8080
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.servicos import rede  # noqa: E402 - precisa do sys.path acima

INTERVALO = 2.0
INICIADO = time.time()


def porta_livre(porta: int) -> bool:
    """Confere se dá para abrir a porta antes de prometer o endereço."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
        teste.settimeout(0.3)
        return teste.connect_ex(("127.0.0.1", porta)) != 0


def iniciar_servidor(porta: int) -> subprocess.Popen:
    """Sobe o uvicorn como processo filho, escutando em toda a rede local."""
    return subprocess.Popen(  # noqa: S603 - comando fixo, sem entrada do usuário
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.app:app",
            "--host",
            "0.0.0.0",  # noqa: S104 - rede doméstica, não internet
            "--port",
            str(porta),
        ],
        cwd=str(RAIZ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Mantém o painel no ar e rearma sob pedido")
    parser.add_argument("--porta", type=int, default=8000)
    args = parser.parse_args()

    rede.PASTA_REDE.mkdir(parents=True, exist_ok=True)
    if rede.SINAL_REARME.exists():
        rede.SINAL_REARME.unlink()

    # Instância única: o batimento recente prova que outro vigia está vivo.
    # Sem isso, dois vigias disputam a porta e o painel "cai" sozinho.
    if rede.vigia_vivo():
        print("Já existe um vigia ativo (batimento recente). Encerrando este.")
        return 0

    if not porta_livre(args.porta):
        print(f"A porta {args.porta} já está ocupada. Pare o servidor antigo primeiro.")
        return 1

    endereco = rede.ip_local()
    print("=" * 60)
    print("  Vigia da rede local ativo")
    print(f"  Neste computador : http://127.0.0.1:{args.porta}")
    print(f"  No celular       : http://{endereco}:{args.porta}" if endereco else "  Sem IPv4")
    print("  Encerre com Ctrl+C.")
    print("=" * 60)

    servidor = iniciar_servidor(args.porta)
    print(f"  servidor iniciado (pid {servidor.pid})")
    rede.gravar_batimento(servidor.pid)
    falhas_seguidas = 0

    try:
        while True:
            time.sleep(INTERVALO)
            rede.gravar_batimento(servidor.pid)

            if rede.SINAL_REARME.exists():
                rede.SINAL_REARME.unlink()
                print("  rearme pedido pela tela: reiniciando o servidor…")
                servidor.terminate()
                servidor.wait(timeout=15)
                servidor = iniciar_servidor(args.porta)
                print(f"  servidor reiniciado (pid {servidor.pid})")

            if servidor.poll() is not None:
                # Subir em laço apertado transformaria "porta ocupada" em centenas
                # de processos mortos. Espera crescente e desiste depois de 5.
                falhas_seguidas += 1
                if falhas_seguidas >= 5:
                    print("  o servidor não sobe (porta ocupada?). Vigia encerrando.")
                    return 1
                espera = min(30, 2 ** falhas_seguidas)
                print(f"  servidor caiu (tentativa {falhas_seguidas}): "
                      f"subindo de novo em {espera}s…")
                time.sleep(espera)
                servidor = iniciar_servidor(args.porta)
                print(f"  servidor reiniciado (pid {servidor.pid})")
                continue

            if servidor.poll() is None and time.time() - INICIADO > 30:
                falhas_seguidas = 0
    except KeyboardInterrupt:
        print("\n  encerrando vigia e servidor…")
        servidor.terminate()
        try:
            servidor.wait(timeout=15)
        except subprocess.TimeoutExpired:
            servidor.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
