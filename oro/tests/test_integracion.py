"""Pruebas de CONJUNTO: que las piezas no se pisen entre sí.

Los fallos más caros de este sistema no han estado en las piezas sueltas, sino
en cómo interactúan: dos trabajos gestionando la misma operación, o dos
guardados chocando y descartando el trabajo del otro.
"""

from __future__ import annotations

import datetime as D
from datetime import datetime, timezone

import pytest

from oro.config import cargar_configuracion
from oro.datos import ProveedorSintetico
from oro.dominio import Direccion, EstadoOperacion, Signal, TakeProfit, dia_sesion
from oro.notificaciones.base import Evento, Notificador
from oro.sentimiento import AnalizadorSentimiento
from oro.vivo import GestorOperaciones, RunnerVivo
import oro.vigilar as V


class _Espia(Notificador):
    """Cuenta los avisos que recibiría el usuario, por tipo."""

    def __init__(self):
        self.eventos = []

    def enviar(self, titulo, cuerpo, evento=Evento.NUEVA_SENAL, html=None):
        self.eventos.append(evento)
        return True

    def cierres(self):
        return [e for e in self.eventos if e is Evento.CIERRE]


def _a_las(h, m=0, dia=27):
    return datetime(2026, 8, dia, h, m, tzinfo=timezone.utc)


def _con_reloj(h, m, fn):
    """Ejecuta fn() como si fueran las h:m UTC."""
    class _Falso(D.datetime):
        @classmethod
        def now(cls, tz=None):
            return D.datetime(2026, 8, 27, h, m, tzinfo=timezone.utc)
    orig = D.datetime
    D.datetime = _Falso
    try:
        return fn()
    finally:
        D.datetime = orig


# ---------- vigilante vs cierre de sesión ----------
def test_el_vigilante_cede_el_turno_al_cierre_de_sesion():
    """Si se solapan, cierran la misma operación dos veces (dos correos).

    El relevo se rige por la hora LOCAL del usuario (verano: UTC+2).
    """
    cfg = cargar_configuracion()
    assert _con_reloj(19, 0, lambda: V._toca_relevo(cfg)) is False   # 21:00 local: vigila
    assert _con_reloj(19, 40, lambda: V._toca_relevo(cfg)) is True   # 21:40 local: cede
    assert _con_reloj(20, 30, lambda: V._toca_relevo(cfg)) is True   # 22:30 local: cede
    assert _con_reloj(22, 5, lambda: V._toca_relevo(cfg)) is False   # 00:05 local: vuelve


def test_el_relevo_cubre_toda_la_franja_del_cierre():
    """Debe cubrir las cuatro citas de cierre (verano e invierno)."""
    from oro.cierre import _toca_cerrar

    cfg = cargar_configuracion()
    for h, m in ((19, 50), (19, 58)):        # citas de verano
        assert _toca_cerrar(datetime(2026, 8, 28, h, m, tzinfo=timezone.utc))[0] is True
        assert _con_reloj(h, m, lambda: V._toca_relevo(cfg)) is True


def test_una_operacion_solo_se_cierra_una_vez():
    """cerrar_ahora es idempotente: no duplica avisos ni resultado."""
    sig = Signal(momento=_a_las(10), direccion=Direccion.COMPRA, entrada=4700.0,
                 stop_loss=4670.0, take_profits=[TakeProfit(4730.0, 1.0, 1.0)],
                 probabilidad=0.6, confianza=0.8, riesgo_recompensa=1.7,
                 tamano_posicion=1.0)
    g = GestorOperaciones(sig, entrada_real=4700.0, cerrar_intradia=True,
                          hora_cierre_utc=21)
    primeros = g.cerrar_ahora(4710.0, _a_las(20, 45), "CIERRE DE SESIÓN")
    segundos = g.cerrar_ahora(4710.0, _a_las(20, 56), "CIERRE DE SESIÓN")
    terceros = g.actualizar(4600.0, _a_las(21, 30))     # el vigilante insistiendo
    assert len(primeros) == 1 and segundos == [] and terceros == []
    assert g.estado is EstadoOperacion.CERRADA_MANUAL


# ---------- ciclo de vida completo ----------
def test_ciclo_de_vida_completo_de_una_operacion():
    """Entrada -> objetivo -> break-even -> cierre, con UN aviso de cada cosa."""
    espia = _Espia()
    sig = Signal(momento=_a_las(10), direccion=Direccion.COMPRA, entrada=4700.0,
                 stop_loss=4670.0,
                 take_profits=[TakeProfit(4730.0, 0.5, 1.0), TakeProfit(4760.0, 0.5, 2.0)],
                 probabilidad=0.65, confianza=0.86, riesgo_recompensa=1.7,
                 tamano_posicion=1.0)
    g = GestorOperaciones(sig, entrada_real=4700.0, cerrar_intradia=True,
                          hora_cierre_utc=21)
    tipos = []
    for precio, momento in ((4710.0, _a_las(11)), (4730.0, _a_las(12)),
                            (4700.0, _a_las(13))):
        tipos += [e.tipo for e in g.actualizar(precio, momento)]
    assert Evento.TP_ALCANZADO in tipos
    assert Evento.MOVER_STOP in tipos
    assert not g.abierta                      # cerrada protegida en break-even
    assert g.r_acumulado == pytest.approx(0.5)


def test_el_estado_sobrevive_al_viaje_completo(tmp_path):
    """Guardar -> cargar -> seguir gestionando: nada se pierde por el camino."""
    cfg = cargar_configuracion()
    ruta = tmp_path / "estado.json"

    def _runner():
        return RunnerVivo(cfg, proveedor=ProveedorSintetico(velas=800, semilla=5),
                          analizador=AnalizadorSentimiento(fuente_titulares=lambda: [],
                                                           fuente_eventos=lambda: []),
                          usar_sentimiento=False, notificador=_Espia())

    r1 = _runner()
    sig = Signal(momento=_a_las(10), direccion=Direccion.COMPRA, entrada=4700.0,
                 stop_loss=4670.0, take_profits=[TakeProfit(4730.0, 1.0, 1.0)],
                 probabilidad=0.6, confianza=0.8, riesgo_recompensa=1.7,
                 tamano_posicion=1.0)
    r1.abiertas.append(GestorOperaciones(sig, entrada_real=4700.0))
    r1._senales_hoy = 1
    r1._ultima_vela_senal = _a_las(10)
    r1._perdida_r_hoy = 0.7
    r1.guardar_estado(ruta)

    r2 = _runner()
    r2.cargar_estado(ruta)
    assert len(r2.abiertas) == 1
    assert r2._senales_hoy == 1
    assert r2._ultima_vela_senal == _a_las(10)   # no repite la señal de esa vela
    assert r2._perdida_r_hoy == pytest.approx(0.7)
    assert r2.abiertas[0].entrada == 4700.0


# ---------- coherencia de reglas entre piezas ----------
def test_la_misma_regla_de_sesion_en_vivo_y_en_backtest():
    """Runner, gestor y backtester deben usar el MISMO día de sesión."""
    from oro.dominio.mercado import HORA_APERTURA_UTC, HORA_CIERRE_UTC

    # Son DOS conceptos distintos y no deben confundirse:
    #  - HORA_CIERRE_UTC (21): cuando cierra el MERCADO (deja de haber velas).
    #  - riesgo.hora_cierre_utc (20): nuestro cierre OPERATIVO, antes, para dar
    #    margen al usuario a cerrar en el bróker.
    assert HORA_CIERRE_UTC == 21
    assert cargar_configuracion().riesgo.hora_cierre_utc < HORA_CIERRE_UTC
    assert HORA_APERTURA_UTC == 22
    # 22:00 UTC ya es la sesión del día siguiente, en cualquier pieza.
    assert dia_sesion(_a_las(22)) != dia_sesion(_a_las(20))
    assert dia_sesion(_a_las(23)) == dia_sesion(_a_las(10, dia=28))
