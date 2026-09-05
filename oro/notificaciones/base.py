"""Interfaz de notificación y formateo de mensajes (texto plano + HTML elegante)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional

from ..dominio import Signal

# Paleta (tema oscuro elegante, seguro para clientes de correo).
_FONDO = "#0b0e14"
_TARJETA = "#151b26"
_BORDE = "#232c3a"
_ORO = "#E8B923"
_VERDE = "#12B76A"
_ROJO = "#F04438"
_AMBAR = "#F5A524"
_TEXTO = "#E6E6E6"
_MUTED = "#8A93A3"
_FUENTE = "'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


class Evento(str, Enum):
    NUEVA_SENAL = "nueva_senal"
    MOVER_STOP = "mover_stop"
    TP_ALCANZADO = "tp_alcanzado"
    CIERRE = "cierre"
    CAMBIO_MERCADO = "cambio_mercado"


def _cierre_local() -> str:
    """Hora a la que llegará el AVISO de cierre, en la hora del usuario.

    Es el dato accionable: no sirve decir "21:00 UTC" ni la hora a la que cierra
    el mercado, sino a qué hora recibirá el aviso para cerrar en el bróker.
    Coincide con la franja del trabajo de cierre (oro.cierre).
    """
    from ..cierre import HORA_AVISO_LOCAL
    return f"{HORA_AVISO_LOCAL}:50"


LOTE_MINIMO = 0.01          # el lote más pequeño que acepta un bróker (= 1 oz).


def _lote_y_riesgo(signal: Signal):
    """Convierte el tamaño (oz) al LOTE del bróker y calcula la pérdida máxima.

    1 lote estándar de XAU/USD = 100 oz. El lote mínimo habitual es 0.01.

    OJO, y es importante: con una cuenta pequeña el lote mínimo puede arriesgar
    MUCHO MÁS que el porcentaje configurado, y no hay forma de bajarlo. Medido
    con 3000 EUR de capital y un tope del 0.25% (7.50 EUR), el oro con stops de
    8 a 50 puntos obliga a arriesgar entre el 112% y el 655% de ese tope. El
    aviso debe decirlo, no taparlo: quien lee el correo tiene que saber que esa
    cifra es la de verdad y no el "riesgo mínimo" que pidió.
    """
    exacto = signal.tamano_posicion / 100.0
    lote = max(LOTE_MINIMO, round(exacto, 2))
    # Pérdida máxima calculada sobre el LOTE que realmente se coloca (1 lote = 100 oz),
    # para que el importe mostrado coincida con lo que se arriesga de verdad.
    perdida_max = abs(signal.entrada - signal.stop_loss) * lote * 100.0
    return lote, perdida_max


def _riesgo_real(signal: Signal) -> tuple[float, float, bool]:
    """(pérdida en divisa, % del capital, ¿supera el tope configurado?)."""
    from ..config import cargar_configuracion

    cfg = cargar_configuracion()
    _, perdida = _lote_y_riesgo(signal)
    pct = perdida / cfg.capital if cfg.capital > 0 else 0.0
    return perdida, pct, pct > cfg.riesgo.riesgo_por_operacion * 1.05


def _texto_riesgo(signal: Signal) -> str:
    """Frase honesta sobre lo que se arriesga de verdad con el lote mínimo."""
    perdida, pct, excede = _riesgo_real(signal)
    if not excede:
        return f"Pérdida máxima si salta el stop: ≈{perdida:.0f} € ({pct:.2%} del capital)"
    return (f"Pérdida máxima si salta el stop: ≈{perdida:.0f} € = {pct:.2%} del capital. "
            f"⚠️ Es el LOTE MÍNIMO (0.01) y arriesga MÁS del objetivo configurado; "
            f"con esta cuenta no se puede bajar más")


# Un objetivo muy lejano no es un objetivo: existe para sostener el R:R ponderado
# y el stop dinámico cierra antes. Anunciarlo como take profit haría poner en el
# bróker una orden que no se ejecuta y dejaría la posición sin gestionar.
R_TOPE_NO_ES_OBJETIVO = 5.0


def _es_tope(tp) -> bool:
    return tp.r_multiple >= R_TOPE_NO_ES_OBJETIVO


def _objetivos_reales(signal: Signal) -> list:
    return [tp for tp in signal.take_profits if not _es_tope(tp)]


def _rr_honesto(signal: Signal) -> str:
    """R:R tal y como se opera, no como sale de multiplicar la configuración."""
    reales = _objetivos_reales(signal)
    if not reales:
        return "sin techo"          # la salida la decide el stop, no un objetivo.
    if len(reales) == len(signal.take_profits):
        return f"{signal.riesgo_recompensa:.2f}"
    return f"{reales[-1].r_multiple:.0f}R + resto"


# Frase única sobre cómo se sale, para que el correo de texto y el HTML no puedan
# contarlo de dos maneras distintas.
SALIDA_GESTIONADA = ("Sin objetivo fijo: el STOP persigue al precio y te aviso "
                     "cuándo salir. No pongas take profit.")


def mensaje_de_senal(signal: Signal) -> str:
    """Versión en texto plano (respaldo y para clientes sin HTML)."""
    compra = signal.direccion.value == "compra"
    lineas = [
        f"{'🟢' if compra else '🔴'} NUEVA SEÑAL XAU/USD — {signal.direccion.value.upper()}",
        "",
        f"Entrada:  {signal.entrada:.2f}",
        f"Stop:     {signal.stop_loss:.2f}",
    ]
    reales = _objetivos_reales(signal)
    for k, tp in enumerate(reales, 1):
        etiqueta = "TP" if len(reales) == 1 else f"TP{k}"
        lineas.append(f"{etiqueta+':':<10}{tp.precio:.2f}  ({tp.r_multiple:.1f}R, {tp.fraccion:.0%})")
    if len(reales) < len(signal.take_profits) or not signal.take_profits:
        lineas.append("")
        lineas.append(f"Salida:   {SALIDA_GESTIONADA}")
    lineas += [
        "",
        f"Probabilidad estimada: {signal.probabilidad:.0%}  (no es garantía)",
        f"Confianza: {signal.confianza:.0%}   R:R: {_rr_honesto(signal)}",
        "",
        f"👉 LOTE a introducir en el bróker: {_lote_y_riesgo(signal)[0]:.2f}",
        f"   {_texto_riesgo(signal)}",
        "   ⚠️ Es LOTES, no onzas. Pon SIEMPRE el Stop Loss indicado arriba.",
        "",
        "Motivos de entrada:",
    ]
    lineas += [f"  • {m}" for m in signal.motivos_entrada[:5]]
    if signal.riesgos:
        lineas += ["", "Riesgos:"]
        lineas += [f"  • {m}" for m in signal.riesgos[:3]]
    lineas += ["", f"Contexto: {signal.contexto_tecnico}"]
    lineas += ["", "⚠️ Herramienta de análisis, no asesoramiento financiero."]
    return "\n".join(lineas)


def _pill(texto: str, valor: str, color: str) -> str:
    return (
        f'<td style="padding:0 5px 0 0;"><table role="presentation" style="border-collapse:collapse;">'
        f'<tr><td style="background:#0e131c;border:1px solid {_BORDE};border-radius:10px;padding:8px 12px;">'
        f'<div style="color:{_MUTED};font-size:10px;letter-spacing:1px;text-transform:uppercase;">{texto}</div>'
        f'<div style="color:{color};font-size:17px;font-weight:700;">{valor}</div>'
        f'</td></tr></table></td>'
    )


def _fila_nivel(etiqueta: str, valor: str, color: str, extra: str = "") -> str:
    return (
        f'<tr>'
        f'<td style="padding:9px 0;border-bottom:1px solid {_BORDE};color:{_MUTED};font-size:14px;">{etiqueta}</td>'
        f'<td style="padding:9px 0;border-bottom:1px solid {_BORDE};text-align:right;">'
        f'<span style="color:{color};font-size:16px;font-weight:700;">{valor}</span>'
        f'<span style="color:{_MUTED};font-size:12px;"> {extra}</span></td>'
        f'</tr>'
    )


def _esc(texto) -> str:
    """Escapa texto antes de meterlo en HTML.

    Hoy todo lo que se interpola se genera dentro del sistema, así que no hay
    inyección posible. Pero parte de ese texto ROZA lo externo: el resumen de
    sentimiento incluye el nombre del próximo evento macro, que viene de un
    calendario de terceros. El día que alguien lo añada a la tarjeta, un nombre
    con "<" rompería el correo o inyectaría marcado. Escapar cuesta nada y
    quita el pie del filo.
    """
    import html as _html
    return _html.escape(str(texto), quote=True)


def mensaje_html_de_senal(signal: Signal) -> str:
    """Tarjeta HTML elegante para el correo (diseño responsive, tema oscuro)."""
    compra = signal.direccion.value == "compra"
    dir_color = _VERDE if compra else _ROJO
    flecha = "▲" if compra else "▼"
    dir_txt = signal.direccion.value.upper()

    niveles = _fila_nivel("Stop Loss", f"{signal.stop_loss:.2f}", _ROJO)
    reales = _objetivos_reales(signal)
    for k, tp in enumerate(reales, 1):
        etiqueta = "Take Profit" if len(reales) == 1 else f"Take Profit {k}"
        niveles += _fila_nivel(etiqueta, f"{tp.precio:.2f}", _VERDE,
                               f"· {tp.r_multiple:.1f}R · {tp.fraccion:.0%}")
    if len(reales) < len(signal.take_profits) or not signal.take_profits:
        niveles += _fila_nivel("Salida", "sin take profit", _ORO,
                               "· la gestiono yo · te aviso")

    motivos = "".join(
        f'<tr><td style="color:{_TEXTO};font-size:13px;padding:3px 0;">'
        f'<span style="color:{_VERDE};">✓</span>&nbsp; {_esc(m)}</td></tr>'
        for m in signal.motivos_entrada[:5]
    )

    return f"""\
<div style="margin:0;padding:22px 10px;background:{_FONDO};font-family:{_FUENTE};">
 <table role="presentation" align="center" width="100%" style="max-width:460px;margin:0 auto;border-collapse:collapse;">
  <tr><td style="background:{_TARJETA};border:1px solid {_BORDE};border-radius:18px;">
   <table role="presentation" width="100%" style="border-collapse:collapse;">
    <tr><td style="background:{dir_color};border-radius:18px 18px 0 0;padding:16px 24px;">
      <div style="color:#ffffff;font-size:12px;letter-spacing:3px;opacity:.85;">◆ XAU/USD · ORO</div>
      <div style="color:#ffffff;font-size:23px;font-weight:800;margin-top:2px;">{flecha} SEÑAL DE {dir_txt}</div>
    </td></tr>
    <tr><td style="padding:22px 24px;">
      <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;">Precio de entrada</div>
      <div style="color:{_TEXTO};font-size:36px;font-weight:800;margin:2px 0 18px;">${signal.entrada:.2f}</div>
      <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:18px;">{niveles}</table>
      <table role="presentation" style="border-collapse:collapse;margin-bottom:16px;"><tr>
        {_pill("Probabilidad", f"{signal.probabilidad:.0%}", _ORO)}
        {_pill("Confianza", f"{signal.confianza:.0%}", _ORO)}
        {_pill("R : R", _rr_honesto(signal), _TEXTO)}
      </tr></table>
      <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:18px;">
       <tr><td style="background:#0e131c;border:1px dashed {_ORO};border-radius:12px;padding:14px 16px;">
         <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;">Lote a introducir en el bróker</div>
         <div style="color:{_ORO};font-size:30px;font-weight:800;">{_lote_y_riesgo(signal)[0]:.2f} <span style="font-size:13px;color:{_MUTED};font-weight:600;">lotes</span></div>
         <div style="color:{_ROJO if _riesgo_real(signal)[2] else _MUTED};font-size:12px;">{_esc(_texto_riesgo(signal))}</div>
         <div style="color:{_ROJO};font-size:12px;margin-top:4px;">⚠️ Es LOTES, no onzas. Pon SIEMPRE el Stop Loss.</div>
       </td></tr>
      </table>
      <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">Motivos de entrada</div>
      <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:14px;">{motivos}</table>
      <div style="color:{_MUTED};font-size:12px;line-height:1.5;border-top:1px solid {_BORDE};padding-top:12px;">
        {_esc(signal.contexto_tecnico)}
      </div>
    </td></tr>
    <tr><td style="background:#0e131c;border-radius:0 0 18px 18px;padding:12px 24px;">
      <div style="color:{_MUTED};font-size:11px;line-height:1.5;">
        ⚠️ La probabilidad es una <b>estimación</b>, no una garantía. Herramienta de análisis,
        no asesoramiento financiero. Opera bajo tu responsabilidad.
      </div>
    </td></tr>
   </table>
  </td></tr>
  <tr><td style="text-align:center;padding:12px 14px;color:#4a5568;font-size:11px;">
     ⏱ Operación INTRADÍA: recibirás el aviso para cerrarla hoy sobre las
     <b>{_cierre_local()}</b> (tu hora), antes de que cierre el mercado.<br>
     Sistema XAU/USD · señal generada automáticamente</td></tr>
 </table>
</div>"""


def mensaje_html_evento(titulo: str, cuerpo_html: str, evento: Evento,
                        datos: dict | None = None) -> str:
    """Tarjeta HTML para eventos de gestión (objetivo, break-even, cierre).

    Con ``datos`` se maqueta la tarjeta completa —resultado grande y a color,
    precios de entrada y salida, chips de contexto—. Sin ``datos`` cae a la
    versión simple con ``cuerpo_html``, que se usa desde otras rutas.

    OJO CON EL CONTRATO, que ya se rompió una vez:

    * ``titulo`` es TEXTO PLANO y se escapa aquí.
    * ``cuerpo_html`` ya viene siendo HTML —lo compone
      ``RunnerVivo._notificar_evento`` con negritas y saltos a propósito— así
      que NO se escapa. Quien lo construye escapa lo que no controle.

    Al añadir el escapado se escapó también el cuerpo, y el correo de cierre
    llegó mostrando "<b>Cierra la operación completa AHORA.</b><br>" como texto
    literal en lugar de en negrita.
    """
    color = {
        Evento.TP_ALCANZADO: _VERDE,
        Evento.MOVER_STOP: _AMBAR,
        Evento.CIERRE: _ORO,
    }.get(evento, _ORO)
    cuerpo = _cuerpo_evento(datos, color) if datos else (
        f'<tr><td style="padding:20px 24px;color:{_TEXTO};font-size:15px;'
        f'line-height:1.6;">{cuerpo_html}</td></tr>')
    return f"""\
<div style="margin:0;padding:22px 10px;background:{_FONDO};font-family:{_FUENTE};">
 <table role="presentation" align="center" width="100%" style="max-width:460px;margin:0 auto;border-collapse:collapse;">
  <tr><td style="background:{_TARJETA};border:1px solid {_BORDE};border-radius:18px;">
   <table role="presentation" width="100%" style="border-collapse:collapse;">
    <tr><td style="background:{color};border-radius:18px 18px 0 0;padding:14px 24px;color:#0b0e14;font-size:18px;font-weight:800;">{_esc(titulo)}</td></tr>
{cuerpo}
    <tr><td style="background:#0e131c;border-radius:0 0 18px 18px;padding:12px 24px;color:{_MUTED};font-size:11px;">
      ⚠️ Herramienta de análisis, no asesoramiento financiero.</td></tr>
   </table>
  </td></tr>
 </table>
</div>"""


def _cuerpo_evento(d: dict, color: str) -> str:
    """Cuerpo maquetado: qué hacer, cuánto llevas, y los precios que importan.

    Lo que el usuario necesita de un vistazo en el móvil, por orden: la ACCIÓN,
    la CIFRA y los PRECIOS. Las dos cajas de precio son genéricas a propósito:
    en un cierre son "Entrada -> Salida", pero en un break-even NO hay salida
    —solo se mueve el stop— y poner ahí una "SALIDA" invitaba a cerrar la
    posición por error.
    """
    r = d.get("r")
    tono = _VERDE if (r or 0) > 0 else _ROJO if (r or 0) < 0 else _MUTED
    filas = []

    # 1) La acción, que es lo único que hay que hacer.
    filas.append(
        f'<tr><td style="padding:22px 24px 6px 24px;">'
        f'<div style="color:{_TEXTO};font-size:19px;font-weight:800;line-height:1.3;">'
        f'{_esc(d["accion"])}</div></td></tr>')

    # 2) La cifra, grande y a color. Es lo que se busca con la vista.
    if r is not None:
        filas.append(
            f'<tr><td style="padding:12px 24px 4px 24px;">'
            f'<table role="presentation" width="100%" style="border-collapse:collapse;">'
            f'<tr><td style="background:#0e131c;border:1px solid {_BORDE};'
            f'border-radius:14px;padding:16px 18px;text-align:center;">'
            f'<div style="color:{_MUTED};font-size:10px;letter-spacing:1.5px;'
            f'text-transform:uppercase;">{_esc(d.get("etiqueta_r", "Resultado"))}</div>'
            f'<div style="color:{tono};font-size:34px;font-weight:800;line-height:1.1;'
            f'margin:2px 0;">{r:+.2f}<span style="font-size:18px;">R</span></div>'
            f'<div style="color:{_MUTED};font-size:12px;line-height:1.4;">'
            f'{_esc(d.get("motivo", ""))}</div>'
            f'</td></tr></table></td></tr>')

    # 3) Dos cajas de precio, con las etiquetas que toquen en cada caso.
    izq, der = d.get("izq"), d.get("der")
    if izq and der:
        borde_der = d.get("color_der", tono)
        filas.append(
            f'<tr><td style="padding:12px 24px 4px 24px;">'
            f'<table role="presentation" width="100%" style="border-collapse:collapse;">'
            f'<tr>'
            f'<td width="45%" style="background:#0e131c;border:1px solid {_BORDE};'
            f'border-radius:12px;padding:12px;text-align:center;">'
            f'<div style="color:{_MUTED};font-size:10px;letter-spacing:1px;'
            f'text-transform:uppercase;">{_esc(izq[0])}</div>'
            f'<div style="color:{_TEXTO};font-size:19px;font-weight:700;">'
            f'{izq[1]:.2f}</div></td>'
            f'<td width="10%" style="text-align:center;color:{_MUTED};font-size:18px;">&rarr;</td>'
            f'<td width="45%" style="background:#0e131c;border:1px solid {borde_der};'
            f'border-radius:12px;padding:12px;text-align:center;">'
            f'<div style="color:{_MUTED};font-size:10px;letter-spacing:1px;'
            f'text-transform:uppercase;">{_esc(der[0])}</div>'
            f'<div style="color:{borde_der};font-size:19px;font-weight:700;">'
            f'{der[1]:.2f}</div></td>'
            f'</tr></table></td></tr>')

    # 4) Contexto en chips pequeños.
    #
    # Van como spans en UNA sola celda, no en celdas de tabla separadas: con una
    # celda por chip la fila no puede partirse y la tarjeta se ensanchaba más
    # allá de los 460 px, desbordando la pantalla del móvil en cuanto había tres
    # chips. Así se reparten en varias líneas cuando no caben.
    chips = ""
    for etiqueta, valor in (("Dirección", d.get("direccion")), ("Hora", d.get("hora")),
                            ("Queda abierto", d.get("restante"))):
        if not valor:
            continue
        chips += (f'<span style="display:inline-block;background:#0e131c;'
                  f'border:1px solid {_BORDE};border-radius:9px;padding:6px 10px;'
                  f'margin:0 6px 6px 0;color:{_MUTED};font-size:11px;">'
                  f'{etiqueta}: <b style="color:{_TEXTO};">{_esc(str(valor))}</b>'
                  f'</span>')
    if chips:
        filas.append(f'<tr><td style="padding:14px 24px 16px 24px;">{chips}</td></tr>')
    return "\n".join(filas)


def _en_automatico() -> bool:
    """¿Corremos desatendidos (GitHub Actions)? Nadie mira la consola."""
    import os
    return os.getenv("GITHUB_ACTIONS", "").lower() == "true"


class Notificador(ABC):
    #: ¿Este canal ENTREGA el aviso al usuario? La consola solo lo MUESTRA: en
    #: una máquina desatendida nadie la lee, así que no cuenta como entrega.
    entrega = True

    @abstractmethod
    def enviar(self, titulo: str, cuerpo: str, evento: Evento = Evento.NUEVA_SENAL,
               html: Optional[str] = None) -> bool:
        """Envía la notificación. ``html`` es opcional (los canales que lo soporten lo usan)."""

    def notificar_senal(self, signal: Signal) -> bool:
        emoji = "🟢" if signal.direccion.value == "compra" else "🔴"
        titulo = f"{emoji} XAU/USD {signal.direccion.value.upper()} @ {signal.entrada:.2f} — señal"
        return self.enviar(titulo, mensaje_de_senal(signal), Evento.NUEVA_SENAL,
                           html=mensaje_html_de_senal(signal))


class NotificadorMultiple(Notificador):
    """Reenvía a varios canales; no falla si alguno individual falla.

    Devuelve verdadero solo si el aviso ha LLEGADO de verdad. La distinción es
    crítica: la consola siempre "funciona", así que antes este método devolvía
    verdadero aunque no hubiera ningún canal real configurado. En GitHub Actions
    eso significaba que, si faltaba o caducaba un secreto SMTP, el vigilante daba
    la señal por avisada, ABRÍA la operación y el usuario no recibía nada —y
    luego le llegaban las salidas de una operación que nunca abrió. Es
    exactamente la operación fantasma que la comprobación del runner existe para
    impedir, colándose por la puerta de atrás.
    """

    def __init__(self, canales: List[Notificador]) -> None:
        self._canales = canales
        self._reales = [c for c in canales if getattr(c, "entrega", True)]
        self._avisado = False

    def enviar(self, titulo: str, cuerpo: str, evento: Evento = Evento.NUEVA_SENAL,
               html: Optional[str] = None) -> bool:
        entregado = mostrado = False
        for canal in self._canales:
            try:
                r = bool(canal.enviar(titulo, cuerpo, evento, html=html))
            except Exception:  # noqa: BLE001 — un canal caído no debe tumbar el resto.
                continue
            if getattr(canal, "entrega", True):
                entregado = entregado or r
            else:
                mostrado = mostrado or r
        if self._reales:
            return entregado
        # Ningún canal de entrega configurado.
        if not self._avisado:
            self._avisado = True
            print("⚠️  NINGÚN canal de aviso configurado (ORO_SMTP_* / "
                  "ORO_TELEGRAM_* / ORO_WEBHOOK_URL). El aviso solo se ha "
                  "impreso por consola.")
        # En local, la consola es un destino legítimo: el usuario la está
        # mirando. Desatendido, no lo es: mejor NO abrir la operación.
        return False if _en_automatico() else mostrado
