"""El árbitro: comprobar nuestro precio contra el patrón oficial del oro.

QUÉ PROBLEMA RESUELVE
---------------------
Durante semanas el sistema calculó los niveles sobre ``GC=F`` —el futuro de
COMEX— mientras el correo decía «busca XAU/USD (oro)», que es el contado. Son
43 $ de diferencia y nadie se enteró, porque el sistema solo veía un feed y un
feed solo no puede contradecirse a sí mismo.

El World Gold Council publica el **LBMA Gold Price**: el precio de referencia
oficial del oro al contado, fijado en subasta a las 10:30 de Londres. Es
diario, así que no sirve para operar. Sirve para lo que hace falta aquí: decir
si nuestro precio es el del oro o es el de otra cosa.

EL CRITERIO: ¿CAE EL FIX DENTRO DE LA VELA EN QUE SE SUBASTÓ?
--------------------------------------------------------------
La subasta se hace a precios que se están negociando en ese momento, así que
el fix tiene que caer dentro del máximo y el mínimo de la vela horaria que
contiene las 10:30 de Londres. Medido el 5-oct-2026:

    Dukascopy contado:  el fix cae DENTRO de la vela 32 de 32 días
    Yahoo GC=F futuro:  el fix cae DENTRO de la vela  0 de 16 días
                        (fuera por 35,66 $ de media)

Separación perfecta, y con UN solo día ya decide. Eso importa: la primera
versión comparaba una media de 5 días contra el marco que carga el plan, que
son 48 horas. En producción no habría tenido nunca 5 días y no se habría
activado jamás. Ahora pide ella misma las velas exactas que necesita.

(Comparar el cierre contra el fix, que fue lo primero que se probó, mezcla la
prima con lo que se mueve el oro entre la subasta y el cierre de la vela.)

CÓMO SE USA
-----------
Antes de mandar el plan. Si el precio del que salen los niveles no es oro al
contado, es mejor NO mandar nada que mandar unas órdenes que en la pantalla del
bróker no existen: se ejecutarían al instante en vez de esperar a la ruptura,
que es el fallo más caro que puede cometer esta estrategia.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional
from zoneinfo import ZoneInfo

API = "https://fsapi.gold.org/api/goldprice/v13/chart/main"
_LONDRES = ZoneInfo("Europe/London")

# Holgura alrededor de la vela, en dólares, por redondeos y por la diferencia
# entre el bid (con el que se arman las velas) y el precio de la subasta. El
# futuro quedó fuera por 35,66 $ de media: 3 $ no lo tapa ni de lejos.
HOLGURA = 3.0

# Cuántos fixes recientes se comprueban. Con uno ya separa; se piden unos pocos
# por si alguno cae en un hueco del proveedor.
DIAS = 3


def serie_fix(tiempo_espera: int = 20) -> dict[dt.date, float]:
    """El LBMA Gold Price AM en dólares, por día. Vacío si no se puede leer."""
    import requests

    try:
        r = requests.get(API, timeout=tiempo_espera, headers={
            "User-Agent": "Mozilla/5.0 oro/0.1",
            "Referer": "https://www.gold.org/goldhub/data/gold-prices"})
        if r.status_code != 200:
            return {}
        serie = r.json().get("chartData", {}).get("lbma_am_usd") or []
    except Exception:  # noqa: BLE001 — sin referencia se sigue, no se rompe.
        return {}
    return {dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).date(): float(v)
            for t, v in serie if v}


def hora_de_la_subasta(dia: dt.date) -> dt.datetime:
    """La hora UTC (en punto) de la vela que contiene las 10:30 de Londres.

    Es las 09:00 UTC con el horario de verano británico y las 10:00 en
    invierno. Se calcula con la zona horaria, no a mano, por la misma razón que
    el resto del sistema: dos cambios de hora al año sin que nadie lo note.
    """
    t = dt.datetime(dia.year, dia.month, dia.day, 10, 30, tzinfo=_LONDRES)
    return t.astimezone(dt.timezone.utc).replace(minute=0)


def _vela(proveedor, hora: dt.datetime, cache: dict) -> Optional[tuple[float, float]]:
    """(mínimo, máximo) de esa vela según el proveedor, o None."""
    if hasattr(proveedor, "vela_de"):
        v = proveedor.vela_de(hora)          # Dukascopy: una petición por hora.
        return (v["low"], v["high"]) if v else None
    if "df" not in cache:                    # Yahoo y demás: una sola petición.
        try:
            df = proveedor.historico(200)
        except Exception:  # noqa: BLE001
            cache["df"] = None
            return None
        idx = df.index if getattr(df.index, "tz", None) else df.index.tz_localize("UTC")
        cache["df"] = df.set_axis(idx)
    df = cache["df"]
    if df is None:
        return None
    import pandas as pd

    clave = pd.Timestamp(hora)
    if clave not in df.index:
        return None
    fila = df.loc[clave]
    return float(fila["low"]), float(fila["high"])


def comprobar_fuente(proveedor, dias: int = DIAS,
                     holgura: float = HOLGURA) -> tuple[bool, str]:
    """¿El proveedor da oro al contado? Devuelve (vale, explicación).

    Devuelve ``True`` cuando no hay con qué comparar: una web caída o un hueco
    del proveedor no pueden dejar al sistema sin mandar el plan. Lo que sí tiene
    que pararlo es una referencia que se lee bien y NO cuadra.
    """
    fixes = serie_fix()
    if not fixes:
        return True, ("No se pudo leer el LBMA Gold Price para contrastar el "
                      "precio. Se sigue adelante, pero esta vez sin árbitro.")

    cache: dict = {}
    dentro, fuera, distancias = 0, 0, []
    for dia in sorted(fixes)[-dias * 3:][::-1]:
        if dentro + fuera >= dias:
            break
        fix = fixes[dia]
        v = _vela(proveedor, hora_de_la_subasta(dia), cache)
        if v is None:
            continue
        bajo, alto = v
        if bajo - holgura <= fix <= alto + holgura:
            dentro += 1
        else:
            fuera += 1
            distancias.append(fix - alto if fix > alto else fix - bajo)

    if dentro + fuera == 0:
        return True, ("No hubo ninguna vela del proveedor a la hora de las "
                      "subastas recientes. Sin árbitro esta vez.")
    if fuera <= dentro:
        return True, (f"Contrastado con el LBMA Gold Price: el fix cae dentro "
                      f"de la vela de la subasta {dentro} de {dentro + fuera} "
                      f"días. Es oro al contado.")
    media = sum(distancias) / len(distancias)
    pista = ""
    if -70.0 <= media <= -20.0:
        pista = (" El fix queda POR DEBAJO de nuestras velas en esa cantidad: "
                 "es la prima del FUTURO de COMEX (GC=F) sobre el contado. Mira "
                 "ORO_FUENTE_VIVO y ORO_SIMBOLO_VIVO.")
    return False, (
        f"EL PRECIO NO ES ORO AL CONTADO. El LBMA Gold Price cae fuera de la "
        f"vela en que se subastó {fuera} de {dentro + fuera} días, a "
        f"{abs(media):.2f} $ de media.{pista} Mandar el plan así daría unos "
        f"niveles que en la pantalla del bróker no existen: las órdenes se "
        f"ejecutarían al instante en vez de esperar a la ruptura.")
