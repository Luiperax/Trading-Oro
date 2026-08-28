"""Día de sesión del oro y hora local del usuario.

El oro cotiza de 22:00 a 21:00 UTC (solo cierra 21:00-22:00 y el fin de semana),
así que el "día" de operativa NO es el de calendario. Usar el calendario cerraba
a medianoche una operación abierta a las 22:30, con 22 h de sesión por delante.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from oro.dominio import Direccion, Signal, TakeProfit, dia_sesion
from oro.tiempo import etiqueta_zona, fecha_hora_local, hora_local
from oro.vivo import GestorOperaciones


def _utc(d, h, mi=0):
    return datetime(2026, 8, d, h, mi, tzinfo=timezone.utc)


# ---------- día de sesión ----------
def test_a_partir_de_las_22_es_la_sesion_del_dia_siguiente():
    assert dia_sesion(_utc(23, 21)) == date(2026, 8, 23)   # aún la sesión vieja
    assert dia_sesion(_utc(23, 22)) == date(2026, 8, 24)   # abre la nueva
    assert dia_sesion(_utc(24, 0)) == date(2026, 8, 24)
    assert dia_sesion(_utc(24, 20)) == date(2026, 8, 24)
    assert dia_sesion(_utc(24, 22)) == date(2026, 8, 25)


# ---------- cierre intradía por sesión ----------
def _gestor(momento_apertura):
    sig = Signal(momento=momento_apertura, direccion=Direccion.COMPRA, entrada=4700.0,
                 stop_loss=4670.0, take_profits=[TakeProfit(4730.0, 1.0, 1.0)],
                 probabilidad=0.6, confianza=0.8, riesgo_recompensa=1.7,
                 tamano_posicion=1.0)
    return GestorOperaciones(sig, entrada_real=4700.0, cerrar_intradia=True,
                             hora_cierre_et=16)


def test_abierta_de_noche_no_se_cierra_a_medianoche():
    """EL FALLO: con el día de calendario se cerraba a las 00:00, recién abierta."""
    g = _gestor(_utc(24, 22, 30))          # sesión del 25
    g.actualizar(4705.0, _utc(25, 0, 30))  # medianoche: MISMA sesión
    assert g.abierta
    g.actualizar(4705.0, _utc(25, 10))     # media sesión: sigue
    assert g.abierta
    g.actualizar(4705.0, _utc(25, 21, 5))  # cierre de SU sesión
    assert not g.abierta


def test_se_cierra_al_llegar_el_cierre_operativo():
    """Cierre operativo: 16:00 Nueva York = 22:00 Madrid, todo el año."""
    g = _gestor(_utc(24, 10))
    g.actualizar(4705.0, _utc(24, 19, 30))    # 21:30 Madrid: aún abierta
    assert g.abierta
    g.actualizar(4705.0, _utc(24, 19, 50))    # 21:50 Madrid: llega TU aviso
    assert g.abierta, "a las 21:50 debe seguir abierta para poder avisarte"
    g.actualizar(4705.0, _utc(24, 20, 10))    # 22:00+ Madrid: cierra
    assert not g.abierta


def test_el_cierre_cae_a_la_misma_hora_de_madrid_en_invierno():
    """El cambio de horario no debe desajustarlo: siempre 22:00 en Madrid.

    Con las horas fijadas en UTC esto fallaba: el mercado cierra a las 17:00 de
    Nueva York, que son las 21:00 UTC en verano pero las 22:00 en invierno.
    """
    invierno = datetime(2026, 1, 16, 10, tzinfo=timezone.utc)
    sig = Signal(momento=invierno, direccion=Direccion.COMPRA, entrada=4700.0,
                 stop_loss=4670.0, take_profits=[TakeProfit(4730.0, 1.0, 1.0)],
                 probabilidad=0.6, confianza=0.8, riesgo_recompensa=1.7,
                 tamano_posicion=1.0)
    g = GestorOperaciones(sig, entrada_real=4700.0, cerrar_intradia=True,
                          hora_cierre_et=16)
    g.actualizar(4705.0, datetime(2026, 1, 16, 20, 50, tzinfo=timezone.utc))
    assert g.abierta, "21:50 en Madrid (invierno): debe seguir abierta"
    g.actualizar(4705.0, datetime(2026, 1, 16, 21, 10, tzinfo=timezone.utc))
    assert not g.abierta, "22:10 en Madrid (invierno): debe estar cerrada"


def test_no_sobrevive_a_la_apertura_de_la_sesion_siguiente():
    g = _gestor(_utc(24, 10))
    g.actualizar(4705.0, _utc(24, 22, 30))   # ya es otra sesión
    assert not g.abierta


# ---------- hora local del usuario ----------
def test_hora_local_es_la_de_madrid_y_ajusta_el_cambio_de_hora():
    verano = datetime(2026, 8, 27, 21, 0, tzinfo=timezone.utc)
    invierno = datetime(2026, 1, 15, 21, 0, tzinfo=timezone.utc)
    assert hora_local(verano) == "23:00"      # CEST = UTC+2
    assert hora_local(invierno) == "22:00"    # CET  = UTC+1
    assert etiqueta_zona(verano) == "CEST"
    assert etiqueta_zona(invierno) == "CET"


def test_zona_configurable(monkeypatch):
    monkeypatch.setenv("ORO_ZONA_HORARIA", "UTC")
    assert hora_local(datetime(2026, 8, 27, 21, tzinfo=timezone.utc)) == "21:00"


def test_fecha_hora_local_legible():
    assert "23:00" in fecha_hora_local(datetime(2026, 8, 27, 21, tzinfo=timezone.utc))
