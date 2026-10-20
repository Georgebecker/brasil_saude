# Backup e recuperação — Brasil Saúde

> Documento exigido pela vaga de DBA e pelo contrato do projeto: **backup sem
> teste de restauração não conta**. Aqui está o que foi feito, o comando, a
> prova e a comparação com o que seria exigido em Oracle.

## 1. O que é protegido

Um único arquivo: `data/brasil_saude.db` (SQLite, modo WAL). Ele contém:

| Conteúdo | Volume em 2026-10-20 |
|---|---|
| UFs | 27 |
| Municípios | 5.571 |
| Semanas de casos (por UF) | 1.377 |
| Repasses (UF × ação × mês) | 2.399 |
| Dias de clima (por estação) | 3.945 |
| Fontes registradas | 7 |

O arquivo bruto (`data/raw/`) **não** entra no backup: pode ser baixado de
novo e não é fonte de verdade. O que não se reconstrói é o banco tratado.

## 2. Estratégia

| Item | Decisão | Motivo |
|---|---|---|
| Frequência | antes e depois de cada coleta; diária em produção | coleta é o único evento que muda o banco |
| Retenção | 7 cópias (configurável) | cobre uma semana de erro descoberto tarde |
| Local | `data/backups/` (mesma máquina) + cópia externa manual | simplicidade; a cópia externa está no plano de produção |
| Método | `sqlite3.Connection.backup()` | cópia coerente com WAL; `copy` do arquivo pode pegar escrita pela metade |
| Verificação | `PRAGMA integrity_check` + contagem das 5 tabelas + SHA-256 | integridade não é só “abriu” |
| Restauração | arquivo separado + nova verificação | restaurar por cima esconderia divergência |

## 3. Comandos

```powershell
# criar cópia datada, verificada e com retenção
python scripts/backup_sqlite.py criar

# conferir uma cópia existente
python scripts/backup_sqlite.py verificar data/backups/brasil_saude_AAAAMMDD_HHMMSS.db

# restaurar em outro arquivo e provar que abre
python scripts/backup_sqlite.py restaurar data/backups/arquivo.db data/processed/volta.db
```

Automação (Windows e Linux) em [`automacao.md`](automacao.md).

## 4. Evidência executada (2026-10-20)

Saída real de `python scripts/backup_sqlite.py criar`:

```json
{
  "arquivo": "brasil_saude_20261020_141237.db",
  "integridade": "ok",
  "contagens": {"fonte": 7, "uf": 27, "caso_semana": 1377, "repasse": 2399, "clima_dia": 3945},
  "bytes": 2277376,
  "sha256": "6f41517ad0374c698199d04e7d6cd16b082a7b60a97b1eba42ed2fb3e2fc19ed"
}
```

Saída real da restauração em `data/processed/restauracao_teste.db`:

```json
{
  "restaurado_em": "data\\processed\\restauracao_teste.db",
  "integridade": "ok",
  "contagens": {"fonte": 7, "uf": 27, "caso_semana": 1377, "repasse": 2399, "clima_dia": 3945},
  "sha256": "6f41517ad0374c698199d04e7d6cd16b082a7b60a97b1eba42ed2fb3e2fc19ed"
}
```

**Leitura da prova:** o SHA-256 do restaurado é **idêntico** ao do backup —
byte a byte. As contagens batem. O teste automatizado `tests/test_backup.py`
reproduz o ciclo (criar → restaurar → comparar) e ainda prova que arquivo
corrompido é recusado.

## 5. Cenários de falha e resposta

| Cenário | Detecção | Resposta |
|---|---|---|
| Arquivo corrompido (disco) | `integrity_check` ≠ ok | restaurar a cópia mais recente íntegra |
| Backup interrompido | arquivo `.parcial` (não é promovido) | ignorar e repetir |
| Erro de ETL (dado errado) | teste/inspeção | restaurar cópia anterior e recoletar |
| Retenção apagou o necessário | manifesto lista o que saiu | ampliar retenção e restaurar de cópia externa |
| Ransomware na máquina | — | cópia externa offline (fora do escopo do MVP) |

## 6. Comparação com Oracle (o que seria diferente)

| Aspecto | Este projeto (SQLite) | Oracle em missão crítica |
|---|---|---|
| Ferramenta | API `backup()` do SQLite | **RMAN** com catálogo de recuperação |
| Tipo | cópia completa | full + incremental + archivelog |
| Consistência | WAL + cópia online | backup online com *BEGIN BACKUP* / RMAN |
| Redundância | outra pasta / disco | **Data Guard** (standby físico) |
| Retenção | 7 arquivos, política simples | política por *recovery window*, com testes periódicos |
| Teste de restore | script + pytest | *restore validation* em ambiente separado |
| RPO | última coleta | segundos (com Data Guard em *maximum availability*) |
| RTO | minutos | minutos com RAC/Data Guard |

O que **não** foi feito: backup incremental, cópia off-site automática,
criptografia da cópia e teste de restauração em máquina diferente. Estão no
backlog e descritos em [`migracao_enterprise.md`](migracao_enterprise.md).
