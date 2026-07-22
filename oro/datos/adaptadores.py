"""Adaptadores a fuentes de datos reales.

:class:`ProveedorYahoo` obtiene velas OHLCV reales del oro desde la API pública
de gráficos de Yahoo Finance. Por defecto usa el futuro continuo del oro
(``GC=F``), que sigue de cerca al XAU/USD al contado y es de acceso gratuito.

Marcos altos (H4, D1): Yahoo no da 4h directamente, así que se descarga en 1h y
se **reagrupa** a 4h. Además se descarta la última vela **en formación** (aún no
cerrada) para no generar señales que "repinten": el sistema decide siempre sobre
velas ya cerradas. Esto es clave en marcos altos y reduce el impacto del retardo
de los avisos.

Nota de honestidad: no es un feed institucional en tiempo real (tiene un ligero
retardo y es el futuro, no el spot exacto). Para operativa real conviene un feed
del bróker (MetaTrader 5, Interactive Brokers…) implementando esta misma
interfaz :class:`~oro.datos.base.ProveedorDatos`.
"""

from __future__ import annotations

import pandas as pd

from .base import ProveedorDatos

# timeframe -> (intervalo Yahoo, rango a descargar, regla de reagrupado, duración de la vela)
# La duración se usa para conservar SOLO velas ya cerradas (inicio + duración <= ahora),
# evitando tanto la vela en formación como el "tick" de precio actual que añade Yahoo.
# Así se decide siempre sobre velas cerradas (sin repintar).
_CONFIG_TF = {
    "M15": ("15m", "60d", None, "15min"),
    "M30": ("30m", "60d", None, "30min"),
    "H1": ("60m", "730d", None, "1h"),
    "H4": ("60m", "730d", "4h", "4h"),
    "D1": ("1d", "10y", None, "1D"),
}
_AGG = {"open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum", "spread": "last"}


class ProveedorYahoo(ProveedorDatos):
    def __init__(self, simbolo: str = "GC=F", timeframe: str = "H4", tiempo_espera: int = 15) -> None:
        self._simbolo = simbolo
        self._intervalo, self._rango, self._resample, self._duracion = \
            _CONFIG_TF.get(timeframe, _CONFIG_TF["H1"])
        self._tiempo_espera = tiempo_espera
        self._cache: pd.DataFrame | None = None

    def _descargar(self) -> pd.DataFrame:
        import requests

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{self._simbolo}"
        params = {"interval": self._intervalo, "range": self._rango}
        resp = requests.get(
            url, params=params, timeout=self._tiempo_espera,
            headers={"User-Agent": "Mozilla/5.0 oro/0.1"},
        )
        resp.raise_for_status()
        datos = resp.json()["chart"]["result"][0]
        ts = datos["timestamp"]
        q = datos["indicators"]["quote"][0]
        df = pd.DataFrame({
            "open": q["open"], "high": q["high"], "low": q["low"],
            "close": q["close"], "volume": q.get("volume", [0] * len(ts)),
        }, index=pd.to_datetime(ts, unit="s", utc=True))
        # Yahoo devuelve None en velas sin datos (festivos, huecos): se descartan.
        df = df.dropna(subset=["open", "high", "low", "close"])
        df["volume"] = df["volume"].fillna(0.0)
        # Spread aproximado no disponible en Yahoo: se estima pequeño y constante.
        df["spread"] = 0.2
        df = df[~df.index.duplicated(keep="last")].sort_index()

        # Reagrupar a marco alto (p. ej. 1h -> 4h) si procede.
        if self._resample:
            df = df.resample(self._resample, label="left", closed="left").agg(_AGG)
            df = df.dropna(subset=["open", "high", "low", "close"])

        # Conservar SOLO velas ya cerradas: inicio + duración <= ahora. Elimina la
        # vela en formación y el "tick" de precio actual que añade Yahoo.
        ahora = pd.Timestamp.now(tz="UTC")
        duracion = pd.Timedelta(self._duracion)
        df = df[df.index + duracion <= ahora]

        self.validar(df)
        return df

    def historico(self, velas: int) -> pd.DataFrame:
        if self._cache is None:
            self._cache = self._descargar()
        return self._cache.tail(velas).copy()

    def refrescar(self) -> None:
        """Fuerza una nueva descarga (para uso en el bucle en vivo)."""
        self._cache = self._descargar()
