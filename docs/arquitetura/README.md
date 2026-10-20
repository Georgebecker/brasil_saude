# Arquitetura de identidade, acesso e serviços (Fase 2)

> Esta pasta responde a uma pergunta que o MVP deixou em aberto: **como o
> painel continuaria público e, ao mesmo tempo, ofereceria uma área restrita
> para gestores?** O código do protótipo está em `src/auth/` e
> `src/rotas/gestao.py`. A documentação vem antes do código porque a decisão
> de quem vê o quê é política pública, não detalhe de implementação.

## 1. Princípios

1. **O painel aberto continua aberto.** Nada de login para ver o mapa, a série
   ou os repasses agregados. A Fase 2 acrescenta uma porta, não uma tranca na
   porta existente.
2. **Menor privilégio.** Cada papel recebe só o que precisa. Gestor estadual
   vê o próprio estado; não vê o do vizinho.
3. **Dado pessoal não entra.** Não há cadastro de cidadão, e-mail de paciente
   ou notificação individual. O protótipo guarda papel e UF, não nome.
4. **Negar por padrão.** Rota nova nasce fechada; abrir é decisão explícita.
5. **Tudo rastreável.** A política é uma matriz legível e testada; o protótipo
   registra o que enfileirou, sem destinatário.

## 2. Visão de componentes

```
                        ┌──────────────────────────┐
   navegador ──────────►│  Painel público (HTML/JS) │  sem login
                        └────────────┬─────────────┘
                                     │ GET /api/estados...
                        ┌────────────▼─────────────┐
                        │  FastAPI (src/app.py)     │
                        │  rotas públicas           │
                        └────────────┬─────────────┘
                                     │
      ┌──────────────────────────────┼──────────────────────────────┐
      │                              │                              │
┌─────▼─────┐                 ┌──────▼──────┐                ┌──────▼──────┐
│Serviço    │                 │Serviço      │                │Serviço      │
│epidemio.  │                 │orçamentário │                │climático    │
└─────┬─────┘                 └──────┬──────┘                └──────┬──────┘
      └──────────────┬───────────────┴──────────────────────────────┘
                     │
              ┌──────▼──────┐        ┌──────────────────────────┐
              │   SQLite    │        │  src/auth (protótipo)    │
              │  + backup   │        │  papéis, tokens, matriz  │
              └─────────────┘        └──────────┬───────────────┘
                                                │
                                     ┌──────────▼───────────┐
                                     │ Área de gestão       │
                                     │ /api/gestao/...      │
                                     │ (401 sem token)      │
                                     └──────────────────────┘
```

## 3. Decisões (ADR curtas)

### ADR-01 — RBAC local em vez de Permify/Warrant no MVP

**Contexto.** O contrato pede um motor dedicado (Permify ou Warrant) para
políticas granulares. **Decisão.** Documentar a matriz e implementar um RBAC
local, sem serviço externo. **Motivo.** Permify/Warrant exigem um servidor a
mais (Docker, banco próprio) e não acrescentam segurança real a um painel
local de um usuário; o risco seria maior complexidade sem auditoria. **Custo.**
Trocar para Permify depois exige reescrever as checagens (`politicas.py`) —
cerca de 100 linhas, isoladas de propósito. **Gatilho de revisão.** Mais de
três papéis ou política por atributo (convênio, finalidade, horário).

### ADR-02 — Tokens HMAC no protótipo, OIDC em produção

**Contexto.** Sem um provedor de identidade, qualquer “login” seria teatro.
**Decisão.** Token assinado com HMAC-SHA256, emitido só quando
`BRASIL_SAUDE_AUTH_DEMO=1`. **Motivo.** Demonstra a política sem senha fraca
nem banco de usuários. **Limite explícito.** Não há MFA, revogação nem
recuperação de senha. Em produção, o `sub` vem do gov.br.

### ADR-03 — E-mail multi-tenant documentado, entrega desligada

**Decisão.** Protótipo grava em `email_outbox` (UF, papel, assunto, corpo) e
**não envia**. **Motivo.** Enviar e-mail real exigiria domínio verificado,
DKIM/SPF, opt-in e tratamento de bounce — e criaria dado pessoal onde hoje não
existe. A avaliação de Hyvor Relay/Mailtura está em
[`integracao_servicos.md`](integracao_servicos.md).

### ADR-04 — Alerta e detalhe seguem a mesma fronteira

**Decisão.** `pode_ver_detalhe` e `pode_enfileirar_alerta` usam a mesma regra.
**Motivo.** Se o gestor não pode ver o dado, não pode disparar comunicação
sobre ele. Uma segunda regra seria uma segunda chance de vazar.

## 4. Como testar o protótipo

```powershell
# 1. Suba com a emissão de token de demonstração ligada
$env:BRASIL_SAUDE_AUTH_DEMO = "1"
python -m uvicorn src.app:app --reload

# 2. Em outro terminal, peça um token de gestor de SP
curl.exe -s -X POST http://127.0.0.1:8000/api/auth/demo-token `
  -H "Content-Type: application/json" `
  -d '{\"papel\":\"gestor_estadual\",\"uf\":\"SP\"}'

# 3. Use o token: SP responde 200, RJ responde 403
curl.exe -s -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8000/api/gestao/estados/SP/resumo
curl.exe -s -o NUL -w "%{http_code}" -H "Authorization: Bearer <TOKEN>" `
  http://127.0.0.1:8000/api/gestao/estados/RJ/resumo
```

O teste automatizado equivalente está em `tests/test_autorizacao.py`
(`test_gestor_nao_ve_outro_estado`).

## 5. O que **não** está pronto

| Item | Situação | Caminho |
|---|---|---|
| Login real (gov.br) | só documentado | `integracao_servicos.md` §3 |
| MFA | só documentado (obrigatório para admin) | §4 |
| Revogação de token | ausente no protótipo | usar OIDC com sessão curta |
| Envio de e-mail | desligado de propósito | §2 |
| Motor ABAC dedicado | substituído por RBAC local | ADR-01 |
| Log de auditoria de acesso | parcial (`email_outbox`); falta tabela de auditoria | roadmap |

## 6. Documentos desta pasta

- [`matriz_permissoes.md`](matriz_permissoes.md) — papéis, permissões e a
  tabela de decisão com os testes que a provam.
- [`integracao_servicos.md`](integracao_servicos.md) — e-mail multi-tenant,
  gov.br (OAuth2/OIDC), MFA e requisitos DATASUS.
