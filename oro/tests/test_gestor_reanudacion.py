"""Reanudar una operación a medias: el estado guardado debe ser fiel.

El vigilante guarda tras cada ciclo y la siguiente ejecución restaura. Si algo
no viaja en la serialización, el resultado cambia entre máquinas.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from oro.dominio import Direccion, Signal, TakeProfit
from oro.vivo.gestor import GestorOperaciones, _hora_cierre_de


def _senal(direccion=Direccion.COMPRA, entrada=4500.0, riesgo=30.0):
    s = direccion.signo
    return Signal(
        momento=datetime(2026, 9, 1, 14, tzinfo=timezone.utc), direccion=direccion,
        entrada=entrada, stop_loss=entrada - s * riesgo,
        take_profits=[TakeProfit(entrada + s * riesgo, 0.5, 1.0),
                      TakeProfit(entrada + s * riesgo * 2, 0.3, 2.0),
                      TakeProfit(entrada + s * riesgo * 3, 0.2, 3.0)],
        probabilidad=0.63, confianza=0.71, riesgo_recompensa=2.0, tamano_posicion=1.0)


# ---------- la hora de cierre operativo ----------
_ESTADO_MINIMO = dict(
    direccion="compra", entrada=100.0, riesgo=10.0, stop_actual=90.0,
    en_breakeven=False, restante=1.0, r_acumulado=0.0, estado="abierta",
    abierta_en="2026-09-01T10:00:00+00:00", niveles=[])


@pytest.mark.parametrize("extra,esperado", [
    ({"hora_cierre_et": 16, "hora_cierre": 16}, 16),   # estado actual
    ({"hora_cierre_et": 14}, 14),                      # valor válido distinto
    ({}, 16),                                          # sin claves
    ({"hora_cierre_et": "basura"}, 16),
    ({"hora_cierre_et": 99}, 16),                      # fuera de rango
])
def test_hora_de_cierre_restaurada(extra, esperado):
    assert _hora_cierre_de(extra) == esperado
    assert GestorOperaciones.desde_dict({**_ESTADO_MINIMO, **extra})._hora_cierre == esperado


def test_una_hora_utc_antigua_no_se_toma_por_hora_de_nueva_york():
    """El fallo: dos asignaciones seguidas y la segunda pisaba a la primera.

    La migración desde el nombre antiguo quedaba muerta y el defecto era 21, la
    hora UTC de antes del cambio. Un 21 leído como hora de Nueva York rompe el
    cierre de fin de sesión EN SILENCIO, porque "21 <= hora_mercado < 18" no se
    cumple nunca: la operación aguantaría hasta el cambio de sesión, ya con el
    mercado cerrado. Los estados antiguos guardaban UTC y convertirlo no es
    fiable (depende del horario de verano), así que se descarta.
    """
    antiguo = {**_ESTADO_MINIMO, "hora_cierre": 21, "hora_cierre_utc": 21}
    assert GestorOperaciones.desde_dict(antiguo)._hora_cierre == 16


# ---------- fidelidad de la reanudación ----------
@pytest.mark.parametrize("direccion", [Direccion.COMPRA, Direccion.VENTA])
def test_guardar_y_restaurar_en_cada_paso_no_cambia_el_resultado(direccion):
    s = direccion.signo
    camino = [4500.0 + s * d for d in (5, 12, 31, 24, 45, 62, 40, 95)]
    t0 = datetime(2026, 9, 1, 14, tzinfo=timezone.utc)

    seguido = GestorOperaciones(_senal(direccion), cerrar_intradia=False)
    troceado = GestorOperaciones(_senal(direccion), cerrar_intradia=False)
    for i, p in enumerate(camino):
        momento = t0 + timedelta(minutes=5 * i)
        seguido.actualizar(p, momento)
        # como hace el vigilante: guardar, morir, restaurar, seguir.
        troceado = GestorOperaciones.desde_dict(json.loads(json.dumps(troceado.a_dict())))
        troceado.actualizar(p, momento)

    assert troceado.estado is seguido.estado
    assert troceado.r_acumulado == pytest.approx(seguido.r_acumulado)
    assert [n.alcanzado for n in troceado.niveles] == [n.alcanzado for n in seguido.niveles]


def test_los_objetivos_ya_alcanzados_no_se_cobran_dos_veces():
    g = GestorOperaciones(_senal(), cerrar_intradia=False)
    g.actualizar(4531.0, datetime(2026, 9, 1, 15, tzinfo=timezone.utc))   # TP1
    assert g.niveles[0].alcanzado and g.r_acumulado == pytest.approx(0.5)

    revivido = GestorOperaciones.desde_dict(json.loads(json.dumps(g.a_dict())))
    revivido.actualizar(4531.0, datetime(2026, 9, 1, 16, tzinfo=timezone.utc))
    assert revivido.r_acumulado == pytest.approx(0.5), "TP1 se cobró dos veces"
