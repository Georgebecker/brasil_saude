"""Testes do ambiente: garantem que a base, a segurança e a métrica seguem de pé.

Estes testes não testam o painel (ele ainda não existe): testam o "chassi" do
projeto. Funcionam como rede de segurança do agente do Loop — se ele quebrar a
régua, a configuração ou deixar escapar um segredo, o ciclo é rejeitado.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

ITENS_DA_BASE = [
    "README.md",
    "LICENSE",
    ".gitignore",
    ".env.example",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    "docs/REGRAS_DE_OURO.md",
    "docs/BASE_PROJETO_LOOP.md",
    "meu-loop-agente/program.md",
    "meu-loop-agente/config_loop.json",
    "meu-loop-agente/referencias_indicadores.json",
    "meu-loop-agente/medir_qualidade.py",
    "meu-loop-agente/verificar_iteracao.py",
]


def test_arquivos_da_base_existem():
    """Nenhum arquivo da base pode desaparecer sem alguém perceber."""
    faltando = [caminho for caminho in ITENS_DA_BASE if not (RAIZ / caminho).exists()]
    assert not faltando, "arquivos da base ausentes: " + ", ".join(faltando)


def test_env_example_nao_guarda_valor_de_chave():
    """O modelo versionado pode citar nomes de chave, nunca valores.

    Chave exposta é chave queimada: este teste é a barreira que impede o
    projeto de subir com um segredo escrito no `.env.example`.
    """
    linhas = (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines()
    suspeitas = []
    for numero, linha in enumerate(linhas, start=1):
        if linha.strip().startswith("#") or "=" not in linha:
            continue
        nome, valor = linha.split("=", 1)
        if re.search(r"(API_KEY|TOKEN|SECRET|PASSWORD)", nome.upper()) and valor.strip():
            suspeitas.append(f"linha {numero}: {nome.strip()}")
    assert not suspeitas, "chave com valor no .env.example: " + "; ".join(suspeitas)


def test_medidor_entrega_a_metrica_no_formato_combinado():
    """O verificador só consegue decidir se o medidor imprimir o formato previsto."""
    config = json.loads((RAIZ / "meu-loop-agente/config_loop.json").read_text(encoding="utf-8"))
    metrica = config["metrica"]

    resultado = subprocess.run(
        [sys.executable, "meu-loop-agente/medir_qualidade.py"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert resultado.returncode == 0, resultado.stderr
    encontrado = re.search(metrica["regex"], resultado.stdout)
    assert encontrado, "o medidor não imprimiu a métrica esperada:\n" + resultado.stdout

    divida = float(encontrado.group(metrica["grupo"]).replace(",", "."))
    assert 0.0 <= divida <= 1.0


def test_regua_tem_ids_unicos():
    """Id repetido na régua faria o medidor contar o mesmo indicador duas vezes."""
    dados = json.loads(
        (RAIZ / "meu-loop-agente/referencias_indicadores.json").read_text(encoding="utf-8")
    )
    identificadores = [indicador["id"] for indicador in dados["indicadores"]]
    assert len(identificadores) == len(set(identificadores)), (
        "ids repetidos na régua: " + ", ".join(sorted(identificadores))
    )


def test_configuracao_do_loop_aponta_para_arquivos_reais():
    """Comando e expressão regular precisam existir de verdade, não só no papel."""
    config = json.loads((RAIZ / "meu-loop-agente/config_loop.json").read_text(encoding="utf-8"))
    comando = config["metrica"]["comando"].split()
    assert (RAIZ / comando[1]).exists(), "arquivo de medição inexistente: " + comando[1]
    re.compile(config["metrica"]["regex"])


def test_pastas_do_fluxo_de_dados_existem():
    """Bruto -> validado -> descartado: o fluxo do projeto não pode perder pastas."""
    for pasta in ("data/raw", "data/processed", "data/descartados", "notebooks", "sql"):
        assert (RAIZ / pasta).is_dir(), "pasta ausente: " + pasta
