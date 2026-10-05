"""El árbitro: comprobar nuestro precio contra el patrón oficial del oro.

QUÉ PROBLEMA RESUELVE
---------------------
Durante semanas el sistema calculó los niveles sobre ``GC=F`` —el futuro de
COMEX— mientras el correo decía «busca XAU/USD (oro)», que es el contado. Son
43 $ de diferencia y nadie se enteró, porque el sistema solo veía un feed y un
feed solo no puede contradecirse a sí mismo.

El World Gold Council publica el **LBMA Gold Price**: el precio de referencia
oficial del oro al contado, fijado en subasta dos veces al día. Es diario, así
que no sirve para operar. Sirve para lo que hace falta aquí: decir si nuestro
precio es el del oro o es el de otra cosa.

POR QUÉ SE COMPARA UNA MEDIA Y NO UN DÍA
-----------------------------------------
Un solo día no distingue nada. El fix puede ser de hace tres días y el oro se
mueve 40 $ en una sesión normal, así que la deriva tapa por completo una prima
de 43 $. Lo que sí la delata es la MEDIA sobre varios días: la deriva cambia de
signo y se cancela, la prima no.

Medido el 5-oct-2026, comparando a la misma hora (la vela de las 09:00 UTC, que
contiene la subasta AM de las 10:30 de Londres):

    Dukascopy contado  vs fix:   +3,34 $ de media  (|dif| mediana 3,99 $, n=21)
    Yahoo GC=F futuro  vs fix:  +43,08 $ de media  (|dif| mediana 44,62 $, n=16)

Los 3-4 $ del contado son la deriva de los 30 minutos que van de la subasta al
cierre de la vela. Los 43 $ del futuro son la prima del contrato.

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

API = "https://fsapi.gold.org/api/goldprice/v13/chart/main"

# La subasta AM de la LBMA es a las 10:30 de Londres. La vela de las 09:00 UTC
# la contiene en horario de verano británico y la de las 10:00 en invierno; se
# usan las dos y se queda la que exista.
HORAS_DEL_FIX = (9, 10)

# Separación media máxima tolerada, en dólares. El contado dio 3,34 y el futuro
# 43,08: con 15 se distinguen de sobra y queda holgura para la deriva de los 30
# minutos. No es un detector de precios raros, es un detector de "esto no es oro
# al contado".
TOLERANCIA = 15.0

# Días mínimos para que la media signifique algo. Con menos, la deriva de un
# solo día puede más que la prima que se busca.
MINIMO_DIAS = 5


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


def comprobar_marco(df, tolerancia: float = TOLERANCIA,
                    minimo_dias: int = MINIMO_DIAS) -> tuple[bool, str]:
    """¿Las velas que usa el sistema son oro al contado?

    ``df`` es el histórico de velas horarias con índice UTC. Se compara el
    cierre de la vela que contiene la subasta con el fix de ese mismo día.

    Devuelve ``True`` cuando no hay con qué comparar: una web caída o un
    histórico corto no pueden dejar al sistema sin mandar el plan. Lo que sí
    tiene que pararlo es una referencia que se lee bien y NO cuadra.
    """
    fixes = serie_fix()
    if not fixes:
        return True, ("No se pudo leer el LBMA Gold Price para contrastar el "
                      "precio. Se sigue adelante, pero esta vez sin árbitro.")

    idx = df.index
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize(dt.timezone.utc)
    difs = []
    for momento, cierre in zip(idx, df["close"]):
        if momento.hour not in HORAS_DEL_FIX:
            continue
        fix = fixes.get(momento.date())
        if fix:
            difs.append(float(cierre) - fix)

    if len(difs) < minimo_dias:
        return True, (f"Solo {len(difs)} día(s) con fix para comparar (hacen "
                      f"falta {minimo_dias}). Sin árbitro esta vez.")

    media = sum(difs) / len(difs)
    if abs(media) <= tolerancia:
        return True, (f"Contrastado con el LBMA Gold Price sobre {len(difs)} "
                      f"días: {media:+.2f} $ de media. Es oro al contado.")
    pista = ""
    if 25.0 <= media <= 70.0:
        pista = (" Una prima de ese tamaño es la del FUTURO de COMEX (GC=F) "
                 "sobre el contado: mira ORO_FUENTE_VIVO y ORO_SIMBOLO_VIVO.")
    return False, (
        f"EL PRECIO NO ES ORO AL CONTADO. Contra el LBMA Gold Price sobre "
        f"{len(difs)} días, el sistema va {media:+.2f} $ de media, con una "
        f"tolerancia de {tolerancia:.0f} $.{pista} Mandar el plan así daría "
        f"unos niveles que en la pantalla del bróker no existen: las órdenes "
        f"se ejecutarían al instante en vez de esperar a la ruptura.")
