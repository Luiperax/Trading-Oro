"""La mitad que se deja correr, y por qué el segundo objetivo está tan lejos.

Medido sobre 4.410 operaciones de 19,6 años, re-simulando LAS MISMAS entradas
con distintas gestiones: cerrar la escalera en 2R/3R cortaba las ganadoras
grandes. Mitad fuera a 1R y mitad dejada correr con el stop dinámico dio
+0.0115 R/op fuera de muestra (t = 2.79, p = 0.005, mejor en 8 de 10 tandas) y
bajó la peor racha de -175 R a -153 R sin empeorar la peor operación.

El 6.0 no es un objetivo real: existe para que el R:R ponderado supere
``r_recompensa_min``, porque si no el motor rechazaría todas las señales. Estas
pruebas fijan las dos cosas para que nadie las rompa sin enterarse.
"""

from __future__ import annotations

import pytest

from oro.config import cargar_configuracion
from oro.dominio import Direccion
from oro.riesgo import calcular_niveles


def test_media_posicion_se_deja_correr():
    r = cargar_configuracion().riesgo
    assert len(r.reparto_tp) == len(r.r_objetivos)
    assert sum(r.reparto_tp) == pytest.approx(1.0), "el reparto debe cubrir la posición"
    assert r.reparto_tp[0] == pytest.approx(0.5), "la mitad sale al primer objetivo"
    assert r.r_objetivos[0] == pytest.approx(1.0)
    # La segunda mitad no debe tener un techo cercano: era lo que cortaba las
    # ganadoras grandes. Con 2R o 3R el efecto medido desaparece.
    assert r.r_objetivos[-1] >= 5.0, "el segundo objetivo no puede acercarse: cortaría las ganadoras"


def test_el_objetivo_lejano_mantiene_vivo_el_filtro_de_calidad():
    # motor.py:184 descarta la señal si el R:R ponderado no llega al mínimo. Sin
    # un segundo objetivo lejano, el R:R sería 0.5 y no se emitiría NINGUNA señal.
    cfg = cargar_configuracion()
    n = calcular_niveles(2000.0, Direccion.COMPRA, atr=5.0, cfg=cfg)
    assert n.riesgo_recompensa >= cfg.riesgo.r_recompensa_min, (
        "el R:R ponderado cae por debajo del mínimo: el motor no emitiría señales")


def test_los_objetivos_van_en_orden_y_al_lado_correcto():
    cfg = cargar_configuracion()
    for direccion, signo in ((Direccion.COMPRA, 1), (Direccion.VENTA, -1)):
        n = calcular_niveles(2000.0, direccion, atr=5.0, cfg=cfg)
        precios = [tp.precio for tp in n.take_profits]
        assert all(signo * (p - 2000.0) > 0 for p in precios), "objetivo del lado equivocado"
        assert precios == sorted(precios, reverse=signo < 0), "objetivos desordenados"
        assert n.take_profits[0].r_multiple < n.take_profits[-1].r_multiple


def _senal_de_ejemplo():
    import datetime as dt
    from oro.dominio import Signal
    from oro.riesgo import dimensionar_posicion

    cfg = cargar_configuracion()
    n = calcular_niveles(4451.90, Direccion.COMPRA, atr=8.4, cfg=cfg)
    return Signal(momento=dt.datetime.now(dt.timezone.utc), direccion=Direccion.COMPRA,
                  entrada=n.entrada, stop_loss=n.stop_loss, take_profits=n.take_profits,
                  probabilidad=0.67, confianza=0.86,
                  riesgo_recompensa=n.riesgo_recompensa,
                  tamano_posicion=dimensionar_posicion(n.riesgo_por_unidad, cfg),
                  motivos_entrada=["Estructura alcista"], riesgos=[],
                  contexto_tecnico="alcista", puntuacion=0.71)


def test_el_aviso_no_presenta_el_tope_como_una_orden_a_poner():
    # Si el correo anunciara el tope de 6R como un take profit normal, se pondría
    # en el bróker una orden que el sistema no persigue y que en 4.410
    # operaciones no se ejecutó nunca: la mitad quedaría sin gestionar.
    from oro.notificaciones.base import mensaje_de_senal, mensaje_html_de_senal

    sig = _senal_de_ejemplo()
    tope = max(tp.precio for tp in sig.take_profits)
    for texto in (mensaje_de_senal(sig), mensaje_html_de_senal(sig)):
        assert "se deja correr" in texto or "DEJA CORRER" in texto
        assert f"Take Profit 2" not in texto and "TP2" not in texto

    # El precio del tope no debe aparecer en el HTML como un nivel más.
    assert f"{tope:.2f}" not in mensaje_html_de_senal(sig)


def test_el_aviso_no_promete_un_rr_que_el_sistema_no_persigue():
    # riesgo_recompensa vale 3.5 por el tope, pero el sistema solo busca 1R en la
    # mitad; el resto lo cierra el stop dinámico donde caiga. Anunciar "3.50"
    # sería vender un premio que no se persigue.
    from oro.notificaciones.base import mensaje_de_senal, mensaje_html_de_senal

    sig = _senal_de_ejemplo()
    for texto in (mensaje_de_senal(sig), mensaje_html_de_senal(sig)):
        assert "3.50" not in texto, "el correo promete un R:R que el sistema no busca"
        assert "resto" in texto.lower()
