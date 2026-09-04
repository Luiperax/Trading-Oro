"""Las semanas en que Europa y EE.UU. NO cambian la hora a la vez.

Europa atrasa el reloj el último domingo de octubre y EE.UU. el primero de
noviembre: una semana descolocados. En primavera es peor —EE.UU. adelanta el
segundo domingo de marzo y Europa el último— y son TRES semanas.

Durante esas cuatro semanas al año, Madrid y Nueva York se separan 5 horas en
vez de 6. Todo el horario que ve el usuario está en hora de Madrid, pero el
mercado va en hora de Nueva York: el cierre operativo cae entonces a las 21:00
de Madrid en lugar de a las 22:00.

Eso NO es un fallo —la operación se cierra igual, y con más margen— pero es la
clase de acoplamiento que ya rompió el horario una vez. Estas pruebas fijan la
propiedad que de verdad importa: nunca puede haber un minuto con el mercado
abierto, el vigilante apartado y el cierre inactivo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import oro.tiempo as tiempo
from oro import cierre, vigilar
from oro.config import cargar_configuracion
from oro.dominio.mercado import mercado_cerrado

_MADRID = ZoneInfo("Europe/Madrid")
_NY = ZoneInfo("America/New_York")

# Fechas representativas: normales y de desfase, en los dos sentidos.
_FECHAS = [
    ("invierno", datetime(2026, 1, 14)),
    ("desfase primavera", datetime(2026, 3, 11)),
    ("desfase primavera", datetime(2026, 3, 25)),
    ("verano", datetime(2026, 6, 10)),
    ("desfase otoño", datetime(2026, 10, 28)),
    ("invierno", datetime(2026, 11, 4)),
]


def _desfase(t: datetime) -> float:
    return (t.astimezone(_MADRID).utcoffset()
            - t.astimezone(_NY).utcoffset()).total_seconds() / 3600


def test_existen_semanas_con_el_desfase_cambiado():
    """Si esto deja de cumplirse, las demás pruebas pierden sentido."""
    assert _desfase(datetime(2026, 1, 14, 12, tzinfo=timezone.utc)) == 6
    assert _desfase(datetime(2026, 3, 11, 12, tzinfo=timezone.utc)) == 5
    assert _desfase(datetime(2026, 10, 28, 12, tzinfo=timezone.utc)) == 5


@pytest.mark.parametrize("etiqueta,fecha", _FECHAS)
def test_nunca_hay_minutos_sin_nadie_al_mando(etiqueta, fecha, monkeypatch):
    """Mercado abierto + vigilante apartado + cierre inactivo = operación huérfana."""
    cfg = cargar_configuracion()
    abierta_de_ayer = [{"abierta_en": "2026-01-01T13:00:00+00:00"}]
    real = tiempo.a_local
    base = fecha.replace(tzinfo=timezone.utc)

    huerfanos = []
    for m in range(0, 24 * 60, 5):
        t = base + timedelta(minutes=m)
        monkeypatch.setattr(tiempo, "a_local", lambda x, _a=t: real(_a))
        try:
            apartado = vigilar._toca_relevo(cfg)
            atiende_cierre, _ = cierre._toca_cerrar(t, abierta_de_ayer)
        finally:
            monkeypatch.setattr(tiempo, "a_local", real)
        if apartado and not atiende_cierre and not mercado_cerrado(t):
            huerfanos.append(real(t))

    assert not huerfanos, (
        f"{etiqueta} {fecha:%d-%b}: {len(huerfanos)} minutos sin nadie al mando, "
        f"desde {huerfanos[0]:%H:%M} hasta {huerfanos[-1]:%H:%M} (hora de Madrid)")


@pytest.mark.parametrize("etiqueta,fecha", _FECHAS)
def test_el_cierre_operativo_llega_antes_que_el_del_mercado(etiqueta, fecha):
    """Con margen suficiente para cerrar en el bróker, también en las semanas raras."""
    from oro.dominio.mercado import hora_mercado

    cfg = cargar_configuracion()
    base = fecha.replace(tzinfo=timezone.utc)
    operativo = mercado = None
    for m in range(24 * 60):
        t = base + timedelta(minutes=m)
        if operativo is None and hora_mercado(t) == cfg.riesgo.hora_cierre_et:
            operativo = t
        if mercado is None and mercado_cerrado(t):
            mercado = t
    assert operativo is not None and mercado is not None
    margen = (mercado - operativo).total_seconds() / 60
    assert margen >= 55, f"{etiqueta} {fecha:%d-%b}: solo {margen:.0f} min de margen"
