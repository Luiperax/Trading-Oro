"""Las citas del parte deben absorber el retraso REAL de GitHub.

Medido sobre 27 ejecuciones: GitHub arranca las citas de este workflow con 4.4 a
4.9 h de retraso, de forma muy consistente. Con la primera cita a las 05:03 UTC,
la ejecución más temprana caía a las 09:30 UTC y el parte llegaba siempre sobre
las 11:30 de Madrid, nunca a las 7:00 "con el café".

La solución no es esperar a que GitHub mejore: es citar antes. Esta prueba fija
esa propiedad, para que nadie borre las citas de madrugada pensando que sobran.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from oro.latido import HORA_ENVIO_LOCAL, HORA_LIMITE_LOCAL

_MADRID = ZoneInfo("Europe/Madrid")
_WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/oro-latido.yml"


def _citas() -> list[tuple[int, int]]:
    datos = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    # "on" es la palabra reservada True en YAML 1.1.
    programa = datos.get("on", datos.get(True))["schedule"]
    fuera = []
    for entrada in programa:
        minuto, hora = entrada["cron"].split()[:2]
        fuera.append((int(hora), int(minuto)))
    return fuera


def _hora_de_llegada(retraso_h: float, dia: datetime) -> datetime | None:
    """Primera cita que, con ese retraso, cae dentro de la franja de envío."""
    mejor = None
    for h, m in _citas():
        t = dia.replace(hour=h, minute=m) + timedelta(hours=retraso_h)
        local = t.astimezone(_MADRID)
        if HORA_ENVIO_LOCAL <= local.hour < HORA_LIMITE_LOCAL:
            if mejor is None or t < mejor:
                mejor = t
    return mejor.astimezone(_MADRID) if mejor else None


@pytest.mark.parametrize("dia", [
    datetime(2026, 9, 4, tzinfo=timezone.utc),    # verano (Madrid UTC+2)
    datetime(2026, 1, 14, tzinfo=timezone.utc),   # invierno (Madrid UTC+1)
])
@pytest.mark.parametrize("retraso", [0.0, 0.5, 1.0, 2.0, 3.0, 4.5, 6.0])
def test_el_parte_llega_por_la_manana_pese_al_retraso(retraso, dia):
    llegada = _hora_de_llegada(retraso, dia)
    assert llegada is not None, f"con {retraso} h de retraso el parte NO llega"
    assert llegada.hour < 12, (
        f"con {retraso} h de retraso el parte llegaría a las {llegada:%H:%M}, "
        f"ya no es 'con el café'")


def test_con_el_retraso_observado_llega_a_primera_hora():
    """4.5 h es el retraso medido de verdad, no un supuesto."""
    llegada = _hora_de_llegada(4.5, datetime(2026, 9, 4, tzinfo=timezone.utc))
    assert llegada is not None and llegada.hour == 7, (
        f"llegaría a las {llegada:%H:%M} en vez de a las 07:0x")


def test_hay_citas_de_madrugada_para_absorber_el_retraso():
    """Sin ellas volvemos a las 11:30: son la pieza que arregla el problema."""
    madrugada = [c for c in _citas() if c[0] < 5]
    assert len(madrugada) >= 4, (
        "faltan citas de madrugada; con el retraso real de GitHub el parte "
        "volvería a llegar a media mañana")
