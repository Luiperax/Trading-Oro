"""Los días «ambiguos», resueltos con velas de un minuto.

    python -m oro.ambiguos

QUÉ PROBLEMA MIDE
-----------------
Un día es ambiguo cuando, dentro de la ventana de disparo, una MISMA vela
horaria cruza el techo y el suelo del rango. Con velas de una hora no se sabe
qué fue primero, y el histórico (``oro.historico``) dejaba esos días fuera de
las cifras: ni ganados ni perdidos. Son unos 360 de 5.370 días con plan.

Fuera de las cifras no es lo mismo que fuera de la cuenta. En vivo, ese día:

* si el precio cayó PRIMERO, la venta se ejecutó y luego subió hasta el techo,
  que es justo el stop: −1 R y los costes;
* si subió primero, la venta ya no valía, pero el aviso de cancelar solo puede
  llegar cuando se publica la vela, al terminar la hora; si dentro de esa hora
  el precio bajó hasta la venta, se ejecutó igualmente y se cierra al recibir
  el aviso (o la cierra antes su stop).

Este módulo baja las velas de un minuto de Dukascopy de esos días y calcula lo
que habría pasado de verdad, con las mismas funciones de producción
(``construir_plan``, ``refinar``, ``seguir``).
"""

from __future__ import annotations

import datetime as dt
import json
import lzma
import struct
import sys
import time
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

URL = ("https://datafeed.dukascopy.com/datafeed/{sim}/{anio}/{mes:02d}/{dia:02d}/"
       "BID_candles_min_1.bi5")
_REG = struct.Struct(">5if")          # segundos, apertura, cierre, mínimo, máximo, volumen
_U = dt.timezone.utc


def velas_minuto_del_dia(dia: dt.date, cache: Path, simbolo: str = "XAUUSD",
                         intentos: int = 10) -> Optional[pd.DataFrame]:
    """Las velas de 1 minuto (bid) de un día UTC, con caché en disco."""
    import requests

    fichero = cache / simbolo / f"{dia.isoformat()}.bi5"
    if not fichero.exists():
        url = URL.format(sim=simbolo, anio=dia.year, mes=dia.month - 1, dia=dia.day)
        for intento in range(intentos):
            try:
                r = requests.get(url, timeout=30,
                                 headers={"User-Agent": "Mozilla/5.0 oro/0.1"})
                if r.status_code == 200 and r.content:
                    fichero.parent.mkdir(parents=True, exist_ok=True)
                    fichero.write_bytes(r.content)
                    break
                espera = 30 if r.status_code == 429 else min(2 ** intento, 10)
            except Exception:  # noqa: BLE001
                espera = 5
            time.sleep(espera)
        else:
            return None
    crudo = lzma.LZMADecompressor().decompress(fichero.read_bytes())
    base = dt.datetime(dia.year, dia.month, dia.day, tzinfo=_U)
    filas = [_REG.unpack_from(crudo, i * _REG.size) for i in range(len(crudo) // _REG.size)]
    if not filas:
        return None
    return pd.DataFrame(
        {"open": [f[1] / 1000 for f in filas], "high": [f[4] / 1000 for f in filas],
         "low": [f[3] / 1000 for f in filas], "close": [f[2] / 1000 for f in filas],
         "volume": [float(f[5]) for f in filas]},
        index=pd.DatetimeIndex([base + dt.timedelta(seconds=f[0]) for f in filas]))


def resolver(plan, velas, minutos: Callable) -> tuple[str, Optional[float]]:
    """(caso, R en bruto) de un día ambiguo; R es ``None`` si no hubo operación.

    ``minutos(hora)`` da las velas de 1 minuto de esa hora UTC.
    """
    from .seguimiento import MARGEN_ULTIMA_VELA, EstadoPlan, refinar, seguir

    fino = refinar(plan, velas, minutos)
    if fino is None:
        return "sin datos de minuto", None
    s = seguir(plan, fino, ahora=plan.cierre_forzoso + MARGEN_ULTIMA_VELA)
    if s.estado is EstadoPlan.CERRADA:
        return f"{s.direccion.value} primero: {s.motivo_cierre}", s.r
    if s.estado is EstadoPlan.ANULADO:
        # `seguir` ya cuenta la venta ejecutada en la misma hora de la rotura
        # al alza (ver seguimiento._ejecutada_en_la_misma_hora).
        if s.salida is None:
            return "arriba primero, la venta no llegó", None
        return (f"arriba primero, venta ejecutada: "
                f"{'stop' if s.motivo_cierre == 'stop tras anular' else 'cerrada al aviso'}",
                s.r)
    return f"sin resolver ({s.estado.value})", None


def main(argv: Optional[list[str]] = None) -> int:
    from .config import cargar_configuracion
    from .datos.dukascopy import ProveedorDukascopy
    from .dominio.mercado import hora_mercado
    from .historico import _por_dia_de_sesion
    from .seguimiento import deslizamiento_de, horas_ambiguas
    from .sesiones import construir_plan
    from .spread import spread_de

    cfg = cargar_configuracion()
    c = cfg.ruptura
    cache = Path.home() / ".cache" / "oro" / "dukascopy_m1"
    hasta = dt.date.today().replace(day=1) - dt.timedelta(days=1)
    df = ProveedorDukascopy().rango(dt.date(2006, 1, 1), hasta)
    print(f"{len(df)} velas H1 hasta {hasta}", flush=True)

    filas = []
    for dia, velas in _por_dia_de_sesion(df):
        horas = [hora_mercado(t.to_pydatetime()) for t in velas.index]
        antes = velas[[h < c.sesion_desde_et for h in horas]]
        if antes.empty:
            continue
        res = construir_plan(antes, cfg, ahora=antes.index[-1].to_pydatetime())
        if not res.hay_plan or res.plan.dia != dia:
            continue
        plan = res.plan
        ambiguas = horas_ambiguas(plan, velas)
        if not ambiguas:
            continue
        cache_dia: dict = {}

        def minutos(hora, _c=cache_dia):
            d = hora.date()
            if d not in _c:
                _c[d] = velas_minuto_del_dia(d, cache)
            m = _c[d]
            if m is None:
                return None
            t = m[(m.index >= hora) & (m.index < hora + dt.timedelta(hours=1))]
            return t if len(t) else None

        caso, r = resolver(plan, velas, minutos)
        coste = (spread_de(dia.year) + deslizamiento_de(plan, cfg)) / plan.rango.amplitud
        filas.append({"dia": dia.isoformat(), "caso": caso,
                      "empleo": plan.dia_de_empleo,
                      "r_bruto": None if r is None else round(r, 3),
                      "r_neto": None if r is None else round(r - coste, 3)})
        print(json.dumps(filas[-1], ensure_ascii=False), flush=True)
        time.sleep(0.3)

    from collections import Counter, defaultdict
    print("\nRESUMEN")
    print(Counter(f["caso"] for f in filas))
    por = defaultdict(list)
    for f in filas:
        if f["r_neto"] is not None:
            por["empleo" if f["empleo"] else "resto"].append(f["r_neto"])
    for k, v in por.items():
        print(f"  {k}: n={len(v)} media {sum(v) / len(v):+.3f} R suma {sum(v):+.1f} R")
    return 0


if __name__ == "__main__":
    sys.exit(main())
