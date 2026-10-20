# Checklist do DBA — o que este projeto demonstra

> Regra: para cada competência, um **arquivo, teste ou comando** que a
> demonstra. Se não há evidência, a coluna diz “não coberta” — e o roadmap.
> Não há competência “declarada”.

## 1. Competências técnicas

| # | Competência | Evidência concreta | Situação |
|---|---|---|---|
| 1 | Modelagem de dados | [`../modelagem.md`](../modelagem.md); `src/db.py` (DDL, PK, FK, CHECK, índices) | ✅ |
| 2 | Integridade referencial | `tests/test_db.py::test_caso_sem_fonte_registrada_e_bloqueado` | ✅ |
| 3 | Transações | `db.transacao()` + `test_backup_e_restauracao_preservam_os_dados` | ✅ |
| 4 | Índices e consulta | `idx_repasse_uf_data`; consultas do mapa em `src/servicos/epidemiologia.py` | ✅ |
| 5 | Backup | [`backup_recovery.md`](backup_recovery.md) §4 (saída real) | ✅ |
| 6 | Restauração testada | `python scripts/backup_sqlite.py restaurar` + `tests/test_backup.py` | ✅ |
| 7 | Retenção | `backup._aplicar_retencao` + teste de retenção | ✅ |
| 8 | Automação | [`automacao.md`](automacao.md); `scripts/coletar.py` | ✅ |
| 9 | Tratamento de falha de fonte | `src/rede.py` (retry/backoff); `fonte.status` | ✅ |
| 10 | Observabilidade | `/api/saude`, `/api/log-coletas`, tabela `log_coleta` | ⚠️ parcial |
| 11 | Segurança de dados | [`seguranca_dados.md`](seguranca_dados.md); RBAC testado | ✅ |
| 12 | Linux | comandos documentados em [`automacao.md`](automacao.md) §3 | ⚠️ não executado |
| 13 | Nuvem (AWS) | [`migracao_enterprise.md`](migracao_enterprise.md) §4 | ⚠️ documentado |
| 14 | PostgreSQL | plano de migração §2 | ⚠️ não executado |
| 15 | Oracle (SQL/administração) | comparações em `backup_recovery.md` §6 e `migracao_enterprise.md` §3 | ❌ não coberta |
| 16 | Oracle RAC | [`alta_disponibilidade.md`](alta_disponibilidade.md) §3.1 | ❌ não coberta |
| 17 | Data Guard | [`backup_recovery.md`](backup_recovery.md) §6 | ❌ não coberta |
| 18 | Exadata | [`migracao_enterprise.md`](migracao_enterprise.md) §3.3 | ❌ não coberta |
| 19 | Kubernetes | [`migracao_enterprise.md`](migracao_enterprise.md) §5 | ❌ não coberta |
| 20 | Capacidade/performance | agregação no back-end; ETL por streaming de CSV de 195 MB | ✅ |

## 2. Competências de processo

| # | Competência | Evidência |
|---|---|---|
| 21 | Documentar antes de codificar (MAD) | `docs/modelagem.md` escrito antes do ETL |
| 22 | Critério de aceitação objetivo | `docs/backlog.md` com impacto × esforço |
| 23 | Registro de decisão | `NOTES.md` com data e motivo |
| 24 | Ciclo medido (Loop Engineering) | `log_loop.md`, `meu-loop-agente/log.md` |
| 25 | Teste como prova | 63 testes; saída registrada no `DIARIO.md` |
| 26 | Honestidade sobre limite | este arquivo, colunas “não coberta” |

## 3. Como reproduzir a verificação

```powershell
# banco e dados
python scripts/coletar.py tudo

# integridade e backup
python scripts/backup_sqlite.py criar

# restauração
python scripts/backup_sqlite.py restaurar data/backups/<arquivo>.db data/processed/volta.db

# suíte e lint
python -m pytest -q
python -m ruff check .
```

## 4. O que eu faria para fechar as lacunas

| Lacuna | Prática mínima |
|---|---|
| Oracle | Oracle XE em VM: usuário, tablespace, import, RMAN, restore |
| RAC | laboratório de 2 nós (Vagrant): SCAN, serviço, teste de queda de nó |
| Data Guard | standby físico, *switchover* e *failover* cronometrados |
| Linux | rodar coleta e backup em VM Linux com systemd timer |
| AWS | RDS PostgreSQL + S3 + IAM mínimo, com orçamento monitorado |
| Kubernetes | `kind` + operador de PostgreSQL + CronJob de coleta |

A diferença entre “saber” e “ter feito” está declarada em cada linha. O valor
do projeto é não confundir as duas.
