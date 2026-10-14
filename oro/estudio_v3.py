"""El indicador de TradingView «XAU/USD M30 — Activo v3», medido en el histórico.

    python -m oro.estudio_v3 --desde 2025-01-01 --hasta 2025-12-31

Reproduce el script de Pine tal como está, con sus valores por defecto, sobre
velas M30 armadas con las de 1 minuto (bid) de Dukascopy. Las salidas se
resuelven minuto a minuto. Imprime una línea por operación (para poder juntar
varios trozos medidos en máquinas distintas) y un resumen.

La hipótesis y cómo se mide están declaradas en docs/ESTRATEGIAS_MEDIDAS.md
(H28), escritas antes de ejecutar esto.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---- Parámetros del script de Pine (valores por defecto) ----
EMA_RAPIDA, EMA_LENTA, EMA_H4 = 21, 50, 50
MIN_SCORE = 3
ATR_LEN, SL_ATR, TP1_ATR, TP2_ATR = 14, 1.5, 1.5, 2.5
SESION_UTC = (7, 21)          # Londres 07-16 ∪ Nueva York 13-21
DESLIZAMIENTO = 0.25
CACHE = Path.home() / ".cache" / "oro" / "dukascopy_m1"


# ---- Indicadores con las fórmulas de TradingView ----
def _rma(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False).mean()


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def indicadores(m30: pd.DataFrame) -> pd.DataFrame:
    c, h, l = m30["close"], m30["high"], m30["low"]
    d = pd.DataFrame(index=m30.index)
    d["close"] = c
    d["ema21"], d["ema50"] = _ema(c, EMA_RAPIDA), _ema(c, EMA_LENTA)
    delta = c.diff()
    rs = _rma(delta.clip(lower=0), 14) / _rma((-delta).clip(lower=0), 14)
    d["rsi"] = 100 - 100 / (1 + rs)
    macd = _ema(c, 12) - _ema(c, 26)
    d["macdh"] = macd - _ema(macd, 9)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    d["atr"] = _rma(tr, ATR_LEN)
    up, down = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=m30.index)
    mdm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=m30.index)
    atr14 = _rma(tr, 14)
    pdi, mdi = 100 * _rma(pdm, 14) / atr14, 100 * _rma(mdm, 14) / atr14
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    d["adx"] = _rma(dx, 14)
    # EMA 50 de H4 con velas de 4 horas YA CERRADAS en el momento en que
    # cierra cada vela M30 (lo que el indicador ve en el histórico).
    h4 = m30["close"].resample("4h", label="right", closed="left").last().dropna()
    ema_h4 = _ema(h4, EMA_H4)
    fin_m30 = m30.index + pd.Timedelta(minutes=30)
    d["ema50h4"] = ema_h4.reindex(fin_m30, method="ffill").to_numpy()
    return d


def senales(d: pd.DataFrame) -> pd.DataFrame:
    rsi, mh, e21, e50, c = d["rsi"], d["macdh"], d["ema21"], d["ema50"], d["close"]
    rsi_alza = (rsi > rsi.shift(1)) & (rsi.shift(1) > rsi.shift(2)) & (rsi < 60)
    rsi_baja = (rsi < rsi.shift(1)) & (rsi.shift(1) < rsi.shift(2)) & (rsi > 40)
    macd_alza = (mh > mh.shift(1)) & (mh.shift(1) > mh.shift(2))
    macd_baja = (mh < mh.shift(1)) & (mh.shift(1) < mh.shift(2))
    cerca_bull = (c > e21 * 0.994) & (c < e21 * 1.008) & (e21 > e50)
    cerca_bear = (c < e21 * 1.006) & (c > e21 * 0.992) & (e21 < e50)
    adx_ok = d["adx"] > 18
    sl_ = ((c > d["ema50h4"]).astype(int) + (e21 > e50).astype(int) + rsi_alza.astype(int)
           + macd_alza.astype(int) + cerca_bull.astype(int) + adx_ok.astype(int))
    ss_ = ((c < d["ema50h4"]).astype(int) + (e21 < e50).astype(int) + rsi_baja.astype(int)
           + macd_baja.astype(int) + cerca_bear.astype(int) + adx_ok.astype(int))
    hora = d.index.hour
    en_sesion = (hora >= SESION_UTC[0]) & (hora < SESION_UTC[1])
    largo = (sl_ >= MIN_SCORE) & (sl_ > sl_.shift(1)) & en_sesion & ~(ss_ >= MIN_SCORE)
    corto = (ss_ >= MIN_SCORE) & (ss_ > ss_.shift(1)) & en_sesion & ~(sl_ >= MIN_SCORE)
    out = d.copy()
    out["senal"] = np.where(largo, 1, np.where(corto, -1, 0))
    return out


# ---- Datos ----
def minutos(desde: dt.date, hasta: dt.date) -> pd.DataFrame:
    from .ambiguos import velas_minuto_del_dia

    trozos = []
    d = desde
    while d <= hasta:
        if d.weekday() != 5:                       # el sábado no hay mercado
            m = velas_minuto_del_dia(d, CACHE)
            if m is not None and len(m):
                m = m[m["high"] > m["low"]]        # fuera los minutos planos de relleno
                trozos.append(m)
        d += dt.timedelta(days=1)
    return pd.concat(trozos).sort_index() if trozos else pd.DataFrame()


def a_m30(m1: pd.DataFrame) -> pd.DataFrame:
    r = m1.resample("30min", label="left", closed="left")
    return pd.DataFrame({"open": r["open"].first(), "high": r["high"].max(),
                         "low": r["low"].min(), "close": r["close"].last()}).dropna()


def tipo_fed() -> pd.Series:
    clave = os.getenv("ORO_FRED_CLAVE", "")
    if clave:
        try:
            import requests
            r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                             params={"series_id": "DFF", "api_key": clave,
                                     "file_type": "json", "observation_start": "2021-01-01"},
                             timeout=30)
            o = r.json()["observations"]
            return pd.Series({pd.Timestamp(x["date"]).date(): float(x["value"]) / 100
                              for x in o if x["value"] != "."}).sort_index()
        except Exception:  # noqa: BLE001
            pass
    return pd.Series(dtype=float)


# ---- Simulación ----
def simular(m1: pd.DataFrame, d: pd.DataFrame, entrar_desde, entrar_hasta,
            ff: pd.Series, cierre_diario: bool = False,
            vela: pd.Timedelta = pd.Timedelta(minutes=30),
            objetivo_primero: bool = False) -> list[dict]:
    """``m1`` son las velas con que se resuelven las salidas (de 1 minuto, o
    las propias velas de la señal si no hay más finas). ``objetivo_primero``
    solo sirve de cota: si una vela toca stop y objetivo, cuenta el objetivo."""
    from .spread import spread_de

    sen = d[(d["senal"] != 0) & (d.index >= entrar_desde) & (d.index <= entrar_hasta)]
    hi, lo, op, cl = (m1[k].to_numpy() for k in ("high", "low", "open", "close"))
    t_m1 = m1.index
    ops, libre_desde = [], pd.Timestamp.min.tz_localize("UTC")
    for t, fila in sen.iterrows():
        fin_vela = t + vela
        if fin_vela < libre_desde:
            continue                                # hay una operación abierta
        i0 = t_m1.searchsorted(fin_vela)
        if i0 >= len(t_m1):
            break
        s = int(fila["senal"]); c0, atr = fila["close"], fila["atr"]
        stop, tp1, tp2 = c0 - s * SL_ATR * atr, c0 + s * TP1_ATR * atr, c0 + s * TP2_ATR * atr
        entrada = op[i0]
        riesgo = abs(entrada - stop)
        if riesgo <= 0 or s * (stop - entrada) >= 0:
            continue
        salida1 = salida2 = None
        i = i0
        limite = None
        if cierre_diario:
            dia = t_m1[i0].normalize()
            limite = dia + pd.Timedelta(hours=21)
            if t_m1[i0] >= limite:
                continue
        while i < len(t_m1):
            if limite is not None and t_m1[i] >= limite:
                px = op[i]
                salida1 = px if salida1 is None else salida1
                salida2 = px
                break
            peor = lo[i] if s > 0 else hi[i]
            mejor = hi[i] if s > 0 else lo[i]
            if objetivo_primero:
                if salida1 is None and s * (mejor - tp1) >= 0:
                    salida1 = tp1
                if salida1 is not None and s * (mejor - tp2) >= 0:
                    salida2 = tp2
                    break
            if s * (peor - stop) <= 0:              # stop (primero, por prudencia)
                if salida1 is None:
                    salida1 = stop
                salida2 = stop
                break
            if salida1 is None and s * (mejor - tp1) >= 0:
                salida1 = tp1
            if salida1 is not None and s * (mejor - tp2) >= 0:
                salida2 = tp2
                break
            i += 1
        if salida2 is None:                         # sin datos para cerrarla
            break
        t_sal = t_m1[min(i, len(t_m1) - 1)]
        r_bruto = s * (0.5 * (salida1 - entrada) + 0.5 * (salida2 - entrada)) / riesgo
        # Noches: cada vez que la posición cruza las 21:00 UTC (rollover).
        noches, fin_noches = [], t_sal
        k = t_m1[i0].normalize() + pd.Timedelta(hours=21)
        if k <= t_m1[i0]:
            k += pd.Timedelta(days=1)
        while k < fin_noches:
            noches.append(k.date()); k += pd.Timedelta(days=1)
        fin = 0.0
        for n in noches:
            tf = float(ff[:n].iloc[-1]) if len(ff) and len(ff[:n]) else 0.04
            tasa = -(tf + 0.025) if s > 0 else (tf - 0.025)
            fin += tasa * entrada / 365
        coste = spread_de(t.year) + DESLIZAMIENTO
        r_neto = r_bruto + (fin - coste) / riesgo
        ops.append({"t": t.isoformat(), "dir": s, "entrada": round(entrada, 2),
                    "riesgo": round(riesgo, 2), "salida": t_sal.isoformat(),
                    "r_bruto": round(r_bruto, 4), "r_neto": round(r_neto, 4),
                    "noches": len(noches)})
        libre_desde = t_sal
    return ops


def resumen(ops: list[dict], titulo: str) -> None:
    if not ops:
        print(f"{titulo}: sin operaciones"); return
    r = np.array([o["r_neto"] for o in ops]); b = np.array([o["r_bruto"] for o in ops])
    n = len(r); t = r.mean() / r.std(ddof=1) * math.sqrt(n)
    h1, h2 = r[: n // 2], r[n // 2:]
    meses = max(1.0, (pd.Timestamp(ops[-1]["t"]) - pd.Timestamp(ops[0]["t"])).days / 30.4)
    print(f"{titulo}: n={n} ({n/meses:.0f}/mes) acierto {np.mean(r > 0):.0%} "
          f"bruto {b.mean():+.4f} R neto {r.mean():+.4f} R t={t:+.2f} "
          f"mitades {h1.mean():+.4f}/{h2.mean():+.4f} total {r.sum():+.1f} R "
          f"noches/op {np.mean([o['noches'] for o in ops]):.1f}")


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--desde", required=True)
    p.add_argument("--hasta", required=True)
    a = p.parse_args(argv)
    desde, hasta = dt.date.fromisoformat(a.desde), dt.date.fromisoformat(a.hasta)
    m1 = minutos(desde - dt.timedelta(days=25), hasta + dt.timedelta(days=10))
    print(f"minutos: {len(m1)} de {m1.index.min()} a {m1.index.max()}", flush=True)
    d = senales(indicadores(a_m30(m1)))
    ff = tipo_fed()
    e0 = pd.Timestamp(desde, tz="UTC"); e1 = pd.Timestamp(hasta, tz="UTC") + pd.Timedelta(days=1)
    for nombre, diario in (("TAL CUAL", False), ("CIERRE 21 UTC", True)):
        ops = simular(m1, d, e0, e1, ff, cierre_diario=diario)
        for o in ops:
            print("OP " + nombre.replace(" ", "_") + " " + json.dumps(o))
        resumen(ops, nombre)
        for s, nom in ((1, "largos"), (-1, "cortos")):
            resumen([o for o in ops if o["dir"] == s], f"  {nombre} {nom}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
