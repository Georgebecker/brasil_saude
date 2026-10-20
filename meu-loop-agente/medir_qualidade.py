#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""medir_qualidade.py - mede a divida de rastreabilidade do Brasil Saude.

Problema que este arquivo resolve: um painel publico so merece confianca se todo
numero publicado disser de onde veio, a que periodo se refere e quando foi
validado. Este medidor confere essa promessa item por item.

Analogia: e o conferente da portaria. Para cada indicador da regua, ele pede
quatro documentos:

    1. publicado - o indicador existe na lista publicada pelo painel;
    2. fonte     - informa o orgao de origem e um endereco https;
    3. periodo   - informa o periodo de referencia (ano, mes ou data);
    4. validado  - tem valor numerico e data de validacao (AAAA-MM-DD).

A divida e a fracao de documentos que faltam:

    divida = itens sem documento / total de itens

    - 0.0000 significa catalogo 100% rastreavel (meta);
    - 1.0000 significa que nada foi publicado ainda (ponto de partida honesto).

Arquivos envolvidos:
    - regua (do humano):      meu-loop-agente/referencias_indicadores.json
    - publicacao (do painel): data/processed/indicadores.json

Formato esperado da publicacao:

    {
      "atualizado_em": "AAAA-MM-DD",
      "indicadores": [
        {
          "id": "mortalidade_infantil",
          "valor": 12.4,
          "unidade": "por 1.000 nascidos vivos",
          "periodo_referencia": "2024",
          "fonte": "DATASUS/SIM",
          "url_fonte": "https://datasus.saude.gov.br/",
          "validado_em": "AAAA-MM-DD"
        }
      ]
    }

Uso:
    python meu-loop-agente/medir_qualidade.py
    python meu-loop-agente/medir_qualidade.py --detalhe

Saida lida pelo verificador (regex de config_loop.json):
    divida_rastreabilidade: 1.0000

Sem emojis de proposito: compatibilidade com o console do Windows.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

# O medidor mora em meu-loop-agente/; a raiz do projeto e a pasta acima.
RAIZ_DO_MEDIDOR = Path(__file__).resolve().parent
RAIZ_DO_PROJETO = RAIZ_DO_MEDIDOR.parent

ARQUIVO_REGUA = RAIZ_DO_MEDIDOR / "referencias_indicadores.json"
ARQUIVO_PUBLICACAO = RAIZ_DO_PROJETO / "data" / "processed" / "indicadores.json"

# Os quatro documentos exigidos de cada indicador. A ordem tambem e a ordem
# em que o detalhe e impresso, para o relatorio ficar estavel entre execucoes.
ITENS = ("publicado", "fonte", "periodo", "validado")


def ler_json(caminho: Path, descricao: str) -> dict:
    """Le um arquivo JSON e devolve o dicionario.

    Devolve dicionario vazio quando o arquivo nao existe (situacao normal: o
    painel ainda nao publicou nada). Se o arquivo existe mas esta corrompido,
    para com codigo 1, porque medir em cima de dado quebrado seria pior do que
    nao medir.
    """
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        print(
            "ERRO: " + descricao + " nao e um JSON valido (" + str(caminho) + "): " + str(erro),
            file=sys.stderr,
        )
        raise SystemExit(1)


def carregar_regua() -> list:
    """Devolve a lista de indicadores que o painel deve publicar.

    A regua e o contrato do humano: se ela estiver vazia, nao existe metrica
    possivel, entao o medidor para e avisa em vez de inventar um numero.
    """
    dados = ler_json(ARQUIVO_REGUA, "a regua de indicadores")
    indicadores = dados.get("indicadores", []) if isinstance(dados, dict) else []
    if not isinstance(indicadores, list) or not indicadores:
        print("ERRO: a regua nao tem indicadores; confira " + str(ARQUIVO_REGUA), file=sys.stderr)
        raise SystemExit(1)
    return indicadores


def carregar_publicados() -> dict:
    """Indexa os indicadores publicados pelo id.

    O dicionario e como uma lista telefônica: procura-se pelo id e se chega ao
    registro completo. Quando o mesmo id aparece duas vezes, vale o ultimo
    registro (o mais recente na ordem do arquivo).
    """
    dados = ler_json(ARQUIVO_PUBLICACAO, "a publicacao de indicadores")
    registros = dados.get("indicadores", []) if isinstance(dados, dict) else []
    if not isinstance(registros, list):
        print(
            "ERRO: data/processed/indicadores.json precisa de uma lista 'indicadores'.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    publicados = {}
    for registro in registros:
        if isinstance(registro, dict) and registro.get("id"):
            publicados[str(registro["id"])] = registro
    return publicados


def texto_preenchido(valor) -> bool:
    """Verdadeiro quando o campo tem texto util.

    Vale como texto util qualquer coisa escrita, menos os disfarces de vazio
    que aparecem em planilhas: "-", "N/D" e "TBD".
    """
    if not isinstance(valor, str):
        return False
    limpo = valor.strip().lower()
    return bool(limpo) and limpo not in {"-", "n/d", "nd", "tbd", "null", "none"}


def data_valida(valor) -> bool:
    """Verdadeiro quando o texto esta no formato AAAA-MM-DD e existe no calendario.

    O corte em 10 caracteres aceita "2026-10-20T12:00:00" e ignora a hora,
    porque para auditoria o que importa e o dia da validacao.
    """
    if not texto_preenchido(valor):
        return False
    try:
        date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        return False
    return True


def valor_numerico(valor) -> bool:
    """Verdadeiro para numero finito (descarta texto, nulo, NaN e infinito)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return False
    return math.isfinite(valor)


def conferir(registro) -> dict:
    """Confere os quatro documentos de um indicador e devolve o resultado.

    Se o indicador nao foi publicado, todos os itens ficam falsos de uma vez:
    sem o numero, nao ha o que rastrear.
    """
    if registro is None:
        return {item: False for item in ITENS}

    endereco = str(registro.get("url_fonte", "")).strip().lower()
    return {
        "publicado": True,
        "fonte": texto_preenchido(registro.get("fonte")) and endereco.startswith("https://"),
        "periodo": texto_preenchido(registro.get("periodo_referencia")),
        "validado": valor_numerico(registro.get("valor")) and data_valida(registro.get("validado_em")),
    }


def main() -> int:
    """Roda a conferencia, imprime o resumo e devolve o codigo de saida."""
    parser = argparse.ArgumentParser(
        description="Mede a divida de rastreabilidade dos indicadores do Brasil Saude."
    )
    parser.add_argument(
        "--detalhe",
        action="store_true",
        help="mostra, indicador por indicador, quais documentos estao faltando",
    )
    args = parser.parse_args()

    regua = carregar_regua()
    publicados = carregar_publicados()

    total_de_itens = 0
    itens_atendidos = 0
    linhas_de_detalhe = []

    for indicador in regua:
        if not isinstance(indicador, dict) or not indicador.get("id"):
            print("ERRO: indicador sem 'id' na regua.", file=sys.stderr)
            return 1

        identificador = str(indicador["id"])
        resultado = conferir(publicados.get(identificador))
        faltando = [item for item in ITENS if not resultado[item]]

        total_de_itens += len(ITENS)
        itens_atendidos += len(ITENS) - len(faltando)

        nome = indicador.get("nome", identificador)
        if faltando:
            linhas_de_detalhe.append(
                "  - " + identificador + " (" + nome + "): falta " + ", ".join(faltando)
            )
        else:
            linhas_de_detalhe.append("  + " + identificador + " (" + nome + "): completo")

    # Divisao protegida: a regua nunca vem vazia (carregar_regua ja garantiu),
    # mas a checagem evita um erro obscuro se o arquivo mudar no futuro.
    divida = 1.0 if total_de_itens == 0 else 1.0 - (itens_atendidos / total_de_itens)

    print("Brasil Saude - conferencia de rastreabilidade")
    print("Indicadores na regua: " + str(len(regua)))
    print("Itens atendidos: " + str(itens_atendidos) + "/" + str(total_de_itens))
    if publicados:
        print("Indicadores com algum registro publicado: " + str(len(publicados)))
    else:
        print("Nenhum indicador publicado ainda (data/processed/indicadores.json ausente).")

    if args.detalhe:
        print("Detalhe:")
        for linha in linhas_de_detalhe:
            print(linha)

    # Esta e a unica linha que o verificador le. Formato fixo, virgula decimal
    # convertida na leitura, para nao depender do idioma do Windows.
    print("divida_rastreabilidade: " + format(divida, ".4f"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
