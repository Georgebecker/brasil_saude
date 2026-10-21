# Roadmap de dados — o que já é público, o que falta e por quê

Este documento responde a uma pergunta prática: **quais dados públicos ainda podem
entrar no painel, de onde eles vêm e o que impede cada um hoje**. Ele existe para
que a lista de ideias não se perca e para que ninguém confunda "não implementado"
com "não existe".

Regra que vale para toda linha desta tabela: **nada entra na tela sem fonte, período
de referência e data de validação.** Quando a fonte não permite saber o período, o
dado não entra — mesmo que seja interessante.

## 1. O que já está publicado

| Tema | Fonte | Situação | Período |
| --- | --- | --- | --- |
| Dengue por UF (semanal) | InfoDengue/Fiocruz (SINAN) | publicado | 52 semanas (2025-SE43 a 2026-SE40) |
| Dengue por capital | InfoDengue `alertcity` | publicado | últimos 2 anos |
| Território e população | IBGE (malha mínima + Censo 2022) | publicado | 2022 |
| Repasses federais (função Saúde) | Portal da Transparência / CGU | publicado | 12 meses |
| Programas e propostas federais | Transferegov | publicado | 2025 e 2026 |
| Clima diário (chuva e temperatura) | INMET + Open-Meteo (fallback declarado) | publicado | 14 dias por estação |
| Quem governava (presidente, ministros, governadores) | Curadoria com fonte oficial | publicado | 2019–2026 |
| Método de alerta | EARS C1 e C2 | publicado | série inteira |

## 2. O que o dono pediu e ainda não está publicado

| Pedido | Fonte candidata | Situação em 21/10/2026 | O que falta |
| --- | --- | --- | --- |
| Outras arboviroses (chikungunya, zika) | InfoDengue, parâmetro `diseases` | **validado nesta sessão**: chikungunya devolve série real; zika devolve série quase toda zerada | acrescentar a coluna `doenca` em `caso_semana`, recalcular o EARS por doença e somar um seletor na tela |
| Internações e SRAG | OpenDataSUS (SIH/SUS e SRAG) | não coletado | arquivos anuais grandes (centenas de MB); precisa de recorte por UF e de um job com cache em disco |
| Queimadas e fumaça | INPE BDQueimadas | não coletado | o serviço passou a exigir cadastro/token para o CSV por estado; sem token não há série confiável |
| Desastres e chuvas extremas (caso do RS em 2024) | S2iD/MIDR e CEMADEN | não coletado | não há API aberta documentada; o caminho é o relatório de reconhecimento federal por município (PDF/planilha) |
| Obras federais, estaduais e municipais | Obrasgov (`obrasgov.gestao.gov.br`) e Transferegov | parcial: já temos propostas e valores | faltam a execução física, o empreendimento e a esfera (federal/estadual/municipal/consórcio) |
| Saneamento (água, esgoto, resíduos) | SNIS (diagnóstico anual) | não coletado | planilhas anuais por município; é a melhor fonte para "quanto foi feito" |
| Prefeitos por município | TSE (candidaturas e resultados) | não coletado | 5.570 municípios; exige curadoria e um recorte de exibição para não invadir privacidade |
| Correlação chuva → dengue | INMET/Open-Meteo + InfoDengue | **parcial**: série de clima publicada só cobre 14 dias por estação | precisa de série diária longa (baixar anos de observação) para calcular correlação com honestidade |
| Correlação queimada → doença respiratória | INPE + SIH/SUS | bloqueado | depende das duas fontes acima |
| Correlação seca → diarreia e cólera | SIH/SUS + FUNASA/SVS | bloqueado | depende de internações por agravo e de série de precipitação longa |

## 3. Por que correlação é o item mais delicado

Duas séries que sobem juntas não provam que uma causa a outra. Em saúde coletiva há
três armadilhas conhecidas:

1. **Falácia ecológica** — o dado é do estado, não da pessoa. Uma taxa estadual não
   descreve ninguém em particular.
2. **Confundidor** — dengue sobe no verão; verão tem chuva, férias e mais notificação.
   A chuva pode ser apenas a companhia do aumento de casos.
3. **Defasagem** — o efeito da chuva aparece semanas depois, e a defasagem muda de
   região para região.

Por isso, quando a correlação entrar, ela vem com: coeficiente, tamanho da amostra,
janela usada, defasagem testada e um aviso explícito de que **correlação não é
causalidade**. Sem esse pacote, é melhor não publicar.

## 4. Ordem sugerida para os próximos ciclos

1. **Chikungunya e zika** — a fonte já responde; é o maior ganho por menor esforço.
2. **Série diária de clima por estado** — destrava a correlação com a dengue.
3. **Obrasgov e SNIS** — responde "quanto foi destinado, quanto foi executado".
4. **Internações (SIH/SUS)** — permite falar de gravidade, não só de caso notificado.
5. **Queimadas e desastres** — dependem de credencial ou de planilha; entram quando a
   fonte ficar estável.
6. **Prefeitos** — por último, porque é o recorte mais próximo da pessoa e o que exige
   mais cuidado com privacidade e com volume de curadoria.

## 5. O que este projeto recusa fazer

- Publicar estimativa no lugar de dado coletado.
- Preencher lacuna com zero.
- Chamar de "executado" o valor que apenas foi planejado na proposta.
- Publicar nome de pessoa física que não seja agente público no exercício do cargo.
- Correlacionar sem declarar janela, defasagem e limitação.
