# Integração de serviços — e-mail multi-tenant e gov.br

> Documento da Fase 2. Ele descreve **como** o painel passaria de um protótipo
> local para um serviço com identidade institucional — sem afirmar que já é
> isso. O que existe hoje está marcado como “protótipo”; o resto é roadmap com
> decisões e critérios de aceite.

## 1. Princípio de isolamento

O “tenant” é a **UF**. Um usuário vinculado a SP nunca recebe, consulta ou
dispara conteúdo de RJ. O isolamento vale em três camadas:

1. **Autorização** — `src/auth/politicas.py` (403 antes de tocar no dado);
2. **Consulta** — o SQL recebe a UF do usuário, não uma UF vinda do corpo;
3. **Saída** — a fila de e-mail registra a UF e recusa destinatário de fora.

O protótipo implementa (1) e (3); (2) está no `resumo_protegido`.

## 2. Serviço de e-mail multi-tenant

### 2.1 O que o serviço precisa fazer

| Requisito | Por quê |
|---|---|
| Isolamento por UF | alerta de SP não pode listar municípios de RJ |
| Domínio e DKIM por tenant | remetente confiável; evita spoofing |
| Opt-in explícito | ninguém recebe alerta sem pedir |
| Descadastro em um clique | exigência legal e de respeito |
| Fila com retry e idempotência | serviço de saúde não pode duplicar alerta |
| Sem PII em log | e-mail é dado pessoal; guardar hash, não endereço |
| Limite de taxa por tenant | um estado grande não derruba os demais |
| Webhooks de bounce/complaint | limpar lista morta e proteger reputação |

### 2.2 Avaliação das opções sugeridas

| Solução | O que foi verificado | Situação |
|---|---|---|
| **Hyvor Relay** (`relay.hyvor.com`) | API REST idempotente, projetos isolados com domínios/chaves/webhooks próprios, DKIM por domínio, tratamento de bounce/complaint e retenção de logs de 30 dias | **Viável tecnicamente.** Antes de adotar: confirmar licença, opção self-hosted, contrato de tratamento de dados e se o fornecedor aceita dado de saúde (não enviamos dado pessoal, mas o conteúdo é sensível). |
| **Mailtura** (`mailtura.com`) | O domínio responde com uma página de apostas (“TURABET”), não com serviço de e-mail | **Não usar.** A solução não pôde ser validada; o nome indicado no contrato não corresponde a um provedor de e-mail. Registrado como achado. |
| Alternativas consolidadas | Postal (self-hosted, licença aberta), Listmonk (self-hosted, newsletter), Amazon SES (com *configuration sets* por tenant) | Candidatas para a Fase 3, sujeitas à mesma due diligence. |

**Decisão do MVP:** não integrar provedor externo. O protótipo **enfileira**
(`email_outbox`) e não envia. Motivo: enviar e-mail real cria dado pessoal,
exige domínio verificado e opt-in, e não há base de usuários ainda.

### 2.3 Desenho proposto (Fase 3)

```
POST /api/gestao/notificacoes/email
        │  (token gov.br → papel + UF)
        ▼
┌───────────────────┐     ┌──────────────────────────┐
│ valida política   │────►│ fila (SQLite/Redis)      │
│ UF do usuário     │     │ chave idempotente        │
└───────────────────┘     └──────────┬───────────────┘
                                     │ worker (fora do request)
                          ┌──────────▼───────────────┐
                          │ provedor por tenant      │
                          │ domínio + DKIM próprios  │
                          └──────────┬───────────────┘
                                     │ webhook
                          ┌──────────▼───────────────┐
                          │ bounce/complaint → baixa │
                          └──────────────────────────┘
```

Idempotência: `id = hash(uf + semana + tipo_alerta + versão_do_dado)`. O mesmo
alerta não sai duas vezes se o job rodar de novo.

### 2.4 O que o protótipo faz hoje

- `POST /api/gestao/notificacoes/email` exige token;
- gestor usa **obrigatoriamente** a própria UF (UF no corpo é recusada com 403);
- admin precisa informar a UF;
- grava `uf`, `papel`, `assunto`, `corpo`, `criado_em`, `status`;
- **não** guarda e-mail, **não** envia, **não** tem worker.

## 3. Plataforma gov.br (OAuth2/OIDC)

### 3.1 Fluxo

1. O usuário clica em “Entrar com gov.br”.
2. Redireciona para o *authorization endpoint* com `client_id`, `redirect_uri`,
   `scope=openid profile email govbr_confiabilidades`, `state` e **PKCE**
   (`code_challenge`/`code_verifier`).
3. O gov.br autentica (senha + segundo fator) e devolve `code`.
4. O backend troca o `code` por `id_token` + `access_token`.
5. Valida o `id_token`: assinatura JWKS, `iss`, `aud`, `exp`, `nonce`.
6. Mapeia o `sub` para um vínculo local (UF + papel). **O papel nunca vem do
   cliente.**
7. Cria sessão curta (cookie `HttpOnly`, `Secure`, `SameSite=Lax`) ou emite
   token interno de curta duração.

### 3.2 Mapeamento de claims → autorização

| Claim | Uso no Brasil Saúde |
|---|---|
| `sub` | identificador estável do usuário; chave do vínculo |
| `name` | exibição na área de gestão (não vai para o painel público) |
| `email` | **não armazenar**; usar apenas para verificação pontual |
| `govbr_confiabilidades` | nível de confiança (bronze/prata/ouro) |

O vínculo institucional (qual UF, qual papel) é cadastrado por um `admin` ou
importado de uma fonte oficial. Autenticar no gov.br **não** concede papel.

### 3.3 Contratos que o backend deve cumprir

- `state` de uso único (previne CSRF) e PKCE obrigatório (clientes públicos);
- `nonce` no `id_token` (previne replay);
- rotação de chaves JWKS em cache com `kid`;
- logout local + *end session endpoint*;
- nada de token em `localStorage`; sessão em cookie `HttpOnly`;
- tempo máximo de sessão: 8 h; reautenticação para ações administrativas.

## 4. MFA (obrigatório para acesso administrativo)

| Papel | MFA | Nível gov.br mínimo |
|---|---|---|
| `publico` | não se aplica | — |
| `gestor_estadual` | **sim** | prata |
| `admin` | **sim, obrigatório** | prata ou ouro |

Regras:

- a exigência é verificada no **backend** (claim de confiabilidade), não na tela;
- `admin` sem MFA não entra nem com senha correta;
- ações destrutivas (mudar papel, apagar dado) exigem reautenticação;
- fallback local (TOTP/WebAuthn) só para ambiente de desenvolvimento.

## 5. Requisitos do DATASUS para dado sensível

O painel público trabalha com **dado agregado** e não precisa dos requisitos
abaixo. Eles passam a valer se o projeto integrar sistemas restritos (SINAN
nominal, SIH com identificação, e-SUS com prontuário):

| Requisito | O que implica |
|---|---|
| **Termo de Responsabilidade** | compromisso formal do gestor com o uso restrito e a segurança |
| **Certificado digital ICP-Brasil** (`.PFX`/`.CER`) | autenticação mútua no Portal de Serviços DATASUS |
| **CNES do estabelecimento** | vínculo do acesso a uma unidade real |
| **Gestor responsável vinculado ao CNES** | rastreabilidade de quem acessa |
| **Homologação e produção separadas** | teste não toca dado real |
| **Registro de acesso** | quem consultou o quê e quando |

Detalhamento em [`../dba/integracao_portal.md`](../dba/integracao_portal.md).
**Nenhum desses itens está implementado no MVP** — e o painel não afirma o
contrário.

## 6. Modelo de ameaças (resumo)

| Ameaça | Mitigação atual | Próximo passo |
|---|---|---|
| Gestor de SP lê RJ | 403 no servidor + teste | manter teste em CI |
| Token forjado | HMAC-SHA256 com segredo local | OIDC + JWKS |
| Token roubado | validade de 1 h | cookie `HttpOnly` + rotação |
| Escalada de papel | papel vem do vínculo, não do corpo | auditoria de mudança de papel |
| Vazamento por e-mail | UF forçada + sem destinatário | opt-in + DKIM por tenant |
| Enumeração de dados | respostas 403 sem detalhe do recurso | rate limit por IP |
| Dado pessoal em log | não guardamos e-mail | revisão de logs antes de produção |

## 7. Roadmap de implantação

1. **Fase 2 (agora)** — matriz + RBAC local + fila de e-mail desligada. ✅
2. **Fase 2.1** — auditoria de acesso (`access_log`) e rate limit.
3. **Fase 3** — gov.br OIDC + MFA + vínculo institucional; migrar RBAC local
   para Permify **se** a política crescer além de papel+UF.
4. **Fase 4** — provedor de e-mail com domínio por tenant, opt-in e webhooks.
5. **Fase 5** — integração DATASUS restrita, com Termo e certificado, em
   ambiente separado.
