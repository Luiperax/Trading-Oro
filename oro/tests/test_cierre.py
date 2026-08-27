"""Pruebas del cierre garantizado de fin de sesión (oro.cierre).

Cubre la queja concreta del usuario: no recibía el aviso para cerrar lo que
estuviera abierto antes del cierre del mercado. El aviso no puede depender de
que haya una ventana de vigilancia viva justo a esa hora.
"""

from __future__ import annotations

from datetime import datetime, timezone

from oro.dominio import Direccion, EstadoOperacion, Signal, TakeProfit
from oro.notificaciones.base import Evento
from oro.vivo import GestorOperaciones


def _gestor():
    sig = Signal(momento=datetime(2026, 8, 25, 10, tzinfo=timezone.utc),
                 direccion=Direccion.COMPRA, entrada=4700.0, stop_loss=4670.0,
                 take_profits=[TakeProfit(4730.0, 0.5, 1.0), TakeProfit(4760.0, 0.5, 2.0)],
                 probabilidad=0.6, confianza=0.8, riesgo_recompensa=1.7,
                 tamano_posicion=1.0)
    return GestorOperaciones(sig, entrada_real=4700.0, cerrar_intradia=True,
                             hora_cierre_utc=21)


def test_cerrar_ahora_cierra_y_avisa():
    g = _gestor()
    evs = g.cerrar_ahora(4712.0, datetime(2026, 8, 25, 20, 45, tzinfo=timezone.utc),
                         "CIERRE DE SESIÓN")
    assert not g.abierta
    assert g.estado is EstadoOperacion.CERRADA_MANUAL
    assert evs and evs[0].cierra_operacion
    assert evs[0].tipo is Evento.CIERRE
    assert "CIERRE DE SESIÓN" in evs[0].mensaje
    # +12 puntos sobre 30 de riesgo = +0.40R
    assert round(g.r_acumulado, 2) == 0.40


def test_cerrar_ahora_respeta_los_parciales_ya_asegurados():
    g = _gestor()
    g.actualizar(4730.0, datetime(2026, 8, 25, 12, tzinfo=timezone.utc))  # TP1: +0.5R
    g.cerrar_ahora(4700.0, datetime(2026, 8, 25, 20, 45, tzinfo=timezone.utc))
    assert not g.abierta
    assert round(g.r_acumulado, 2) == 0.50   # el parcial cobrado se conserva


def test_cerrar_ahora_es_idempotente():
    """Llamarlo dos veces no debe duplicar resultado ni avisos."""
    g = _gestor()
    g.cerrar_ahora(4712.0, datetime(2026, 8, 25, 20, 45, tzinfo=timezone.utc))
    r1 = g.r_acumulado
    assert g.cerrar_ahora(4650.0, datetime(2026, 8, 25, 20, 50, tzinfo=timezone.utc)) == []
    assert g.r_acumulado == r1
