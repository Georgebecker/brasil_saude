# Portal de Serviços do DATASUS — o que é e por que o MVP não usa

> Documento que separa **dado aberto** de **sistema restrito**. O painel vive
> no primeiro; o segundo exige identidade institucional, certificado e termo de
> responsabilidade. Confundir os dois é o erro mais comum de quem tenta
> integrar com o DATASUS.

## 1. O que é o Portal

O **Portal de Serviços do DATASUS** é o canal oficial para sistemas de saúde
(troca de dados com o Ministério da Saúde). Não é um catálogo de dados abertos:
é uma área autenticada, com contrato de uso e responsável legal.

## 2. Requisitos de acesso (o que ele pede)

| Requisito | Detalhe | Efeito prático |
|---|---|---|
| **Login gov.br** | conta com nível de confiabilidade adequado | identidade individual |
| **Certificado digital ICP-Brasil** | arquivo `.PFX` (com senha) ou `.CER` | autenticação mútua (mTLS) |
| **CNES do estabelecimento** | Cadastro Nacional de Estabelecimentos de Saúde | o acesso é de uma unidade real |
| **Gestor responsável vinculado ao CNES** | quem responde pelo uso | rastreabilidade |
| **Homologação e produção separadas** | dois ambientes | teste não toca dado real |
| **Termo de Responsabilidade** | compromisso de uso restrito | responsabilidade civil |

Sem esses itens, o Portal não libera o serviço — e não há “modo público” para
dado nominal.

## 3. Por que o MVP não usa

1. **Não é necessário.** Dengue por UF/semana é dado público agregado,
   disponível no SINAN/OpenDataSUS e no InfoDengue.
2. **Não é viável em ambiente pessoal.** Exige CNES, gestor institucional e
   certificado ICP-Brasil.
3. **Não é seguro improvisar.** Guardar `.PFX` ou senha em repositório pessoal
   violaria as regras do projeto (nenhum valor de chave em arquivo versionado).
4. **O contrato manda documentar, não implementar.** Seção 2 do prompt:
   “O Portal entra como roadmap documentado, não como dependência do MVP.”

## 4. O que o Portal daria de diferente

| Serviço | Dado | Ganho | Custo |
|---|---|---|---|
| SINAN nominal | notificação individual | investigação, duplicidade | dado pessoal sensível |
| SIH/SIA | produção assistencial nominal | custo e acesso | identidade + termo |
| e-SUS | prontuário | atenção primária | LGPD pesada |
| RNDS | interoperabilidade | histórico do paciente | certificado + governança |

Nenhum desses é necessário para responder “qual a situação da dengue no meu
estado e houve repasse?”.

## 5. Caminho de integração (se um dia for necessário)

1. **Institucional:** a organização obtém CNES e indica gestor responsável.
2. **Certificado:** emite e-CNPJ (ou e-CPF do gestor) ICP-Brasil, guarda em
   cofre (nunca no git).
3. **Termo:** assina o Termo de Responsabilidade no Portal.
4. **Homologação:** integra e testa em ambiente de homologação.
5. **Produção:** promove após validação; ativa auditoria e monitoramento.
6. **Operação:** registra quem acessou o quê; revisa permissões periodicamente.

## 6. Requisitos técnicos que já estão prontos no projeto

| Requisito | Situação |
|---|---|
| Cliente HTTP com retry e timeout | ✅ `src/rede.py` |
| Registro de proveniência por coleta | ✅ `fonte` + `log_coleta` |
| Ausência de dado pessoal no banco | ✅ agregação |
| Autorização por papel | ✅ protótipo RBAC |
| Segredo fora do repositório | ✅ `.env` local + variável de ambiente |
| Auditoria de acesso | ⚠️ parcial |
| MFA | ❌ documentado |
| HTTPS/mTLS | ❌ não implementado |

## 7. Regra de ouro

> **Dado aberto não vira restrito por conveniência, e dado restrito não vira
> aberto por descuido.** O painel publica só o que já é público e agregado.
> Qualquer ampliação passa por Termo, certificado e revisão jurídica.
