"""Hora local del usuario en los avisos.

Todo el sistema razona internamente en UTC (es lo correcto: el mercado es
global y así no hay ambigüedad con los cambios de hora). Pero los avisos los lee
una persona, y "cierre a las 21:00" no significa nada si vives en Madrid y para
ti son las 23:00. Aquí se traduce solo de cara al mensaje.

La zona se ajusta con ORO_ZONA_HORARIA (por defecto Europe/Madrid). El cambio
de hora verano/invierno lo resuelve la propia base de datos de zonas horarias.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import entorno

ZONA_POR_DEFECTO = "Europe/Madrid"


def zona_usuario():
    """Zona horaria configurada; UTC si el sistema no la reconoce."""
    # Con la variable VACÍA (que es como GitHub manda una Variable no definida)
    # esto devolvía ZoneInfo("") -> excepción -> UTC, y TODAS las horas de los
    # correos salían mal sin dar ningún error. Es el fallo más peligroso de los
    # tres de su clase, porque no se nota. Ver oro/entorno.py.
    nombre = entorno.texto("ORO_ZONA_HORARIA", ZONA_POR_DEFECTO)
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(nombre)
    except Exception:  # noqa: BLE001 — sin zoneinfo, mejor UTC que reventar.
        if nombre != ZONA_POR_DEFECTO:
            print(f"⚠️  ORO_ZONA_HORARIA={nombre!r} no se reconoce; se prueba "
                  f"{ZONA_POR_DEFECTO}.")
            try:
                from zoneinfo import ZoneInfo
                return ZoneInfo(ZONA_POR_DEFECTO)
            except Exception:  # noqa: BLE001
                pass
        print("⚠️  Sin base de datos de zonas horarias: las horas irán en UTC.")
        return timezone.utc


def a_local(momento: datetime) -> datetime:
    """Pasa un instante a la hora local del usuario."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(zona_usuario())


def hora_local(momento: datetime) -> str:
    """Solo la hora: '23:42'."""
    return f"{a_local(momento):%H:%M}"


def fecha_hora_local(momento: datetime) -> str:
    """Fecha y hora legibles: '27-ago 23:42'."""
    return f"{a_local(momento):%d-%b %H:%M}"


def etiqueta_zona(momento: datetime | None = None) -> str:
    """Abreviatura de la zona ('CEST'/'CET'), para no dejar dudas."""
    return f"{a_local(momento or datetime.now(timezone.utc)):%Z}" or "local"
