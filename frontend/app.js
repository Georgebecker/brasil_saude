/* =========================================================================
   Brasil Saúde — painel em JavaScript puro, sem framework e sem CDN.

   Regras que valem para o arquivo inteiro:
   1. nada de `innerHTML` com dado vindo da rede — todo texto entra por
      `textContent`. É a defesa mais barata contra XSS e não custa nada aqui;
   2. quando um serviço falha, a tela mostra o motivo em português em vez de
      ficar em branco;
   3. os gráficos são SVG montado à mão. Sem biblioteca, sem requisição a
      terceiros: o painel não conta a ninguém quem abriu a página;
   4. número, data e valor seguem a convenção brasileira (ABNT NBR 5891:
      ponto no milhar, vírgula no decimal) via Intl com locale pt-BR.
   ========================================================================= */

(() => {
  "use strict";

  const API = "/api";
  const NS = "http://www.w3.org/2000/svg";

  // Cores de dado — as mesmas do CSS, repetidas aqui porque o SVG precisa do
  // valor literal no atributo `fill`.
  const CORES = {
    sem: "#dbe3ee",
    faixas: ["#cdeee3", "#7fd3bd", "#f6cf5c", "#f08a4b", "#d13b3b"],
    linha: "#0f766e",
    alerta: "#d13b3b",
    parcial: "#c7d2fe",
    grade: "#e3e8f0",
  };

  // Formatação brasileira: 1.234,5 · R$ 1.234 · 21/10/2026
  const fmtInteiro = new Intl.NumberFormat("pt-BR");
  const fmtCompacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
  const fmtMoeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
  const fmtMoedaCompacta = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    notation: "compact",
    maximumFractionDigits: 1,
  });
  const fmtDecimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
  const fmtData = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" });

  const estado = {
    ufs: [],
    malha: null,
    ufSelecionada: null,
    metodo: "C1",
    ano: 2026,
  };

  // ------------------------------------------------------------- utilidades

  async function pedir(caminho) {
    const resposta = await fetch(`${API}${caminho}`, { headers: { Accept: "application/json" } });
    if (!resposta.ok) {
      let detalhe = `HTTP ${resposta.status}`;
      try {
        const corpo = await resposta.json();
        detalhe = corpo.detail || detalhe;
      } catch (_) {
        /* corpo não era JSON; o status já basta */
      }
      throw new Error(detalhe);
    }
    return resposta.json();
  }

  function el(tag, classe, texto) {
    const no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto !== undefined && texto !== null) no.textContent = texto;
    return no;
  }

  function svg(tag, atributos = {}) {
    const no = document.createElementNS(NS, tag);
    for (const [chave, valor] of Object.entries(atributos)) {
      if (valor !== null && valor !== undefined) no.setAttribute(chave, String(valor));
    }
    return no;
  }

  function numero(valor, formatador = fmtInteiro) {
    if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
    return formatador.format(valor);
  }

  function dataCurta(iso) {
    if (!iso) return "—";
    const data = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
    return Number.isNaN(data.getTime()) ? iso : fmtData.format(data);
  }

  function limpar(no) {
    if (no) no.replaceChildren();
  }

  function mostrarErro(destino, mensagem) {
    if (!destino) return;
    limpar(destino);
    destino.append(el("p", "erro", `Não foi possível carregar: ${mensagem}`));
  }

  function corDaIncidencia(incidencia, disponivel) {
    if (!disponivel || incidencia === null || incidencia === undefined) return CORES.sem;
    if (incidencia < 2) return CORES.faixas[0];
    if (incidencia < 5) return CORES.faixas[1];
    if (incidencia < 10) return CORES.faixas[2];
    if (incidencia < 20) return CORES.faixas[3];
    return CORES.faixas[4];
  }

  function chaveSemana(ponto) {
    return (ponto.ano || 0) * 100 + (ponto.semana || 0);
  }

  // ------------------------------------------------------- topo: situação

  async function carregarStatus() {
    const selo = document.getElementById("status-coleta");
    try {
      const saude = await pedir("/saude");
      if (saude.status === "ok") {
        const quando = saude.ultima_semana ? `Dados até ${saude.ultima_semana}` : "Dados carregados";
        selo.textContent =
          `${quando} · ${numero(saude.ufs)} estados · ${numero(saude.casos)} registros semanais · ` +
          `${numero(saude.municipios)} municípios`;
        selo.classList.add("ok");
      } else {
        selo.textContent = "Coleta ainda não executada — o painel está sem números.";
        selo.classList.add("alerta");
      }
    } catch (erro) {
      selo.textContent = `Não foi possível ler a situação do painel: ${erro.message}`;
      selo.classList.add("alerta");
    }
  }

  // ----------------------------------------------------- topo: KPIs gerais

  async function carregarResumo() {
    const destino = document.getElementById("kpis");
    try {
      const resumo = await pedir("/resumo");
      const cartoes = [
        ["Casos na semana", numero(resumo.casos_semana), `SE ${resumo.semana || "—"} de ${resumo.ano || "—"}`, null],
        ["Estados com dado", `${numero(resumo.ufs_com_dado)}/${numero(resumo.ufs_total)}`, "com publicação na semana", null],
        ["Estados em anomalia", numero(resumo.ufs_anomalia_12s), "sinal de EARS nas últimas 12 semanas", null],
        ["Repasses federais", numero(resumo.repasses_total, fmtMoedaCompacta), "somatório coletado", "#subsidios"],
        ["Estações de clima", numero(resumo.estacoes), "com série diária", null],
        [
          "Fontes coletadas",
          `${numero(resumo.fontes_ok)}/${numero(resumo.fontes_total)}`,
          "abrir a lista de fontes",
          "#fontes",
        ],
      ];
      limpar(destino);
      for (const [rotulo, valor, pe, href] of cartoes) {
        const cartao = el(href ? "a" : "div", `kpi${href ? " kpi--link" : ""}`);
        if (href) cartao.href = href;
        cartao.append(
          el("span", "kpi__rotulo", rotulo),
          el("span", "kpi__valor", valor),
          el("span", "kpi__pe", pe),
        );
        destino.append(cartao);
      }
    } catch (erro) {
      mostrarErro(destino, erro.message);
    }
  }

  // ------------------------------------------------------------------ mapa

  function mercador(lat) {
    // A latitude vai para radianos no cálculo, mas o resultado volta em graus:
    // a longitude do GeoJSON está em graus e misturar as duas unidades achata
    // o mapa (foi o que deixou o Brasil com 2 px de altura na primeira versão).
    const rad = (lat * Math.PI) / 180;
    return (Math.log(Math.tan(Math.PI / 4 + rad / 2)) * 180) / Math.PI;
  }

  function aneisDaGeometria(geometria) {
    if (!geometria) return [];
    if (geometria.type === "Polygon") return geometria.coordinates;
    if (geometria.type === "MultiPolygon") return geometria.coordinates.flat();
    return [];
  }

  function ufDoCodigo(codigo) {
    return (estado.ufs || []).find((linha) => String(linha.codigo_ibge) === String(codigo));
  }

  function textoDaUf(situacao, codigo) {
    if (!situacao) return `Estado ${codigo}: fora da base do IBGE`;
    if (!situacao.disponivel) return `${situacao.nome}: sem dado publicado na semana`;
    return (
      `${situacao.nome} · ${numero(situacao.casos)} casos · ` +
      `${numero(situacao.incidencia, fmtDecimal)} por 100 mil`
    );
  }

  /** Cria o SVG do mapa com projeção de Mercator ajustada à caixa. */
  function desenharMapa(malha) {
    const largura = 640;
    const altura = 620;
    const margem = 10;

    let xMin = Infinity;
    let xMax = -Infinity;
    let yMin = Infinity;
    let yMax = -Infinity;
    for (const feature of malha.features) {
      for (const anel of aneisDaGeometria(feature.geometry)) {
        for (const [lon, lat] of anel) {
          if (lon < xMin) xMin = lon;
          if (lon > xMax) xMax = lon;
          const my = mercador(lat);
          if (my < yMin) yMin = my;
          if (my > yMax) yMax = my;
        }
      }
    }

    const escala = Math.min((largura - 2 * margem) / (xMax - xMin), (altura - 2 * margem) / (yMax - yMin));
    const deslocamentoX = (largura - (xMax - xMin) * escala) / 2;
    const deslocamentoY = (altura - (yMax - yMin) * escala) / 2;
    const projetar = ([lon, lat]) => [
      deslocamentoX + (lon - xMin) * escala,
      deslocamentoY + (yMax - mercador(lat)) * escala,
    ];

    const raiz = svg("svg", {
      viewBox: `0 0 ${largura} ${altura}`,
      role: "img",
      "aria-label": "Mapa do Brasil dividido por estado, colorido pela incidência de dengue",
    });

    const dica = el("div", "mapa__dica");
    const recipiente = document.getElementById("mapa");

    for (const feature of malha.features) {
      const codigo = String(feature.properties.codarea || "");

      const partes = [];
      for (const anel of aneisDaGeometria(feature.geometry)) {
        anel.forEach((ponto, indice) => {
          const [x, y] = projetar(ponto);
          partes.push(`${indice === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`);
        });
        partes.push("Z");
      }

      const caminho = svg("path", {
        d: partes.join(" "),
        fill: CORES.sem,
        tabindex: "0",
        role: "button",
        "aria-label": "estado",
      });
      // O código do IBGE é a ponte estável entre a malha e o JSON da API: o
      // mapa é desenhado antes de os dados chegarem, então guardar a UF na
      // criação deixaria todos os estados sem identificação.
      caminho.dataset.codigo = codigo;
      caminho.append(svg("title"));

      const mostrar = (evento) => {
        const caixa = recipiente.getBoundingClientRect();
        dica.textContent = caminho.firstChild.textContent;
        dica.style.left = `${evento.clientX - caixa.left}px`;
        dica.style.top = `${evento.clientY - caixa.top}px`;
        dica.classList.add("visivel");
      };

      caminho.addEventListener("pointermove", mostrar);
      caminho.addEventListener("pointerleave", () => dica.classList.remove("visivel"));
      caminho.addEventListener("focus", () => {
        const caixa = recipiente.getBoundingClientRect();
        const alvo = caminho.getBoundingClientRect();
        dica.textContent = caminho.firstChild.textContent;
        dica.style.left = `${alvo.left - caixa.left + alvo.width / 2}px`;
        dica.style.top = `${alvo.top - caixa.top + alvo.height / 2}px`;
        dica.classList.add("visivel");
      });
      caminho.addEventListener("blur", () => dica.classList.remove("visivel"));

      const abrir = () => {
        const atual = ufDoCodigo(codigo);
        if (atual) selecionarEstado(atual.uf);
      };
      caminho.addEventListener("click", abrir);
      caminho.addEventListener("keydown", (evento) => {
        if (evento.key === "Enter" || evento.key === " ") {
          evento.preventDefault();
          abrir();
        }
      });

      raiz.append(caminho);
    }

    limpar(recipiente);
    recipiente.append(raiz, dica);
    estado.malha = raiz;
  }

  function pintarMapa() {
    if (!estado.malha) return;
    for (const caminho of estado.malha.querySelectorAll("path")) {
      const situacao = ufDoCodigo(caminho.dataset.codigo);
      const texto = textoDaUf(situacao, caminho.dataset.codigo);
      caminho.setAttribute("fill", corDaIncidencia(situacao?.incidencia, situacao?.disponivel));
      caminho.setAttribute("aria-label", texto);
      caminho.classList.toggle("sem-dado", !situacao?.disponivel);
      caminho.classList.toggle("selecionado", situacao?.uf === estado.ufSelecionada);
      if (caminho.firstChild) caminho.firstChild.textContent = texto;
    }
  }

  function montarLegenda() {
    const destino = document.getElementById("legenda");
    const faixas = [
      ["sem dado", CORES.sem],
      ["até 2", CORES.faixas[0]],
      ["2 a 5", CORES.faixas[1]],
      ["5 a 10", CORES.faixas[2]],
      ["10 a 20", CORES.faixas[3]],
      ["20 ou mais", CORES.faixas[4]],
    ];
    limpar(destino);
    for (const [rotulo, cor] of faixas) {
      const item = el("li");
      const marca = el("i");
      marca.style.background = cor;
      item.append(marca, document.createTextNode(rotulo));
      destino.append(item);
    }
  }

  // -------------------------------------------------------------- ranking

  function desenharRanking(destino, itens, { aoClicar, formatarValor } = {}) {
    limpar(destino);
    if (!itens.length) {
      destino.append(el("p", "nota", "Sem dado para ranquear nesta semana."));
      return;
    }
    const maximo = Math.max(...itens.map((item) => item.valor || 0)) || 1;

    for (const item of itens) {
      const linha = el(aoClicar ? "button" : "div", "barra");
      if (aoClicar) {
        linha.type = "button";
        linha.addEventListener("click", () => aoClicar(item.uf));
        if (item.uf === estado.ufSelecionada) linha.setAttribute("aria-current", "true");
      }
      const trilho = el("div", "barra__trilho");
      const preenchimento = el("div", "barra__preenchimento");
      preenchimento.style.width = `${Math.max(2, ((item.valor || 0) / maximo) * 100)}%`;
      if (item.cor) preenchimento.style.background = item.cor;
      trilho.append(preenchimento);
      linha.append(
        el("span", "barra__uf", item.uf),
        trilho,
        el("span", "barra__valor", formatarValor ? formatarValor(item.valor) : numero(item.valor, fmtDecimal)),
      );
      destino.append(linha);
    }
  }

  // --------------------------------------------------------------- tabela

  function montarTabela(destino, colunas, linhas, legenda, limite = 10) {
    limpar(destino);
    const tabela = el("table");
    if (legenda) tabela.append(el("caption", null, legenda));

    const th = el("thead");
    const linhaCabecalho = el("tr");
    for (const coluna of colunas) {
      const celula = el("th", coluna.numerica ? "numero" : null, coluna.titulo);
      celula.scope = "col";
      linhaCabecalho.append(celula);
    }
    th.append(linhaCabecalho);
    tabela.append(th);

    const corpo = el("tbody");
    for (const linha of linhas.slice(0, limite)) {
      const tr = el("tr");
      for (const coluna of colunas) {
        const td = el("td", coluna.numerica ? "numero" : null, coluna.valor(linha));
        td.dataset.rotulo = coluna.titulo;
        tr.append(td);
      }
      corpo.append(tr);
    }
    tabela.append(corpo);
    destino.append(tabela);

    // Tabela longa no celular vira 30 cartões e a página fica sem fim.
    // Mostrar dez e oferecer o resto sob demanda mantém a leitura possível.
    if (linhas.length > limite) {
      const botao = el("button", "botao botao--texto", `Mostrar todas as ${linhas.length} linhas`);
      botao.type = "button";
      botao.addEventListener("click", () =>
        montarTabela(destino, colunas, linhas, legenda, linhas.length),
      );
      const rodape = el("div", "tabela-rodape");
      rodape.append(botao);
      destino.append(rodape);
    }
  }

  // ------------------------------------------------------------ série SVG

  /**
   * Gráfico da série semanal: barra por semana + linha tracejada do limite
   * do EARS. Barra em vez de linha porque o dado é contagem inteira por
   * semana — barra não sugere continuidade entre semanas que não existe.
   */
  function desenharSerie(semanas, ultima) {
    const usadas = semanas.slice(-30);
    const largura = 520;
    const altura = 220;
    const margem = { topo: 14, direita: 10, base: 34, esquerda: 42 };
    const areaLargura = largura - margem.esquerda - margem.direita;
    const areaAltura = altura - margem.topo - margem.base;

    const valores = usadas.flatMap((ponto) =>
      [ponto.casos, ponto.limite].filter((valor) => valor !== null && valor !== undefined),
    );
    const maximo = Math.max(1, ...valores) * 1.08;

    const passo = areaLargura / Math.max(1, usadas.length);
    const centro = (indice) => margem.esquerda + passo * (indice + 0.5);
    const y = (valor) => margem.topo + areaAltura - (valor / maximo) * areaAltura;

    const raiz = svg("svg", {
      viewBox: `0 0 ${largura} ${altura}`,
      class: "serie",
      role: "img",
      "aria-label":
        "Casos de dengue por semana epidemiológica, com a linha de limite de alerta do método EARS",
    });

    // Grade horizontal + rótulo do eixo vertical.
    for (let faixa = 0; faixa <= 3; faixa += 1) {
      const valor = (maximo / 3) * faixa;
      raiz.append(
        svg("line", {
          x1: margem.esquerda,
          x2: largura - margem.direita,
          y1: y(valor),
          y2: y(valor),
          class: "eixo",
        }),
      );
      const rotulo = svg("text", { x: 2, y: y(valor) + 3, class: "rotulo" });
      rotulo.textContent = numero(Math.round(valor), maximo > 999 ? fmtCompacto : fmtInteiro);
      raiz.append(rotulo);
    }

    const referencia = ultima ? chaveSemana(ultima) : null;

    usadas.forEach((ponto, indice) => {
      if (ponto.casos === null || ponto.casos === undefined) return;
      const alturaBarra = Math.max(1.5, y(0) - y(ponto.casos));
      const parcial = referencia !== null && chaveSemana(ponto) > referencia;
      const barra = svg("rect", {
        x: centro(indice) - passo * 0.34,
        y: y(ponto.casos),
        width: passo * 0.68,
        height: alturaBarra,
        rx: Math.min(3, passo * 0.2),
        fill: parcial ? CORES.parcial : ponto.anomalo ? CORES.alerta : CORES.linha,
        opacity: ponto.anomalo ? 1 : 0.92,
      });
      barra.append(svg("title"));
      barra.firstChild.textContent =
        `SE ${ponto.semana} de ${ponto.ano}: ${numero(ponto.casos)} casos` +
        (ponto.limite ? ` · limite ${numero(Math.round(ponto.limite))}` : "") +
        (ponto.anomalo ? " · acima do limite" : "") +
        (parcial ? " · semana em curso" : "");
      raiz.append(barra);
    });

    // Limite do EARS: linha tracejada, sem preenchimento.
    const pontosLimite = usadas
      .map((ponto, indice) =>
        ponto.limite === null || ponto.limite === undefined
          ? null
          : `${centro(indice).toFixed(1)} ${y(ponto.limite).toFixed(1)}`,
      )
      .filter(Boolean);
    if (pontosLimite.length > 1) {
      raiz.append(
        svg("path", {
          d: `M${pontosLimite.join(" L")}`,
          fill: "none",
          stroke: CORES.alerta,
          "stroke-width": 1.6,
          "stroke-dasharray": "5 4",
          opacity: 0.8,
        }),
      );
    }

    // Eixo horizontal: semana epidemiológica, em passos que cabem na largura.
    const passoRotulo = Math.max(1, Math.ceil(usadas.length / 6));
    usadas.forEach((ponto, indice) => {
      const ultimo = indice === usadas.length - 1;
      if (indice % passoRotulo !== 0 && !ultimo) return;
      const rotulo = svg("text", {
        x: centro(indice),
        y: altura - 16,
        class: "rotulo",
        "text-anchor": "middle",
      });
      rotulo.textContent = `SE ${ponto.semana}`;
      raiz.append(rotulo);
    });

    const anos = [...new Set(usadas.map((ponto) => ponto.ano))].join(" e ");
    const notaAno = svg("text", {
      x: largura - margem.direita,
      y: altura - 3,
      class: "rotulo",
      "text-anchor": "end",
    });
    notaAno.textContent = `semanas epidemiológicas · ${anos}`;
    raiz.append(notaAno);

    return raiz;
  }

  // ---------------------------------------------------------- detalhe da UF

  function blocoNumeros(ultima) {
    const lista = el("dl", "detalhe__numeros");
    const itens = [
      ["Casos na semana", ultima && ultima.casos !== null ? numero(ultima.casos) : "—"],
      ["Limite do EARS", ultima && ultima.limite !== null ? numero(Math.round(ultima.limite)) : "—"],
      ["Anomalia", ultima && ultima.anomalo ? "sim" : "não"],
    ];
    for (const [rotulo, valor] of itens) {
      const bloco = el("div");
      bloco.append(el("dt", null, rotulo), el("dd", null, valor));
      lista.append(bloco);
    }
    return lista;
  }

  function blocoContexto(contexto) {
    const caixa = el("section", "contexto");
    caixa.append(el("h4", null, "Quem respondia naquele período"));
    const lista = el("ul", "lista-limpa");
    const linhas = [];
    if (contexto.governador) {
      linhas.push([
        `Governador(a) — ${contexto.governador.cargo_inicio || "mandato"}`,
        `${contexto.governador.nome} (${contexto.governador.partido})`,
      ]);
    }
    if (contexto.presidente) {
      linhas.push([
        "Presidente da República",
        `${contexto.presidente.nome} (${contexto.presidente.partido})`,
      ]);
    }
    for (const ministro of contexto.ministros_saude || []) {
      linhas.push([
        `Ministro(a) da Saúde · ${ministro.periodo}`,
        `${ministro.nome} (${ministro.partido})`,
      ]);
    }
    for (const [rotulo, valor] of linhas) {
      const item = el("li");
      item.append(el("span", null, rotulo), el("strong", null, valor));
      lista.append(item);
    }
    caixa.append(lista);
    if (contexto.aviso) caixa.append(el("p", "nota", contexto.aviso));
    return caixa;
  }

  async function selecionarEstado(uf) {
    if (!uf) return;
    estado.ufSelecionada = uf;
    const seletor = document.getElementById("seletor-uf");
    if (seletor && seletor.value !== uf) seletor.value = uf;
    pintarMapa();
    atualizarRanking();
    destacarGovernador(uf);

    const destino = document.getElementById("detalhe");
    destino.setAttribute("aria-busy", "true");
    limpar(destino);
    destino.append(el("p", "nota", "Carregando…"));

    try {
      const [serie, repasses, clima, contexto] = await Promise.all([
        pedir(`/estados/${uf}?metodo=${estado.metodo}`),
        pedir(`/estados/${uf}/repasses?limite=6`),
        pedir(`/estados/${uf}/clima`),
        pedir(`/estados/${uf}/contexto`),
      ]);

      const situacao = estado.ufs.find((linha) => linha.uf === uf);
      // O selo olha a mesma semana que os cartões de número mostram. Misturar
      // a semana de referência nacional com a última publicada pelo estado
      // fazia o painel dizer "anomalia" olhando para outra semana.
      const referencia = serie.ultima;
      const anomalo = Boolean(referencia && referencia.anomalo);
      const temDado = Boolean(referencia && referencia.casos !== null && referencia.casos !== undefined);
      limpar(destino);

      const cabecalho = el("div", "detalhe__cabecalho");
      cabecalho.append(
        el("span", "detalhe__uf", situacao?.nome || uf),
        el("span", "detalhe__semana", referencia ? `SE ${referencia.semana} de ${referencia.ano}` : ""),
      );
      const selo = el(
        "span",
        `selo ${anomalo ? "selo--alerta" : temDado ? "selo--ok" : "selo--neutro"}`,
        anomalo ? "anomalia" : temDado ? "dentro do esperado" : "sem dado",
      );
      cabecalho.append(selo);
      destino.append(cabecalho);

      destino.append(blocoNumeros(referencia));
      destino.append(desenharSerie(serie.semanas, referencia));
      destino.append(
        el(
          "p",
          "nota",
          `Método ${serie.metodo} · barra = casos da semana · linha tracejada = limite de alerta · ` +
            `barra clara = semana ainda em curso`,
        ),
      );

      destino.append(el("h4", null, "Repasses federais (12 meses)"));
      if (repasses.disponivel) {
        const lista = el("ul", "lista-limpa");
        const total = el("li");
        total.append(el("span", null, "Total no período"), el("strong", null, numero(repasses.total, fmtMoeda)));
        lista.append(total);
        for (const repasse of repasses.repasses.slice(0, 4)) {
          const item = el("li");
          item.append(el("span", null, repasse.descricao), el("strong", null, numero(repasse.valor, fmtMoeda)));
          lista.append(item);
        }
        destino.append(lista);
        destino.append(el("p", "nota", `Período: ${repasses.periodo || "não informado"}`));
      } else {
        destino.append(
          el("p", "nota", "Nenhum repasse de saúde registrado para este estado no período coletado."),
        );
      }

      destino.append(el("h4", null, "Clima favorável à reprodução do mosquito"));
      if (clima.length) {
        const lista = el("ul", "lista-limpa");
        for (const alerta of clima.slice(0, 3)) {
          const item = el("li");
          item.append(
            el("span", null, `${alerta.municipio} · ${alerta.nivel}`),
            el(
              "strong",
              null,
              alerta.chuva_7d_mm === null ? "—" : `${numero(alerta.chuva_7d_mm, fmtDecimal)} mm`,
            ),
          );
          lista.append(item);
        }
        destino.append(lista);
      } else {
        destino.append(el("p", "nota", "Sem leitura de clima coletada para os municípios deste estado."));
      }

      destino.append(blocoContexto(contexto));
    } catch (erro) {
      mostrarErro(destino, erro.message);
    } finally {
      destino.removeAttribute("aria-busy");
    }
  }

  // ------------------------------------------------------------- estados

  function atualizarRanking() {
    const ranking = estado.ufs
      .filter((linha) => linha.disponivel && linha.incidencia !== null)
      .map((linha) => ({ uf: linha.uf, valor: linha.incidencia }))
      .sort((a, b) => b.valor - a.valor)
      .slice(0, 12);

    desenharRanking(document.getElementById("ranking"), ranking, {
      aoClicar: selecionarEstado,
      formatarValor: (valor) => `${numero(valor, fmtDecimal)}/100 mil`,
    });
  }

  function preencherSeletor() {
    const seletor = document.getElementById("seletor-uf");
    limpar(seletor);
    for (const linha of [...estado.ufs].sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"))) {
      const opcao = el("option", null, `${linha.uf} — ${linha.nome}`);
      opcao.value = linha.uf;
      seletor.append(opcao);
    }
    if (estado.ufSelecionada) seletor.value = estado.ufSelecionada;
  }

  function montarTabelaEstados() {
    const linhas = [...estado.ufs]
      .sort((a, b) => (b.incidencia ?? -1) - (a.incidencia ?? -1))
      .map((linha) => ({ ...linha, _casos: linha.disponivel ? numero(linha.casos) : "sem dado" }));

    montarTabela(
      document.getElementById("tabela-estados"),
      [
        { titulo: "UF", valor: (linha) => linha.uf },
        { titulo: "Estado", valor: (linha) => linha.nome },
        { titulo: "Casos", numerica: true, valor: (linha) => linha._casos },
        {
          titulo: "Incidência",
          numerica: true,
          valor: (linha) => (linha.incidencia === null ? "—" : numero(linha.incidencia, fmtDecimal)),
        },
        { titulo: "Situação", valor: (linha) => (linha.anomalo ? "anomalia" : linha.disponivel ? "esperado" : "—") },
      ],
      linhas,
      "Incidência por 100 mil habitantes na última semana publicada",
    );
  }

  async function carregarEstados(ufInicial) {
    try {
      estado.ufs = await pedir(`/estados?metodo=${estado.metodo}`);
      preencherSeletor();
      pintarMapa();
      atualizarRanking();
      montarTabelaEstados();

      const inicial =
        ufInicial ||
        estado.ufs
          .filter((linha) => linha.disponivel && linha.incidencia !== null)
          .sort((a, b) => b.incidencia - a.incidencia)[0]?.uf ||
        estado.ufs[0]?.uf;
      if (inicial) await selecionarEstado(inicial);
    } catch (erro) {
      mostrarErro(document.getElementById("detalhe"), erro.message);
      mostrarErro(document.getElementById("ranking"), erro.message);
    }
  }

  // ------------------------------------------------------------ subsídios

  function kpiClaro(rotulo, valor, pe) {
    const cartao = el("div", "kpi");
    cartao.append(
      el("span", "kpi__rotulo", rotulo),
      el("span", "kpi__valor", valor),
      el("span", "kpi__pe", pe),
    );
    return cartao;
  }

  function nomeDoEixo(eixo) {
    if (eixo === "saude_fundo_a_fundo") return "Saúde · fundo a fundo";
    if (eixo === "cidades_discricionaria") return "Cidades · discricionária";
    return eixo;
  }

  async function carregarSubsidios() {
    const destinoKpis = document.getElementById("kpis-subsidios");
    const destinoProgramas = document.getElementById("programas");
    const destinoRanking = document.getElementById("ranking-subsidios");

    try {
      const dados = await pedir(`/subsidios?ano=${estado.ano}`);
      const totais = dados.totais;

      limpar(destinoKpis);
      destinoKpis.append(
        kpiClaro("Programas no ano", numero(totais.programas), `${dados.ano}`),
        kpiClaro("Propostas", numero(totais.propostas), "apresentadas ao governo federal"),
        kpiClaro("Aprovadas", numero(totais.aprovadas), "situação de aprovação no cadastro"),
        kpiClaro("Valor planejado", numero(totais.valor_planejado, fmtMoedaCompacta), "soma das propostas"),
        kpiClaro("Valor de repasse", numero(totais.valor_repasse, fmtMoedaCompacta), "eixo Cidades"),
        kpiClaro("Estados com proposta", numero(totais.ufs_com_proposta), `de ${numero(totais.ufs_total || 27)}`),
      );

      limpar(destinoProgramas);
      document.getElementById("programas-nota").textContent =
        `${numero(totais.programas)} programas disponibilizados em ${dados.ano}, do mais recente ao mais antigo.`;
      if (!dados.programas.length) {
        destinoProgramas.append(el("p", "nota", "Nenhum programa coletado para este ano."));
      }
      for (const programa of dados.programas) {
        const cartao = el("article", "programa");
        const cidades = programa.orgao.includes("CIDADES");
        cartao.append(
          el("p", `programa__orgao${cidades ? " programa__orgao--cidades" : ""}`, programa.orgao),
          el("p", "programa__nome", programa.nome),
        );
        const meta = el("p", "programa__meta");
        meta.append(
          el("span", null, programa.modalidade || "modalidade não informada"),
          el("span", null, programa.situacao || "situação não informada"),
          el("span", null, `disponível em ${dataCurta(programa.data_disponibilizacao)}`),
        );
        cartao.append(meta);
        destinoProgramas.append(cartao);
      }

      // Ranking: soma dos dois eixos por estado.
      const porUf = new Map();
      for (const linha of dados.ufs) {
        porUf.set(linha.uf, (porUf.get(linha.uf) || 0) + (linha.valor_planejado || 0));
      }
      const ranking = [...porUf.entries()]
        .map(([uf, valor]) => ({ uf, valor }))
        .sort((a, b) => b.valor - a.valor)
        .slice(0, 12);
      desenharRanking(destinoRanking, ranking, {
        aoClicar: selecionarEstado,
        formatarValor: (valor) => numero(valor, fmtMoedaCompacta),
      });

      montarTabela(
        document.getElementById("tabela-subsidios"),
        [
          { titulo: "UF", valor: (linha) => linha.uf },
          { titulo: "Eixo", valor: (linha) => nomeDoEixo(linha.eixo) },
          { titulo: "Propostas", numerica: true, valor: (linha) => numero(linha.propostas) },
          { titulo: "Aprovadas", numerica: true, valor: (linha) => numero(linha.aprovadas) },
          { titulo: "Valor planejado", numerica: true, valor: (linha) => numero(linha.valor_planejado, fmtMoeda) },
          {
            titulo: "Repasse",
            numerica: true,
            valor: (linha) => (linha.valor_repasse ? numero(linha.valor_repasse, fmtMoeda) : "—"),
          },
        ],
        dados.ufs,
        `Propostas e valores por estado em ${dados.ano}`,
      );

      document.getElementById("aviso-subsidios").textContent = dados.aviso_metodologico;
      document.getElementById("subsidios-lead").textContent =
        `Programas do Ministério da Saúde e do Ministério das Cidades em ${dados.ano}, ` +
        "com o número de propostas apresentadas e o valor planejado por estado.";
    } catch (erro) {
      mostrarErro(destinoKpis, erro.message);
      mostrarErro(destinoProgramas, erro.message);
      mostrarErro(destinoRanking, erro.message);
    }
  }

  // ---------------------------------------------------- contexto político

  // Cor fixa por partido: a mesma legenda vale para o mapa de governadores e
  // para qualquer outro bloco que use partido, e o leitor reconhece a cor
  // antes de ler o nome.
  const PARTIDOS = {
    PT: "#c0261f",
    PL: "#1e40af",
    "UNIÃO": "#0e7490",
    PP: "#7c3aed",
    MDB: "#059669",
    PSD: "#b45309",
    PSDB: "#2563eb",
    PSB: "#ca8a04",
    REPUBLICANOS: "#15803d",
    NOVO: "#ea580c",
    SOLIDARIEDADE: "#db2777",
    DEM: "#6b7280",
    "sem partido": "#94a3b8",
  };

  function corDoPartido(partido) {
    return PARTIDOS[partido] || "#64748b";
  }

  const SITUACOES = {
    em_exercicio: "em exercício",
    cargo_eletivo: "cargo eletivo",
    setor_privado: "setor privado",
    instituicao_publica: "instituição pública",
    aposentado: "aposentado",
    nao_verificado: "não verificado",
  };

  function montarTimeline(destino, historico, atual) {
    limpar(destino);
    const chaveAtual = atual ? `${atual.nome}|${atual.periodo}` : "";
    for (const ministro of historico) {
      const item = el(
        "div",
        `timeline__item${`${ministro.nome}|${ministro.periodo}` === chaveAtual ? " timeline__item--atual" : ""}`,
      );
      item.append(
        el("p", "timeline__periodo", ministro.periodo),
        el("p", "timeline__nome", ministro.nome),
      );
      const partido = el("span", "timeline__partido", ministro.partido);
      partido.style.color = corDoPartido(ministro.partido);
      partido.style.borderColor = corDoPartido(ministro.partido);
      item.append(partido);

      // Situação depois do cargo: só entra na tela o que foi conferido. O que
      // falta aparece como "não verificado" — melhor do que afirmar algo sobre
      // uma pessoa real sem fonte.
      const pos = ministro.pos_mandato;
      if (pos) {
        const rotulo = SITUACOES[pos.situacao] || pos.situacao;
        const chip = el(
          "span",
          `timeline__pos${pos.verificado ? "" : " timeline__pos--pendente"}`,
          pos.verificado ? rotulo : "situação não verificada",
        );
        item.append(chip);
        if (pos.verificado) {
          const detalhe = el("p", "timeline__detalhe", pos.resumo);
          item.append(detalhe);
        }
      }
      destino.append(item);
    }
  }

  function montarGovernadores(destino, governadores, siglaSelecionada) {
    limpar(destino);
    const ordenados = [...governadores].sort((a, b) => a.uf.localeCompare(b.uf));
    for (const governador of ordenados) {
      const cor = corDoPartido(governador.partido);
      const cartao = el(
        "article",
        `governador${governador.uf === siglaSelecionada ? " governador--atual" : ""}`,
      );
      cartao.style.borderLeftColor = cor;
      cartao.dataset.uf = governador.uf;
      cartao.append(
        el("span", "governador__uf", governador.uf),
        el("span", "governador__nome", governador.nome),
      );
      const partido = el("span", "governador__partido", governador.partido);
      partido.style.color = cor;
      cartao.append(partido);
      destino.append(cartao);
    }
  }

  function montarLegendaPartidos(destino, governadores) {
    limpar(destino);
    const contagem = new Map();
    for (const governador of governadores) {
      contagem.set(governador.partido, (contagem.get(governador.partido) || 0) + 1);
    }
    for (const [partido, total] of [...contagem.entries()].sort((a, b) => b[1] - a[1])) {
      const item = el("li");
      const marca = el("i");
      marca.style.background = corDoPartido(partido);
      item.append(marca, document.createTextNode(`${partido} (${total})`));
      destino.append(item);
    }
  }

  function destacarGovernador(uf) {
    const destino = document.getElementById("governadores");
    if (!destino) return;
    for (const cartao of destino.querySelectorAll(".governador")) {
      cartao.classList.toggle("governador--atual", cartao.dataset.uf === uf);
    }
  }

  async function carregarContexto() {
    const destino = document.getElementById("governadores");
    try {
      const dados = await pedir("/contexto");
      const atual = (dados.ministros_saude || [])[0] || null;
      montarTimeline(document.getElementById("timeline-ministros"), dados.historico_ministros, atual);
      montarLegendaPartidos(document.getElementById("legenda-partidos"), dados.governadores);
      montarGovernadores(destino, dados.governadores, estado.ufSelecionada);
      document.getElementById("contexto-aviso").textContent = dados.aviso;
      document.getElementById("contexto-limitacao").textContent = dados.limitacao || "";
    } catch (erro) {
      mostrarErro(destino, erro.message);
    }
  }

  // ---------------------------------------------------------------- fontes

  // Logo oficial quando existe arquivo local; quando não existe, o nome do
  // órgão em texto. Nada é carregado de servidor de terceiros.
  const LOGOS = {
    ibge_localidades: { src: "/static/img/fontes/ibge.svg", alt: "Logotipo do IBGE" },
    infodengue_sinan: { src: "/static/img/fontes/infodengue.png", alt: "Logotipo do InfoDengue" },
    infodengue_alertcity: { src: "/static/img/fontes/infodengue.png", alt: "Logotipo do InfoDengue" },
    inmet_estacoes: { src: "/static/img/fontes/inmet.png", alt: "Logotipo do INMET" },
    portal_transparencia_transferencias: {
      src: "/static/img/fontes/cgu.png",
      alt: "Logotipo da Controladoria-Geral da União",
    },
    transferegov_subsidios: { texto: "Transferegov" },
    open_meteo: { texto: "Open-Meteo" },
    curadoria_responsaveis: { texto: "Curadoria própria" },
  };

  async function carregarFontes() {
    const destino = document.getElementById("fontes-lista");
    try {
      const fontes = await pedir("/fontes");
      limpar(destino);
      for (const fonte of fontes) {
        const cartao = el("article", "fonte");
        const logo = el("div", "fonte__logo");
        const marca = LOGOS[fonte.id];
        if (marca && marca.src) {
          const imagem = el("img");
          imagem.src = marca.src;
          imagem.alt = marca.alt;
          imagem.loading = "lazy";
          logo.append(imagem);
        } else {
          logo.classList.add("fonte__logo--texto");
          logo.textContent = (marca && marca.texto) || fonte.orgao;
        }

        const status = el(
          "span",
          `fonte__status fonte__status--${fonte.status === "ok" ? "ok" : "falha"}`,
          fonte.status === "ok" ? "coletada" : fonte.status,
        );

        const meta = el("div", "fonte__meta");
        meta.append(
          el("span", null, `Período: ${fonte.periodo_referencia || "não informado"}`),
          el("span", null, `Coleta: ${dataCurta(fonte.coletado_em)}`),
        );
        if (fonte.licenca) meta.append(el("span", null, `Licença: ${fonte.licenca}`));

        const titulo = el("a", "fonte__nome", fonte.nome);
        titulo.href = fonte.url;
        titulo.target = "_blank";
        titulo.rel = "noopener noreferrer";

        cartao.append(logo, titulo, el("p", "fonte__orgao", fonte.orgao), meta, status);
        destino.append(cartao);
      }
    } catch (erro) {
      mostrarErro(destino, erro.message);
    }
  }

  // ---------------------------------------------------------------- início

  function lerUfDaUrl() {
    const parametro = new URLSearchParams(window.location.search).get("uf");
    return parametro ? parametro.toUpperCase() : null;
  }

  async function iniciar() {
    montarLegenda();

    document.getElementById("seletor-metodo").addEventListener("change", (evento) => {
      estado.metodo = evento.target.value;
      carregarEstados(estado.ufSelecionada);
    });

    document.getElementById("seletor-uf").addEventListener("change", (evento) => {
      selecionarEstado(evento.target.value);
      const url = new URL(window.location.href);
      url.searchParams.set("uf", evento.target.value);
      window.history.replaceState({}, "", url);
    });

    document.getElementById("seletor-ano").addEventListener("change", (evento) => {
      estado.ano = Number(evento.target.value);
      carregarSubsidios();
    });

    try {
      const malha = await fetch("/static/data/br_uf.geojson").then((resposta) => {
        if (!resposta.ok) throw new Error("malha do mapa não encontrada (rode a coleta do IBGE)");
        return resposta.json();
      });
      desenharMapa(malha);
    } catch (erro) {
      mostrarErro(document.getElementById("mapa"), erro.message);
    }

    await Promise.all([
      carregarStatus(),
      carregarResumo(),
      carregarEstados(lerUfDaUrl()),
      carregarSubsidios(),
      carregarContexto(),
      carregarFontes(),
    ]);
  }

  document.addEventListener("DOMContentLoaded", iniciar);
})();
