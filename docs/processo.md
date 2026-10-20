# Processo de vigilância e responsabilização (MGProc)

> O painel não mostra “números soltos”: ele mostra um **processo de saúde
> pública**. Este documento descreve o fluxo que existe na vida real e indica,
> em cada etapa, o que o Brasil Saúde exibe — e o que ele não vê.

## 1. O fluxo em quatro etapas

```
(1) NOTIFICAÇÃO          (2) INVESTIGAÇÃO         (3) RESPOSTA           (4) REPASSE
     │                        │                       │                      │
     ▼                        ▼                       ▼                      ▼
ficha do SINAN        classificação final      ações de vigilância    empenho/pagamento
(dengue suspeita)     (confirmado/descartado)  (controle do vetor)    (fundo → estado)
     │                        │                       │                      │
     └────────────► banco `caso_semana` ◄──────────────┘                      │
                              │                                              │
                              └────────────► painel ◄─────── `repasse` ◄────┘
```

### Etapa 1 — Notificação

- **Quem faz:** unidade de saúde (pública ou privada) lança a ficha no SINAN.
- **Quando:** suspeita clínica; a semana epidemiológica vem do campo `SEM_NOT`.
- **O que o painel vê:** a **contagem** por UF/semana. Não vê nome, CPF, CNS
  nem endereço — a fonte já entrega agregado.
- **Risco:** notificação atrasada. Por isso existe a variante **C2** do EARS,
  que ignora os dois dias mais recentes.

### Etapa 2 — Investigação

- **Quem faz:** vigilância municipal/estadual encerra a ficha com
  `classi_fin` (confirmado, descartado, inconclusivo) e `criterio`
  (laboratorial, clínico-epidemiológico).
- **O que o painel vê:** hoje, **todas as notificações**. O filtro por
  classificação está no backlog (#11) porque excluir “em investigação”
  subestimaria o presente.
- **Risco:** mudança de critério ao longo do ano cria degrau na série. A nota
  metodológica da tela avisa.

### Etapa 3 — Resposta

- **Quem faz:** secretaria estadual/municipal aciona controle vetorial,
  assistência e comunicação.
- **O que o painel vê:** o **clima** (chuva e temperatura), que indica condição
  favorável ao mosquito, e a **anomalia** estatística. Não vê a ação
  propriamente dita.
- **Risco:** confundir “condição favorável” com “surto”. A tela usa a primeira
  expressão, nunca a segunda.

### Etapa 4 — Repasse

- **Quem faz:** União empenha e paga transferências (fundo a fundo ou
  voluntárias); o estado executa.
- **O que o painel vê:** o valor **transferido** por UF e mês, função Saúde
  (código 10), conforme o SIAFI.
- **Risco:** empenho ≠ pagamento ≠ serviço prestado. A tela diz “repasses” e
  traz aviso de causalidade.

## 2. Onde o painel entra (e onde não entra)

| Pergunta do cidadão | Etapa | O que o painel responde |
|---|---|---|
| “Qual a situação no meu estado?” | 1 | casos da última semana e série |
| “Isso é anômalo?” | 1–2 | faixa esperada do EARS e anomalia |
| “Houve repasse?” | 4 | total e datas por UF |
| “Quem responde?” | 1–4 | governador + link do estado |
| “Vai piorar?” | 3 | **não** — só condição climática favorável |
| “Por que faltou remédio?” | 3–4 | **não** — fora do escopo e sem dado |

## 3. Responsabilidades por esfera

| Esfera | Papel legal | O que o painel mostra |
|---|---|---|
| União | financiamento, coordenação nacional, vigilância | repasses federais (função 10) |
| Estado | coordenação estadual do SUS, repasse a municípios | série por UF, responsável estadual |
| Município | execução, notificação, controle vetorial | clima e incidência nos municípios monitorados |

## 4. Rastreabilidade do processo

Cada elo deixa rastro no banco:

- `fonte` — quem publicou, com URL e data de coleta;
- `log_coleta` — quando o ETL rodou e quantos registros entraram;
- `alerta_ears.calculado_em` — quando a faixa foi calculada;
- `repasse.url_fonte` — link do arquivo mensal do Portal da Transparência.

Se um elo quebrar, a tela mostra a lacuna — e a lacuna é dado, não zero.
