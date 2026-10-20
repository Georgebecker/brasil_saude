# Segurança dos dados — DICA na prática

> A sigla **DICA** (Disponibilidade, Integridade, Confidencialidade,
> Autenticidade) é o roteiro. Cada item abaixo diz o que o projeto faz, como
> prova e onde ainda falha.

## 1. DICA aplicado

### Disponibilidade

- **O que faz:** cache local em SQLite; retry com backoff; fallback de fonte;
  falha de uma UF/mês não apaga o resto; backup verificado.
- **Prova:** `src/rede.py`, `src/backup.py`, `tests/test_backup.py`.
- **Limite:** uma máquina só. Sem réplica, sem failover
  ([`alta_disponibilidade.md`](alta_disponibilidade.md)).

### Integridade

- **O que faz:** chave estrangeira obrigatória para `fonte`; `CHECK` de faixa
  (semana 1–53, casos ≥ 0); transação por lote; reconstrói lacuna como `None`
  em vez de zero.
- **Prova:** `tests/test_db.py` (fonte ausente e caso negativo recusados),
  `tests/test_epidemiologia.py` (lacuna não vira zero).
- **Limite:** não há assinatura criptográfica do dado coletado; a garantia é a
  URL da fonte + data de coleta.

### Confidencialidade

- **O que faz:** nenhum dado pessoal é armazenado. A menor célula é
  município × semana (agregado). Não há nome de paciente, CNS, data de
  nascimento, endereço ou telefone.
- **Prova:** `docs/modelagem.md` §5; `rg -i "cpf|cns|nome_paciente" src/` não
  encontra campo.
- **Limite:** município pequeno + semana pode permitir reidentificação
  estatística em cenários extremos. A fonte já publica agregado; o painel não
  adiciona granularidade.

### Autenticidade

- **O que faz:** cada fonte tem órgão, URL, licença, período e data de coleta;
  a seção “Fontes e Metodologia” lê a tabela `fonte`; cada repasse guarda a URL
  do arquivo mensal.
- **Prova:** `/api/fontes`, `/api/saude`, `repasse.url_fonte`.
- **Limite:** não há hash do arquivo bruto guardado no banco. O SHA-256 existe
  para o backup; para o dado de origem, fica a URL e a data.

## 2. Controle de acesso

| Papel | Alcance | Verificação |
|---|---|---|
| público | dado agregado | rotas abertas |
| gestor_estadual | detalhe do próprio estado | 403 em outro estado (teste) |
| admin | qualquer estado | teste |

- Token assinado (HMAC) apenas no protótipo; em produção, OIDC gov.br + MFA
  ([`../arquitetura/integracao_servicos.md`](../arquitetura/integracao_servicos.md)).
- A UF do alerta vem do vínculo do usuário, nunca do corpo da requisição.

## 3. Superfície de ataque

| Vetor | Mitigação atual | Pendência |
|---|---|---|
| SQL injection | consultas parametrizadas (`?`) em todo o código | testes de fuzz |
| XSS | frontend usa `textContent`, não `innerHTML` com dado | CSP |
| CSRF | API só de leitura no público; protótipo sem cookie | token CSRF quando houver sessão |
| Força bruta | não há login no MVP | rate limit + MFA |
| Corpo grande | middleware recusa > 1 MB | limite por rota |
| CORS | origens locais explícitas | revisar domínio de produção |
| Vazamento por log | sem PII em `log_coleta`/`email_outbox` | revisão de logs |
| Dependência vulnerável | versões fixadas em `requirements.txt` | `pip-audit` no CI |

## 4. Comparação com ambiente governamental

| Requisito | Governo | Este projeto |
|---|---|---|
| HTTPS obrigatório | sim | **não** (local) |
| Certificado ICP-Brasil | para sistemas restritos | não se aplica ao dado aberto |
| Termo de Responsabilidade | para dado sensível | não se aplica |
| Trilha de auditoria | sim | parcial (`log_coleta`, `email_outbox`) |
| MFA para admin | sim | documentado, não implementado |
| Segregação de ambientes | homologação/produção | não há |
| Backup off-site | sim | não |
| Varredura de vulnerabilidade | sim | não |

## 5. LGPD

- **Base legal:** dados públicos agregados, sem dado pessoal (art. 7º, §3º —
  dados tornados públicos pelo titular; aqui nem chegam ao nível individual).
- **Minimização:** só o necessário para o painel.
- **Transparência:** fonte e metodologia na tela.
- **Direitos do titular:** não há titular identificável no banco; se houver
  contato por e-mail no futuro, será opt-in com descadastro.

## 6. O que eu não afirmo

Não afirmo que o painel é “seguro para produção”. Ele é um protótipo local
com boas práticas de modelagem e autorização. Antes de publicar: HTTPS, rate
limit, auditoria, MFA, revisão de dependências e teste de intrusão.
