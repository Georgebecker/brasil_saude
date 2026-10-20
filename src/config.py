"""Configuração central do Brasil Saúde: caminhos e variáveis do `.env`.

Analogia: este módulo é o balcão de informações do projeto. Em vez de cada
arquivo decorar onde ficam os dados, todos perguntam aqui — e a resposta é
sempre a mesma.

Regra de segurança: valor de chave nunca mora em arquivo versionado. O `.env`
é local e não vai para o git; o `.env.example` é só o modelo, com os campos
vazios ou comentados.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# A raiz do projeto é a pasta acima de `src/`. `resolve()` transforma o caminho
# relativo em absoluto, então o código funciona de qualquer pasta de trabalho.
RAIZ = Path(__file__).resolve().parent.parent

# `override=False` de propósito: variável de ambiente do Windows manda mais que
# o arquivo. Assim uma chave definida na máquina não é sobrescrita pelo `.env`.
load_dotenv(RAIZ / ".env", override=False)


def caminho_do_projeto(variavel: str, padrao: str) -> Path:
    """Devolve um caminho absoluto a partir do `.env` (ou do padrão).

    O `.env` guarda caminhos relativos (`data/raw`). Aqui eles são resolvidos
    contra a raiz do projeto, como quem completa um endereço a partir do CEP:
    o resto do caminho já está no arquivo, só falta o "bairro".
    """
    valor = os.getenv(variavel, padrao).strip() or padrao
    caminho = Path(valor)
    return caminho if caminho.is_absolute() else RAIZ / caminho


NOME_DO_PROJETO = os.getenv("PROJETO_NOME", "brasil_saude")

# --- Pastas do fluxo bruto -> validado -> usado -----------------------------
PASTA_RAW = caminho_do_projeto("PASTA_DADOS_RAW", "data/raw")
PASTA_PROCESSED = caminho_do_projeto("PASTA_DADOS_PROCESSED", "data/processed")
PASTA_DESCARTADOS = RAIZ / "data" / "descartados"
PASTA_NOTEBOOKS = caminho_do_projeto("PASTA_NOTEBOOKS", "notebooks")
PASTA_SAIDAS = caminho_do_projeto("PASTA_SAIDAS", "saidas")

# --- Arquivos e banco -------------------------------------------------------
ARQUIVO_INDICADORES = PASTA_PROCESSED / "indicadores.json"
BANCO_URL = os.getenv("DB_URL", "sqlite:///data/brasil_saude.db")

# Semente fixa: o mesmo dado + o mesmo código precisam dar o mesmo número.
SEMENTE = int(os.getenv("SEMENTE_ALEATORIA", "42"))
