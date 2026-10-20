# DIARIO — o que foi feito, por que e o que você vê na tela

> Este arquivo é parte do produto. Cada entrada responde a quatro perguntas:
> **o que foi feito**, **por que assim**, **o que o usuário final vê** e
> **qual foi a dificuldade**. Se ele sumir, o projeto perde a memória.

---

## 2026-10-20 — Leitura do contrato e decisões iniciais

**O que foi feito.** Li o prompt master (192 linhas) e conferi o estado do
repositório: base `projeto_loop`, `src/config.py`, testes do ambiente e git
limpo. Antes de escrever código, testei a conectividade real das fontes
candidatas.

**Por que assim.** O contrato proíbe inventar número. Se uma fonte não responde,
todo o desenho muda — então a primeira tarefa é saber o que responde.

**O que o usuário vê.** Ainda nada: o painel não existia. O que passa a existir
é um banco com esquema e a decisão registrada em `NOTES.md`.

**Dificuldade.** O `User-Agent` do projeto tinha acento (`vigilância`) e o IBGE
respondia **400** — cabeçalho HTTP só aceita ASCII. Corrigido em
`src/config.py`. Lição: erro 400 em API pública pode ser o próprio cliente.

---

## 2026-10-20 — Base territorial: IBGE

**O que foi feito.** Coleta de 27 UFs, 5.571 municípios, população (Censo 2022,
UF e município) e a malha GeoJSON das UFs (98 KB, qualidade mínima).

**Por que assim.** O SINAN identifica município por código IBGE; sem essa
tabela não há soma por estado nem mapa. A malha mínima foi escolhida de
propósito: 98 KB abrem no celular; a malha detalhada travaria a página.

**O que o usuário vê.** O contorno do Brasil no mapa, com os estados clicáveis.

**Dificuldade.** O JSON de municípios do IBGE tem dois formatos
(`microrregiao…UF` e `regiao-imediata…UF`). O parser procura a UF onde ela
estiver e descarta o município que não casar — nunca chuta a UF.

---

## 2026-10-20 — Fonte de dengue: três tentativas até a certa

**O que foi feito.** Testei o caminho “oficial” e documentei cada bloqueio:

1. **PySUS** (download do SINAN): não instala no Python 3.14 — `pyreaddbc` e
   `fastparquet` não têm wheel cp314.
2. **API de Dados Abertos do MS**: o prefixo `/v1` não existe; sem ele,
   `limit=20` estoura em 502 após 60 s, e a paginação não tem ordenação estável
   (offsets repetem linhas). Inutilizável para extração em massa.
3. **InfoDengue/Fiocruz**: funciona. `/api/notif_reduced` devolve a série
   semanal por UF em **uma** requisição; `/api/alertcity` devolve a série
   municipal das capitais. São notificações do SINAN, agregadas pela Fiocruz.

**Por que assim.** Entre uma fonte oficial que não entrega e uma agregação
confiável do mesmo dado, escolhi a que entrega — e escrevi a proveniência na
tela (“SINAN, agregado pelo InfoDengue”), sem fingir acesso ao microdado.

**O que o usuário vê.** Casos por estado na última semana consolidada, e a
série de 51 semanas ao clicar no estado.

**Dificuldade.** O arquivo traz a **semana em curso zerada** (notificação ainda
não digitada). Zero ali significa “não chegou”, não “não houve caso”: a última
linha zerada é descartada e a decisão fica no log.

---

## 2026-10-20 — Semana epidemiológica com a convenção brasileira

**O que foi feito.** A data do arquivo é o **domingo** que abre a semana.
Calculei (ano, semana) pela regra brasileira: semana 1 é a que contém 4 de
janeiro, em semanas de domingo a sábado.

**Por que assim.** Usar ISO-8601 erra o número em várias datas: 19/10/2025 é
**SE 43** no Brasil e W42 na ISO. O teste fixa os dois casos.

**O que o usuário vê.** O rótulo `2026-SE40` no gráfico e no mapa — o mesmo
número que o boletim oficial usa.

**Dificuldade.** Sem essa correção, o EARS compararia semanas deslocadas e o
painel “inventaria” um pico que não existe.

---

## 2026-10-20 — EARS C1 e C2 (e por que C3 ficou de fora)

**O que foi feito.** Implementei média + k desvios com janela de 7 pontos,
desvio amostral (n−1):

- **C1**: janela imediatamente anterior (sem atraso), k = 3;
- **C2**: ignora os 2 dias mais recentes, k = 3;
- **C3**: não implementado — é uma soma acumulada de C2, não uma terceira
  janela. Fingir que é daria resultado errado.

**Por que assim.** Validei com o exemplo numérico do CDC/`surveillance::earsC`:
série `[10,12,11,9,13,12,10,25,12,16]` → C1 não alerta (limite 29,34) e C2
alerta (limite 15,24). O teste `test_exemplo_canonico_do_relatorio` fixa isso.

**O que o usuário vê.** A linha de casos observados, a linha do esperado e a
faixa do limite; texto dizendo “anomalia estatística, não diagnóstico”.

**Dificuldade.** Lacuna na janela não pode virar zero: o detector devolve
`None` e o ponto fica sem faixa. Zero criaria uma queda falsa e, depois, um
pico falso.

---

## 2026-10-20 — Repasses: Portal da Transparência, sem token

**O que foi feito.** A API REST do Portal exige token (401). O **download
mensal** é aberto: um ZIP por mês com o CSV completo. Filtrei `função = 10`
(Saúde) e agreguei por UF e ação. Em setembro/2025: 73.452 linhas de saúde,
R$ 14,04 bi, 27 UFs, processadas em 3,4 s por streaming.

**Por que assim.** Não pede cadastro, é oficial (SIAFI) e o volume é
gerenciável. A pesquisa alertou que o CDN pode pedir CAPTCHA após muitos
downloads seguidos — por isso o ZIP fica em cache local e a coleta tolera mês
ausente.

**O que o usuário vê.** Total em reais no período, gráfico mensal e os últimos
lançamentos com link para o arquivo de origem — sempre com o aviso de que
**não há afirmação de causalidade**.

**Dificuldade.** O CSV é latin-1 e o código do município é SIAFI (não IBGE).
Por isso o MVP agrega só por UF e diz isso na metodologia.

---

## 2026-10-20 — Clima: INMET para localizar, Open-Meteo para medir

**O que foi feito.** O catálogo do INMET (668 automáticas + 87 convencionais)
dá nome, UF, coordenadas e o código IBGE embutido no campo `CD_WSI`. A série
diária do INMET respondeu **204** em todas as tentativas (exige token). Usei o
**Open-Meteo** nas coordenadas da estação, para chuva e temperatura.

**Por que assim.** Não dá para chamar de “dado do INMET” o que veio de outro
lugar. A tela mostra Open-Meteo como fonte da série e INMET como fonte das
estações — fallback declarado, não escondido.

**O que o usuário vê.** Municípios com maior incidência e, ao lado, chuva de 7
dias e temperatura; um selo de “atenção/alto” quando a chuva passa de 50/100 mm.

**Dificuldade.** O código IBGE do `CD_WSI` pode terminar com letras
(`3550308000W83781`); o parser usa expressão regular e valida o prefixo da UF.
Estação de capital só aparece no catálogo **M** (convencional) — sem ele, São
Paulo ficava sem clima.

---

## 2026-10-20 — API em três serviços

**O que foi feito.** FastAPI com rotas separadas: epidemiologia, orçamento,
clima, responsáveis e proveniência. Cada serviço tem seu módulo em
`src/servicos/` e seus testes.

**Por que assim.** MDSOA: serviço independente e testável. A rota só traduz;
a regra mora no serviço.

**O que o usuário vê.** A página carrega sozinha: mapa, série, repasses, clima,
responsáveis e a tabela de fontes, sem recarregar.

**Dificuldade.** O mapa precisa de uma **semana de referência única**. Usar o
`MAX` global deixava 26 estados cinza quando uma UF publicava uma semana a
mais. A referência agora é a semana com maior cobertura de UFs.

---

## 2026-10-20 — Painel: mapa, série e leitura honesta

**O que foi feito.** HTML/CSS/JS puro, sem build. Leaflet para o mapa (malha
local), Chart.js para os gráficos. Cores por incidência (casos/100 mil), borda
tracejada quando o EARS sinaliza anomalia. Estados sem dado ficam cinza.

**Por que assim.** O público é cidadão, jornalista e gestor — não pode depender
de `npm install`. Tudo é servido pela própria API.

**O que o usuário vê.** Mapa do Brasil; ao clicar, casos da semana, faixa
esperada, gráfico, repasses, clima e responsável; no fim, a metodologia.

**Dificuldade.** Nunca usar `innerHTML` com dado da rede (XSS). Todo texto é
inserido via `textContent`, e a UF é validada no servidor antes de qualquer
consulta.

---

## 2026-10-20 — Backup com prova de restauração

**O que foi feito.** `scripts/backup_sqlite.py` cria cópia datada pela API de
backup do SQLite, verifica `integrity_check`, calcula SHA-256, guarda manifesto
e aplica retenção. Restaurei em arquivo separado: hash idêntico
(`6f4151…19ed`), 2.277.376 bytes, contagens iguais.

**Por que assim.** Backup sem restauração testada é extintor nunca conferido.
O teste `tests/test_backup.py` repete o ciclo e recusa arquivo corrompido.

**O que o usuário vê.** Nada diretamente — mas o painel continua de pé se um
erro de ETL precisar ser revertido.

**Dificuldade.** Copiar o `.db` com `copy` durante escrita em WAL pode gerar
arquivo inconsistente; a API `backup()` tira um instantâneo coerente.

---

## 2026-10-20 — Fase 2: identidade e autorização

**O que foi feito.** Matriz de permissões (público, gestor estadual, admin),
tokens HMAC para demonstração, rota de gestão protegida e caixa de saída de
e-mail por UF (sem envio real). `tests/test_autorizacao.py` prova o critério:
**gestor de SP recebe 403 em RJ**.

**Por que assim.** O painel público não ganha login; a área restrita nasce
fechada. Sem provedor de identidade, um token assinado localmente demonstra a
política sem inventar senha. Em produção, gov.br (OIDC) + MFA.

**O que o usuário vê.** Nada muda no painel aberto. Quem tiver token de gestão
vê o resumo do próprio estado e pode enfileirar um alerta.

**Dificuldade.** O papel **não** pode vir do corpo da requisição: ele vem do
vínculo. E a UF do alerta é forçada para a do usuário — tentar outro estado é
403, não “corrigido em silêncio”.

---

## 2026-10-20 — Verificação final

**O que foi feito.** Suíte completa, lint, coleta real, backup, restauração e
conferência dos 19 critérios de sucesso.

**O que o usuário vê.** O painel com dados de 27 UFs, série de 51 semanas,
repasses de 12 meses (R$ 25,6 bi em SP), clima de ~300 estações e a lista de
fontes com data de coleta.

**Dificuldade.** Os números só valem se a origem estiver visível: por isso a
seção “Fontes e Metodologia” lê o banco, não um texto fixo no HTML.
