"""Días en que sale el dato de empleo de EE. UU. (NFP), 8:30 de Nueva York.

POR QUÉ IMPORTA, MEDIDO
-----------------------
El informe de empleo se publica a las 8:30 ET: dentro de la ventana en que
puede saltar la orden (8-10 ET). En esos días la rotura del rango de Londres no
es una rotura cualquiera, es el mercado reaccionando al dato, y sigue en la
dirección en que sale — en las DOS direcciones.

Medido sobre 21 años con el RELLENO REAL de cada operación, sacado tick a tick
de Dukascopy (con velas horarias la simulación supone un relleno exacto en el
nivel; a las 8:30 el precio lo atraviesa de golpe):

    días de empleo        n      R/op       t    1ª mitad   2ª mitad
    venta                83   +0.5646    2.83     +0.533     +0.594
    compra               76   +0.7947    4.01     +0.827     +0.764
    las dos             159   +0.6746    4.79   19 años positivos de 21

    resto de días      2048   +0.0444    1.72    (solo venta)

Quitando los 10 mejores días de empleo sigue en +0.3503 (t = 3.32): no lo
sostienen unos pocos días extraordinarios. La compra se midió con un spread
entero de más, por si dispararla con el ask adelanta falsas rupturas que la
simulación no ve.

El deslizamiento real a esa hora: mediana 0,10 $ (el dato no siempre mueve en
el primer segundo), media 1,31 $, y un día extremo 34,55 $. El correo lo avisa.

Hasta octubre de 2026 este efecto estaba documentado y DESCARTADO: una sesión
anterior lo vio con dos órdenes (+0.5315 R, t = 4.47) y lo dio por perdido en
el deslizamiento, suponiendo 2 $ sin poder medirlo. Con ticks, la mediana real
es 0,10 $.

CÓMO SE CALCULA LA FECHA
------------------------
La web del BLS no responde desde el entorno de desarrollo (403), así que la
fecha se calcula con la regla que usa el propio BLS: el informe sale el TERCER
VIERNES después de la semana (domingo a sábado) que contiene el día 12 del mes
de referencia. Comprobado contra 9 publicaciones reales: acierta 8, y la que
falla es la excepción de enero — cuando la regla cae el 1-4 de enero, el BLS lo
retrasa una semana por las fiestas (pasó en 2015 y en 2020). Con esa excepción
añadida, acierta las 9.

Lo que la regla NO puede saber son los retrasos por cierre del Gobierno
federal. Para eso está el calendario de FRED (ver más abajo), que se usa cuando
hay clave.
"""

from __future__ import annotations

import datetime as dt


def dia_de_empleo(anio: int, mes: int) -> dt.date:
    """Fecha de publicación del informe de empleo del mes de referencia dado.

    El informe de MARZO sale en abril: ``dia_de_empleo(2026, 3)`` → 3-abr-2026.
    """
    doce = dt.date(anio, mes, 12)
    # Sábado que cierra la semana del 12 (si el 12 es sábado, es ese mismo día).
    sabado = doce + dt.timedelta(days=(5 - doce.weekday()) % 7)
    # Primer viernes DESPUÉS de ese sábado, y dos semanas más: el tercero.
    viernes = sabado + dt.timedelta(days=(4 - sabado.weekday()) % 7 or 7)
    publicacion = viernes + dt.timedelta(weeks=2)
    # Excepción de enero: si cae el 1-3, se retrasa una semana por las fiestas.
    # (El día 4 NO: en 2008, 2013 y 2019 salió el 4 de enero. La primera
    # versión decía 1-4 y fallaba esos tres años.)
    if publicacion.month == 1 and publicacion.day <= 3:
        publicacion += dt.timedelta(weeks=1)
    # Festivo de la independencia: si cae el 3 o el 4 de julio (viernes
    # festivo o puente), se adelanta al jueves. Pasó en 2008, 2009, 2014, 2015,
    # 2020, 2025 y 2026.
    if publicacion.month == 7 and publicacion.day in (3, 4):
        publicacion -= dt.timedelta(days=1)
    return publicacion


def _por_regla(fecha: dt.date) -> bool:
    for delta in (1, 0):
        anio, mes = fecha.year, fecha.month - delta
        if mes == 0:
            anio, mes = anio - 1, 12
        if dia_de_empleo(anio, mes) == fecha:
            return True
    return False


# ---------------------------------------------------------------------------
# El calendario REAL, de FRED
# ---------------------------------------------------------------------------
# Comprobada contra el calendario de FRED (publicación 50, "Employment
# Situation"), 2006-2026, la regla acierta 246 de 251 fechas. Las 5 que falla
# son TODAS retrasos por cierre del Gobierno federal (22-oct y 8-nov de 2013,
# 20-nov y 16-dic de 2025, 11-feb de 2026), que ninguna regla puede prever.
#
# Así que con clave de FRED (secreto ORO_FRED_CLAVE) se usa su calendario, y la
# regla queda de respaldo si FRED no responde. FRED mete en esa publicación
# también algunas revisiones (p. ej. la anual de agosto); se filtran quedándose
# con la PRIMERA fecha de cada mes, que es siempre la del informe.
_FRED = "https://api.stlouisfed.org/fred/release/dates"
_cache: dict = {}


def fechas_fred(clave: str, tiempo_espera: int = 20) -> set:
    """Las fechas del informe de empleo según FRED. Vacío si no responde."""
    if clave in _cache:
        return _cache[clave]
    import requests

    fechas: set = set()
    try:
        r = requests.get(_FRED, timeout=tiempo_espera, params={
            "release_id": 50, "api_key": clave, "file_type": "json",
            "realtime_start": "2005-01-01", "realtime_end": "2030-12-31",
            "include_release_dates_with_no_data": "true",
            "limit": 1000, "sort_order": "asc"})
        if r.status_code == 200:
            primera: dict = {}
            for x in r.json().get("release_dates", []):
                f = dt.date.fromisoformat(x["date"])
                if (f.year, f.month) not in primera or f < primera[(f.year, f.month)]:
                    primera[(f.year, f.month)] = f
            fechas = set(primera.values())
    except Exception:  # noqa: BLE001 — sin FRED, la regla.
        fechas = set()
    _cache[clave] = fechas
    return fechas


def es_dia_de_empleo(fecha: dt.date) -> bool:
    """¿Sale hoy el informe de empleo de EE. UU.?

    Con ORO_FRED_CLAVE, según el calendario real de FRED (que sabe de los
    cierres del Gobierno). Sin clave, o si FRED no responde, por la regla.
    """
    from . import entorno

    clave = entorno.texto("ORO_FRED_CLAVE")
    if clave:
        fechas = fechas_fred(clave)
        # Solo se fía de FRED si cubre esa fecha: un calendario vacío o que no
        # llega hasta hoy no puede decir que hoy no hay dato.
        if fechas and max(fechas) >= fecha:
            return fecha in fechas
    return _por_regla(fecha)
