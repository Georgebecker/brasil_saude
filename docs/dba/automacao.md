# Automação — coleta, alerta e backup

> Nada aqui roda escondido: cada comando imprime JSON com o resultado real.
> Automação sem log é fé, não engenharia.

## 1. O que é automatizável (e o que já está)

| Tarefa | Comando | Tempo medido (2026-10-20) |
|---|---|---|
| Território + população + malha | `python scripts/coletar.py base` | 6,2 s |
| Responsáveis (curadoria local) | `python scripts/coletar.py responsaveis` | < 0,1 s |
| Série de dengue por UF | `python scripts/coletar.py dengue` | 72,3 s (27 UFs) |
| Série das capitais | `python scripts/coletar.py capitais` | 9,1 s |
| Repasses (12 meses) | `python scripts/coletar.py orcamento --meses 12` | 37,9 s |
| Clima (catálogo + ~300 estações) | `python scripts/coletar.py clima` | 181 s |
| Recalcular EARS | `python scripts/coletar.py ears` | 0,1 s |
| Backup verificado | `python scripts/backup_sqlite.py criar` | ~0,5 s |

Tudo junto: `python scripts/coletar.py tudo` (≈ 5 min).

## 2. Ordem obrigatória

```
base → responsaveis → dengue → capitais → orcamento → clima → ears
```

- `base` antes de todos: sem UF/município, as chaves estrangeiras recusam.
- `ears` por último: depende de `caso_semana`.
- `clima` depois de `base`: depende de `municipio`.

O script `tudo` já impõe essa ordem.

## 3. Agendamento

### Windows (Agendador de Tarefas)

```powershell
$acao = New-ScheduledTaskAction -Execute "D:\Projetos\brasil_saude\.venv\Scripts\python.exe" `
  -Argument "scripts\coletar.py tudo" -WorkingDirectory "D:\Projetos\brasil_saude"
$gatilho = New-ScheduledTaskTrigger -Daily -At 03:00
Register-ScheduledTask -TaskName "BrasilSaude-Coleta" -Action $acao -Trigger $gatilho
```

### Linux (systemd timer)

`/etc/systemd/system/brasil-saude.service`:

```ini
[Unit]
Description=Coleta Brasil Saúde
[Service]
Type=oneshot
WorkingDirectory=/opt/brasil_saude
ExecStart=/opt/brasil_saude/.venv/bin/python scripts/coletar.py tudo
User=brasaude
```

`/etc/systemd/system/brasil-saude.timer`:

```ini
[Unit]
Description=Coleta diária Brasil Saúde
[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
[Install]
WantedBy=timers.target
```

`systemctl enable --now brasil-saude.timer`

### Cron equivalente

```cron
0 3 * * * cd /opt/brasil_saude && .venv/bin/python scripts/coletar.py tudo >> logs/coleta.log 2>&1
```

## 4. Idempotência e falha

| Situação | Comportamento |
|---|---|
| Coleta roda duas vezes | apaga e regrava o período da mesma fonte (sem duplicar) |
| Uma UF falha | as outras são gravadas; `falhas` aparece no JSON |
| Um mês não existe | registra `meses_ausentes`; mantém os demais |
| Download interrompido | arquivo `.parcial`, nunca promovido a final |
| Falha no meio da transação | rollback; banco fica no estado anterior |

O histórico fica em `log_coleta` (início, fim, status, linhas, mensagem).

## 5. O que mudaria em Oracle/AWS

| Necessidade | Aqui | Oracle | AWS |
|---|---|---|---|
| Agendar | cron / Task Scheduler | **DBMS_SCHEDULER** | EventBridge + Lambda |
| Orquestrar etapas | script Python | chains do Scheduler | **Step Functions** |
| Retry | `src/rede.py` | job com retry | retry policy do Step Functions |
| Log | tabela + stdout | tabela + alert log | CloudWatch |
| Segredo | `.env`/ambiente | wallet | Secrets Manager |
| Notificação de falha | JSON/exit code | e-mail do Scheduler | SNS |

## 6. Checklist antes de ligar o agendamento

1. `.venv` existe e tem as dependências (`pip install -r requirements.txt`).
2. `python scripts/coletar.py tudo` roda verde manualmente.
3. `python scripts/backup_sqlite.py criar` roda e verifica.
4. `data/backups/` tem espaço e a retenção está definida.
5. `log_coleta` está crescendo (sinal de que a tarefa executou).
6. Nenhum segredo em argumento de linha de comando (aparece no histórico).
