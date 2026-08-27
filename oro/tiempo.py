"""Hora local del usuario en los avisos.

Todo el sistema razona internamente en UTC (es lo correcto: el mercado es
global y así no hay ambigüedad con los cambios de hora). Pero los avisos los lee
una persona, y "cierre a las 21:00" no significa nada si vives en Madrid y para
ti son las 23:00. Aquí se traduce solo de cara al mensaje.

La zona se ajusta con ORO_ZONA_HORARIA (por defecto Europe/Madrid). El cambio
de hora verano/invierno lo resuelve la propia base de datos de zonas horarias.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

ZONA_POR_DEFECTO = "Europe/Madrid"


def zona_usuario():
    """Zona horaria configurada; UTC si el sistema no la reconoce."""
    nombre = os.getenv("ORO_ZONA_HORARIA", ZONA_POR_DEFECTO)
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(nombre)
    except Exception:  # noqa: BLE001 — sin zoneinfo, mejor UTC que reventar.
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
