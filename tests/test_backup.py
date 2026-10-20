"""Testes de backup e restauração — a prova exigida pelo contrato.

O teste restaura de verdade: cria banco com dado, tira a cópia, restaura em
outro arquivo e compara as contagens. Se este teste passa, a afirmação
"o backup funciona" tem evidência; se falhar, o projeto não está pronto.
"""

from __future__ import annotations

from src import backup, db


def semear(caminho):
    """Banco pequeno, mas com as tabelas que o painel usa."""
    conexao = db.conectar(caminho)
    db.inicializar(conexao)
    db.registrar_fonte(
        conexao,
        id_fonte="teste",
        nome="Fonte de teste",
        orgao="Teste",
        url="https://example.org",
    )
    conexao.execute("INSERT INTO uf (sigla, nome, codigo_ibge) VALUES ('SP', 'São Paulo', '35')")
    for semana in range(1, 11):
        conexao.execute(
            "INSERT INTO caso_semana (uf, ano, semana, casos, fonte_id) "
            "VALUES ('SP', 2025, ?, ?, 'teste')",
            (semana, semana * 10),
        )
    conexao.commit()
    conexao.close()


def test_backup_e_restauracao_preservam_os_dados(tmp_path):
    """Copia, restaura e confere: mesmo conteúdo, integridade ok, hash igual."""
    origem = tmp_path / "brasil_saude.db"
    semear(origem)

    registro = backup.criar(origem, tmp_path / "backups", retencao=3)
    restaurado = backup.restaurar(tmp_path / "backups" / registro["arquivo"], tmp_path / "volta.db")

    assert registro["integridade"] == "ok"
    assert registro["contagens"]["caso_semana"] == 10
    assert restaurado["integridade"] == "ok"
    assert restaurado["contagens"] == registro["contagens"]
    assert restaurado["sha256"] == registro["sha256"]


def test_manifesto_registra_a_prova(tmp_path):
    """O manifesto é o rastro: nome, data, hash e contagens de cada cópia."""
    origem = tmp_path / "brasil_saude.db"
    semear(origem)

    backup.criar(origem, tmp_path / "backups")

    manifesto = (tmp_path / "backups" / "manifesto.json").read_text(encoding="utf-8")
    assert "sha256" in manifesto
    assert "caso_semana" in manifesto


def test_arquivo_corrompido_e_recusado(tmp_path):
    """Restaurar lixo como se fosse banco é o pior cenário: recusar é obrigatório."""
    falso = tmp_path / "falso.db"
    falso.write_bytes(b"isto nao e um banco sqlite")

    prova = backup.verificar(falso)

    assert prova["integridade"].startswith("erro")


def test_retencao_remove_as_copias_mais_antigas(tmp_path):
    """A retenção não pode apagar a cópia mais nova — só as excedentes."""
    pasta = tmp_path / "backups"
    pasta.mkdir()
    for dia in range(1, 5):
        (pasta / f"brasil_saude_2026010{dia}_120000.db").write_bytes(b"x")

    removidos = backup._aplicar_retencao(pasta, retencao=2)

    restantes = sorted(caminho.name for caminho in pasta.glob("brasil_saude_*.db"))
    assert len(restantes) == 2
    assert restantes[-1].endswith("20260104_120000.db")
    assert len(removidos) == 2
