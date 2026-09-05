"""Proveedores de datos de mercado.

La interfaz :class:`ProveedorDatos` desacopla el sistema de la fuente concreta.
Se incluyen dos implementaciones que funcionan **sin conexión**:

* :class:`ProveedorSintetico` — genera series OHLCV realistas (con tendencia,
  regímenes de volatilidad y ruido) para desarrollo, pruebas y backtesting.
* :class:`ProveedorCSV` — carga histórico real desde un CSV OHLCV.

Los adaptadores a fuentes reales (MetaTrader 5, brokers, APIs) se implementan
sobre la misma interfaz en :mod:`oro.datos.adaptadores`.

Para **investigación** hay además :class:`ProveedorDukascopy`, que da XAU/USD
spot en H1 desde 2007 y quita el tope de 730 días de Yahoo. No se usa en vivo
(no ofrece el precio del último tick), pero multiplica por ocho la muestra de
cualquier medición histórica.
"""

from __future__ import annotations

from .base import ProveedorDatos
from .sintetico import ProveedorSintetico
from .csv import ProveedorCSV
from .adaptadores import ProveedorYahoo
from .dukascopy import ProveedorDukascopy

__all__ = ["ProveedorDatos", "ProveedorSintetico", "ProveedorCSV", "ProveedorYahoo", "ProveedorDukascopy"]
