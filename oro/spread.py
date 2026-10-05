"""Mide el spread REAL de XAU/USD desde los ticks de Dukascopy.

POR QUÉ ESTE MÓDULO EXISTE
--------------------------
``ConfiguracionRiesgo.coste_operacion`` valía 0.30 $ porque alguien lo puso. El
coste es la restricción que decide si una estrategia de este proyecto es viable
o no —está en cada R que el sistema registra y en cada conclusión de la
documentación— así que un coste inventado invalida todo lo demás.

Dukascopy publica ficheros de ticks por hora con **bid y ask reales**, que es
algo que ninguna otra fuente gratuita da. Medido con esto el 5-oct-2026 sobre
3.189.713 ticks de 20 días, el spread real resultó ser 0.60 $ en la ventana en
que salta la orden y 0.68 $ al cierre de la sesión: el doble de lo que se
asumía.

El número envejece —el spread sube con el precio del oro: 0.29 $ en 2016, 0.63 $
en 2026— así que esto se vuelve a ejecutar de vez en cuando en vez de confiar en
una constante escrita hace meses.

Uso:
    python -m oro.spread                 # últimos 10 días de mercado
    python -m oro.spread --dias 20       # más muestra
    python -m oro.spread --horas 12,13   # solo la ventana de disparo
"""

from __future__ import annotations

import datetime as dt
import lzma
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

_REGISTRO = struct.Struct(">3I2f")
URL = ("https://datafeed.dukascopy.com/datafeed/{sim}/{anio}/{mes:02d}/{dia:02d}/"
       "{hora:02d}h_ticks.bi5")

# Las horas que de verdad importan, en UTC: la ventana en que puede saltar la
# orden (8-10 de Nueva York) y el cierre de la sesión (15-16 ET). Medir el
# spread a las 3 de la mañana no dice nada sobre lo que cuesta esta estrategia.
HORAS_POR_DEFECTO = (12, 13, 14, 19, 20)


def _ticks(simbolo: str, t: dt.datetime, intentos: int = 5) -> Optional[list[float]]:
    """Los spreads (ask-bid) de esa hora, o ``None`` si no hay mercado."""
    import requests

    url = URL.format(sim=simbolo, anio=t.year, mes=t.month - 1, dia=t.day,
                     hora=t.hour)
    for i in range(intentos):
        try:
            r = requests.get(url, timeout=30,
                             headers={"User-Agent": "Mozilla/5.0 oro/0.1"})
            if r.status_code == 404:
                return None
            if r.status_code == 200 and r.content:
                datos = lzma.LZMADecompressor().decompress(r.content)
                n = len(datos) // _REGISTRO.size
                if n == 0:
                    return None
                return [(_REGISTRO.unpack_from(datos, j * _REGISTRO.size)[1]
                         - _REGISTRO.unpack_from(datos, j * _REGISTRO.size)[2]) / 1000.0
                        for j in range(n)]
        except Exception:  # noqa: BLE001 — servidor intermitente, se reintenta.
            pass
        time.sleep(min(2 ** i, 6))
    return None


def medir(dias: int = 10, horas: tuple[int, ...] = HORAS_POR_DEFECTO,
          simbolo: str = "XAUUSD", hilos: int = 6) -> dict:
    """Devuelve el spread por hora y el global, en dólares por onza."""
    import numpy as np

    hoy = dt.datetime.now(dt.timezone.utc).date()
    fechas, d = [], hoy - dt.timedelta(days=1)
    while len(fechas) < dias:
        if d.weekday() < 5:          # el mercado de oro no cotiza el finde.
            fechas.append(d)
        d -= dt.timedelta(days=1)

    tareas = [dt.datetime(f.year, f.month, f.day, h, tzinfo=dt.timezone.utc)
              for f in fechas for h in horas]
    por_hora: dict[int, list[float]] = {h: [] for h in horas}
    total = 0
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        for t, s in zip(tareas, ex.map(lambda x: _ticks(simbolo, x), tareas)):
            if not s:
                continue
            por_hora[t.hour].append(float(np.median(s)))
            total += len(s)

    resumen = {h: float(np.median(v)) for h, v in por_hora.items() if v}
    todos = [x for v in por_hora.values() for x in v]
    return {
        "por_hora": resumen,
        "mediana": float(np.median(todos)) if todos else float("nan"),
        "ticks": total,
        "horas_medidas": len(todos),
        "dias": dias,
    }


# ---------------------------------------------------------------------------
# El spread medido, año por año
# ---------------------------------------------------------------------------
# Muestreado el 5-oct-2026 con este mismo módulo: 6 días por año en las horas en
# que la estrategia opera (12, 13 y 19 UTC = 8, 9 y 15 de Nueva York).
#
# Hace falta porque la alternativa —un coste fijo para 21 años— es falsa en los
# dos extremos: cobrarle a 2016 el spread de 2026 hunde el resultado histórico
# (+0.0680 R/op en vez de +0.1029), y cobrarle a 2026 el de 2016 lo infla.
#
# En dólares el spread sube con el oro; en puntos básicos no ha parado de
# mejorar (6.9 pb en 2007, 1.35 pb en 2026).
SPREAD_POR_ANIO = {
    2007: 0.460,
    2008: 0.470,
    2009: 0.462,
    2010: 0.554,
    2011: 0.454,
    2013: 0.289,
    2014: 0.301,
    2015: 0.304,
    2016: 0.295,
    2018: 0.221,
    2019: 0.287,
    2020: 0.387,
    2021: 0.334,
    2022: 0.340,
    2024: 0.373,
    2025: 0.550,
    2026: 0.630,
}


def spread_de(anio: int) -> float:
    """El spread medido de ese año. Interpola los que no se muestrearon.

    Para un año futuro devuelve el del último medido: suponer que el spread
    seguirá bajando sería optimismo sin dato que lo sostenga.
    """
    if anio in SPREAD_POR_ANIO:
        return SPREAD_POR_ANIO[anio]
    antes = [a for a in SPREAD_POR_ANIO if a < anio]
    despues = [a for a in SPREAD_POR_ANIO if a > anio]
    if antes and despues:
        return (SPREAD_POR_ANIO[max(antes)] + SPREAD_POR_ANIO[min(despues)]) / 2
    return SPREAD_POR_ANIO[max(antes)] if antes else SPREAD_POR_ANIO[min(despues)]


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dias = 10
    horas = HORAS_POR_DEFECTO
    for i, a in enumerate(argv):
        if a == "--dias" and i + 1 < len(argv):
            dias = int(argv[i + 1])
        if a == "--horas" and i + 1 < len(argv):
            horas = tuple(int(x) for x in argv[i + 1].split(","))

    from .config import cargar_configuracion

    cfg = cargar_configuracion()
    print(f"Midiendo el spread real de XAU/USD con los ticks de Dukascopy "
          f"({dias} días de mercado, horas UTC {list(horas)})…")
    r = medir(dias=dias, horas=horas, simbolo=cfg.simbolo)
    if not r["por_hora"]:
        print("No se pudo medir: el servidor no devolvió ticks.")
        return 1

    print()
    print("%8s %8s %12s" % ("hora UTC", "hora ET", "spread $"))
    for h in sorted(r["por_hora"]):
        # ET es UTC-4 en horario de verano y UTC-5 en invierno; para una tabla
        # orientativa basta con restar 4 o 5 según el mes.
        et = (h - (4 if 3 <= dt.date.today().month <= 10 else 5)) % 24
        print("%8d %8d %12.3f" % (h, et, r["por_hora"][h]))

    actual = cfg.riesgo.coste_operacion
    print()
    print(f"MEDIANA: {r['mediana']:.3f} $ por onza "
          f"({r['ticks']:,} ticks en {r['horas_medidas']} horas)")
    print(f"Configurado ahora: {actual:.2f} $ (ORO_COSTE_OPERACION)")
    dif = r["mediana"] - actual
    if abs(dif) < 0.05:
        print("→ La configuración coincide con lo medido. No hay que tocar nada.")
    elif dif > 0:
        print(f"→ El coste real es {dif:.2f} $ MAYOR que el configurado. El "
              f"sistema está apuntando sus resultados mejor de lo que son: "
              f"sube ORO_COSTE_OPERACION a {r['mediana']:.2f}.")
    else:
        print(f"→ El coste real es {abs(dif):.2f} $ MENOR que el configurado. "
              f"El sistema se está penalizando de más: baja "
              f"ORO_COSTE_OPERACION a {r['mediana']:.2f}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
