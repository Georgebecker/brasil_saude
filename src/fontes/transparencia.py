"""Repasses federais de saúde — Portal da Transparência (dados abertos).

Por que esta fonte: a API REST do Portal exige token e recusou nossas chamadas
(HTTP 401). O **download mensal** é público e não pede cadastro: um ZIP por
mês, com o CSV completo de transferências da União. Filtramos a **função 10
(Saúde)** e somamos por UF e por ação orçamentária.

Limites que a tela precisa dizer:

- o arquivo registra a **transferência** (empenho/pagamento) como lançada no
  SIAFI; não é “dinheiro que chegou ao posto de saúde”;
- o código do município no arquivo é **SIAFI**, não IBGE. Por isso o MVP
  agrega só por UF; cruzar com município exigiria uma tabela de conversão;
- saúde é a função 10; outras funções (saneamento, por exemplo) não entram.

O processamento é por streaming: o CSV tem ~200 MB descomprimido, e carregar
tudo na memória seria desperdício. Lemos linha a linha e descartamos o resto.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from src import config, db
from src.rede import ClienteHTTP

URL_MENSAL = "https://portaldatransparencia.gov.br/download-de-dados/transferencias/{mes}"
FONTE_ID = "portal_transparencia_transferencias"
FUNCAO_SAUDE = "10"

# Índices das colunas no CSV (0-based). Usar índice em vez de nome evita
# depender de acentuação: o arquivo vem em latin-1 e o cabeçalho muda de
# capitalização com o tempo.
COL_MES = 0
COL_UF = 3
COL_FUNCAO = 10
COL_ACAO = 18
COL_VALOR = 35


def meses_recentes(quantidade: int = 12, *, referencia: date | None = None) -> list[str]:
    """Lista os últimos `quantidade` meses no formato AAAAMM, do antigo ao novo."""
    referencia = referencia or date.today()
    meses: list[str] = []
    ano, mes = referencia.year, referencia.month
    for _ in range(quantidade):
        meses.append(f"{ano:04d}{mes:02d}")
        mes -= 1
        if mes == 0:
            mes = 12
            ano -= 1
    return list(reversed(meses))


def _valor(texto: str) -> float:
    """Converte '1.234.567,89' em 1234567.89; campo vazio vira 0."""
    limpo = texto.strip().replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def processar(caminho_zip: Path, mes: str) -> list[dict]:
    """Lê o ZIP e devolve linhas agregadas por (UF, ação) com função Saúde."""
    acumulado: dict[tuple[str, str], float] = defaultdict(float)
    contagem: dict[tuple[str, str], int] = defaultdict(int)

    with zipfile.ZipFile(caminho_zip) as pacote:
        nome = next((n for n in pacote.namelist() if n.lower().endswith(".csv")), None)
        if nome is None:
            raise ValueError(f"{caminho_zip.name}: nenhum CSV dentro do ZIP")
        with pacote.open(nome) as bruto:
            leitor = csv.reader(io.TextIOWrapper(bruto, encoding="latin-1"), delimiter=";")
            next(leitor, None)  # cabeçalho
            for linha in leitor:
                if len(linha) <= COL_VALOR or linha[COL_FUNCAO] != FUNCAO_SAUDE:
                    continue
                uf = linha[COL_UF].strip().upper()
                if not uf:
                    continue
                acao = linha[COL_ACAO].strip() or "Sem descrição"
                chave = (uf, acao)
                acumulado[chave] += _valor(linha[COL_VALOR])
                contagem[chave] += 1

    return [
        {
            "uf": uf,
            "mes": mes,
            "acao": acao,
            "valor": round(valor, 2),
            "quantidade": contagem[(uf, acao)],
        }
        for (uf, acao), valor in sorted(acumulado.items())
    ]


def baixar_mes(mes: str, cliente: ClienteHTTP, pasta: Path) -> Path:
    """Baixa o ZIP do mês para o cache local (não sobrescreve)."""
    return cliente.baixar(URL_MENSAL.format(mes=mes), pasta / f"transferencias_{mes}.zip")


def coletar(
    meses: list[str],
    *,
    cliente: ClienteHTTP | None = None,
    pasta_cache: Path | None = None,
    caminho_banco: Path | None = None,
) -> dict[str, int]:
    """Baixa, processa e grava os meses pedidos; meses ausentes são registrados.

    Um mês que ainda não foi publicado (404) não derruba a coleta inteira: ele
    entra no relatório como `ausente`, e a aba de orçamento mostra só o que
    existe — sem buraco preenchido a dedo.
    """
    cliente = cliente or ClienteHTTP()
    pasta_cache = pasta_cache or (config.PASTA_RAW / "transparencia")
    pasta_cache.mkdir(parents=True, exist_ok=True)

    total_linhas = 0
    publicados: list[str] = []
    ausentes: list[str] = []

    with db.transacao(caminho_banco) as conexao:
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID,
            nome="Transferências federais — função Saúde",
            orgao="Portal da Transparência (CGU) / SIAFI",
            url=URL_MENSAL.format(mes=meses[-1] if meses else ""),
            licenca="Dados abertos do Governo Federal",
            periodo_referencia=None,
            status="parcial",
            detalhe="coleta em andamento",
        )
        conexao.execute("DELETE FROM repasse WHERE fonte_id = ?", (FONTE_ID,))
        for mes in meses:
            iniciado = db.agora_utc()
            try:
                caminho = baixar_mes(mes, cliente, pasta_cache)
                linhas = processar(caminho, mes)
            except Exception as erro:  # noqa: BLE001 - falha de fonte é prevista
                ausentes.append(mes)
                db.registrar_log(
                    conexao,
                    fonte_id=FONTE_ID,
                    iniciado_em=iniciado,
                    status="falhou",
                    mensagem=f"{mes}: {type(erro).__name__}: {erro}"[:300],
                )
                continue

            conexao.executemany(
                """
                INSERT INTO repasse (uf, data, valor, descricao, fonte_id, url_fonte, coletado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        linha["uf"],
                        f"{mes[:4]}-{mes[4:6]}-01",
                        linha["valor"],
                        f"{linha['acao']} ({linha['quantidade']} lançamentos)",
                        FONTE_ID,
                        URL_MENSAL.format(mes=mes),
                        db.agora_utc(),
                    )
                    for linha in linhas
                    if linha["valor"] > 0
                ],
            )
            publicados.append(mes)
            total_linhas += len(linhas)
            db.registrar_log(
                conexao,
                fonte_id=FONTE_ID,
                iniciado_em=iniciado,
                status="ok",
                registros=len(linhas),
                mensagem=f"{mes}: {len(linhas)} combinações UF/ação",
            )

        status = "ok" if not ausentes else ("parcial" if publicados else "falhou")
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID,
            nome="Transferências federais — função Saúde",
            orgao="Portal da Transparência (CGU) / SIAFI",
            url=URL_MENSAL.format(mes=publicados[-1]) if publicados else URL_MENSAL.format(mes=""),
            licenca="Dados abertos do Governo Federal",
            periodo_referencia=f"{publicados[0]} a {publicados[-1]}" if publicados else None,
            status=status,
            detalhe=f"meses ausentes: {', '.join(ausentes)}" if ausentes else None,
        )
        db.definir_meta(conexao, "orcamento_coletado_em", db.agora_utc())

    return {
        "meses_publicados": len(publicados),
        "meses_ausentes": len(ausentes),
        "linhas": total_linhas,
    }


def gravar_em(conexao: sqlite3.Connection, linhas: list[dict]) -> int:
    """Grava linhas já processadas — usado por testes, sem rede."""
    conexao.executemany(
        """
        INSERT INTO repasse (uf, data, valor, descricao, fonte_id, url_fonte, coletado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                linha["uf"],
                f"{linha['mes'][:4]}-{linha['mes'][4:6]}-01",
                linha["valor"],
                linha["acao"],
                FONTE_ID,
                URL_MENSAL.format(mes=linha["mes"]),
                db.agora_utc(),
            )
            for linha in linhas
        ],
    )
    return len(linhas)
