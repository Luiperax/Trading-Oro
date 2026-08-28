"""Parte diario del vigilante: "sigo vivo y esto es lo que pasó".

Nace de un problema real: el sistema puede pasar días sin emitir una sola señal
porque sus filtros son muy selectivos y el oro está en rango. Desde fuera, ese
silencio es indistinguible de una avería.

Informa SIEMPRE de la última sesión YA CERRADA, no del día de calendario. Es
importante: GitHub retrasa las tareas programadas de forma muy irregular (se ha
medido desde 30 min hasta 8 h). Cuando el parte se enviaba "de hoy" y llegaba a
la mañana siguiente, resumía un día recién empezado —todo a cero— en vez de la
jornada que acababa de cerrar. Ahora el contenido es correcto llegue cuando
llegue.

    python -m oro.latido            # lo imprime
    python -m oro.latido --email    # lo envía por los canales configurados
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import cargar_configuracion
from .dominio.mercado import HORA_APERTURA_UTC, dia_sesion
from .tiempo import etiqueta_zona, hora_local


def _estado(ruta: str) -> dict:
    p = Path(ruta)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def sesion_a_informar(ahora: datetime) -> date:
    """Última sesión del oro que YA ha cerrado.

    La sesión va de 22:00 a 21:00 UTC. Si la de ahora sigue abierta, se informa
    de la anterior: así el parte dice la verdad aunque se entregue con horas de
    retraso.
    """
    s = dia_sesion(ahora)
    cfg_cierre = cargar_configuracion().riesgo.hora_cierre_utc
    ya_cerro = cfg_cierre <= ahora.hour < HORA_APERTURA_UTC
    return s if ya_cerro else s - timedelta(days=1)


def _motivo_actual(cfg) -> tuple[float | None, str]:
    """Precio actual y por qué NO hay entrada ahora mismo (sin efectos)."""
    try:
        from .datos import ProveedorYahoo
        from .dominio import MarketSnapshot, sesion_de
        from .indicadores import atr as _atr
        from .senales import MotorSenales

        prov = ProveedorYahoo(timeframe=cfg.timeframe)
        df = prov.historico(500)
        precio = float(df["close"].iloc[-1])
        atr_val = float(_atr(df, 14).iloc[-1])
        momento = df.index[-1].to_pydatetime()
        snap = MarketSnapshot(momento=momento, precio=precio, spread=0.2,
                              atr=atr_val, sesion=sesion_de(momento))
        r = MotorSenales(cfg).analizar(df, snap)
        if r.hay_operacion:
            return precio, "hay una oportunidad ahora mismo (se avisará en el próximo ciclo)."
        return precio, "; ".join(r.motivos_no) or r.mensaje
    except Exception as e:  # noqa: BLE001 — el parte no debe caerse por la red.
        return None, f"no se pudo consultar el mercado ({type(e).__name__})."


def _recopilar(cfg, ahora: datetime) -> dict:
    """Reúne todo lo que el parte necesita contar."""
    sesion = sesion_a_informar(ahora)
    est = _estado(os.getenv("ORO_ESTADO", "oro_estado.json"))
    historial = est.get("historial", []) or []

    def _de_la_sesion(tipos):
        out = []
        for h in historial:
            try:
                m = datetime.fromisoformat(str(h.get("momento", "")))
            except ValueError:
                continue
            if dia_sesion(m) == sesion and h.get("tipo") in tipos:
                out.append(h)
        return out

    ultima = None
    for h in historial:
        if h.get("tipo") == "entrada":
            try:
                ultima = datetime.fromisoformat(str(h["momento"]))
            except (ValueError, KeyError):
                pass
            break

    precio, motivo = _motivo_actual(cfg)
    return {
        "sesion": sesion,
        "ahora": ahora,
        "entradas": _de_la_sesion({"entrada"}),
        "salidas": _de_la_sesion({"cierre"}),
        "gestiones": _de_la_sesion({"tp_alcanzado", "mover_stop"}),
        "abiertas": est.get("abiertas", []) or [],
        "dias_sin": (ahora - ultima).days if ultima else None,
        "precio": precio,
        "motivo": motivo,
    }


# ---------- versión de texto (respaldo para clientes sin HTML) ----------
def construir_parte(cfg, ahora: datetime | None = None) -> str:
    d = _recopilar(cfg, ahora or datetime.now(timezone.utc))
    L = ["=" * 46,
         f"  PARTE XAU/USD — sesión del {d['sesion']}",
         "=" * 46,
         f"El vigilante está EN MARCHA. (Horas en {etiqueta_zona(d['ahora'])}, tu hora.)"]
    L.append(f"Oro ahora: {d['precio']:.2f} $" if d["precio"] else "Oro ahora: (sin dato)")
    L.append("")
    L.append(f"En esa sesión: {len(d['entradas'])} entrada(s), {len(d['salidas'])} salida(s), "
             f"{len(d['gestiones'])} aviso(s) de gestión.")
    if d["entradas"] or d["salidas"] or d["gestiones"]:
        L.append("")
        for h in reversed(d["entradas"] + d["gestiones"] + d["salidas"]):
            try:
                hh = hora_local(datetime.fromisoformat(str(h.get("momento", ""))))
            except ValueError:
                hh = "--:--"
            L.append(f"  · {hh}  {str(h.get('mensaje', ''))[:70]}")
    L.append("")
    if d["abiertas"]:
        L.append(f"OPERACIÓN ABIERTA ({len(d['abiertas'])}): se avisará al cerrarse.")
        for a in d["abiertas"]:
            L.append(f"  · {str(a.get('direccion', '')).upper()} desde {a.get('entrada')} "
                     f"| stop {a.get('stop_actual')}")
    else:
        L.append("Sin operaciones abiertas: no hay nada que cerrar ahora mismo.")
        L.append("(Si no recibes avisos de salida es porque no hay nada abierto.)")
    L.append("")
    if not d["entradas"]:
        L.append("No hubo señal en esa sesión. Motivo ahora mismo:")
        L.append(f"  {d['motivo']}")
    if d["dias_sin"] is not None and d["dias_sin"] >= 3:
        L += ["", f"⚠ Llevas {d['dias_sin']} días sin señales. No es una avería: los",
              "  filtros son muy selectivos y el oro lleva en rango."]
    L += ["", "Parte automático. Análisis, no asesoramiento financiero."]
    return "\n".join(L)


# ---------- versión visual (tarjeta HTML, como las señales) ----------
def construir_parte_html(cfg, ahora: datetime | None = None) -> str:
    from .notificaciones.base import (_AMBAR, _BORDE, _FONDO, _FUENTE, _MUTED,
                                      _ORO, _ROJO, _TARJETA, _TEXTO, _VERDE)

    d = _recopilar(cfg, ahora or datetime.now(timezone.utc))
    hay_actividad = bool(d["entradas"] or d["salidas"] or d["gestiones"])
    color = _VERDE if hay_actividad else _ORO
    zona = etiqueta_zona(d["ahora"])

    def _cifra(valor, etiqueta, tono):
        return (f'<td width="33%" align="center" style="padding:6px;">'
                f'<div style="color:{tono};font-size:26px;font-weight:800;line-height:1;">{valor}</div>'
                f'<div style="color:{_MUTED};font-size:11px;text-transform:uppercase;'
                f'letter-spacing:.5px;margin-top:4px;">{etiqueta}</div></td>')

    filas = ""
    for h in reversed(d["entradas"] + d["gestiones"] + d["salidas"]):
        try:
            hh = hora_local(datetime.fromisoformat(str(h.get("momento", ""))))
        except ValueError:
            hh = "--:--"
        tono = {"entrada": _VERDE, "cierre": _ROJO}.get(str(h.get("tipo")), _AMBAR)
        filas += (f'<tr><td style="padding:7px 0;border-top:1px solid {_BORDE};">'
                  f'<span style="color:{tono};font-weight:700;">{hh}</span>'
                  f'<span style="color:{_TEXTO};font-size:13px;"> · '
                  f'{str(h.get("mensaje", ""))[:64]}</span></td></tr>')
    bloque_actividad = (
        f'<table width="100%" style="border-collapse:collapse;margin-top:6px;">{filas}</table>'
        if filas else
        f'<div style="color:{_MUTED};font-size:13px;padding:8px 0;">'
        f'Sin movimientos en esa sesión.</div>')

    if d["abiertas"]:
        det = "".join(
            f'<div style="color:{_TEXTO};font-size:14px;">'
            f'{str(a.get("direccion", "")).upper()} desde <b>{a.get("entrada")}</b> · '
            f'stop {a.get("stop_actual")}</div>' for a in d["abiertas"])
        bloque_abiertas = (
            f'<div style="background:#1a2230;border-left:3px solid {_AMBAR};'
            f'border-radius:8px;padding:12px 14px;margin-top:14px;">'
            f'<div style="color:{_AMBAR};font-size:12px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.5px;">Operación abierta</div>'
            f'{det}<div style="color:{_MUTED};font-size:12px;margin-top:4px;">'
            f'Se te avisará al cerrarse.</div></div>')
    else:
        bloque_abiertas = (
            f'<div style="background:#141c17;border-left:3px solid {_VERDE};'
            f'border-radius:8px;padding:12px 14px;margin-top:14px;">'
            f'<div style="color:{_VERDE};font-size:13px;font-weight:700;">'
            f'✓ Sin operaciones abiertas</div>'
            f'<div style="color:{_MUTED};font-size:12px;margin-top:3px;">'
            f'No hay nada que cerrar. Si no recibes avisos de salida, es por esto.</div></div>')

    bloque_motivo = ""
    if not d["entradas"]:
        bloque_motivo = (
            f'<div style="margin-top:14px;padding-top:12px;border-top:1px solid {_BORDE};">'
            f'<div style="color:{_MUTED};font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.5px;">Por qué no hay señal ahora</div>'
            f'<div style="color:{_TEXTO};font-size:13px;margin-top:4px;">{d["motivo"]}</div></div>')

    bloque_silencio = ""
    if d["dias_sin"] is not None and d["dias_sin"] >= 3:
        bloque_silencio = (
            f'<div style="background:#241f14;border-left:3px solid {_AMBAR};'
            f'border-radius:8px;padding:11px 14px;margin-top:12px;color:{_TEXTO};font-size:13px;">'
            f'⚠ <b>{d["dias_sin"]} días sin señales.</b> No es una avería: los filtros son '
            f'muy selectivos y el oro lleva en rango.</div>')

    precio = f"{d['precio']:.2f} $" if d["precio"] else "sin dato"
    return f"""\
<div style="margin:0;padding:22px 10px;background:{_FONDO};font-family:{_FUENTE};">
 <table role="presentation" align="center" width="100%" style="max-width:460px;margin:0 auto;border-collapse:collapse;">
  <tr><td style="background:{_TARJETA};border:1px solid {_BORDE};border-radius:18px;overflow:hidden;">
   <table role="presentation" width="100%" style="border-collapse:collapse;">
    <tr><td style="background:{color};padding:16px 22px;">
      <div style="color:#0b0e14;font-size:11px;font-weight:700;letter-spacing:2px;">XAU/USD · PARTE DIARIO</div>
      <div style="color:#0b0e14;font-size:21px;font-weight:800;margin-top:2px;">Sesión del {d['sesion']}</div>
    </td></tr>
    <tr><td style="padding:16px 22px 4px;">
      <div style="color:{_MUTED};font-size:12px;">
        ✓ El vigilante está EN MARCHA · Oro ahora <b style="color:{_TEXTO};">{precio}</b>
      </div>
    </td></tr>
    <tr><td style="padding:8px 12px;">
      <table role="presentation" width="100%" style="border-collapse:collapse;background:#111823;border-radius:12px;">
       <tr>{_cifra(len(d['entradas']), 'Entradas', _VERDE)}
           {_cifra(len(d['salidas']), 'Salidas', _ROJO)}
           {_cifra(len(d['gestiones']), 'Gestión', _AMBAR)}</tr>
      </table>
    </td></tr>
    <tr><td style="padding:6px 22px 18px;">
      {bloque_actividad}
      {bloque_abiertas}
      {bloque_motivo}
      {bloque_silencio}
    </td></tr>
    <tr><td style="background:#0e131c;padding:12px 22px;color:{_MUTED};font-size:11px;">
      Horas en {zona} (tu hora) · Parte automático.<br>
      ⚠️ Herramienta de análisis, no asesoramiento financiero.
    </td></tr>
   </table>
  </td></tr>
 </table>
</div>"""


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = cargar_configuracion()
    ahora = datetime.now(timezone.utc)
    texto = construir_parte(cfg, ahora)
    print(texto)
    if "--email" in argv:
        from .cli import _construir_notificador
        from .notificaciones.base import Evento
        ok = _construir_notificador().enviar(
            f"📋 XAU/USD · parte de la sesión del {sesion_a_informar(ahora)}",
            texto, Evento.CAMBIO_MERCADO, html=construir_parte_html(cfg, ahora))
        print("\n(Parte enviado.)" if ok else "\n⚠️  No se pudo enviar el parte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
