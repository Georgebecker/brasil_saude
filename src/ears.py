"""Detecção de anomalias com EARS (Early Aberration Reporting System).

O EARS foi criado pelo CDC para responder a uma pergunta simples: *o número de
hoje é maior do que o barulho normal dos últimos dias?* Ele compara o valor
observado com uma faixa construída a partir da média e do desvio-padrão de uma
janela curta e recente. Se o valor sai da faixa, é **anomalia estatística** —
não é prova de surto, nem culpa de ninguém.

As três variantes clássicas mudam a "faixa de guarda" (dias que ficam de fora
para não contaminar a média com o próprio evento) e o multiplicador:

===========  =================  ==============  ================================
Variante     Guarda (dias)      k (desvios)     Uso típico
===========  =================  ==============  ================================
C1           0                  3               reação rápida a picos isolados
C2           2                  3               tolera atraso de notificação
C3           —                  —               não implementado no MVP
===========  =================  ==============  ================================

C3 não entra porque a fórmula é **acumulada** (soma de três C2 deslocados, com
limiar 2), e não uma terceira janela com outro `k`. Implementar pela metade
seria pior que não ter: o contrato pede C1 e C2, e são esses que o painel
mostra.

Referências: Hutwagner et al., "The bioterrorism preparedness and response
Early Aberration Reporting System (EARS)", J Urban Health, 2003; e Hutwagner et
al., "Comparing aberration detection methods with simulated data", Emerg Infect
Dis, 2005 (doi:10.3201/eid1102.040587). A janela é de 7 pontos e o desvio é
amostral (divisor n−1), como em `surveillance::earsC`.

Limite conhecido: se a janela é toda zero (município sem casos), o desvio é
zero e **qualquer** caso vira anomalia. Isso é intencional e precisa estar
escrito na tela — um primeiro caso em área silenciosa merece atenção, mas o
painel não pode chamar isso de epidemia.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

# Guarda e multiplicador de cada variante, em um só lugar para não divergirem
# entre documentação, código e teste.
VARIANTES: dict[str, tuple[int, float]] = {
    "C1": (0, 3.0),
    "C2": (2, 3.0),
}

JANELA = 7


@dataclass(frozen=True)
class ResultadoEARS:
    """Veredito de um único ponto da série."""

    metodo: str
    observado: float
    esperado: float
    limite: float
    anomalo: bool
    nivel: str
    janela: tuple[float, ...]

    @property
    def explicacao(self) -> str:
        """Frase curta em português para a interface, sem jargão solto."""
        faixa = f"{self.esperado:.1f} a {self.limite:.1f}"
        if self.anomalo:
            return (
                f"Observado {self.observado:.0f}; a faixa esperada era de {faixa}. "
                "Valor acima do limite: anomalia estatística, não diagnóstico."
            )
        return (
            f"Observado {self.observado:.0f} dentro da faixa esperada ({faixa}). "
            "Sem sinal de anomalia nesta semana."
        )


def _media_desvio(valores: list[float]) -> tuple[float, float]:
    """Média e desvio-padrão amostral (n-1), iguais aos do EARS original."""
    if len(valores) < 2:
        return (valores[0] if valores else 0.0), 0.0
    return statistics.fmean(valores), statistics.stdev(valores)


def detectar(
    serie: list[float | None],
    indice: int,
    *,
    variante: str = "C1",
    janela: int = JANELA,
) -> ResultadoEARS | None:
    """Aplica o EARS ao ponto `indice` da série.

    Devolve `None` quando não há histórico suficiente — e isso é uma resposta
    honesta: não se inventa faixa esperada para as primeiras semanas.

    `None` na série representa **semana sem dado** (lacuna do SINAN). A janela
    com lacuna não é avaliada: tratar buraco como zero criaria uma "queda" que
    nunca existiu e, depois, um "pico" falso.
    """
    if variante not in VARIANTES:
        if variante == "C3":
            raise ValueError("C3 não implementado no MVP (fórmula acumulada)")
        raise ValueError(f"variante desconhecida: {variante}")
    guarda, k = VARIANTES[variante]
    fim = indice - guarda
    inicio = fim - janela
    if inicio < 0 or indice < 0 or indice >= len(serie):
        return None

    trecho = serie[inicio:fim]
    if any(valor is None for valor in trecho) or serie[indice] is None:
        return None

    valores = [float(valor) for valor in trecho if valor is not None]
    media, desvio = _media_desvio(valores)
    limite = media + k * desvio
    observado = float(serie[indice])  # type: ignore[arg-type]
    anomalo = observado > limite

    if observado <= media:
        nivel = "esperado"
    elif anomalo:
        nivel = "anomalo"
    else:
        nivel = "atencao"

    return ResultadoEARS(
        metodo=variante,
        observado=observado,
        esperado=media,
        limite=limite,
        anomalo=anomalo,
        nivel=nivel,
        janela=tuple(valores),
    )


def detectar_serie(
    serie: list[float | None], *, variante: str = "C1", janela: int = JANELA
) -> list[ResultadoEARS | None]:
    """Roda o detector em cada ponto; `None` onde falta histórico."""
    return [detectar(serie, i, variante=variante, janela=janela) for i in range(len(serie))]


def resumo(serie: list[float | None], *, variante: str = "C1") -> dict[str, object]:
    """Último veredito + quantos pontos da série foram sinalizados.

    O resumo é o que a API devolve na listagem de estados: evita mandar a
    série inteira para desenhar um mapa.
    """
    resultados = [r for r in detectar_serie(serie, variante=variante) if r is not None]
    if not resultados:
        return {"metodo": variante, "avaliados": 0, "anomalias": 0, "ultimo": None}
    ultimo = resultados[-1]
    return {
        "metodo": variante,
        "avaliados": len(resultados),
        "anomalias": sum(1 for r in resultados if r.anomalo),
        "ultimo": ultimo,
    }
