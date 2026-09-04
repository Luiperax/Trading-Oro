"""El aviso de cierre debe caer en su franja pese al retraso de GitHub.

MEDIDO sobre 18 ejecuciones reales, y el dato importante es que el retraso NO es
estable: en agosto iba de 6 a 9 h, en septiembre de 2 h 00 a 2 h 26. Con las
citas puestas a las 19:50/20:50 UTC, la ejecución caía a las 23:55 de Madrid,
ya con el mercado cerrado, y el aviso de las 21:50 no se ejecutó jamás.

Apuntar a un retraso concreto no sirve: ya cambió una vez. Lo que sí funciona es
aritmética: la franja dura 20 min, así que con citas cada 15 —espaciado MENOR
que la franja— siempre cae alguna dentro.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from oro import cierre

_MADRID = ZoneInfo("Europe/Madrid")
_WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/oro-cierre.yml"
_VERANO = datetime(2026, 9, 4, tzinfo=timezone.utc)
_INVIERNO = datetime(2026, 1, 14, tzinfo=timezone.utc)


def _citas() -> list[tuple[int, int]]:
    datos = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    programa = datos.get("on", datos.get(True))["schedule"]
    return sorted((int(e["cron"].split()[1]), int(e["cron"].split()[0])) for e in programa)


def _avisa(retraso_min: int, dia: datetime) -> datetime | None:
    """Primera ejecución que cae en la franja del aviso (21:40-21:59 locales)."""
    for h, m in _citas():
        t = dia.replace(hour=h, minute=m) + timedelta(minutes=retraso_min)
        local = t.astimezone(_MADRID)
        if local.hour == cierre.HORA_AVISO_LOCAL and local.minute >= 40:
            return local
    return None


def test_las_citas_estan_mas_juntas_que_la_franja():
    """La propiedad de la que depende todo: espaciado < anchura de la franja."""
    citas = _citas()
    assert len(citas) >= 20, "hacen falta citas densas para cubrir el retraso"
    minutos = [h * 60 + m for h, m in citas]
    huecos = [b - a for a, b in zip(minutos, minutos[1:])]
    assert max(huecos) <= 15, (
        f"hay un hueco de {max(huecos)} min entre citas; la franja del aviso "
        f"dura 20 min, así que un hueco mayor deja pasar retrasos sin acertar")


@pytest.mark.parametrize("dia,etiqueta", [(_VERANO, "verano"), (_INVIERNO, "invierno")])
def test_acierta_con_cualquier_retraso_de_cero_a_cinco_horas(dia, etiqueta):
    fallos = [r for r in range(0, 5 * 60 + 1, 5) if _avisa(r, dia) is None]
    assert not fallos, (
        f"{etiqueta}: sin aviso con retrasos de {fallos[:5]} min "
        f"(el real medido en septiembre es ~122 min)")


@pytest.mark.parametrize("dia,etiqueta", [(_VERANO, "verano"), (_INVIERNO, "invierno")])
def test_con_el_retraso_medido_hoy_avisa_a_las_21_4x(dia, etiqueta):
    """122 min es la mediana real de septiembre, no un supuesto."""
    llegada = _avisa(122, dia)
    assert llegada is not None
    assert llegada.hour == 21 and 40 <= llegada.minute <= 59, (
        f"{etiqueta}: avisaría a las {llegada:%H:%M}")


def test_las_citas_de_la_tarde_no_cierran_una_operacion_sana():
    """Con 26 citas repartidas, ninguna debe cerrar antes de tiempo.

    La regla de recuperación solo actúa sobre operaciones de una sesión YA
    terminada; una abierta hoy se respeta hasta su hora.
    """
    abierta_hoy = [{"abierta_en": "2026-09-04T00:00:00+00:00"}]
    for h, m in _citas():
        t = _VERANO.replace(hour=h, minute=m)
        toca, motivo = cierre._toca_cerrar(t, abierta_hoy)
        local = t.astimezone(_MADRID)
        if local.hour == cierre.HORA_AVISO_LOCAL and local.minute >= 40:
            assert toca, f"a las {local:%H:%M} SÍ debía avisar"
        else:
            assert not toca, (
                f"a las {local:%H:%M} cerraría una operación sana de hoy: {motivo}")
