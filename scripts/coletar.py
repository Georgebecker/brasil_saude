"""Coleta os dados públicos do painel e grava no SQLite.

Uso:

    python scripts/coletar.py base          # UFs, municípios, população, malha
    python scripts/coletar.py dengue        # série semanal por UF (InfoDengue)
    python scripts/coletar.py capitais      # série municipal das capitais
    python scripts/coletar.py orcamento     # repasses da função Saúde (12 meses)
    python scripts/coletar.py clima         # estações INMET + série diária
    python scripts/coletar.py tudo          # tudo na ordem certa + EARS

Cada etapa imprime um JSON com o resultado real da coleta. Nada é estimado:
se uma fonte falhar, o número de falhas aparece na saída e fica registrado em
`log_coleta`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src import config, db  # noqa: E402
from src.fontes import ibge, infodengue, inmet, responsaveis, transferegov, transparencia  # noqa: E402
from src.rede import ClienteHTTP  # noqa: E402
from src.servicos import epidemiologia  # noqa: E402


def etapa_base(args: argparse.Namespace) -> dict:
    """IBGE: divisão territorial, população e malha do mapa."""
    cliente = ClienteHTTP()
    ufs, municipios, populacao, ano = ibge.coletar(cliente)
    resultado = ibge.gravar(ufs, municipios, populacao, ano, caminho=args.banco)
    try:
        caminho = ibge.baixar_malha(cliente)
        resultado["malha"] = caminho.name
    except Exception as erro:  # noqa: BLE001
        resultado["malha"] = f"falhou: {erro}"
    return resultado


def etapa_dengue(args: argparse.Namespace) -> dict:
    """SINAN agregado por UF, via InfoDengue."""
    return infodengue.coletar(meses=args.meses, caminho_banco=args.banco)


def etapa_capitais(args: argparse.Namespace) -> dict:
    """Série municipal das capitais (alertcity)."""
    return infodengue.coletar_capitais(caminho_banco=args.banco)


def etapa_orcamento(args: argparse.Namespace) -> dict:
    """Transferências federais da função Saúde, por UF e mês."""
    meses = transparencia.meses_recentes(args.meses)
    return transparencia.coletar(meses, caminho_banco=args.banco)


def etapa_responsaveis(args: argparse.Namespace) -> dict:
    """Governadores estaduais (curadoria versionada, com fonte)."""
    return responsaveis.coletar(caminho_banco=args.banco)


def etapa_clima(args: argparse.Namespace) -> dict:
    """Estações do INMET e série diária de chuva/temperatura."""
    estacoes = inmet.coletar_estacoes(caminho_banco=args.banco)
    clima = inmet.coletar_clima(caminho_banco=args.banco)
    return {**estacoes, **clima}


def etapa_subsidios(args: argparse.Namespace) -> dict:
    """Programas federais e propostas por UF (Transferegov)."""
    return transferegov.coletar(args.ano, caminho_banco=args.banco)


def etapa_ears(args: argparse.Namespace) -> dict:
    """Recalcula os alertas EARS a partir dos casos já gravados."""
    caminho = args.banco or db.caminho_banco()
    conexao = db.conectar(caminho)
    try:
        total = epidemiologia.calcular_alertas(conexao)
    finally:
        conexao.close()
    return {"alertas": total}


ETAPAS = {
    "base": etapa_base,
    "responsaveis": etapa_responsaveis,
    "dengue": etapa_dengue,
    "capitais": etapa_capitais,
    "orcamento": etapa_orcamento,
    "subsidios": etapa_subsidios,
    "clima": etapa_clima,
    "ears": etapa_ears,
}

ORDEM_COMPLETA = [
    "base", "responsaveis", "dengue", "capitais", "orcamento", "subsidios", "clima", "ears"
]


def executar(nome: str, args: argparse.Namespace) -> dict:
    """Roda uma etapa medindo o tempo — o relógio é dado do relatório."""
    inicio = time.perf_counter()
    resultado = ETAPAS[nome](args)
    resultado["segundos"] = round(time.perf_counter() - inicio, 1)
    return resultado


def main() -> int:
    """Monta os argumentos e executa as etapas pedidas."""
    parser = argparse.ArgumentParser(description="Coleta de dados do Brasil Saúde")
    parser.add_argument("etapa", choices=[*ORDEM_COMPLETA, "tudo"])
    parser.add_argument("--meses", type=int, default=12, help="janela de meses (orçamento)")
    parser.add_argument("--ano", type=int, default=2026, help="ano dos subsídios")
    parser.add_argument("--banco", type=Path, default=None, help="caminho do SQLite")
    parser.add_argument("--json", action="store_true", help="imprime só o JSON final")
    args = parser.parse_args()

    caminho = args.banco or config.CAMINHO_BANCO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = db.conectar(caminho)
    db.inicializar(conexao)
    conexao.close()

    etapas = ORDEM_COMPLETA if args.etapa == "tudo" else [args.etapa]
    relatorio: dict[str, dict] = {}
    for nome in etapas:
        if not args.json:
            print(f"[{nome}] coletando...", flush=True)
        try:
            relatorio[nome] = executar(nome, args)
        except Exception as erro:  # noqa: BLE001 - o relatório precisa registrar
            relatorio[nome] = {"erro": f"{type(erro).__name__}: {erro}"}
        if not args.json:
            print(f"[{nome}] {json.dumps(relatorio[nome], ensure_ascii=False)}", flush=True)

    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    falhou = any("erro" in resultado for resultado in relatorio.values())
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
