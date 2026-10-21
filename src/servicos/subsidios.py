"""Serviço de subsídios: oferta de programas e aproveitamento por UF.

A pergunta que a tela responde é dupla:

1. **O que o governo federal ofertou?** Programas disponibilizados em 2026 pelo
   Ministério da Saúde e pelo Ministério das Cidades.
2. **Quem aproveitou?** Quantas propostas cada estado apresentou, quantas foram
   aprovadas e quanto foi planejado.

O painel **não** afirma que a verba foi executada. Proposta aprovada é intenção
registrada; execução física e pagamento são outro dado (e outro módulo).
"""

from __future__ import annotations

import sqlite3

from src.fontes import transferegov

AVISO = (
    "Propostas apresentadas e aprovadas não significam obra entregue. "
    "Os valores são os planejados no momento da proposta; pagamento e execução "
    "dependem de outra fonte."
)


def resumo(conexao: sqlite3.Connection, ano: int) -> dict:
    """Programas ofertados + agregados por UF + totais do ano."""
    programas = transferegov.ofertas(conexao)
    linhas = transferegov.por_uf(conexao, ano)

    propostas = sum(linha["propostas"] for linha in linhas)
    aprovadas = sum(linha["aprovadas"] for linha in linhas)
    valor = sum(linha["valor_planejado"] for linha in linhas)
    repasse = sum(linha["valor_repasse"] for linha in linhas)

    return {
        "ano": ano,
        "programas": programas,
        "ufs": linhas,
        "totais": {
            "programas": len(programas),
            "propostas": propostas,
            "aprovadas": aprovadas,
            "valor_planejado": round(valor, 2),
            "valor_repasse": round(repasse, 2),
            "ufs_com_proposta": len({linha["uf"] for linha in linhas if linha["propostas"]}),
            "ufs_total": 27,
        },
        "aviso_metodologico": AVISO,
    }
