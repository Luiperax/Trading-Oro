"""El correo del plan de ruptura de sesión.

Es distinto del correo de señal y por eso vive aparte: una señal dice «entra
AHORA a este precio», y esto dice «deja preparadas estas DOS órdenes y que el
mercado elija». Quien lo recibe no tiene que decidir nada ni estar delante: se
teclean las dos órdenes en el bróker a las 14:00 y se olvida.

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
    """Una frase que diga cuál de las dos órdenes tiene más respaldo, y cuánto.

    Va con el número al lado a propósito. "Más confianza" a secas invita a
    pensar que la otra no vale, y no es eso: la otra no pierde, simplemente no
    gana casi nada. Y la diferencia, dicha en voz alta, no llega a demostrada.
    """
    if plan.favorita is None:
        return ("Hoy NINGUNA de las dos destaca: la sesión asiática ha cerrado "
                "casi donde abrió, y en esos días los dos lados se comportan "
                "igual. Trátalas como iguales.")
    lado = "COMPRA" if plan.favorita.value == "compra" else "VENTA"
    otro = "VENTA" if lado == "COMPRA" else "COMPRA"
    subio = "subido" if plan.sesgo.cuerpo > 0 else "bajado"
    return (f"La {lado} tiene más respaldo: la sesión asiática ha {subio} "
            f"{abs(plan.sesgo.cuerpo):.2f} $ y, en 19,6 años, la ruptura que "
            f"acompaña a Asia ha dado {_R_A_FAVOR} R por operación frente a "
            f"{_R_EN_CONTRA} R la contraria. La {otro} no pierde dinero, "
            f"simplemente casi no gana.")


def aviso_confianza() -> str:
    """El límite de lo anterior, sin el cual la frase promete de más."""
    return ("Es una INDICACIÓN, no un hecho probado: la diferencia entre lados "
            "da t = 2,07 y no supera la corrección estadística que aplico "
            "(haría falta 2,81). La respaldan 15 de 20 años y las 5 formas de "
            "medirlo que probé. Deja las DOS órdenes puestas igualmente.")


def pasos_plan(plan: PlanRuptura) -> list[str]:
    """Los pasos exactos, en el orden en que se teclean en el bróker."""
    c, v = plan.compra, plan.venta
    return [
        "Abre tu bróker y busca XAU/USD (oro). Vas a dejar DOS órdenes "
        "pendientes del tamaño que decidas. No se abre nada todavía.",
        f"Orden 1 — COMPRA tipo «BUY STOP» en {c.entrada:.2f}, "
        f"con stop loss en {c.stop:.2f} y take profit en {c.objetivo:.2f}."
        + (" ← la de más respaldo hoy" if plan.es_favorita(c) else ""),
        f"Orden 2 — VENTA tipo «SELL STOP» en {v.entrada:.2f}, "
        f"con stop loss en {v.stop:.2f} y take profit en {v.objetivo:.2f}."
        + (" ← la de más respaldo hoy" if plan.es_favorita(v) else ""),
        "Ese take profit está MUY lejos a propósito: es una red de seguridad "
        "para el día extraordinario, no la salida. Se ejecuta 1 de cada 1.000 "
        "veces. La salida de verdad es cerrar a mano al final de la sesión.",
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
        "DOS ÓRDENES PENDIENTES (salta una, cancela la otra):",
        f"  COMPRA (buy stop)  en {plan.compra.entrada:.2f}   "
        f"stop {plan.compra.stop:.2f}   objetivo {plan.compra.objetivo:.2f}"
        f"{'   ★ MÁS RESPALDO' if plan.es_favorita(plan.compra) else ''}",
        f"  VENTA  (sell stop) en {plan.venta.entrada:.2f}   "
        f"stop {plan.venta.stop:.2f}   objetivo {plan.venta.objetivo:.2f}"
        f"{'   ★ MÁS RESPALDO' if plan.es_favorita(plan.venta) else ''}",
        "",
        "CUÁL DE LAS DOS ES LA DE FIAR:",
        f"  {texto_confianza(plan)}",
        f"  {aviso_confianza()}",
        "",
        f"Riesgo si salta el stop: {riesgo_por_onza(plan):.2f} $ por onza.",
    ]
    lineas += [
        "",
        f"Válido hasta las {hora_local(plan.valido_hasta)} ({zona}). "
        f"Después, cancela las dos.",
        f"Cierre a mano: {hora_cierre(plan)} ({zona}), gane o pierda.",
        "",
        "QUÉ HACER, paso a paso:",
    ]
    lineas += [f"  {i}. {t}" for i, t in enumerate(pasos_plan(plan), 1)]
    lineas += [
        "",
        "LO QUE HAY QUE SABER ANTES DE OPERARLA:",
        "  • Acierta el 45 % de las veces. La mayoría de los días pierde; gana",
        "    porque las ganadoras son mucho mayores que las perdedoras.",
        "  • Medido sobre 19,6 años: 14 años en positivo de 20, y una racha mala",
        "    de 2017 a 2020 en la que perdió cuatro años seguidos.",
        f"  • El spread se lleva hoy el {plan.coste_r:.1%} de lo que arriesgas.",
        "",
        "⚠️ Herramienta de análisis, no asesoramiento financiero.",
    ]
    return "\n".join(lineas)


def _caja_orden(orden: OrdenPendiente, etiqueta: str, color: str,
                favorita: bool = False) -> str:
    """Una de las dos órdenes. La favorita lleva borde grueso y una chapa.

    La distinción es visual además de textual porque el correo se lee en el
    móvil y de un vistazo: si hay que buscar la frase para saber cuál es, el
    dato no sirve de nada.
    """
    borde = f'2px solid {color}' if favorita else f'1px solid {color}'
    chapa = (f'<span style="display:inline-block;background:{color};color:#0b0e14;'
             f'border-radius:8px;padding:2px 8px;font-size:10px;font-weight:800;'
             f'letter-spacing:1px;margin-left:6px;">★ MÁS RESPALDO</span>'
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
        for t in (
            "Acierta el 45 % de las veces: la mayoría de los días pierde. "
            "Gana porque las ganadoras son mucho mayores.",
            "Medido sobre 19,6 años reales: 14 años en positivo de 20, con una "
            "racha mala de 2017 a 2020 que perdió cuatro años seguidos.",
            f"El spread se lleva hoy el {plan.coste_r:.1%} de lo que arriesgas.",
        ))

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

      <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;">Deja estas dos órdenes puestas</div>
      {_caja_orden(plan.compra, "▲ COMPRA · BUY STOP", _VERDE,
                   plan.es_favorita(plan.compra))}
      {_caja_orden(plan.venta, "▼ VENTA · SELL STOP", _ROJO,
                   plan.es_favorita(plan.venta))}
      <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:10px;">
       <tr><td style="background:#0e131c;border:1px solid {_BORDE};border-radius:12px;padding:12px 16px;">
         <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">Cuál de las dos es la de fiar</div>
         <div style="color:{_TEXTO};font-size:13px;line-height:1.5;">{_esc(texto_confianza(plan))}</div>
         <div style="color:{_MUTED};font-size:11px;line-height:1.5;margin-top:6px;">{_esc(aviso_confianza())}</div>
       </td></tr>
      </table>
      <div style="background:#0e131c;border:1px dashed {_ORO};border-radius:12px;padding:12px 16px;margin-bottom:18px;">
        <div style="color:{_ORO};font-size:13px;font-weight:700;">Salta una → cancela la otra</div>
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
     ⏱ Las órdenes valen hasta las <b>{hora_local(plan.valido_hasta)}</b> ({_esc(zona)}).
     Ciérrala a mano a las <b>{hora_cierre(plan)}</b>, gane o pierda.<br>
     Sistema XAU/USD · plan generado automáticamente</td></tr>
 </table>
</div>"""


__all__ = ["riesgo_por_onza", "pasos_plan", "mensaje_de_plan", "mensaje_html_de_plan"]
