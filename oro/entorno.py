"""Lectura de variables de entorno a prueba de la cadena vacía.

POR QUÉ EXISTE ESTE MÓDULO
--------------------------
Las «Variables» de GitHub Actions que no están definidas NO llegan ausentes:
llegan como CADENA VACÍA. Y una cadena vacía se cuela por todas partes:

    int("")                  -> ValueError, el proceso muere
    ZoneInfo("")             -> excepción capturada -> UTC en SILENCIO
    cfg.simbolo = ""         -> el proveedor de datos pide un símbolo vacío

El caso real (6-sep-2026): al añadir `ORO_SMTP_PUERTO: ${{ vars.ORO_SMTP_PUERTO }}`
a los workflows —para arreglar que la configuración no llegaba a producción— la
variable pasó de estar AUSENTE a estar VACÍA, y `int(os.getenv("ORO_SMTP_PUERTO",
"587"))` reventó. El vigilante llevaba horas muriendo a los 17 segundos sin
mandar una sola alerta. El arreglo de un problema creó otro peor, porque el
primero era silencioso y este mataba el proceso.

El más traicionero de los tres es el segundo: con `ORO_ZONA_HORARIA` vacía, la
zona cae a UTC sin dar ningún error y TODAS las horas de los correos salen mal
—«cierra a las 20:00» cuando en Madrid son las 22:00— sin que nada lo delate.

LA REGLA
--------
Una variable vacía es una variable NO DEFINIDA. Siempre. Sin excepciones.
"""

from __future__ import annotations

import os
from typing import Optional


def texto(nombre: str, defecto: str = "") -> str:
    """Valor de la variable, o el defecto si no está o está vacía."""
    return (os.getenv(nombre) or "").strip() or defecto


def presente(nombre: str) -> bool:
    """¿La variable tiene un valor de verdad? (no ausente y no vacía)."""
    return bool(texto(nombre))


def entero(nombre: str, defecto: int) -> int:
    """Entero de la variable. Si falta, está vacía o no es un número, el defecto.

    No se deja reventar: un puerto mal escrito no puede tumbar el vigilante y
    dejar al usuario sin avisos. Se queja por el registro y sigue.
    """
    bruto = texto(nombre)
    if not bruto:
        return defecto
    try:
        return int(bruto)
    except ValueError:
        print(f"⚠️  {nombre}={bruto!r} no es un número entero; se usa {defecto}.")
        return defecto


def decimal(nombre: str, defecto: float) -> float:
    """Igual que :func:`entero`, para números con decimales."""
    bruto = texto(nombre)
    if not bruto:
        return defecto
    try:
        return float(bruto)
    except ValueError:
        print(f"⚠️  {nombre}={bruto!r} no es un número; se usa {defecto}.")
        return defecto


def booleano(nombre: str, defecto: bool) -> bool:
    """Interruptor por entorno. Vacío = se mantiene el valor actual."""
    bruto = texto(nombre).lower()
    if not bruto:
        return defecto
    if bruto in ("1", "true", "si", "sí", "on", "yes"):
        return True
    if bruto in ("0", "false", "no", "off"):
        return False
    print(f"⚠️  {nombre}={bruto!r} no es sí/no; se mantiene {defecto}.")
    return defecto


def opcional(nombre: str) -> Optional[str]:
    """El valor, o ``None`` si no está o está vacío."""
    return texto(nombre) or None


__all__ = ["texto", "presente", "entero", "decimal", "booleano", "opcional"]
