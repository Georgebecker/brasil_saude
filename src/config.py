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
import secrets
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


def _caminho_do_banco() -> Path:
    """Resolve o arquivo SQLite a partir de `BRASIL_SAUDE_DB`.

    Por que uma variável própria: o modelo da base trazia `DB_URL`, herdado de
    um projeto de estudos. Aqui o banco tem nome fixo e previsível para o
    backup, sem depender de um `.env` que o agente não pode alterar.
    """
    valor = os.getenv("BRASIL_SAUDE_DB", "data/brasil_saude.db").strip() or "data/brasil_saude.db"
    caminho = Path(valor)
    return caminho if caminho.is_absolute() else RAIZ / caminho


CAMINHO_BANCO = _caminho_do_banco()

# --- Autenticação (protótipo da Fase 2) -------------------------------------
# O segredo assina os tokens de demonstração. Em produção ele viria do cofre
# de segredos; aqui, da variável de ambiente ou de um arquivo local ignorado.


def _segredo_de_auth() -> str:
    """Lê o segredo do ambiente ou cria um local (nunca versionado)."""
    valor = os.getenv("BRASIL_SAUDE_AUTH_SECRET", "").strip()
    if valor:
        return valor
    arquivo = RAIZ / "data" / ".auth_secret"
    if arquivo.exists():
        return arquivo.read_text(encoding="utf-8").strip()
    novo = secrets.token_urlsafe(48)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(novo, encoding="utf-8")
    return novo


SEGREDO_AUTH = _segredo_de_auth()

# A emissão de token de demonstração só existe quando esta variável vale "1".
# Sem ela, o endpoint responde 404 — o painel público não ganha porta dos fundos.
AUTH_DEMO = os.getenv("BRASIL_SAUDE_AUTH_DEMO", "0") == "1"
VALIDADE_TOKEN_SEGUNDOS = int(os.getenv("BRASIL_SAUDE_TOKEN_TTL", "3600"))

# --- Rede -------------------------------------------------------------------
# Um único User-Agent identifica o projeto nas APIs públicas e facilita a vida
# de quem administra esses serviços: se algo abusar, eles sabem a quem avisar.
# Precisa ser ASCII puro: acento em cabeçalho HTTP faz o IBGE responder 400.
USER_AGENT = os.getenv(
    "BRASIL_SAUDE_USER_AGENT",
    "BrasilSaude/1.0 (painel publico de vigilancia; contato: repositorio GitHub)",
)
TEMPO_LIMITE_SEGUNDOS = float(os.getenv("BRASIL_SAUDE_TIMEOUT", "60"))
TENTATIVAS_REDE = int(os.getenv("BRASIL_SAUDE_TENTATIVAS", "4"))

# Semente fixa: o mesmo dado + o mesmo código precisam dar o mesmo número.
SEMENTE = int(os.getenv("SEMENTE_ALEATORIA", "42"))
