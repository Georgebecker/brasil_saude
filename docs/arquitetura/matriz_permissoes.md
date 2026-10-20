# Matriz de permissões — Brasil Saúde (Fase 2)

> Fonte de verdade: `src/auth/politicas.py`. Este documento explica; o código
> decide. O teste `tests/test_autorizacao.py` verifica os casos críticos.

## 1. Papéis

| Papel | Quem é | O que vê | O que faz |
|---|---|---|---|
| `publico` | qualquer pessoa, sem login | dado **agregado** (mapa, série por UF, repasses por UF, clima, fontes) | consulta e baixa a página |
| `gestor_estadual` | servidor vinculado a **uma** UF | tudo do público **+ detalhe do próprio estado** (municípios, responsáveis, repasses detalhados) | enfileira alerta para a própria UF; exporta relatório do próprio estado |
| `admin` | equipe de operação do serviço | tudo, de **qualquer** estado | administra usuários/políticas, vê logs, enfileira alerta para qualquer UF |

O papel é atribuído no cadastro (hoje, no token de demonstração). **Ninguém
escolhe o próprio papel** em produção: ele vem do vínculo institucional
validado no gov.br.

## 2. Matriz permissão × papel

Legenda: ✓ permitido · ✗ negado · — não se aplica.

| Permissão | público | gestor_estadual | admin |
|---|:---:|:---:|:---:|
| `ver_agregado` (painel aberto) | ✓ | ✓ | ✓ |
| `ver_detalhe_do_proprio_estado` | ✗ | ✓ | ✓ |
| `ver_detalhe_de_qualquer_estado` | ✗ | ✗ | ✓ |
| `enfileirar_alerta` (própria UF) | ✗ | ✓ | ✓ |
| `administrar_usuarios` | ✗ | ✗ | ✓ |
| `ver_logs` | ✗ | ✗ | ✓ |

## 3. Regras de decisão (RBAC + atributo)

A política combina **papel** (RBAC) com **atributo do recurso** (ABAC):

```
permitir se:
    papel == "admin"
  OU (papel == "gestor_estadual" E uf_do_usuario == uf_do_recurso)
```

Atributos usados hoje:

| Atributo | Origem | Exemplo |
|---|---|---|
| `papel` | token (produção: claim do gov.br) | `gestor_estadual` |
| `uf` do usuário | cadastro/token | `SP` |
| `uf` do recurso | caminho da rota | `RJ` |
| `sensibilidade` | decisão de modelagem | `agregado` ou `detalhe` |

Para a Fase 3, `sensibilidade` pode virar atributo explícito no recurso, e a
política ganha `finalidade` (vigilância, auditoria) — aí sim um motor ABAC
dedicado passa a valer a pena.

## 4. Tabela de decisão (casos testados)

| Requisição | Papel / vínculo | Resultado | Teste |
|---|---|---|---|
| `GET /api/gestao/estados/SP/resumo` | sem token | **401** | `test_rota_de_gestao_exige_autenticacao` |
| `GET /api/gestao/estados/SP/resumo` | gestor SP | **200** | `test_gestor_ve_o_proprio_estado` |
| `GET /api/gestao/estados/RJ/resumo` | gestor SP | **403** | `test_gestor_nao_ve_outro_estado` |
| `GET /api/gestao/estados/RJ/resumo` | admin | **200** | `test_admin_ve_qualquer_estado` |
| `GET /api/gestao/estados/SP/resumo` | público | **403** | `test_publico_nao_ve_detalhe` |
| `POST /api/gestao/notificacoes/email` (sem UF) | gestor SP | **201**, UF = SP | `test_email_do_gestor_usa_a_propria_uf` |
| `POST /api/gestao/notificacoes/email` (uf=RJ) | gestor SP | **403**, nada gravado | `test_email_para_outro_estado_e_bloqueado` |

## 5. O que o público realmente vê

O painel aberto **não** usa token. Ele consome:

- `/api/estados` e `/api/estados/{uf}` — agregado por UF/semana;
- `/api/estados/{uf}/repasses` — total por UF/mês;
- `/api/estados/{uf}/clima` — municípios com incidência e chuva;
- `/api/estados/{uf}/responsaveis` — **cargo público e nome de gestor**.

Não há, em nenhuma rota pública, notificação individual, nome de paciente,
endereço, telefone ou e-mail. Se um dia houver dado mais sensível, ele nasce
**apenas** nas rotas de gestão — nunca nas públicas.

## 6. Invariantes que não podem quebrar

1. **Negar por padrão:** rota nova de gestão exige `exigir_usuario`.
2. **Fronteira territorial única:** detalhe e alerta usam `pode_ver_detalhe`.
3. **Nada de “filtrar no frontend”:** o 403 acontece no servidor; a tela não
   recebe o dado proibido.
4. **Sem dado pessoal em log:** `email_outbox` guarda UF e papel, não e-mail.
5. **Matriz e código juntos:** mudar `PERMISSOES` sem atualizar este arquivo
   quebra a revisão de PR (e o teste de coerência).
