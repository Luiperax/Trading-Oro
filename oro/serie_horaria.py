"""Las velas horarias de las últimas semanas, en vivo.

El proveedor en vivo arma cada vela con una petición (ver
:mod:`oro.datos.dukascopy_vivo`) y solo baja las últimas 24 horas. Los
indicadores del v3 (EMA 50 de H4 = 200 velas, ADX, MACD…) y la EMA 200 del
filtro del plan necesitan semanas de historia. Se arman así:

* meses ya cerrados: el fichero mensual de velas H1 de Dukascopy (una petición
  por mes, con caché en disco);
* días que el fichero mensual no cubre (el mes en curso, o el anterior si aún
  no está publicado): los ficheros de velas de un minuto de cada día, también
  con caché en disco;
* las últimas 24 horas: las velas en vivo.

Lo más caro se hace una vez por día y por proceso; en cada pasada solo se
añaden las velas en vivo.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

import pandas as pd

DIAS = 45
_COLS = ["open", "high", "low", "close"]
_base: dict = {}          # {(hoy, dias): DataFrame} — caché del proceso


def _utc(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index if df.index.tz is not None else df.index.tz_localize("UTC")
    return df.set_axis(idx.tz_convert("UTC"))


def _de_minutos(m: pd.DataFrame) -> pd.DataFrame:
    m = m[m["high"] > m["low"]]
    r = m.resample("1h", label="left", closed="left")
    return pd.DataFrame({"open": r["open"].first(), "high": r["high"].max(),
                         "low": r["low"].min(), "close": r["close"].last()}).dropna()


def base(hoy: dt.date, dias: int = DIAS) -> pd.DataFrame:
    """Velas H1 desde ``hoy - dias`` hasta el final de AYER (UTC)."""
    clave = (hoy, dias)
    if clave in _base:
        return _base[clave]
    from .ambiguos import velas_minuto_del_dia
    from .datos.dukascopy import ProveedorDukascopy

    inicio = hoy - dt.timedelta(days=dias)
    partes = []
    fin_meses = hoy.replace(day=1) - dt.timedelta(days=1)
    if fin_meses >= inicio:
        try:
            m = ProveedorDukascopy(intentos=3).rango(inicio, fin_meses)
            if m is not None and len(m):
                partes.append(_utc(m)[_COLS])
        except Exception as e:  # noqa: BLE001
            print(f"  serie horaria: sin ficheros mensuales ({type(e).__name__}).")
    cubiertos = {t.date() for t in partes[0].index} if partes else set()
    cache = Path.home() / ".cache" / "oro" / "dukascopy_m1"
    d = inicio
    while d < hoy:
        if d.weekday() != 5 and d not in cubiertos:
            m = velas_minuto_del_dia(d, cache, intentos=4)
            if m is not None and len(m):
                partes.append(_de_minutos(_utc(m)))
        d += dt.timedelta(days=1)
    if not partes:
        return pd.DataFrame(columns=_COLS)
    serie = pd.concat(partes).sort_index()
    serie = serie[~serie.index.duplicated(keep="last")]
    serie = serie[serie.index >= pd.Timestamp(inicio, tz="UTC")]
    _base.clear()
    _base[clave] = serie
    return serie


def serie_h1(df_vivo: Optional[pd.DataFrame], hoy: Optional[dt.date] = None,
             dias: int = DIAS) -> pd.DataFrame:
    """La serie completa: la base de días anteriores más las velas en vivo."""
    hoy = hoy or dt.datetime.now(dt.timezone.utc).date()
    partes = [base(hoy, dias)]
    if df_vivo is not None and len(df_vivo):
        partes.append(_utc(df_vivo)[_COLS])
    serie = pd.concat([p for p in partes if len(p)]).sort_index() if any(len(p) for p in partes) \
        else pd.DataFrame(columns=_COLS)
    return serie[~serie.index.duplicated(keep="last")]


__all__ = ["serie_h1", "base", "DIAS"]
