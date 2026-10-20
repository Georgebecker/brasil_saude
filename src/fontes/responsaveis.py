"""Responsáveis legais: carrega a curadoria versionada em `src/dados`.

Por que curadoria e não scraping: a lista de gestores estaduais muda por
eleição, renúncia e nomeação, e cada portal estadual tem um layout. Raspar 27
sites a cada coleta seria frágil e poderia publicar nome errado — pior que não
publicar. O arquivo JSON é revisado à mão, com a data e a fonte da conferência.

O titular da Secretaria Estadual de Saúde ainda **não** é coletado: o CONASS
carrega a lista por JavaScript, sem endpoint público estável (ver NOTES.md).
O painel mostra o governador — responsável legal pelo SUS estadual — e o link
para o portal do estado, sem inventar o nome do secretário.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import config, db

FONTE_ID = "curadoria_responsaveis"
ARQUIVO = config.RAIZ / "src" / "dados" / "responsaveis.json"


def carregar(caminho: Path | None = None) -> dict:
    """Lê o JSON de curadoria; erro de formato precisa estourar, não passar."""
    caminho = caminho or ARQUIVO
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados.get("responsaveis"), list):
        raise ValueError("responsaveis.json sem a lista 'responsaveis'")
    return dados


def gravar(dados: dict, *, caminho: Path | None = None) -> int:
    """Substitui os responsáveis no banco em uma transação."""
    with db.transacao(caminho) as conexao:
        db.registrar_fonte(
            conexao,
            id_fonte=FONTE_ID,
            nome="Governadores estaduais (mandato 2023–2027)",
            orgao="Curadoria do projeto, com verificação em fonte pública",
            url=dados.get("_fonte_verificacao", "https://pt.wikipedia.org/"),
            licenca="Dados públicos",
            periodo_referencia="mandato 2023–2027",
            status="parcial",
            detalhe="titular da Secretaria Estadual de Saúde ainda não coletado",
        )
        conexao.execute("DELETE FROM responsavel")
        conexao.executemany(
            """
            INSERT INTO responsavel (uf, cargo, nome, url_fonte, atualizado_em)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    linha["uf"],
                    dados.get("_cargo", "Governador(a)"),
                    linha["nome"],
                    linha["url_fonte"],
                    db.agora_utc(),
                )
                for linha in dados["responsaveis"]
            ],
        )
        db.definir_meta(conexao, "responsaveis_atualizado_em", db.agora_utc())
    return len(dados["responsaveis"])


def coletar(*, caminho_banco: Path | None = None) -> dict[str, int]:
    """Carrega e grava; devolve a contagem para o relatório."""
    dados = carregar()
    total = gravar(dados, caminho=caminho_banco)
    return {"responsaveis": total, "ufs": len({linha["uf"] for linha in dados["responsaveis"]})}
