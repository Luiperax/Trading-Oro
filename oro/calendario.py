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

Lo que NO puede saber: los retrasos por cierre del Gobierno federal (octubre de
2013, octubre-noviembre de 2025). Esos días el sistema pondrá dos órdenes sin
que salga el dato. El coste es pequeño —una compra en un día normal pierde de
media 0,06 R— y no hay forma de anticiparlo sin una fuente de calendario.
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
    # Excepción de enero: si cae el 1-4, se retrasa una semana por las fiestas.
    if publicacion.month == 1 and publicacion.day <= 4:
        publicacion += dt.timedelta(weeks=1)
    return publicacion


def es_dia_de_empleo(fecha: dt.date) -> bool:
    """¿Sale hoy el informe de empleo de EE. UU.?

    Basta mirar el mes anterior al de la fecha y el de la propia fecha: la
    publicación cae siempre a principios del mes siguiente al de referencia.
    """
    for delta in (1, 0):
        anio, mes = fecha.year, fecha.month - delta
        if mes == 0:
            anio, mes = anio - 1, 12
        if dia_de_empleo(anio, mes) == fecha:
            return True
    return False
