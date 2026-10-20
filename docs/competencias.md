# Competências demonstradas — alinhamento com a vaga de DBA do DATASUS

> Regra do projeto: **não fingir que tem, mas provar que sabe como seria.**
> Cada linha aponta um artefato real ou uma lacuna assumida. A coluna
> “evidência” é um arquivo, teste ou comando que qualquer pessoa pode abrir.

## 1. Matriz principal

| Competência da vaga | Coberta no MVP? | Evidência | O que faltaria para produção |
|---|---|---|---|
| **Modelagem de dados** | ✅ | [`modelagem.md`](modelagem.md), `src/db.py`, chaves e FKs testadas em `tests/test_db.py` | modelagem dimensional para volume; versionamento de esquema |
| **Administração de SGBD** | ✅ (SQLite) | `PRAGMA foreign_keys`, WAL, índices, transações em `src/db.py` | Oracle (RAC/ASM), PostgreSQL com replicação |
| **Backup e recuperação** | ✅ | `scripts/backup_sqlite.py`, `tests/test_backup.py`, [`dba/backup_recovery.md`](dba/backup_recovery.md) | RMAN, backup incremental, Data Guard |
| **Alta disponibilidade** | ✅ (mínimo viável) | fallback de fonte, cache local, retry em `src/rede.py`, [`dba/alta_disponibilidade.md`](dba/alta_disponibilidade.md) | RAC, Data Guard, failover automático |
| **Automação** | ✅ | `scripts/coletar.py`, [`dba/automacao.md`](dba/automacao.md) | DBMS_SCHEDULER, Lambda/Step Functions |
| **Linux** | ⚠️ parcial | comandos documentados; execução real no Windows | systemd timer, permissões, SELinux, shell |
| **Nuvem (AWS)** | ⚠️ documentado | [`dba/migracao_enterprise.md`](dba/migracao_enterprise.md) | RDS/EC2, IAM, VPC, backup S3 |
| **Monitoramento** | ⚠️ parcial | `/api/saude`, `log_coleta`, aviso de fonte com problema | métricas Prometheus, alerta, SLO |
| **Segurança da informação** | ✅ | DICA aplicado, [`dba/seguranca_dados.md`](dba/seguranca_dados.md), RBAC testado | HTTPS, WAF, auditoria, MFA |
| **Oracle RAC** | ❌ não coberta | explicada em [`dba/alta_disponibilidade.md`](dba/alta_disponibilidade.md) | ambiente com 2+ nós, ASM, SCAN, VIP |
| **Data Guard** | ❌ não coberta | explicada em [`dba/backup_recovery.md`](dba/backup_recovery.md) | standby físico, switchover/failover |
| **Exadata** | ❌ não coberta | explicada em [`dba/migracao_enterprise.md`](dba/migracao_enterprise.md) | hardware dedicado, Smart Scan, cells |
| **Kubernetes** | ❌ não coberta | roadmap em [`dba/migracao_enterprise.md`](dba/migracao_enterprise.md) | cluster, Helm, operador de banco |

Legenda: ✅ demonstrado · ⚠️ parcial/documentado · ❌ não coberto (assumido).

## 2. O que o projeto prova sobre raciocínio de DBA

1. **Proveniência obrigatória por chave estrangeira.** Não é disciplina de
   processo: o banco recusa caso sem fonte (teste `test_caso_sem_fonte_registrada_e_bloqueado`).
2. **Lacuna não é zero.** A série reconstrói a grade e marca `None`; o EARS não
   avalia janela com buraco (`test_lacuna_impede_alerta_em_vez_de_inventar_queda`).
3. **Backup com prova.** A cópia é feita pela API de backup do SQLite (coerente
   com WAL), verificada por `integrity_check` e restaurada em arquivo separado.
4. **Migração consciente.** O documento de migração diz o que seria reescrito e
   o que seria reaproveitado — sem prometer que SQLite é Oracle.
5. **Capacidade.** Agregação no back-end e paginação evitam mandar 5 mil
   municípios para o navegador; o ETL processa CSV de 195 MB por streaming.

## 3. Competências de engenharia de software (bônus)

| Competência | Evidência |
|---|---|
| API REST tipada | FastAPI + Pydantic (`src/modelos.py`), OpenAPI em `/api/docs` |
| Testes automatizados | 63 testes (`python -m pytest -q`) |
| Lint | `ruff check .` sem erros |
| Frontend sem build | `frontend/index.html`, `app.js`, `styles.css` |
| Autorização | RBAC/ABAC local com 11 testes (`tests/test_autorizacao.py`) |
| Documentação viva | `DIARIO.md`, `NOTES.md`, `docs/` |

## 4. Lacunas assumidas (e o que faria para fechar)

| Lacuna | Plano |
|---|---|
| Oracle real | montar VM com Oracle XE; criar usuário, tablespace, testar RMAN |
| RAC/Data Guard | laboratório com 2 nós (Vagrant/Docker), observar *split-brain* |
| Linux como rotina | migrar o deploy para uma VM Linux e usar `systemd timers` |
| AWS | conta *free tier*: RDS PostgreSQL, S3 para backup, IAM mínimo |
| Kubernetes | `kind` local com um Postgres e um job de backup |
| MFA/gov.br | integrar OIDC com *mock* local e depois com cliente gov.br |

Nenhuma dessas lacunas é apresentada como competência no currículo ou no
README. O valor está em saber **o que** fazer e **por quê**, com a mão na
massa no que é possível hoje.
