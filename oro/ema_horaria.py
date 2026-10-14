"""La EMA de 200 velas horarias del oro, en vivo.

Es el filtro del plan de ruptura (H19 en docs/ESTRATEGIAS_MEDIDAS.md): la venta
solo se deja puesta si a las 8:00 de Nueva York el precio está POR DEBAJO de su
EMA 200 horaria, y la compra del día de empleo, solo si está por encima.

POR QUÉ UN ESTADO GUARDADO
--------------------------
Una EMA de 200 horas necesita unas 600 velas de historia para valer lo mismo que
en el histórico, y el proveedor en vivo arma cada vela con una petición (ver
:mod:`oro.datos.dukascopy_vivo`): 600 peticiones cada mañana no son viables.
Pero la EMA es recursiva: con su último valor y las velas posteriores basta.
Así que se guarda en ``oro_ema.json`` (valor, hasta qué vela, y las últimas 48
para poder mirar atrás) y cada pasada del vigilante la avanza con las 24 horas
que ya baja para el plan.

Si entre el estado guardado y las velas nuevas falta alguna hora de mercado
abierto (el vigilante estuvo parado más de un día), se reconstruye desde cero:
meses cerrados con los ficheros horarios de Dukascopy, el mes en curso con los
de un minuto, y el día de hoy con las velas en vivo.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd

RUTA_EMA = "oro_ema.json"
PERIODO = 200
ALFA = 2 / (PERIODO + 1)
GUARDAR = 48                     # velas de historial que se conservan


def _ruta() -> Path:
    return Path(os.getenv("ORO_RUTA_EMA", RUTA_EMA))


def cargar() -> Optional[dict]:
    try:
        d = json.loads(_ruta().read_text(encoding="utf-8"))
        return d if "hasta" in d and "ema" in d else None
    except (OSError, ValueError):
        return None


def _guardar(estado: dict) -> None:
    try:
        _ruta().write_text(json.dumps(estado, indent=1), encoding="utf-8")
    except OSError as e:  # noqa: BLE001
        print(f"⚠️  No se pudo guardar la EMA horaria ({e}).")


def _cerrado(hora: pd.Timestamp) -> bool:
    from .datos.dukascopy_vivo import ProveedorDukascopyVivo

    return ProveedorDukascopyVivo.mercado_cerrado(hora.to_pydatetime())


def _utc(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return idx if idx.tz is not None else idx.tz_localize("UTC")


def avanzar(df: pd.DataFrame, estado: Optional[dict] = None,
            guardar: bool = True) -> Optional[dict]:
    """Avanza la EMA guardada con las velas de ``df`` posteriores a ella.

    Devuelve el estado nuevo, o ``None`` si no hay estado o si falta alguna
    hora de mercado abierto entre lo guardado y lo nuevo (entonces hay que
    reconstruir: seguir avanzando daría una EMA que no es la de verdad).
    """
    estado = estado if estado is not None else cargar()
    if estado is None or df is None or len(df) == 0:
        return estado
    cierres = df["close"].copy()
    cierres.index = _utc(cierres.index)
    hasta = pd.Timestamp(estado["hasta"])
    nuevas = cierres[cierres.index > hasta]
    if nuevas.empty:
        return estado
    h = hasta + pd.Timedelta(hours=1)
    while h < nuevas.index[0]:
        if not _cerrado(h):
            return None
        h += pd.Timedelta(hours=1)
    ema = float(estado["ema"])
    hist = dict(estado.get("historial", {}))
    for t, c in nuevas.items():
        ema += ALFA * (float(c) - ema)
        hist[t.isoformat()] = round(ema, 4)
    hist = dict(sorted(hist.items())[-GUARDAR:])
    nuevo = {"hasta": nuevas.index[-1].isoformat(), "ema": round(ema, 4),
             "historial": hist}
    if guardar:
        _guardar(nuevo)
    return nuevo


def desde_cierres(cierres: pd.Series) -> dict:
    """Estado a partir de una serie larga de cierres horarios."""
    cierres = cierres.sort_index()
    cierres.index = _utc(cierres.index)
    ema = cierres.ewm(span=PERIODO, adjust=False).mean()
    hist = {t.isoformat(): round(float(v), 4) for t, v in ema.iloc[-GUARDAR:].items()}
    return {"hasta": cierres.index[-1].isoformat(), "ema": round(float(ema.iloc[-1]), 4),
            "historial": hist}


def reconstruir(df_vivo: Optional[pd.DataFrame], hoy: Optional[dt.date] = None,
                guardar: bool = True) -> Optional[dict]:
    """Rehace la EMA con ~45 días de velas horarias (ver el docstring del módulo)."""
    from .ambiguos import velas_minuto_del_dia
    from .datos.dukascopy import ProveedorDukascopy

    hoy = hoy or dt.datetime.now(dt.timezone.utc).date()
    inicio = hoy - dt.timedelta(days=45)
    partes = []
    try:
        meses = ProveedorDukascopy().rango(inicio, hoy.replace(day=1) - dt.timedelta(days=1))
        partes.append(meses["close"])
    except Exception as e:  # noqa: BLE001
        print(f"  EMA: sin los meses cerrados de Dukascopy ({type(e).__name__}).")
    cache = Path.home() / ".cache" / "oro" / "dukascopy_m1"
    d = max(inicio, hoy.replace(day=1))
    while d < hoy:
        if d.weekday() != 5:
            m = velas_minuto_del_dia(d, cache, intentos=4)
            if m is not None and len(m):
                m = m[m["high"] > m["low"]]
                partes.append(m["close"].resample("1h", label="left", closed="left").last().dropna())
        d += dt.timedelta(days=1)
    if df_vivo is not None and len(df_vivo):
        partes.append(df_vivo["close"])
    if not partes:
        return None
    serie = pd.concat([p.set_axis(_utc(p.index)) for p in partes])
    serie = serie[~serie.index.duplicated(keep="last")].sort_index()
    if len(serie) < 3 * PERIODO:
        print(f"  EMA: solo {len(serie)} velas para reconstruirla; no vale.")
        return None
    estado = desde_cierres(serie)
    if guardar:
        _guardar(estado)
    return estado


def ema_en(df_vivo: pd.DataFrame, vela: pd.Timestamp) -> Optional[float]:
    """La EMA 200 horaria al cierre de la vela que empieza en ``vela`` (UTC)."""
    estado = avanzar(df_vivo)
    if estado is None:
        print("  EMA 200 horaria: el estado guardado no enlaza con las velas de "
              "ahora; se reconstruye.")
        estado = reconstruir(df_vivo)
    if estado is None:
        return None
    clave = pd.Timestamp(vela).tz_convert("UTC").isoformat() if pd.Timestamp(vela).tzinfo \
        else pd.Timestamp(vela).tz_localize("UTC").isoformat()
    v = estado.get("historial", {}).get(clave)
    return float(v) if v is not None else None


__all__ = ["RUTA_EMA", "avanzar", "reconstruir", "ema_en", "cargar", "desde_cierres"]
