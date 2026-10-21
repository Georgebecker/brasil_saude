"""Banco SQLite do Brasil Saúde: esquema, conexão e registro de proveniência.

Analogia: o banco é o **cartório** do painel. Nenhum número entra sem que o
cartório registre de onde veio, quando foi coletado e qual foi o período de
referência. Se o dado não tem "escritura" (a linha na tabela `fonte`), ele não
é publicado — é assim que a rastreabilidade deixa de ser promessa e passa a
ser uma restrição do próprio banco.

Por que SQLite: o projeto é local e didático. Um arquivo único cabe no backup,
não exige servidor e ensina o essencial de modelagem. A migração para
PostgreSQL/Oracle está documentada em `docs/dba/migracao_enterprise.md`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from src import config

# DDL em um único lugar: quem cria o banco e quem testa leem o mesmo texto.
# `IF NOT EXISTS` permite rodar a inicialização quantas vezes for preciso.
ESQUEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS fonte (
    id                  TEXT PRIMARY KEY,
    nome                TEXT NOT NULL,
    orgao               TEXT NOT NULL,
    url                 TEXT NOT NULL,
    licenca             TEXT,
    periodo_referencia  TEXT,
    coletado_em         TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('ok', 'parcial', 'falhou')),
    detalhe             TEXT
);

CREATE TABLE IF NOT EXISTS uf (
    sigla           TEXT PRIMARY KEY,
    nome            TEXT NOT NULL,
    codigo_ibge     TEXT NOT NULL UNIQUE,
    regiao          TEXT,
    populacao       INTEGER,
    populacao_ano   INTEGER
);

CREATE TABLE IF NOT EXISTS municipio (
    codigo_ibge  TEXT PRIMARY KEY,
    nome         TEXT NOT NULL,
    uf           TEXT NOT NULL REFERENCES uf(sigla),
    latitude     REAL,
    longitude    REAL,
    populacao    INTEGER,
    populacao_ano INTEGER
);

-- Casos agregados por UF e semana epidemiológica (SEM_NOT do SINAN).
CREATE TABLE IF NOT EXISTS caso_semana (
    uf          TEXT NOT NULL REFERENCES uf(sigla),
    ano         INTEGER NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    semana      INTEGER NOT NULL CHECK (semana BETWEEN 1 AND 53),
    casos       INTEGER NOT NULL CHECK (casos >= 0),
    fonte_id    TEXT NOT NULL REFERENCES fonte(id),
    PRIMARY KEY (uf, ano, semana, fonte_id)
);

CREATE TABLE IF NOT EXISTS caso_municipio_semana (
    municipio_codigo TEXT NOT NULL REFERENCES municipio(codigo_ibge),
    ano              INTEGER NOT NULL,
    semana           INTEGER NOT NULL,
    casos            INTEGER NOT NULL CHECK (casos >= 0),
    fonte_id         TEXT NOT NULL REFERENCES fonte(id),
    PRIMARY KEY (municipio_codigo, ano, semana, fonte_id)
);

-- Repasses federais de saúde. `valor` em reais, `data` em ISO (AAAA-MM-DD).
CREATE TABLE IF NOT EXISTS repasse (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    uf                TEXT NOT NULL REFERENCES uf(sigla),
    municipio_codigo  TEXT REFERENCES municipio(codigo_ibge),
    data              TEXT NOT NULL,
    valor             REAL NOT NULL,
    descricao         TEXT NOT NULL,
    fonte_id          TEXT NOT NULL REFERENCES fonte(id),
    url_fonte         TEXT NOT NULL,
    coletado_em       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_repasse_uf_data ON repasse (uf, data);

CREATE TABLE IF NOT EXISTS estacao (
    codigo            TEXT PRIMARY KEY,
    nome              TEXT NOT NULL,
    uf                TEXT NOT NULL REFERENCES uf(sigla),
    municipio_codigo  TEXT REFERENCES municipio(codigo_ibge),
    latitude          REAL,
    longitude         REAL,
    tipo              TEXT,
    situacao          TEXT,
    fonte_id          TEXT NOT NULL REFERENCES fonte(id)
);

-- Clima diário por estação do INMET. Nulos são permitidos de propósito:
-- estação sem sensor de chuva é um dado ausente real, não um zero.
CREATE TABLE IF NOT EXISTS clima_dia (
    estacao           TEXT NOT NULL,
    uf                TEXT NOT NULL REFERENCES uf(sigla),
    municipio_codigo  TEXT REFERENCES municipio(codigo_ibge),
    data              TEXT NOT NULL,
    precipitacao_mm   REAL,
    temp_max_c        REAL,
    temp_min_c        REAL,
    fonte_id          TEXT NOT NULL REFERENCES fonte(id),
    coletado_em       TEXT NOT NULL,
    PRIMARY KEY (estacao, data)
);

CREATE TABLE IF NOT EXISTS alerta_ears (
    uf            TEXT NOT NULL REFERENCES uf(sigla),
    ano           INTEGER NOT NULL,
    semana        INTEGER NOT NULL,
    metodo        TEXT NOT NULL,
    observado     INTEGER NOT NULL,
    esperado      REAL NOT NULL,
    limite        REAL NOT NULL,
    anomalo       INTEGER NOT NULL CHECK (anomalo IN (0, 1)),
    calculado_em  TEXT NOT NULL,
    PRIMARY KEY (uf, ano, semana, metodo)
);

-- Responsáveis legais: governador e secretário estadual de saúde.
CREATE TABLE IF NOT EXISTS responsavel (
    uf              TEXT NOT NULL REFERENCES uf(sigla),
    cargo           TEXT NOT NULL,
    nome            TEXT NOT NULL,
    url_fonte       TEXT NOT NULL,
    atualizado_em   TEXT NOT NULL,
    PRIMARY KEY (uf, cargo)
);

CREATE TABLE IF NOT EXISTS log_coleta (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte_id      TEXT NOT NULL,
    iniciado_em   TEXT NOT NULL,
    concluido_em  TEXT,
    status        TEXT NOT NULL,
    registros     INTEGER NOT NULL DEFAULT 0,
    mensagem      TEXT
);

-- Programas federais disponibilizados para propostas (oferta de subsídio).
CREATE TABLE IF NOT EXISTS subsidio_programa (
    id_programa             INTEGER PRIMARY KEY,
    orgao                   TEXT NOT NULL,
    nome                    TEXT NOT NULL,
    situacao                TEXT,
    modalidade              TEXT,
    data_disponibilizacao   TEXT,
    inicio_recebimento      TEXT,
    fim_recebimento         TEXT,
    fonte_id                TEXT NOT NULL REFERENCES fonte(id)
);

-- Aproveitamento por UF: propostas apresentadas e valores planejados.
CREATE TABLE IF NOT EXISTS subsidio_uf (
    uf               TEXT NOT NULL REFERENCES uf(sigla),
    ano              INTEGER NOT NULL,
    eixo             TEXT NOT NULL,  -- saude_fundo_a_fundo | cidades_discricionaria
    propostas        INTEGER NOT NULL DEFAULT 0,
    aprovadas        INTEGER NOT NULL DEFAULT 0,
    valor_planejado  REAL NOT NULL DEFAULT 0,
    valor_repasse    REAL NOT NULL DEFAULT 0,
    programas        INTEGER NOT NULL DEFAULT 0,
    fonte_id         TEXT NOT NULL REFERENCES fonte(id),
    PRIMARY KEY (uf, ano, eixo)
);

CREATE TABLE IF NOT EXISTS meta (
    chave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);

-- Caixa de saída do protótipo de e-mail multi-tenant. Não guarda destinatário
-- (dado pessoal) nem envia nada: registra o que seria enviado e para qual UF.
CREATE TABLE IF NOT EXISTS email_outbox (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    uf          TEXT NOT NULL REFERENCES uf(sigla),
    papel       TEXT NOT NULL,
    assunto     TEXT NOT NULL,
    corpo       TEXT NOT NULL,
    criado_em   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'enfileirado'
);
"""


def agora_utc() -> str:
    """Instante atual em ISO-8601 UTC — o mesmo formato em todo o projeto."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def caminho_banco() -> Path:
    """Caminho do arquivo SQLite, criando a pasta se ela não existir."""
    caminho = config.CAMINHO_BANCO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


def conectar(caminho: Path | None = None) -> sqlite3.Connection:
    """Abre uma conexão já configurada (linhas como dicionário e FK ligadas).

    `row_factory = sqlite3.Row` é o que permite escrever `linha["casos"]` em vez
    de decorar a posição da coluna — menos erro, mais leitura.
    """
    conexao = sqlite3.connect(caminho or caminho_banco(), check_same_thread=False)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def inicializar(conexao: sqlite3.Connection | None = None) -> None:
    """Cria as tabelas que faltarem. Idempotente: pode rodar em todo start."""
    fechar = conexao is None
    conexao = conexao or conectar()
    try:
        conexao.executescript(ESQUEMA)
        _garantir_colunas(conexao)
        conexao.commit()
    finally:
        if fechar:
            conexao.close()


def _garantir_colunas(conexao: sqlite3.Connection) -> None:
    """Migração leve: acrescenta coluna nova em banco que já existia.

    SQLite não tem "ADD COLUMN IF NOT EXISTS"; por isso conferimos o esquema
    antes. É o suficiente para um banco local — migração de verdade (com
    versionamento) está no roadmap de `docs/dba/migracao_enterprise.md`.
    """
    colunas = {linha["name"] for linha in conexao.execute("PRAGMA table_info(uf)")}
    if "populacao" not in colunas:
        conexao.execute("ALTER TABLE uf ADD COLUMN populacao INTEGER")
    if "populacao_ano" not in colunas:
        conexao.execute("ALTER TABLE uf ADD COLUMN populacao_ano INTEGER")

    colunas_municipio = {linha["name"] for linha in conexao.execute("PRAGMA table_info(municipio)")}
    if "populacao" not in colunas_municipio:
        conexao.execute("ALTER TABLE municipio ADD COLUMN populacao INTEGER")
    if "populacao_ano" not in colunas_municipio:
        conexao.execute("ALTER TABLE municipio ADD COLUMN populacao_ano INTEGER")


@contextmanager
def transacao(caminho: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Transação "tudo ou nada": grava o lote inteiro ou não grava nada.

    Sem isso, uma falha no meio de uma coleta deixaria metade dos municípios
    dentro do banco — e o painel mostraria um total que nunca existiu.
    """
    conexao = conectar(caminho)
    try:
        # Garante o esquema: escrever num banco recém-criado não pode falhar
        # por falta de tabela. `inicializar` é idempotente e barato.
        inicializar(conexao)
        with conexao:
            yield conexao
    finally:
        conexao.close()


def registrar_fonte(
    conexao: sqlite3.Connection,
    *,
    id_fonte: str,
    nome: str,
    orgao: str,
    url: str,
    licenca: str | None = None,
    periodo_referencia: str | None = None,
    status: str = "ok",
    detalhe: str | None = None,
) -> None:
    """Grava/atualiza a "escritura" de uma fonte (insert or replace)."""
    conexao.execute(
        """
        INSERT INTO fonte (id, nome, orgao, url, licenca, periodo_referencia,
                           coletado_em, status, detalhe)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome = excluded.nome,
            orgao = excluded.orgao,
            url = excluded.url,
            licenca = excluded.licenca,
            periodo_referencia = excluded.periodo_referencia,
            coletado_em = excluded.coletado_em,
            status = excluded.status,
            detalhe = excluded.detalhe
        """,
        (id_fonte, nome, orgao, url, licenca, periodo_referencia, agora_utc(), status, detalhe),
    )


def registrar_log(
    conexao: sqlite3.Connection,
    *,
    fonte_id: str,
    iniciado_em: str,
    status: str,
    registros: int = 0,
    mensagem: str | None = None,
) -> None:
    """Histórico de coletas: o que rodou, quando e com que resultado."""
    conexao.execute(
        """
        INSERT INTO log_coleta (fonte_id, iniciado_em, concluido_em, status, registros, mensagem)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (fonte_id, iniciado_em, agora_utc(), status, registros, mensagem),
    )


def definir_meta(conexao: sqlite3.Connection, chave: str, valor: str) -> None:
    """Pares chave/valor para estados simples (última coleta, versão do esquema)."""
    conexao.execute(
        "INSERT INTO meta (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, valor),
    )


def ler_meta(conexao: sqlite3.Connection, chave: str, padrao: str | None = None) -> str | None:
    """Lê um par chave/valor; devolve `padrao` quando a chave ainda não existe."""
    linha = conexao.execute("SELECT valor FROM meta WHERE chave = ?", (chave,)).fetchone()
    return linha["valor"] if linha else padrao
