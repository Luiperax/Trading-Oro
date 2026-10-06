"""El correo del plan de ruptura de sesión.

Es distinto del correo de señal y por eso vive aparte: una señal dice «entra
AHORA a este precio», y esto dice «deja preparada esta orden y que el mercado
decida». Quien lo recibe no tiene que decidir nada ni estar delante: se teclea
la orden en el bróker a las 14:00 y se olvida.

CON ``solo_ventas`` (lo medido y lo que va puesto) el correo lleva UNA orden de
venta, no dos. El motivo está en :class:`oro.config.ConfiguracionRuptura`: sobre
21 años, la rotura al alza es un lastre de -7.7 R al año, y la rotura a la baja
que llega DESPUÉS de una rotura al alza vale -0.29 R de media. De ahí el aviso
de cancelar: es la pieza que separa +10.78 R al año de -1.07.

El formato es el mismo del resto de correos —tablas e estilos en línea, que es
lo único que renderiza igual en Gmail, Outlook y el móvil— y comparte la paleta
con :mod:`oro.notificaciones.base`.
"""

from __future__ import annotations

from ..sesiones import OrdenPendiente, PlanRuptura
from ..tiempo import etiqueta_zona, hora_local
from .base import (
    _BORDE,
    _FONDO,
    _FUENTE,
    _MUTED,
    _ORO,
    _ROJO,
    _TARJETA,
    _TEXTO,
    _VERDE,
    _esc,
)


# Cifras medidas sobre 4.064 rupturas de 19,6 años, neto de 0.60 $ y objetivo 3R.
# Se citan literalmente en el correo para que nadie tenga que fiarse de mi palabra.
_R_A_FAVOR = "+0,088"
_R_EN_CONTRA = "+0,013"


# ---- Modo «solo papel» (ver ConfiguracionRuptura.solo_papel) ----
PAPEL_TITULO = "📝 SOLO PAPEL — NO OPERES CON DINERO REAL"
PAPEL_EXPLICACION = (
    "Revisión del 6-oct-2026: el histórico dejaba fuera de las cifras los días "
    "en que, en la misma hora, el precio cruza el techo Y el suelo del rango "
    "(unos 17 al año, y 1 de cada 3 días de empleo por el salto de las 8:30). "
    "Resueltos con velas de un minuto, son pérdidas casi seguras: la venta salta "
    "y en esa misma hora el precio sube hasta el stop. Con esos días contados la "
    "estrategia no tiene ventaja (días de empleo +0,02 R por operación, resto "
    "-0,04). Este plan se manda para seguir midiendo en real, no para operarlo.")


def en_papel() -> bool:
    from ..config import cargar_configuracion

    return cargar_configuracion().ruptura.solo_papel


def riesgo_por_onza(plan: PlanRuptura) -> float:
    """Lo que se pierde por cada onza si salta el stop: el rango entero.

    Es el único dato de riesgo que da el correo. El TAMAÑO de la posición lo
    decide el usuario, así que aquí no se calcula ningún lote ni se avisa de
    ningún mínimo: con este número y su cuenta, quien opera hace su cuenta.
    """
    return plan.rango.amplitud


def hora_cierre(plan: PlanRuptura) -> str:
    """A qué hora hay que cerrar la operación, en la hora del usuario.

    Es la hora del cierre de la estrategia (16:00 de Nueva York), la misma a la
    que el seguimiento manda el aviso de «CIERRA» y la misma con la que está
    medido el histórico. Antes decía las 21:50 —la hora del aviso del motor
    intradía, que está apagado— y el aviso del cierre llegaba a las 22:00: dos
    horas distintas para lo mismo. Las semanas en que Europa y EE. UU. no han
    cambiado aún la hora a la vez, sale sola la hora correcta (las 21:00).
    """
    return hora_local(plan.cierre_forzoso)


def texto_confianza(plan: PlanRuptura) -> str:
    """Qué dice el sesgo asiático, SIN que parezca una predicción.

    El orden de la frase importa: primero lo que NO es, porque es lo que todo
    el mundo asume al leerla, y después lo que sí.
    """
    if en_papel():
        return ("Es el plan de la estrategia tal cual, para comparar con lo que "
                "haga el precio. El motivo de no operarlo está arriba.")
    if plan.dia_de_empleo:
        return ("Hoy sale el dato de empleo de EE. UU. a las 8:30 de Nueva York "
                "y van LAS DOS órdenes. Ese día la rotura no es una rotura "
                "cualquiera: es el mercado reaccionando al dato, y sigue en la "
                "dirección en que sale, en las dos. Medido sobre 161 días de "
                "empleo de 21 años, con el relleno real sacado tick a tick: "
                "+0,64 R por operación (t = 4,58). Son unos 8 días al año y "
                "aportan casi dos tercios del rendimiento anual de la estrategia.")
    if plan.solo_ventas:
        # Con una sola orden no hay nada que elegir, y la pregunta que importa
        # no es «qué lado» sino «por qué solo este».
        return ("Hoy solo va una orden, y a la baja. Medido sobre 21 años con "
                "todos los costes reales (spread y deslizamiento sacados de los "
                "ticks): la estrategia da +0,073 R por operación (t = 2,80; "
                "+0,088 y +0,058 en las dos mitades del histórico). La rotura al "
                "alza no se opera porque resta: solo 4 años a favor de 21.")
    if plan.favorita is None:
        return ("Hoy la sesión asiática ha cerrado casi donde abrió, así que no "
                "aporta nada: trata las dos órdenes como iguales.")
    lado = "COMPRA" if plan.favorita.value == "compra" else "VENTA"
    otro = "VENTA" if lado == "COMPRA" else "COMPRA"
    subio = "subido" if plan.sesgo.cuerpo > 0 else "bajado"
    return (f"Esto NO dice cuál de las dos va a saltar: la asiática acierta el "
            f"lado el 50,0 % de las veces, o sea nada. Lo que dice es qué pasa "
            f"DESPUÉS. La asiática ha {subio} {abs(plan.sesgo.cuerpo):.2f} $, y "
            f"en 19,6 años la ruptura que la acompaña —aquí la {lado}— ha dado "
            f"{_R_A_FAVOR} R por operación, frente a {_R_EN_CONTRA} R cuando "
            f"salta la contraria. Si hoy salta la {otro}, no es que el sistema "
            f"se haya equivocado: es la mitad de los días.")


def aviso_confianza(plan: PlanRuptura | None = None) -> str:
    """El límite de lo anterior, sin el cual la frase promete de más."""
    if en_papel():
        return ("Las cifras que se daban antes (+0,073 R por operación, +7,8 R "
                "al año) no contaban esos días y ya no valen.")
    if plan is not None and plan.dia_de_empleo:
        return ("Cuidado con las 8:30: el precio salta de golpe y la orden se "
                "llena en el primer precio que cruza el nivel, no en el nivel. "
                "Medido en 83 días de empleo: mediana 0,10 $ peor, media 1,31 $, "
                "y un día 34,55 $. Ya está descontado en la cifra de arriba. "
                "Usa una orden OCO si tu bróker la tiene: a esa hora pueden "
                "saltar las dos en segundos y no da tiempo a cancelar a mano.")
    if plan is not None and plan.solo_ventas:
        return ("El límite: son +7,8 R al año, unos 117 € con 0,5 % de riesgo "
                "sobre 3.000 €, y 6 de los 21 años fueron en pérdida (el peor, "
                "-18,7 R). Casi dos tercios salen de los ~8 días de empleo al "
                "año; el resto de días la venta da +0,03 R, que no se distingue "
                "de cero. Espera rachas negativas de 45 R.")
    return ("De dónde sale: se probaron 8 condiciones distintas conocidas a las "
            "8:00 (dólar, medias de 5 y 20 días, dónde cierra Londres, anchura "
            "del rango, cierre de ayer) combinadas en un modelo entrenado con "
            "años anteriores. NO funcionó fuera de muestra. La asiática sola es "
            "lo único que aguanta: 14 de 20 años a favor, t = 2,31. Aun así no "
            "supera la corrección estadística estricta, así que deja las DOS "
            "órdenes puestas: el sistema no elige lado, elige el mercado.")


def pasos_plan(plan: PlanRuptura) -> list[str]:
    """Los pasos exactos, en el orden en que se teclean en el bróker."""
    c, v = plan.compra, plan.venta
    if plan.dia_de_empleo:
        return [
            "Abre tu bróker y busca XAU/USD (oro). Hoy vas a dejar DOS órdenes "
            "pendientes del tamaño que decidas: sale el dato de empleo de EE. UU.",
            f"COMPRA tipo «BUY STOP» en {c.entrada:.2f}, con stop loss en "
            f"{c.stop:.2f} y take profit en {c.objetivo:.2f}.",
            f"VENTA tipo «SELL STOP» en {v.entrada:.2f}, con stop loss en "
            f"{v.stop:.2f} y take profit en {v.objetivo:.2f}.",
            "Ponlas como OCO (una cancela la otra) si tu bróker lo permite. A "
            "las 8:30 de Nueva York el precio puede pasar por las dos en "
            "segundos y no da tiempo a cancelar a mano.",
            f"Si a las {hora_local(plan.valido_hasta)} no ha saltado ninguna, "
            f"cancela las dos. Hoy no hay operación.",
            f"A las {hora_cierre(plan)} CIERRA LA QUE ESTÉ ABIERTA, gane o "
            f"pierda. No se queda de un día para otro.",
            f"Cuando te dé {plan.rango.amplitud:.2f} $ de beneficio (1R), mueve "
            f"el stop al precio de entrada. Desde ahí ya no puede perder.",
        ]
    if plan.solo_ventas:
        return [
            "Abre tu bróker y busca XAU/USD (oro). Vas a dejar UNA orden "
            "pendiente del tamaño que decidas. No se abre nada todavía.",
            f"VENTA tipo «SELL STOP» en {v.entrada:.2f}, con stop loss en "
            f"{v.stop:.2f} y take profit en {v.objetivo:.2f}.",
            "Ese take profit está lejos a propósito: es una red de seguridad "
            "para el día en que el precio se desploma y no estás mirando, no la "
            "salida. Salta 1 o 2 veces al año. La salida de verdad es cerrar a "
            "mano al final de la sesión.",
            f"IMPORTANTE — si el precio sube por encima de {c.entrada:.2f} "
            f"(el techo del rango) antes de que salte tu venta, CANCÉLALA. Hoy "
            f"ya no vale. Te mandaré un correo en cuanto pase, pero si puedes "
            f"poner una alerta en {c.entrada:.2f}, mejor. Esto no es un detalle: "
            f"la misma venta, cuando llega después de que el rango se haya roto "
            f"al alza, pierde 0,29 R de media sobre 869 días medidos, y dejarla "
            f"puesta borra toda la ventaja de la estrategia.",
            f"Si a las {hora_local(plan.valido_hasta)} no ha saltado, cancélala. "
            f"Hoy no hay operación: lo que se rompe más tarde ya no es la "
            f"ruptura de la mañana y está medido que no compensa.",
            f"A las {hora_cierre(plan)} CIÉRRALA A MERCADO, gane o pierda. Esta "
            f"es la salida, y no se queda de un día para otro.",
            f"Cuando la operación te dé {plan.rango.amplitud:.2f} $ de beneficio "
            f"(1R), mueve el stop al precio de entrada. Desde ahí ya no puede "
            f"perder. Es parte de la estrategia medida, no un extra.",
        ]
    return [
        "Abre tu bróker y busca XAU/USD (oro). Vas a dejar DOS órdenes "
        "pendientes del tamaño que decidas. No se abre nada todavía.",
        f"Orden 1 — COMPRA tipo «BUY STOP» en {c.entrada:.2f}, "
        f"con stop loss en {c.stop:.2f} y take profit en {c.objetivo:.2f}."
        + (" ← si salta esta, históricamente rinde más" if plan.es_favorita(c) else ""),
        f"Orden 2 — VENTA tipo «SELL STOP» en {v.entrada:.2f}, "
        f"con stop loss en {v.stop:.2f} y take profit en {v.objetivo:.2f}."
        + (" ← si salta esta, históricamente rinde más" if plan.es_favorita(v) else ""),
        "Ese take profit está lejos a propósito: es una red de seguridad para "
        "el día en que el precio se dispara y no estás mirando, no la salida. "
        "Salta 1 o 2 veces al año. La salida de verdad es cerrar a mano al "
        "final de la sesión.",
        "En cuanto una de las dos se abra, CANCELA la otra. Si tu bróker tiene "
        "órdenes «OCO» (una cancela la otra), úsalo y se encarga solo.",
        f"Si a las {hora_local(plan.valido_hasta)} no ha saltado ninguna, cancela "
        f"las dos. Hoy no hay operación: lo que se rompe más tarde ya no es la "
        f"ruptura de la mañana y está medido que no compensa.",
        f"A las {hora_cierre(plan)} CIÉRRALA A MERCADO, gane o pierda. Esta es "
        f"la salida: cerrar al final de la sesión rinde +0,069 R por operación "
        f"frente a +0,050 con un objetivo cercano. Y no se queda de un día para "
        f"otro.",
        f"OPCIONAL, si puedes mirar el móvil una vez: cuando la operación te dé "
        f"{plan.rango.amplitud:.2f} $ de beneficio (1R), mueve el stop al precio "
        f"de entrada. Desde ahí ya no puede perder. Medido: sube la ventaja de "
        f"+0,069 a +0,077 R por operación.",
    ]


def mensaje_de_plan(plan: PlanRuptura) -> str:
    """Versión en texto plano (respaldo y clientes sin HTML)."""
    zona = etiqueta_zona(plan.valido_hasta)
    lineas = ([PAPEL_TITULO, "", PAPEL_EXPLICACION, ""] if en_papel() else []) + [
        "⚡ PLAN DEL DÍA — XAU/USD · ruptura del rango de la mañana",
        "",
        f"Rango de la mañana de Londres: {plan.rango.bajo:.2f} — {plan.rango.alto:.2f}",
        f"Amplitud: {plan.rango.amplitud:.2f} $ por onza  (esto es 1R, tu riesgo)",
        "",
        f"Sesión asiática: {plan.sesgo.cuerpo:+.2f} $ sobre un rango de "
        f"{plan.sesgo.rango:.2f} $",
        "",
    ]
    if plan.solo_ventas:
        lineas += [
            "UNA ORDEN PENDIENTE:",
            f"  VENTA  (sell stop) en {plan.venta.entrada:.2f}   "
            f"stop {plan.venta.stop:.2f}   objetivo {plan.venta.objetivo:.2f}",
            "",
            f"ANULA LA ORDEN si el precio sube de {plan.compra.entrada:.2f} "
            f"antes de que salte.",
        ]
    else:
        lineas += [
            "DOS ÓRDENES PENDIENTES (salta una, cancela la otra):",
            f"  COMPRA (buy stop)  en {plan.compra.entrada:.2f}   "
            f"stop {plan.compra.stop:.2f}   objetivo {plan.compra.objetivo:.2f}"
            f"{'   ◆ LA MEJOR SI SALTA' if plan.es_favorita(plan.compra) else ''}",
            f"  VENTA  (sell stop) en {plan.venta.entrada:.2f}   "
            f"stop {plan.venta.stop:.2f}   objetivo {plan.venta.objetivo:.2f}"
            f"{'   ◆ LA MEJOR SI SALTA' if plan.es_favorita(plan.venta) else ''}",
        ]
    lineas += [
        "",
        ("POR QUÉ ESTE PLAN:" if (plan.solo_ventas or plan.dia_de_empleo)
         else "CUÁL DE LAS DOS ES LA DE FIAR:"),
        f"  {texto_confianza(plan)}",
        f"  {aviso_confianza(plan)}",
        "",
        f"Riesgo si salta el stop: {riesgo_por_onza(plan):.2f} $ por onza.",
    ]
    nota = aviso_instrumento()
    if nota:
        lineas += ["", f"DE DÓNDE SALEN LOS PRECIOS: {nota}"]
    lineas += [
        "",
        f"Válido hasta las {hora_local(plan.valido_hasta)} ({zona}). "
        + ("Después, cancélala." if plan.solo_ventas else "Después, cancela las dos."),
        f"Cierre a mano: {hora_cierre(plan)} ({zona}), gane o pierda.",
        "",
        ("LO QUE HARÍA LA ESTRATEGIA (no lo hagas con dinero real):" if en_papel()
         else "QUÉ HACER, paso a paso:"),
    ]
    lineas += [f"  {i}. {t}" for i, t in enumerate(pasos_plan(plan), 1)]
    lineas += [
        "",
        ("POR QUÉ VA EN PAPEL:" if en_papel()
         else "LO QUE HAY QUE SABER ANTES DE OPERARLA:"),
    ]
    lineas += [f"  • {t}" for t in _hechos_honestos(plan)]
    lineas += [
        "",
        "⚠️ Herramienta de análisis, no asesoramiento financiero.",
    ]
    return "\n".join(lineas)


def _hechos_honestos(plan: PlanRuptura) -> tuple[str, ...]:
    """Lo que hay que saber antes de operarla, medido, sin adornos.

    Lo comparten el texto plano y el HTML para que no puedan contar cosas
    distintas: cuando estaban duplicados, cambiar la estrategia dejó el texto
    plano citando las cifras de la versión anterior.
    """
    if en_papel():
        return (
            "Los niveles son los de la estrategia, para comparar con lo que haga "
            "el precio. Los avisos de la tarde también llegarán, marcados igual.",
            "Se vuelve a operar solo si aparece una regla que aguante con esos "
            "días contados, medida sin mirar el resultado antes de declararla.",
        )
    if plan.solo_ventas or plan.dia_de_empleo:
        return (
            "Acierta el 39 % de las veces: la mayoría de los días pierde. Gana "
            "porque las ganadoras valen +1,23 R de media y las perdedoras -0,66 R.",
            "Medido sobre 2.209 operaciones de 21 años con TODOS los costes "
            "reales —spread de cada año y deslizamiento, sacados de los ticks— "
            "y cerrando a la hora de verdad: +0,073 R por operación, 15 años en "
            "positivo de 21.",
            "El peor año perdió 18,7 R y la peor racha fue de 45 R. Con 0,5 % de "
            "riesgo sobre 3.000 € eso son -281 € y -681 €, con +117 € de media al año.",
            "Los días de empleo (unos 8 al año) dan +0,64 R por operación y "
            "aportan casi dos tercios. El resto de días la venta da +0,03 R: "
            "no se distingue de cero.",
        )
    return (
        "Acierta el 45 % de las veces: la mayoría de los días pierde. Gana "
        "porque las ganadoras son mucho mayores.",
        "Medido sobre 19,6 años reales: 14 años en positivo de 20, con una "
        "racha mala de 2017 a 2020 que perdió cuatro años seguidos.",
    )


def aviso_instrumento() -> str | None:
    """De qué instrumento salen los precios, para poder contrastarlo una vez.

    El sistema calcula sobre el feed gratuito de Yahoo, que por defecto es
    `GC=F`: el FUTURO de oro de COMEX, no el contado. Medido en septiembre de
    2026, el futuro cotizó de media 40,17 $ por encima del XAU/USD al contado
    (y la base se movió de 48,63 a 31,70 dentro del mes). La mayoría de los
    brókeres minoristas cotizan el contado.

    Si los dos no coinciden, los niveles del correo no existen en la pantalla
    del bróker y la orden se ejecutaría al instante en vez de esperar a la
    ruptura. Es el fallo más caro posible y no se puede detectar desde aquí: el
    sistema solo ve un feed. Así que se dice, y quien opera lo comprueba una vez.

    Devuelve ``None`` si el símbolo configurado ya es el contado.
    """
    from ..config import cargar_configuracion

    cfg = cargar_configuracion()
    if cfg.fuente_vivo == "dukascopy":
        # El contado de verdad: no hay prima de futuro que advertir. Lo que sí
        # puede variar es el spread de cada bróker, que mueve unos céntimos.
        return None
    simbolo = (cfg.simbolo_vivo or "").upper()
    if simbolo in ("XAUUSD", "XAU/USD", "GOLD", "XAUUSD=X"):
        return None
    return (f"Los precios salen de {simbolo or 'GC=F'} (futuro de oro de COMEX). "
            f"Si tu bróker cotiza XAU/USD al CONTADO, marcará unos 30-50 $ menos "
            f"y estos niveles no le valdrán. Compruébalo una vez contra tu "
            f"pantalla antes de poner la primera orden.")


def _titulo_ordenes(plan: PlanRuptura) -> str:
    if en_papel():
        return "La orden del plan (solo papel)"
    return ("Deja esta orden puesta" if plan.solo_ventas
            else "Deja estas dos órdenes puestas")


def _regla_cancelar(plan: PlanRuptura) -> str:
    """La regla que hay que recordar sí o sí, en una línea."""
    if plan.dia_de_empleo:
        return "Día de empleo: salta una → cancela la otra (mejor con OCO)"
    if plan.solo_ventas:
        return f"Si sube de {plan.compra.entrada:.2f} → cancela la venta"
    return "Salta una → cancela la otra"


def _cajas_ordenes(plan: PlanRuptura) -> str:
    """Las cajas de las órdenes que de verdad se dejan puestas."""
    etiquetas = {"compra": ("▲ COMPRA · BUY STOP", _VERDE),
                 "venta": ("▼ VENTA · SELL STOP", _ROJO)}
    partes = []
    for orden in plan.ordenes:
        etiqueta, color = etiquetas[orden.direccion.value]
        partes.append(_caja_orden(orden, etiqueta, color, plan.es_favorita(orden)))
    return "\n      ".join(partes)


def _caja_orden(orden: OrdenPendiente, etiqueta: str, color: str,
                favorita: bool = False) -> str:
    """Una de las dos órdenes, con la marca redactada en CONDICIONAL.

    Aquí hubo una estrella de "más respaldo" junto a una de las dos, y era
    engañosa: medido sobre 3.180 días, la marcada es la que salta el 50,0 % de
    las veces (z = 0.00). O sea que como predicción de cuál va a ocurrir vale
    exactamente lo que una moneda, y puesta al lado de una orden se lee así.

    El resultado práctico era que el 49 % de los días parecía equivocarse: un
    25 % saltaba la marcada y perdía, un 24 % saltaba la otra y ganaba. Un dato
    correcto presentado de forma que parece fallar la mitad de las veces
    destruye la confianza en todo lo demás que dice el correo.

    Lo que el sesgo asiático SÍ dice va ahora en su bloque de texto, explicado.
    """
    borde = f'2px solid {color}' if favorita else f'1px solid {color}'
    chapa = (f'<span style="display:inline-block;background:{color};color:#0b0e14;'
             f'border-radius:8px;padding:2px 8px;font-size:10px;font-weight:800;'
             f'letter-spacing:1px;margin-left:6px;">◆ LA MEJOR SI SALTA</span>'
             if favorita else '')
    return (
        f'<table role="presentation" width="100%" style="border-collapse:collapse;'
        f'margin-bottom:10px;">'
        f'<tr><td style="background:#0e131c;border:{borde};'
        f'border-radius:14px;padding:14px 16px;">'
        f'<div style="color:{color};font-size:13px;font-weight:800;'
        f'letter-spacing:1px;">{_esc(etiqueta)}{chapa}</div>'
        f'<div style="color:{_TEXTO};font-size:26px;font-weight:800;'
        f'margin:2px 0 8px;">{orden.entrada:.2f}</div>'
        f'<table role="presentation" width="100%" style="border-collapse:collapse;">'
        f'<tr>'
        f'<td style="color:{_MUTED};font-size:11px;letter-spacing:1px;'
        f'text-transform:uppercase;">Stop loss</td>'
        f'<td style="text-align:right;color:{_ROJO};font-size:15px;'
        f'font-weight:700;">{orden.stop:.2f}</td></tr>'
        f'<tr>'
        f'<td style="color:{_MUTED};font-size:11px;letter-spacing:1px;'
        f'text-transform:uppercase;">Take profit</td>'
        f'<td style="text-align:right;color:{_VERDE};font-size:15px;'
        f'font-weight:700;">{orden.objetivo:.2f}</td></tr>'
        f'</table></td></tr></table>'
    )


def mensaje_html_de_plan(plan: PlanRuptura) -> str:
    """Tarjeta HTML del plan del día (misma paleta que el resto de avisos)."""
    zona = etiqueta_zona(plan.valido_hasta)

    pasos = "".join(
        f'<div style="color:{_TEXTO};font-size:13px;line-height:1.5;'
        f'margin-bottom:6px;">'
        f'<span style="color:{_ORO};font-weight:700;">{i}.</span> {_esc(t)}</div>'
        for i, t in enumerate(pasos_plan(plan), 1))

    aviso_riesgo = (
        f'<div style="color:{_MUTED};font-size:12px;">Riesgo si salta el stop: '
        f'{riesgo_por_onza(plan):.2f} $ por onza.</div>')

    _nota = aviso_instrumento()
    nota_instrumento = (
        f'<div style="color:{_MUTED};font-size:11px;line-height:1.5;'
        f'margin-top:8px;border-top:1px solid {_BORDE};padding-top:8px;">'
        f'{_esc(_nota)}</div>' if _nota else "")

    honestidad = "".join(
        f'<tr><td style="color:{_TEXTO};font-size:12px;padding:3px 0;'
        f'line-height:1.5;">• {_esc(t)}</td></tr>'
        for t in _hechos_honestos(plan))

    banda_papel = (
        f'<tr><td style="background:{_ROJO};border-radius:18px 18px 0 0;padding:14px 24px;">'
        f'<div style="color:#ffffff;font-size:17px;font-weight:800;">{_esc(PAPEL_TITULO)}</div>'
        f'<div style="color:#ffffff;font-size:12px;line-height:1.5;margin-top:6px;">'
        f'{_esc(PAPEL_EXPLICACION)}</div></td></tr>' if en_papel() else "")
    radio_oro = "0" if en_papel() else "18px 18px 0 0"
    return f"""\
<div style="margin:0;padding:22px 10px;background:{_FONDO};font-family:{_FUENTE};">
 <table role="presentation" align="center" width="100%" style="max-width:460px;margin:0 auto;border-collapse:collapse;">
  <tr><td style="background:{_TARJETA};border:1px solid {_BORDE};border-radius:18px;">
   <table role="presentation" width="100%" style="border-collapse:collapse;">
    {banda_papel}
    <tr><td style="background:{_ORO};border-radius:{radio_oro};padding:16px 24px;">
      <div style="color:#0b0e14;font-size:12px;letter-spacing:3px;opacity:.75;">◆ XAU/USD · ORO</div>
      <div style="color:#0b0e14;font-size:23px;font-weight:800;margin-top:2px;">⚡ PLAN DEL DÍA</div>
    </td></tr>
    <tr><td style="padding:22px 24px;">
      <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;">Rango de la mañana de Londres</div>
      <div style="color:{_TEXTO};font-size:30px;font-weight:800;margin:2px 0 2px;">{plan.rango.bajo:.2f} <span style="color:{_MUTED};font-size:18px;">—</span> {plan.rango.alto:.2f}</div>
      <div style="color:{_MUTED};font-size:12px;margin-bottom:18px;">Amplitud {plan.rango.amplitud:.2f} $ · eso es 1R, lo que arriesgas</div>

      <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;">{_esc(_titulo_ordenes(plan))}</div>
      {_cajas_ordenes(plan)}
      <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:10px;">
       <tr><td style="background:#0e131c;border:1px solid {_BORDE};border-radius:12px;padding:12px 16px;">
         <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">{'Por qué este plan' if (plan.solo_ventas or plan.dia_de_empleo) else 'Cuál de las dos es la de fiar'}</div>
         <div style="color:{_TEXTO};font-size:13px;line-height:1.5;">{_esc(texto_confianza(plan))}</div>
         <div style="color:{_MUTED};font-size:11px;line-height:1.5;margin-top:6px;">{_esc(aviso_confianza(plan))}</div>
       </td></tr>
      </table>
      <div style="background:#0e131c;border:1px dashed {_ORO};border-radius:12px;padding:12px 16px;margin-bottom:18px;">
        <div style="color:{_ORO};font-size:13px;font-weight:700;">{_esc(_regla_cancelar(plan))}</div>
        {aviso_riesgo}{nota_instrumento}
      </div>

      <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:18px;">
       <tr><td style="background:#0e131c;border-radius:12px;padding:14px 16px;">
         <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;">{"Lo que haría la estrategia (no lo hagas con dinero real)" if en_papel() else "Qué hacer, paso a paso"}</div>
         {pasos}
       </td></tr>
      </table>

      <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">{"Por qué va en papel" if en_papel() else "Lo que hay que saber antes de operarla"}</div>
      <table role="presentation" width="100%" style="border-collapse:collapse;">{honestidad}</table>
    </td></tr>
    <tr><td style="background:#0e131c;border-radius:0 0 18px 18px;padding:12px 24px;">
      <div style="color:{_MUTED};font-size:11px;line-height:1.5;">
        ⚠️ Herramienta de análisis, no asesoramiento financiero. Opera bajo tu responsabilidad.
      </div>
    </td></tr>
   </table>
  </td></tr>
  <tr><td style="text-align:center;padding:12px 14px;color:#4a5568;font-size:11px;">
     ⏱ {'La orden vale' if plan.solo_ventas else 'Las órdenes valen'} hasta las <b>{hora_local(plan.valido_hasta)}</b> ({_esc(zona)}).
     Ciérrala a mano a las <b>{hora_cierre(plan)}</b>, gane o pierda.<br>
     Sistema XAU/USD · plan generado automáticamente</td></tr>
 </table>
</div>"""


__all__ = ["riesgo_por_onza", "pasos_plan", "mensaje_de_plan", "mensaje_html_de_plan"]


# ---------------------------------------------------------------------------
# Los avisos del seguimiento, en tarjeta
# ---------------------------------------------------------------------------
# El color de la cabecera dice QUÉ tipo de aviso es antes de leer una palabra:
# rojo = hay que cancelar o cerrar algo, verde = la operación va a favor.
_COLOR_AVISO = {
    "cierre": _ROJO,
    "mover_stop": _VERDE,
    "tp_alcanzado": _VERDE,
    "ampliar_objetivo": _VERDE,
    "_": _ORO,
}



def mensaje_html_de_aviso(titulo: str, cuerpo: str, destacado: str = "",
                          color: str = _ORO) -> str:
    """La misma tarjeta del plan, para los avisos de la sesión.

    Salían en texto plano, y el de CANCELAR es el que sostiene la estrategia:
    si no se actúa, la orden se ejecuta en la población que pierde 0,29 R de
    media y la ventaja entera desaparece. Un correo que hay que leer deprisa en
    el móvil, entre otros muchos, no puede ser el más gris de todos.

    ``destacado`` es el dato que hay que ver sin leer: el precio que anula la
    orden, o los R que lleva la operación.
    """
    # Texto oscuro sobre el dorado, blanco sobre el rojo y el verde: sobre
    # #F04438 el texto oscuro queda por debajo del contraste legible, y este es
    # justo el correo que hay que leer de un vistazo.
    tinta = "#0b0e14" if color == _ORO else "#ffffff"
    caja = ""
    if destacado:
        caja = (f'<div style="background:#0e131c;border:1px dashed {color};'
                f'border-radius:12px;padding:14px 16px;margin-bottom:16px;'
                f'text-align:center;">'
                f'<div style="color:{color};font-size:26px;font-weight:800;'
                f'letter-spacing:.5px;">{_esc(destacado)}</div></div>')
    return f"""\
<div style="margin:0;padding:22px 10px;background:{_FONDO};font-family:{_FUENTE};">
 <table role="presentation" align="center" width="100%" style="max-width:460px;margin:0 auto;border-collapse:collapse;">
  <tr><td style="background:{_TARJETA};border:1px solid {_BORDE};border-radius:18px;">
   <table role="presentation" width="100%" style="border-collapse:collapse;">
    <tr><td style="background:{color};border-radius:18px 18px 0 0;padding:16px 24px;">
      <div style="color:{tinta};font-size:12px;letter-spacing:3px;opacity:.75;">◆ XAU/USD · ORO</div>
      <div style="color:{tinta};font-size:20px;font-weight:800;margin-top:2px;">{_esc(titulo)}</div>
    </td></tr>
    <tr><td style="padding:22px 24px;">
      {caja}
      <div style="color:{_TEXTO};font-size:14px;line-height:1.6;">{_esc(cuerpo)}</div>
    </td></tr>
    <tr><td style="background:#0e131c;border-radius:0 0 18px 18px;padding:12px 24px;">
      <div style="color:{_MUTED};font-size:11px;line-height:1.5;">
        ⚠️ Herramienta de análisis, no asesoramiento financiero. Opera bajo tu responsabilidad.
      </div>
    </td></tr>
   </table>
  </td></tr>
 </table>
</div>"""
