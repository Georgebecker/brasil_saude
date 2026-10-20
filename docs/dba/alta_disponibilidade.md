# Alta disponibilidade — o mínimo viável e o padrão enterprise

> O projeto **não tem RAC, Data Guard nem cluster**. O que ele tem é
> resiliência de fonte e de processo. Este documento separa uma coisa da outra
> sem fingir equivalência.

## 1. O que existe hoje

| Mecanismo | Onde | O que resolve |
|---|---|---|
| Retry com espera exponencial + *jitter* | `src/rede.py` | API pública instável (429/5xx/timeout) |
| Cache local em SQLite | banco inteiro | painel continua servindo o último dado bom |
| Fallback declarado de fonte | clima (Open-Meteo quando INMET responde 204) | endpoint morto não derruba a seção |
| Falha parcial tolerada | coleta por UF e por mês | uma UF/mês ausente não apaga o resto |
| `status` por fonte | tabela `fonte` | a tela avisa “fonte com problema” |
| Transação “tudo ou nada” | `src/db.py` | coleta interrompida não grava metade |
| Backup verificado | `src/backup.py` | recuperação após erro de dados |
| Diagnóstico | `/api/saude` | saber se há dado e até quando |

**O que isso NÃO é:** não há segundo nó, nem replicação, nem failover
automático. Se a máquina morrer, o painel para.

## 2. Modos de falha cobertos

| Falha | Comportamento |
|---|---|
| IBGE fora do ar | coleta falha; banco mantém UFs/municípios anteriores |
| InfoDengue fora do ar | série anterior permanece; `log_coleta` registra falha |
| Portal da Transparência com CAPTCHA | meses já baixados ficam no cache; coleta marca ausente |
| INMET responde 204 | clima usa Open-Meteo (fallback documentado) |
| Disco cheio | escrita falha na transação; banco não fica pela metade |
| Banco corrompido | restaurar a cópia verificada mais recente |

## 3. O que seria necessário em missão crítica

### 3.1 Oracle RAC (Real Application Clusters)

- 2+ nós compartilhando o mesmo banco via **ASM**;
- **SCAN** + VIP para o cliente não saber o nó;
- *Cache Fusion* para consistência entre instâncias;
- *failover* transparente de sessão;
- **o que muda no projeto:** o acesso ao banco precisaria ser stateless por
  requisição (já é) e o SQL compatível com Oracle (hoje é SQLite: `ON CONFLICT`,
  `AUTOINCREMENT` e `PRAGMA` teriam de ser reescritos).

### 3.2 Data Guard

- standby físico com **redo apply** contínuo;
- modos *maximum performance* / *availability* / *protection*;
- *switchover* (planejado) e *failover* (desastre);
- RPO próximo de zero;
- **o que muda:** aplicar *archivelog mode* e copiar redo; no SQLite não há
  equivalente direto (o WAL não é replicável entre máquinas).

### 3.3 Nuvem (AWS)

- RDS Multi-AZ (banco gerenciado) ou EC2 + réplica;
- ALB + Auto Scaling para a API;
- S3 versionado para backup;
- Route 53 com *health check*;
- **o que muda:** conexão por TLS, IAM, VPC privada, segredos no Secrets Manager.

## 4. Comparação honesta

| Requisito | MVP | Enterprise |
|---|---|---|
| Continuar servindo com fonte fora | ✅ cache | ✅ réplica |
| Continuar servindo com máquina fora | ❌ | ✅ RAC/ALB |
| Perder zero transação | ❌ | ✅ Data Guard |
| Failover automático | ❌ | ✅ |
| RPO | última coleta | segundos |
| RTO | manual (restaurar backup) | automático |

## 5. Roadmap mínimo para HA de verdade

1. Containerizar a API e o banco (PostgreSQL) — `docker compose`.
2. Duas instâncias da API atrás de um proxy (Caddy/Nginx).
3. PostgreSQL com *streaming replication* (1 primário + 1 réplica).
4. Backup contínuo com WAL archiving para S3.
5. Ensaio de *failover* documentado, com tempo medido.

Nenhum passo acima está implementado. O que existe está na seção 1 e é
verificado por teste (`test_backup_e_restauracao_preservam_os_dados`,
`test_arquivo_corrompido_e_recusado`).
