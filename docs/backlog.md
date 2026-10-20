# Backlog — Brasil Saúde

> Exigido pela **MGP/MPPDS**: prioridade é decisão objetiva (impacto × esforço),
> não preferência. Cada item tem critério de aceitação verificável e status.
>
> Escala de impacto: 1 (cosmético) a 5 (muda a utilidade pública).
> Escala de esforço: 1 (horas) a 5 (semanas). Prioridade = impacto ÷ esforço.

## 1. Feito no MVP (versoes 1.0)

| # | Item | Impacto | Esforço | Critério de aceitação | Status |
|---|---|---:|---:|---|---|
| 1 | Mapa do Brasil com dengue por UF e semana | 5 | 3 | `/api/estados` devolve 27 UFs com casos e semana | ✅ |
| 2 | Série histórica com faixa EARS C1/C2 | 5 | 3 | gráfico mostra observado, esperado e limite; teste canônico do CDC passa | ✅ |
| 3 | Repasses federais da função Saúde por UF/mês | 5 | 3 | total por UF confere com a soma do CSV; aviso de causalidade na tela | ✅ |
| 4 | Clima nos municípios com maior incidência | 4 | 3 | lista ordenada por incidência com chuva de 7 dias | ✅ |
| 5 | Responsáveis legais (governadores) com fonte | 4 | 1 | 27 UFs com nome e link; teste de cobertura | ✅ |
| 6 | Seção “Fontes e Metodologia” | 5 | 1 | tabela lê `/api/fontes` (fonte, órgão, período, coleta) | ✅ |
| 7 | Backup com teste de restauração | 4 | 2 | `scripts/backup_sqlite.py` roda e `tests/test_backup.py` passa | ✅ |
| 8 | RBAC da Fase 2 (protótipo) | 4 | 2 | gestor de SP recebe 403 em RJ | ✅ |
| 9 | Documentação DATASUS/DBA (7 arquivos) | 3 | 2 | arquivos existem e estão preenchidos | ✅ |

## 2. Próximos (prioridade calculada)

| # | Item | Impacto | Esforço | Prioridade | Critério de aceitação |
|---|---|---:|---:|---:|---|
| 10 | Titular da Secretaria Estadual de Saúde | 5 | 2 | **2,50** | 27 UFs com nome do secretário e fonte oficial |
| 11 | Filtro `classi_fin` (provável × confirmado × descartado) | 5 | 3 | 1,67 | série mostra as três categorias, com definição na tela |
| 12 | Zika e chikungunya com seletor | 4 | 2 | 2,00 | `/api/estados?doenca=zika` e seletor no painel |
| 13 | Auditoria de acesso (`access_log`) | 3 | 2 | 1,50 | toda rota de gestão registra usuário, UF e resultado |
| 14 | Rate limit por IP nas rotas públicas | 3 | 1 | 3,00 | 429 após N requisições/minuto |
| 15 | Cobertura municipal completa (5.570) | 5 | 5 | 1,00 | série municipal para todas as UFs |
| 16 | Integração gov.br (OIDC + MFA) | 4 | 5 | 0,80 | login real; admin sem MFA não entra |
| 17 | Envio real de e-mail com opt-in | 3 | 4 | 0,75 | bounce tratado; descadastro em 1 clique |
| 18 | Deploy containerizado | 3 | 3 | 1,00 | `docker compose up` sobe API + banco |
| 19 | Migração para PostgreSQL | 3 | 4 | 0,75 | schema + migrações versionadas; testes verdes |
| 20 | Capturas de tela no README | 2 | 1 | 2,00 | até 5 imagens com legenda |

## 3. Regras de priorização

1. **Dado sem fonte não entra em nenhuma prioridade** — primeiro se resolve a
   proveniência, depois a funcionalidade.
2. Empate em prioridade: ganha o item que **reduz risco de erro publicado**
   (ex.: auditoria antes de envio de e-mail).
3. Item com impacto 5 e esforço 5 entra só se destravar outro item de impacto 5.
4. Nada de “todas as doenças de uma vez”: cada agravo é um ciclo com fonte,
   teste e nota metodológica própria.

## 4. Fora de escopo declarado

Autenticação de cidadão, banco de usuários, notícias em tempo real, machine
learning avançado, deploy público, mapa com todos os municípios, Oracle RAC,
Data Guard, Exadata e Kubernetes em produção. O caminho de migração está em
[`dba/migracao_enterprise.md`](dba/migracao_enterprise.md).
