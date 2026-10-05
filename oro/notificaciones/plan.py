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
    _cierre_local,
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


def riesgo_por_onza(plan: PlanRuptura) -> float:
    """Lo que se pierde por cada onza si salta el stop: el rango entero.

    Es el único dato de riesgo que da el correo. El TAMAÑO de la posición lo
    decide el usuario, así que aquí no se calcula ningún lote ni se avisa de
    ningún mínimo: con este número y su cuenta, quien opera hace su cuenta.
    """
    return plan.rango.amplitud


def hora_cierre(plan: PlanRuptura) -> str:
    """A qué hora hay que cerrar la operación, en la hora del usuario.

    Son las 21:50 casi todo el año, pero Europa y EE. UU. no cambian la hora el
    mismo fin de semana (1 semana desfasada en octubre y 3 en marzo) y esas
    cuatro semanas el mercado ya ha cerrado a las 21:00. Decir "21:50" entonces
    sería mandar a cerrar una posición que ya se cerró sola.
    """
    from ..config import cargar_configuracion

    return _cierre_local(plan.cierre_forzoso,
                         cargar_configuracion().ruptura.cierre_et)


def texto_confianza(plan: PlanRuptura) -> str:
    """Qué dice el sesgo asiático, SIN que parezca una predicción.

    El orden de la frase importa: primero lo que NO es, porque es lo que todo
    el mundo asume al leerla, y después lo que sí.
    """
    if plan.solo_ventas:
        # Con una sola orden no hay nada que elegir, y la pregunta que importa
        # no es «qué lado» sino «por qué solo este».
        return ("Hoy solo va una orden, y a la baja. Medido sobre 4.646 días "
                "con rotura de 21 años: la rotura a la baja da +0,114 R por "
                "operación (t = 4,37, positiva en las dos mitades del histórico, "
                "17 años a favor de 21) y la rotura al alza da -0,064 R "
                "(t = -2,56, solo 4 años a favor de 21). No es que la compra "
                "sea peor: es que resta.")
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
    if plan is not None and plan.solo_ventas:
        return ("El límite: son +11,6 R al año, unos 174 € con 0,5 % de riesgo "
                "sobre 3.000 €, y 4 de los 21 años fueron en pérdida (el peor, "
                "-8,3 R). La ventaja sobrevive a 11 perturbaciones de horario y "
                "a quitar el mejor y el peor año, pero 101 operaciones al año "
                "tardan en demostrar nada: espera rachas negativas de 23 R.")
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
            f"perder. Medido: sube la ventaja de +0,096 a +0,114 R por operación.",
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
    lineas = [
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
        "POR QUÉ ESTE PLAN:" if plan.solo_ventas else "CUÁL DE LAS DOS ES LA DE FIAR:",
        f"  {texto_confianza(plan)}",
        f"  {aviso_confianza(plan)}",
        "",
        f"Riesgo si salta el stop: {riesgo_por_onza(plan):.2f} $ por onza.",
        "",
        f"Válido hasta las {hora_local(plan.valido_hasta)} ({zona}). "
        + ("Después, cancélala." if plan.solo_ventas else "Después, cancela las dos."),
        f"Cierre a mano: {hora_cierre(plan)} ({zona}), gane o pierda.",
        "",
        "QUÉ HACER, paso a paso:",
    ]
    lineas += [f"  {i}. {t}" for i, t in enumerate(pasos_plan(plan), 1)]
    lineas += [
        "",
        "LO QUE HAY QUE SABER ANTES DE OPERARLA:",
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
    if plan.solo_ventas:
        return (
            "Acierta el 40 % de las veces: la mayoría de los días pierde. Gana "
            "porque las ganadoras valen +1,21 R de media y las perdedoras -0,61 R.",
            "Medido sobre 2.131 roturas a la baja de 21 años reales: +0,114 R "
            "por operación, 101 operaciones al año, 17 años en positivo de 21.",
            "El peor año perdió 8,3 R y la peor racha fue de 23 R. Con 0,5 % de "
            "riesgo sobre 3.000 € eso son -125 € y -345 €, con +174 € de media al año.",
            "No se opera la rotura al alza porque está medida y resta: -0,064 R "
            "por operación, solo 4 años a favor de 21.",
        )
    return (
        "Acierta el 45 % de las veces: la mayoría de los días pierde. Gana "
        "porque las ganadoras son mucho mayores.",
        "Medido sobre 19,6 años reales: 14 años en positivo de 20, con una "
        "racha mala de 2017 a 2020 que perdió cuatro años seguidos.",
    )


def _titulo_ordenes(plan: PlanRuptura) -> str:
    return ("Deja esta orden puesta" if plan.solo_ventas
            else "Deja estas dos órdenes puestas")


def _regla_cancelar(plan: PlanRuptura) -> str:
    """La regla que hay que recordar sí o sí, en una línea."""
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

    honestidad = "".join(
        f'<tr><td style="color:{_TEXTO};font-size:12px;padding:3px 0;'
        f'line-height:1.5;">• {_esc(t)}</td></tr>'
        for t in _hechos_honestos(plan))

    return f"""\
<div style="margin:0;padding:22px 10px;background:{_FONDO};font-family:{_FUENTE};">
 <table role="presentation" align="center" width="100%" style="max-width:460px;margin:0 auto;border-collapse:collapse;">
  <tr><td style="background:{_TARJETA};border:1px solid {_BORDE};border-radius:18px;">
   <table role="presentation" width="100%" style="border-collapse:collapse;">
    <tr><td style="background:{_ORO};border-radius:18px 18px 0 0;padding:16px 24px;">
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
         <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">{'Por qué este plan' if plan.solo_ventas else 'Cuál de las dos es la de fiar'}</div>
         <div style="color:{_TEXTO};font-size:13px;line-height:1.5;">{_esc(texto_confianza(plan))}</div>
         <div style="color:{_MUTED};font-size:11px;line-height:1.5;margin-top:6px;">{_esc(aviso_confianza(plan))}</div>
       </td></tr>
      </table>
      <div style="background:#0e131c;border:1px dashed {_ORO};border-radius:12px;padding:12px 16px;margin-bottom:18px;">
        <div style="color:{_ORO};font-size:13px;font-weight:700;">{_esc(_regla_cancelar(plan))}</div>
        {aviso_riesgo}
      </div>

      <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:18px;">
       <tr><td style="background:#0e131c;border-radius:12px;padding:14px 16px;">
         <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;">Qué hacer, paso a paso</div>
         {pasos}
       </td></tr>
      </table>

      <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">Lo que hay que saber antes de operarla</div>
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
