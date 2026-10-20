"""Testes do EARS: a conta precisa bater com o exemplo calculado à mão.

Se este teste falhar, todo o mapa do painel está errado — por isso ele fixa
média, desvio e limite com três casas decimais, em vez de só conferir o
"anômalo/não anômalo".
"""

from __future__ import annotations

import pytest

from src import ears

SERIE = [10, 12, 11, 13, 12, 10, 11, 12, 13, 50]


def test_c1_usa_os_sete_dias_imediatamente_anteriores():
    """C1 não tem guarda: a janela termina no dia anterior ao observado."""
    resultado = ears.detectar(SERIE, 9, variante="C1")

    assert resultado is not None
    assert resultado.janela == (11, 13, 12, 10, 11, 12, 13)
    assert resultado.esperado == pytest.approx(11.714, abs=1e-3)
    assert resultado.limite == pytest.approx(15.052, abs=1e-3)
    assert resultado.observado == 50
    assert resultado.anomalo is True
    assert resultado.nivel == "anomalo"


def test_c2_aplica_dois_dias_de_guarda():
    """Com dois dias de guarda, a janela termina dois dias antes do observado."""
    resultado = ears.detectar(SERIE, 9, variante="C2")

    assert resultado is not None
    assert resultado.janela == (10, 12, 11, 13, 12, 10, 11)
    assert resultado.esperado == pytest.approx(11.286, abs=1e-3)
    assert resultado.limite == pytest.approx(14.624, abs=1e-3)
    assert resultado.anomalo is True


def test_serie_curta_nao_inventa_esperado():
    """Sem sete pontos de histórico, o detector devolve `None` em vez de chutar."""
    assert ears.detectar([1, 2, 3], 2) is None


def test_valor_dentro_da_faixa_nao_e_anomalia():
    """O dia 9 vale 13; a faixa de C1 vai até 15,05 — logo, sem alarme."""
    resultado = ears.detectar(SERIE, 8, variante="C1")

    assert resultado is not None
    assert resultado.observado == 13
    assert resultado.anomalo is False
    assert resultado.nivel == "atencao"


def test_janela_toda_zero_sinaliza_primeiro_caso():
    """Área silenciosa: um caso já ultrapassa o limite zero.

    É comportamento conhecido do EARS e precisa estar documentado na tela —
    o teste existe para que ninguém "corrija" isso sem decidir de propósito.
    """
    serie = [0] * 9 + [1]
    resultado = ears.detectar(serie, 9, variante="C1")

    assert resultado is not None
    assert resultado.esperado == 0
    assert resultado.limite == 0
    assert resultado.anomalo is True


def test_variante_desconhecida_falha_alto():
    """Erro de digitação não pode virar silêncio: melhor estourar no teste."""
    with pytest.raises(ValueError, match="variante desconhecida"):
        ears.detectar(SERIE, 9, variante="C9")


def test_c3_nao_e_implementado_de_proposito():
    """C3 é acumulado; fingir que é uma terceira janela daria resultado errado."""
    with pytest.raises(ValueError, match="C3"):
        ears.detectar(SERIE, 9, variante="C3")


def test_exemplo_canonico_do_relatorio():
    """Valida a convenção A contra o exemplo numérico do CDC/surveillance.

    Série de 10 dias terminando em 16. C1 usa os dias 3..9 e não alerta;
    C2 ignora os dois últimos dias e alerta. Se este teste falhar, a fórmula
    (janela, atraso ou divisor n−1) está errada.
    """
    serie = [10, 12, 11, 9, 13, 12, 10, 25, 12, 16]

    c1 = ears.detectar(serie, 9, variante="C1")
    c2 = ears.detectar(serie, 9, variante="C2")

    assert c1 is not None and c2 is not None
    assert c1.esperado == pytest.approx(13.142857, abs=1e-6)
    assert c1.limite == pytest.approx(29.338094, abs=1e-6)
    assert c1.anomalo is False
    assert c2.esperado == pytest.approx(11.0, abs=1e-9)
    assert c2.limite == pytest.approx(15.242641, abs=1e-6)
    assert c2.anomalo is True


def test_resumo_conta_apenas_pontos_avaliaveis():
    """O resumo precisa dizer quantos pontos tinham histórico suficiente."""
    resumo = ears.resumo(SERIE, variante="C1")

    assert resumo["avaliados"] == 3
    assert resumo["anomalias"] == 1
    assert resumo["ultimo"].observado == 50  # type: ignore[union-attr]
