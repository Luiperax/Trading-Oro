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


def _lote_y_riesgo(signal: Signal):
    """Convierte el tamaño (oz) al LOTE del bróker y calcula la pérdida máxima.

    1 lote estándar de XAU/USD = 100 oz. El lote mínimo habitual es 0.01.
    """
    lote = max(0.01, round(signal.tamano_posicion / 100.0, 2))
    # Pérdida máxima calculada sobre el LOTE que realmente se coloca (1 lote = 100 oz),
    # para que el importe mostrado coincida con lo que se arriesga de verdad.
    perdida_max = abs(signal.entrada - signal.stop_loss) * lote * 100.0
    return lote, perdida_max


def mensaje_de_senal(signal: Signal) -> str:
    """Versión en texto plano (respaldo y para clientes sin HTML)."""
    compra = signal.direccion.value == "compra"
    lineas = [
        f"{'🟢' if compra else '🔴'} NUEVA SEÑAL XAU/USD — {signal.direccion.value.upper()}",
        "",
        f"Entrada:  {signal.entrada:.2f}",
        f"Stop:     {signal.stop_loss:.2f}",
    ]
    for k, tp in enumerate(signal.take_profits, 1):
        lineas.append(f"TP{k}:      {tp.precio:.2f}  ({tp.r_multiple:.1f}R, {tp.fraccion:.0%})")
    lineas += [
        "",
        f"Probabilidad estimada: {signal.probabilidad:.0%}  (no es garantía)",
        f"Confianza: {signal.confianza:.0%}   R:R: {signal.riesgo_recompensa:.2f}",
        "",
        f"👉 LOTE a introducir en el bróker: {_lote_y_riesgo(signal)[0]:.2f}",
        f"   Pérdida máxima si salta el stop: ≈{_lote_y_riesgo(signal)[1]:.0f} (riesgo mínimo por operación)",
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


def mensaje_html_de_senal(signal: Signal) -> str:
    """Tarjeta HTML elegante para el correo (diseño responsive, tema oscuro)."""
    compra = signal.direccion.value == "compra"
    dir_color = _VERDE if compra else _ROJO
    flecha = "▲" if compra else "▼"
    dir_txt = signal.direccion.value.upper()

    niveles = _fila_nivel("Stop Loss", f"{signal.stop_loss:.2f}", _ROJO)
    for k, tp in enumerate(signal.take_profits, 1):
        niveles += _fila_nivel(f"Take Profit {k}", f"{tp.precio:.2f}", _VERDE,
                               f"· {tp.r_multiple:.1f}R · {tp.fraccion:.0%}")

    motivos = "".join(
        f'<tr><td style="color:{_TEXTO};font-size:13px;padding:3px 0;">'
        f'<span style="color:{_VERDE};">✓</span>&nbsp; {m}</td></tr>'
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
        {_pill("R : R", f"{signal.riesgo_recompensa:.2f}", _TEXTO)}
      </tr></table>
      <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:18px;">
       <tr><td style="background:#0e131c;border:1px dashed {_ORO};border-radius:12px;padding:14px 16px;">
         <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;">Lote a introducir en el bróker</div>
         <div style="color:{_ORO};font-size:30px;font-weight:800;">{_lote_y_riesgo(signal)[0]:.2f} <span style="font-size:13px;color:{_MUTED};font-weight:600;">lotes</span></div>
         <div style="color:{_MUTED};font-size:12px;">Pérdida máxima si salta el stop: <b style="color:{_TEXTO};">≈{_lote_y_riesgo(signal)[1]:.0f}</b> (riesgo mínimo por operación)</div>
         <div style="color:{_ROJO};font-size:12px;margin-top:4px;">⚠️ Es LOTES, no onzas. Pon SIEMPRE el Stop Loss.</div>
       </td></tr>
      </table>
      <div style="color:{_MUTED};font-size:11px;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">Motivos de entrada</div>
      <table role="presentation" width="100%" style="border-collapse:collapse;margin-bottom:14px;">{motivos}</table>
      <div style="color:{_MUTED};font-size:12px;line-height:1.5;border-top:1px solid {_BORDE};padding-top:12px;">
        {signal.contexto_tecnico}
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
  <tr><td style="text-align:center;padding:12px;color:#4a5568;font-size:11px;">Sistema XAU/USD · señal generada automáticamente</td></tr>
 </table>
</div>"""


def mensaje_html_evento(titulo: str, cuerpo: str, evento: Evento) -> str:
    """Tarjeta HTML para eventos de gestión (objetivo, break-even, cierre)."""
    color = {
        Evento.TP_ALCANZADO: _VERDE,
        Evento.MOVER_STOP: _AMBAR,
        Evento.CIERRE: _ORO,
    }.get(evento, _ORO)
    return f"""\
<div style="margin:0;padding:22px 10px;background:{_FONDO};font-family:{_FUENTE};">
 <table role="presentation" align="center" width="100%" style="max-width:460px;margin:0 auto;border-collapse:collapse;">
  <tr><td style="background:{_TARJETA};border:1px solid {_BORDE};border-radius:18px;">
   <table role="presentation" width="100%" style="border-collapse:collapse;">
    <tr><td style="background:{color};border-radius:18px 18px 0 0;padding:14px 24px;color:#0b0e14;font-size:18px;font-weight:800;">{titulo}</td></tr>
    <tr><td style="padding:20px 24px;color:{_TEXTO};font-size:15px;line-height:1.6;">{cuerpo}</td></tr>
    <tr><td style="background:#0e131c;border-radius:0 0 18px 18px;padding:12px 24px;color:{_MUTED};font-size:11px;">
      ⚠️ Herramienta de análisis, no asesoramiento financiero.</td></tr>
   </table>
  </td></tr>
 </table>
</div>"""


class Notificador(ABC):
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
    """Reenvía a varios canales; no falla si alguno individual falla."""

    def __init__(self, canales: List[Notificador]) -> None:
        self._canales = canales

    def enviar(self, titulo: str, cuerpo: str, evento: Evento = Evento.NUEVA_SENAL,
               html: Optional[str] = None) -> bool:
        ok = False
        for canal in self._canales:
            try:
                ok = canal.enviar(titulo, cuerpo, evento, html=html) or ok
            except Exception:  # noqa: BLE001 — un canal caído no debe tumbar el resto.
                continue
        return ok
