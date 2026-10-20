"""Testes dos parsers das fontes: rede não entra aqui.

Cada teste usa uma amostra pequena, montada à mão, que reproduz o formato
real observado nas chamadas (inclusive os defeitos: acento em latin-1, campo
vazio, código de município inválido). Se o governo mudar o layout, o teste
continua passando — e a coleta real avisa.
"""

from __future__ import annotations

import csv
import io
import zipfile

from src.fontes import ibge, infodengue, inmet, responsaveis, transparencia


def test_infodengue_converte_domingo_em_semana_epidemiologica():
    """A data do arquivo é o domingo da semana; a SE segue a convenção brasileira."""
    texto = "dt_week,Casos\n2025-10-19,100\n2025-10-26,120\n2026-01-04,80\n"
    linhas = infodengue.normalizar_serie(texto, "sp")

    assert [(linha["ano"], linha["semana"], linha["casos"]) for linha in linhas] == [
        (2025, 43, 100),
        (2025, 44, 120),
        (2026, 1, 80),
    ]
    assert {linha["uf"] for linha in linhas} == {"SP"}


def test_infodengue_remove_apenas_a_ultima_semana_zerada():
    """Semana em curso vem zerada; cauda longa de zeros é dado e fica."""
    linhas = [
        {"uf": "SP", "ano": 2026, "semana": 40, "casos": 10},
        {"uf": "SP", "ano": 2026, "semana": 41, "casos": 0},
    ]
    restantes, removeu = infodengue.remover_semana_em_curso(linhas)

    assert removeu is True
    assert len(restantes) == 1

    zeros = [
        {"uf": "AC", "ano": 2026, "semana": 39, "casos": 0},
        {"uf": "AC", "ano": 2026, "semana": 40, "casos": 0},
    ]
    restantes, removeu = infodengue.remover_semana_em_curso(zeros)
    assert removeu is True
    assert len(restantes) == 1  # só a última saiu


def test_ibge_le_municipio_com_microrregiao_e_com_regiao_imediata():
    """O IBGE tem dois formatos; nenhum dos dois pode perder o município."""
    bruto = [
        {
            "id": 3550308,
            "nome": "São Paulo",
            "microrregiao": {"mesorregiao": {"UF": {"sigla": "SP"}}},
        },
        {
            "id": 5300108,
            "nome": "Brasília",
            "regiao-imediata": {"regiao-intermediaria": {"UF": {"sigla": "DF"}}},
        },
    ]
    linhas = ibge.normalizar_municipios(bruto)

    assert {linha["uf"] for linha in linhas} == {"SP", "DF"}


def test_inmet_extrai_municipio_do_wsi_e_descarta_codigo_invalido():
    """O código IBGE mora no WSI; município de outra UF é descartado."""
    bruto = [
        {
            "CD_ESTACAO": "A701",
            "DC_NOME": "BRASILIA",
            "SG_ESTADO": "DF",
            "VL_LATITUDE": "-15.79",
            "VL_LONGITUDE": "-47.93",
            "CD_WSI": "0-76-0-5300108000000000",
            "TP_ESTACAO": "Automatica",
            "CD_SITUACAO": "Operante",
            "FL_CAPITAL": "S",
        },
        {
            "CD_ESTACAO": "A999",
            "DC_NOME": "LUGAR ERRADO",
            "SG_ESTADO": "SP",
            "VL_LATITUDE": "-1",
            "VL_LONGITUDE": "-1",
            "CD_WSI": "0-76-0-3300100000000000",  # município do RJ
            "TP_ESTACAO": "Automatica",
            "CD_SITUACAO": "Operante",
            "FL_CAPITAL": "N",
        },
    ]
    linhas = inmet.normalizar_estacoes(bruto)

    por_codigo = {linha["codigo"]: linha for linha in linhas}
    assert por_codigo["A701"]["municipio_codigo"] == "5300108"
    assert por_codigo["A999"]["municipio_codigo"] is None


def test_inmet_prefere_capital_na_selecao(tmp_path):
    """Capital ganha da estação do interior, mesmo aparecendo depois."""
    estacoes = [
        {"codigo": "A1", "nome": "INTERIOR", "uf": "SP", "capital": False,
         "situacao": "Operante", "latitude": -22.0, "municipio_codigo": "3500000"},
        {"codigo": "A2", "nome": "CAPITAL", "uf": "SP", "capital": True,
         "situacao": "Operante", "latitude": -23.5, "municipio_codigo": "3550308"},
    ]
    escolhidas = inmet.selecionar_estacoes(estacoes, por_uf=1)

    assert [estacao["codigo"] for estacao in escolhidas] == ["A2"]


def _linha_transferencia(uf: str, funcao: str, acao: str, valor: str) -> list[str]:
    """Monta uma linha com 36 colunas nos índices que o parser usa."""
    linha = [""] * 36
    linha[0] = "202509"
    linha[3] = uf
    linha[10] = funcao
    linha[18] = acao
    linha[35] = valor
    return linha


def test_transparencia_soma_so_saude_e_ignora_outras_funcoes(tmp_path):
    """Função 10 entra; educação (12) fica fora; valor com vírgula é decimal."""
    arquivo = tmp_path / "transferencias_202509.zip"
    cabecalho = [""] * 36
    with zipfile.ZipFile(arquivo, "w") as pacote:
        texto = io.StringIO()
        escritor = csv.writer(texto, delimiter=";")
        escritor.writerow(cabecalho)
        escritor.writerow(_linha_transferencia("SP", "10", "TETO MAC", "1.000,50"))
        escritor.writerow(_linha_transferencia("SP", "10", "TETO MAC", "500,25"))
        escritor.writerow(_linha_transferencia("SP", "12", "ESCOLA", "9.999,00"))
        escritor.writerow(_linha_transferencia("RJ", "10", "TETO MAC", "300,00"))
        pacote.writestr("202509_Transferencias.csv", texto.getvalue().encode("latin-1"))

    linhas = transparencia.processar(arquivo, "202509")

    por_chave = {(linha["uf"], linha["acao"]): linha for linha in linhas}
    assert por_chave[("SP", "TETO MAC")]["valor"] == 1500.75
    assert por_chave[("SP", "TETO MAC")]["quantidade"] == 2
    assert por_chave[("RJ", "TETO MAC")]["valor"] == 300.0
    assert len(linhas) == 2


def test_meses_recentes_atravessa_a_virada_do_ano():
    """Janeiro precisa voltar para dezembro do ano anterior."""
    from datetime import date

    meses = transparencia.meses_recentes(3, referencia=date(2026, 1, 15))
    assert meses == ["202511", "202512", "202601"]


def test_responsaveis_cobrem_as_27_ufs_com_link():
    """Curadoria incompleta deixaria estados sem responsável na tela."""
    dados = responsaveis.carregar()
    ufs = {linha["uf"] for linha in dados["responsaveis"]}

    assert len(ufs) == 27
    assert all(linha["url_fonte"].startswith("http") for linha in dados["responsaveis"])
    assert all(linha["nome"].strip() for linha in dados["responsaveis"])
