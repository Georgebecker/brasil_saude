/* =========================================================
   Brasil Saúde — painel sem framework, sem build.
   Regras de ouro do arquivo:
   1. nada de innerHTML com dado vindo da rede (XSS);
   2. todo texto exibido tem origem no JSON da API;
   3. quando um serviço falha, a tela mostra o motivo em português.
   ========================================================= */

(() => {
  "use strict";

  const API = "/api";
  const CORES = ["#c9d1cb", "#e3f2d9", "#b7dfa8", "#f4cf72", "#e88c45", "#c0392b"];

  const fmtNumero = new Intl.NumberFormat("pt-BR");
  const fmtCompacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
  const fmtMoeda = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
  const fmtData = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

  const estado = {
    ufSelecionada: null,
    mapa: null,
    camada: null,
    graficoSerie: null,
    graficoBarras: null,
    estados: [],
  };

  // ---------- utilidades ----------

  async function pedir(caminho) {
    const resposta = await fetch(`${API}${caminho}`, { headers: { Accept: "application/json" } });
    if (!resposta.ok) {
      let detalhe = `HTTP ${resposta.status}`;
      try {
        const corpo = await resposta.json();
        detalhe = corpo.detail || detalhe;
      } catch (_) {
        /* corpo não era JSON; mantém o status */
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

  function dataCurta(iso) {
    if (!iso) return "—";
    const data = new Date(iso);
    return Number.isNaN(data.getTime()) ? iso : fmtData.format(data);
  }

  function formatarNumero(valor, sufixo = "") {
    if (valor === null || valor === undefined) return "—";
    return fmtNumero.format(valor) + sufixo;
  }

  function corDaIncidencia(incidencia, disponivel) {
    if (!disponivel || incidencia === null || incidencia === undefined) return CORES[0];
    if (incidencia < 2) return CORES[1];
    if (incidencia < 5) return CORES[2];
    if (incidencia < 10) return CORES[3];
    if (incidencia < 20) return CORES[4];
    return CORES[5];
  }

  // ---------- topo ----------

  async function carregarStatus() {
    const selo = document.getElementById("status-coleta");
    try {
      const saude = await pedir("/saude");
      if (saude.status === "ok") {
        const semana = saude.ultima_semana ? `Dados até ${saude.ultima_semana}` : "Dados carregados";
        selo.textContent = `${semana} · ${fmtCompacto.format(saude.casos)} registros de casos`;
        selo.classList.add("ok");
      } else {
        selo.textContent = "Coleta ainda não executada — painel sem números";
        selo.classList.add("alerta");
      }
      if (saude.fontes_com_problema > 0) {
        selo.textContent += ` · ${saude.fontes_com_problema} fonte(s) com problema`;
      }
    } catch (erro) {
      selo.textContent = `Servidor indisponível: ${erro.message}`;
      selo.classList.add("alerta");
    }
  }

  // ---------- mapa ----------

  function estilizar(feature) {
    const codigo = feature.properties.codarea;
    const situacao = estado.estados.find((linha) => linha.codigo_ibge === codigo);
    const cor = corDaIncidencia(situacao?.incidencia, situacao?.disponivel);
    return {
      fillColor: cor,
      fillOpacity: 0.92,
      color: situacao?.anomalo ? "#9b1c1c" : "#ffffff",
      weight: situacao?.anomalo ? 2.2 : 1,
      dashArray: situacao?.anomalo ? "4 3" : null,
    };
  }

  function textoDoEstado(situacao) {
    if (!situacao || !situacao.disponivel) return `${situacao?.nome || ""} — sem dado na semana`;
    const incidencia =
      situacao.incidencia === null || situacao.incidencia === undefined
        ? ""
        : ` · ${fmtNumero.format(situacao.incidencia)} por 100 mil`;
    return `${situacao.nome}: ${fmtNumero.format(situacao.casos)} casos${incidencia}`;
  }

  async function montarMapa() {
    const resposta = await fetch("/static/data/br_uf.geojson");
    if (!resposta.ok) throw new Error("malha do mapa não encontrada (rode a coleta do IBGE)");
    const malha = await resposta.json();

    estado.mapa = L.map("mapa", {
      zoomControl: true,
      scrollWheelZoom: false,
      attributionControl: true,
    }).setView([-14.5, -52], 4);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 8,
      attribution: "&copy; OpenStreetMap",
    }).addTo(estado.mapa);

    estado.camada = L.geoJSON(malha, {
      style: estilizar,
      onEachFeature: (feature, camada) => {
        const situacao = estado.estados.find((linha) => linha.codigo_ibge === feature.properties.codarea);
        camada.bindTooltip(textoDoEstado(situacao), { sticky: true });
        camada.on("click", () => {
          if (situacao) selecionarEstado(situacao.uf);
        });
        camada.on("keypress", (evento) => {
          if (evento.originalEvent.key === "Enter" && situacao) selecionarEstado(situacao.uf);
        });
      },
    }).addTo(estado.mapa);

    estado.mapa.fitBounds(estado.camada.getBounds(), { padding: [12, 12] });
  }

  function atualizarMapa() {
    if (!estado.camada) return;
    estado.camada.setStyle(estilizar);
    estado.camada.eachLayer((camada) => {
      const codigo = camada.feature.properties.codarea;
      const situacao = estado.estados.find((linha) => linha.codigo_ibge === codigo);
      camada.setTooltipContent(textoDoEstado(situacao));
    });
  }

  // ---------- detalhe ----------

  function limparGraficos() {
    if (estado.graficoSerie) {
      estado.graficoSerie.destroy();
      estado.graficoSerie = null;
    }
    if (estado.graficoBarras) {
      estado.graficoBarras.destroy();
      estado.graficoBarras = null;
    }
  }

  function mostrarErro(container, mensagem) {
    container.replaceChildren();
    const aviso = el("p", "erro", `Não foi possível carregar: ${mensagem}`);
    container.append(aviso);
  }

  async function selecionarEstado(uf, metodo = "C1") {
    atualizarUrl(uf);
    estado.ufSelecionada = uf;
    document.getElementById("seletor-uf").value = uf;

    const painel = document.getElementById("detalhe");
    painel.setAttribute("aria-busy", "true");
    limparGraficos();
    painel.replaceChildren(el("p", "nota", "Carregando…"));

    try {
      const [serie, repasses, mensal, clima, responsaveis] = await Promise.all([
        pedir(`/estados/${uf}?metodo=${metodo}`),
        pedir(`/estados/${uf}/repasses?limite=8`),
        pedir(`/estados/${uf}/repasses/mensal`),
        pedir(`/estados/${uf}/clima?limite=8`).catch(() => []),
        pedir(`/estados/${uf}/responsaveis`).catch(() => []),
      ]);
      renderizarDetalhe(painel, serie, repasses, mensal, clima, responsaveis);
    } catch (erro) {
      mostrarErro(painel, erro.message);
    } finally {
      painel.removeAttribute("aria-busy");
    }
  }

  function renderizarDetalhe(painel, serie, repasses, mensal, clima, responsaveis) {
    const situacao = estado.estados.find((linha) => linha.uf === serie.uf);
    const ultima = serie.ultima || {};
    painel.replaceChildren();

    const cabecalho = el("div", "detalhe-cabecalho");
    cabecalho.append(
      el("h2", null, `${situacao?.nome || serie.uf}`),
      el("span", "uf-selo", serie.uf),
    );
    painel.append(cabecalho);

    // Alternância C1/C2: mesma série, mesma janela, atraso diferente. Fica
    // visível para o leitor comparar a sensibilidade do método.
    const linhaMetodo = el("div", "linha-metodo");
    const rotuloMetodo = el("label", "nota", "Variante do EARS ");
    const seletorMetodo = el("select");
    seletorMetodo.setAttribute("aria-label", "Variante do EARS");
    for (const [valor, texto] of [
      ["C1", "C1 — sem atraso (3 desvios)"],
      ["C2", "C2 — 2 dias de guarda (3 desvios)"],
    ]) {
      const opcao = el("option", null, texto);
      opcao.value = valor;
      if (serie.metodo === valor) opcao.selected = true;
      seletorMetodo.append(opcao);
    }
    seletorMetodo.addEventListener("change", (evento) => {
      selecionarEstado(serie.uf, evento.target.value);
    });
    rotuloMetodo.append(seletorMetodo);
    linhaMetodo.append(rotuloMetodo);
    painel.append(linhaMetodo);

    painel.append(
      el("p", "nota", `Semana ${ultima.rotulo || "—"} · ${serie.metodo} · casos notificados`),
    );

    // KPIs
    const areaSerie = el("section", "area-serie");
    const kpis = el("div", "kpis");
    kpis.append(
      kpi(formatarNumero(ultima.casos), "casos na semana"),
      kpi(
        ultima.esperado === null || ultima.esperado === undefined
          ? "—"
          : fmtNumero.format(Math.round(ultima.esperado)),
        "esperado (média)",
      ),
      kpi(
        ultima.limite === null || ultima.limite === undefined
          ? "—"
          : fmtNumero.format(Math.ceil(ultima.limite)),
        "limite do EARS",
      ),
    );
    areaSerie.append(kpis);

    if (situacao?.incidencia !== null && situacao?.incidencia !== undefined) {
      areaSerie.append(
        el(
          "p",
          "nota",
          `Incidência na semana: ${fmtNumero.format(situacao.incidencia)} casos por 100 mil habitantes.`,
        ),
      );
    }

    const nivel = ultima.anomalo === true ? "anomalo" : ultima.anomalo === false ? "esperado" : "atencao";
    const textoFaixa =
      ultima.casos === null || ultima.casos === undefined
        ? "Esta semana não foi publicada na fonte. O gráfico mostra a lacuna — não interpolamos."
        : ultima.anomalo
          ? `Observado ${fmtNumero.format(ultima.casos)}; a faixa esperada ia até ${fmtNumero.format(Math.ceil(ultima.limite))}. Anomalia estatística, não diagnóstico.`
          : `Observado ${fmtNumero.format(ultima.casos)}, dentro da faixa esperada. Sem anomalia nesta semana.`;
    areaSerie.append(el("p", `faixa ${nivel}`, textoFaixa));

    // Gráfico da série
    const caixaGrafico = el("div", "grafico");
    const canvas = el("canvas");
    canvas.setAttribute("aria-label", "Série semanal de casos com faixa esperada pelo EARS");
    canvas.setAttribute("role", "img");
    caixaGrafico.append(canvas);
    areaSerie.append(caixaGrafico);
    painel.append(areaSerie);
    desenharSerie(canvas, serie.semanas);

    // Repasses
    painel.append(blocoRepasses(repasses, mensal));

    // Clima
    painel.append(blocoClima(clima));

    // Responsáveis
    painel.append(blocoResponsaveis(responsaveis));

    painel.append(
      el(
        "p",
        "nota",
        "Fontes, período e data de coleta estão na seção “Fontes e Metodologia”, no fim da página.",
      ),
    );
  }

  function kpi(valor, rotulo) {
    const caixa = el("div", "kpi");
    caixa.append(el("span", "valor", valor), el("span", "rotulo", rotulo));
    return caixa;
  }

  function desenharSerie(canvas, semanas) {
    const rotulos = semanas.map((ponto) => ponto.rotulo.replace("-SE", "/"));
    estado.graficoSerie = new Chart(canvas, {
      type: "line",
      data: {
        labels: rotulos,
        datasets: [
          {
            label: "Esperado",
            data: semanas.map((ponto) => ponto.esperado),
            borderColor: "rgba(22,104,63,0.55)",
            backgroundColor: "rgba(22,104,63,0.10)",
            borderWidth: 1,
            pointRadius: 0,
            fill: false,
            tension: 0.2,
          },
          {
            label: "Limite EARS",
            data: semanas.map((ponto) => ponto.limite),
            borderColor: "rgba(22,104,63,0.85)",
            borderDash: [5, 4],
            borderWidth: 1.4,
            pointRadius: 0,
            fill: "-1",
            backgroundColor: "rgba(22,104,63,0.10)",
            tension: 0.2,
          },
          {
            label: "Casos observados",
            data: semanas.map((ponto) => ponto.casos),
            borderColor: "#1f2d25",
            backgroundColor: "#1f2d25",
            borderWidth: 2,
            pointRadius: 2.5,
            pointHoverRadius: 5,
            spanGaps: false,
            tension: 0.15,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { boxWidth: 12, font: { size: 10 } } },
          tooltip: {
            callbacks: {
              label: (item) => `${item.dataset.label}: ${formatarNumero(item.parsed.y)}`,
            },
          },
        },
        scales: {
          x: { ticks: { maxTicksLimit: 10, font: { size: 9 } }, grid: { display: false } },
          y: { beginAtZero: true, ticks: { font: { size: 10 } } },
        },
      },
    });
  }

  function blocoRepasses(repasses, mensal) {
    const bloco = el("section", "bloco bloco-repasses");
    const titulo = el("h3", null, "Repasses federais de saúde");
    titulo.append(el("span", "contagem", `${repasses.quantidade} registro(s)`));
    bloco.append(titulo);

    if (!repasses.disponivel) {
      bloco.append(
        el("p", "nota", "Ainda não há repasse coletado para este estado nesta base."),
      );
    } else {
      bloco.append(
        el("p", "total-dinheiro", `${fmtMoeda.format(repasses.total)} no período`),
        el("p", "nota", `Período: ${repasses.periodo || "—"}`),
      );
      if (mensal.length) {
        const caixa = el("div", "grafico-barras");
        const canvas = el("canvas");
        canvas.setAttribute("role", "img");
        canvas.setAttribute("aria-label", "Soma mensal dos repasses federais");
        caixa.append(canvas);
        bloco.append(caixa);
        desenharBarras(canvas, mensal);
      }
      const lista = el("ul", "lista-limpa");
      repasses.repasses.slice(0, 5).forEach((repasse) => {
        const item = el("li");
        const link = el("a", null, fmtMoeda.format(repasse.valor));
        link.href = repasse.url_fonte;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        item.append(link, el("span", "secundario", `${repasse.data} · ${repasse.descricao}`));
        lista.append(item);
      });
      bloco.append(lista);
    }

    bloco.append(el("p", "aviso-metodologico", repasses.aviso_metodologico));
    return bloco;
  }

  function desenharBarras(canvas, mensal) {
    estado.graficoBarras = new Chart(canvas, {
      type: "bar",
      data: {
        labels: mensal.map((linha) => linha.mes),
        datasets: [
          {
            label: "Repasse no mês (R$)",
            data: mensal.map((linha) => linha.valor),
            backgroundColor: "rgba(22,104,63,0.55)",
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: (item) => fmtMoeda.format(item.parsed.y) },
          },
        },
        scales: {
          x: { ticks: { font: { size: 9 } }, grid: { display: false } },
          y: {
            beginAtZero: true,
            ticks: { font: { size: 9 }, callback: (valor) => fmtCompacto.format(valor) },
          },
        },
      },
    });
  }

  function blocoClima(alertas) {
    const bloco = el("section", "bloco bloco-clima");
    bloco.append(el("h3", null, "Clima e condições favoráveis"));
    if (!alertas.length) {
      bloco.append(
        el(
          "p",
          "nota",
          "Nenhuma estação meteorológica com dado para este estado. Sem alerta inventado.",
        ),
      );
      return bloco;
    }
    const lista = el("ul", "lista-limpa");
    alertas.forEach((alerta) => {
      const item = el("li");
      const incidencia =
        alerta.incidencia === null || alerta.incidencia === undefined
          ? "incidência indisponível"
          : `${fmtNumero.format(alerta.incidencia)} por 100 mil`;
      const chuva =
        alerta.chuva_7d_mm === null || alerta.chuva_7d_mm === undefined
          ? "sem chuva medida"
          : `${fmtNumero.format(alerta.chuva_7d_mm)} mm em 7 dias`;
      item.append(
        el("span", null, alerta.municipio),
        el("span", `chip chip-${alerta.nivel}`, rotuloNivel(alerta.nivel)),
        el("span", "secundario", `${incidencia} · ${chuva} · estação ${alerta.estacao} · ${alerta.data_referencia}`),
      );
      lista.append(item);
    });
    bloco.append(lista);
    bloco.append(
      el(
        "p",
        "aviso-metodologico",
        "Chuva alta favorece criadouros do mosquito, mas não é previsão de surto. A leitura é de contexto.",
      ),
    );
    return bloco;
  }

  function rotuloNivel(nivel) {
    return { alto: "alto", atencao: "atenção", baixo: "baixo", sem_dado: "sem dado" }[nivel] || nivel;
  }

  function blocoResponsaveis(responsaveis) {
    const bloco = el("section", "bloco bloco-responsaveis");
    bloco.append(el("h3", null, "Responsáveis legais"));
    if (!responsaveis.length) {
      bloco.append(
        el("p", "nota", "Ainda não coletado para este estado. O painel não inventa nome."),
      );
      return bloco;
    }
    const grade = el("div", "responsaveis");
    responsaveis.forEach((pessoa) => {
      const linha = el("div", "responsavel");
      const texto = el("div");
      texto.append(el("span", "cargo", pessoa.cargo), el("strong", null, pessoa.nome));
      const link = el("a", null, "fonte");
      link.href = pessoa.url_fonte;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      linha.append(texto, link);
      grade.append(linha);
    });
    bloco.append(grade)
    bloco.append(
      el(
        "p",
        "nota",
        "O titular da Secretaria Estadual de Saúde ainda não é coletado nesta versão; "
        + "o link leva ao portal do estado. Nome de gestor muda por eleição e nomeação: "
        + "confirme na fonte antes de citar.",
      ),
    );
    return bloco;
  }

  // ---------- fontes ----------

  async function carregarFontes() {
    const corpo = document.querySelector("#tabela-fontes tbody");
    try {
      const fontes = await pedir("/fontes");
      if (!fontes.length) {
        const linha = el("tr");
        const celula = el("td", null, "Nenhuma fonte coletada ainda.");
        celula.colSpan = 5;
        linha.append(celula);
        corpo.replaceChildren(linha);
        return;
      }
      corpo.replaceChildren();
      fontes.forEach((fonte) => {
        const linha = el("tr");
        const nome = el("td");
        const link = el("a", null, fonte.nome);
        link.href = fonte.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        nome.append(link);
        const situacao = el("td");
        situacao.append(
          el("span", `chip chip-${fonte.status === "ok" ? "baixo" : "atencao"}`, fonte.status),
        );
        linha.append(
          nome,
          el("td", null, fonte.orgao),
          el("td", null, fonte.periodo_referencia || "—"),
          el("td", null, dataCurta(fonte.coletado_em)),
          situacao,
        );
        if (fonte.detalhe) {
          const detalhe = el("td", "secundario", fonte.detalhe);
          detalhe.colSpan = 5;
          const extra = el("tr");
          extra.append(detalhe);
          corpo.append(linha, extra);
        } else {
          corpo.append(linha);
        }
      });
    } catch (erro) {
      const linha = el("tr");
      const celula = el("td", "erro", `Falha ao listar fontes: ${erro.message}`);
      celula.colSpan = 5;
      linha.append(celula);
      corpo.replaceChildren(linha);
    }
  }

  // ---------- seletor e URL ----------

  function preencherSeletor() {
    const seletor = document.getElementById("seletor-uf");
    estado.estados
      .slice()
      .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"))
      .forEach((linha) => {
        const opcao = el("option", null, linha.nome);
        opcao.value = linha.uf;
        seletor.append(opcao);
      });
    seletor.addEventListener("change", (evento) => {
      if (evento.target.value) selecionarEstado(evento.target.value);
    });
  }

  function atualizarUrl(uf) {
    const url = new URL(window.location.href);
    url.searchParams.set("uf", uf);
    window.history.replaceState({}, "", url);
  }

  function ufDaUrl() {
    return new URL(window.location.href).searchParams.get("uf");
  }

  // ---------- início ----------

  async function iniciar() {
    carregarStatus();
    try {
      estado.estados = await pedir("/estados");
    } catch (erro) {
      document.getElementById("status-coleta").textContent = `Falha ao carregar: ${erro.message}`;
      estado.estados = [];
    }
    preencherSeletor();

    const referencia = estado.estados[0];
    document.getElementById("referencia-semana").textContent = referencia
      ? `Semana de referência: ${referencia.ano}-SE${String(referencia.semana).padStart(2, "0")}`
      : "Semana de referência: sem dados coletados";

    try {
      await montarMapa();
    } catch (erro) {
      document.getElementById("mapa").textContent = `Mapa indisponível: ${erro.message}`;
    }

    carregarFontes();

    const uf = ufDaUrl();
    if (uf && estado.estados.some((linha) => linha.uf === uf)) {
      selecionarEstado(uf);
    }
  }

  document.addEventListener("DOMContentLoaded", iniciar);
})();
