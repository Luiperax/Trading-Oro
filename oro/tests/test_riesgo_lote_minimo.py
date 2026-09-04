"""El lote mínimo puede arriesgar MUCHO más de lo configurado. Hay que decirlo.

Hallazgo de auditoría: con 3000 EUR de capital y un tope del 0.25% (7.50 EUR),
el lote más pequeño que acepta un bróker (0.01 = 1 oz) arriesga entre el 112% y
el 655% de ese tope, porque el oro tiene stops de 8 a 50 puntos. No hay forma de
bajarlo: es una restricción del bróker, no del programa.

Lo que sí está en nuestra mano es no mentir. El correo decía "(riesgo mínimo por
operación)" junto a una cifra que era el 1.64% del capital, no el 0.25%.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from oro.config import cargar_configuracion
from oro.dominio import Direccion, Signal, TakeProfit
from oro.notificaciones.base import (
    LOTE_MINIMO, _lote_y_riesgo, _riesgo_real, _texto_riesgo, mensaje_de_senal,
    mensaje_html_de_senal,
)


def _senal(entrada: float, stop: float, oz: float = 0.111) -> Signal:
    return Signal(
        momento=datetime(2026, 9, 4, 12, tzinfo=timezone.utc),
        direccion=Direccion.COMPRA, entrada=entrada, stop_loss=stop,
        take_profits=[TakeProfit(entrada + 30, 1.0, 1.0)],
        probabilidad=0.65, confianza=0.80, riesgo_recompensa=1.7,
        tamano_posicion=oz)


def test_nunca_se_propone_menos_del_lote_minimo():
    lote, _ = _lote_y_riesgo(_senal(4500.0, 4450.0, oz=0.001))
    assert lote == LOTE_MINIMO


def test_la_perdida_mostrada_es_la_del_lote_que_se_coloca():
    """Si se muestra el importe del tamaño teórico, el usuario se lleva un susto."""
    lote, perdida = _lote_y_riesgo(_senal(5378.90, 5329.74, oz=0.111))
    assert lote == 0.01
    assert perdida == pytest.approx(abs(5378.90 - 5329.74) * 0.01 * 100.0)


def test_se_avisa_cuando_el_lote_minimo_supera_el_objetivo():
    """El caso real: stop de 49 puntos, 3000 EUR de capital."""
    texto = _texto_riesgo(_senal(5378.90, 5329.74))
    _, pct, excede = _riesgo_real(_senal(5378.90, 5329.74))
    assert excede is True
    assert pct > cargar_configuracion().riesgo.riesgo_por_operacion
    assert "LOTE MÍNIMO" in texto and "no se puede bajar" in texto
    assert "%" in texto, "hay que decir qué porcentaje del capital se arriesga"


def test_no_se_alarma_cuando_el_riesgo_si_cabe():
    texto = _texto_riesgo(_senal(4500.0, 4496.0))
    assert "⚠️" not in texto and "LOTE MÍNIMO" not in texto
    assert "% del capital" in texto


def test_el_aviso_llega_al_correo_en_texto_y_en_html():
    s = _senal(5378.90, 5329.74)
    assert "LOTE MÍNIMO" in mensaje_de_senal(s)
    html = mensaje_html_de_senal(s)
    assert "LOTE M" in html          # escapado incluido
    assert "riesgo mínimo por operación" not in html, "la frase engañosa vuelve"


def test_la_frase_enganosa_ya_no_existe():
    """Decía 'riesgo mínimo por operación' junto a una cifra 6 veces mayor."""
    import inspect

    from oro.notificaciones import base

    assert "riesgo mínimo por operación" not in inspect.getsource(base)
