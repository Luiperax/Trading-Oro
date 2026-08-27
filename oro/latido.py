"""Parte diario del vigilante: "sigo vivo y esto es lo que ha pasado".

Nace de un problema real: el sistema puede pasar días sin emitir una sola señal
porque sus filtros son muy selectivos y el oro está en rango. Desde fuera, ese
silencio es indistinguible de una avería —y de hecho el usuario lo interpretó
como avería tras 6 días sin avisos—. Este parte se manda una vez al día y dice
con claridad: si está vivo, qué ha hecho hoy, si hay algo abierto y, cuando no
hay señales, POR QUÉ no las hay.

    python -m oro.latido            # lo imprime
    python -m oro.latido --email    # lo envía por los canales configurados
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import cargar_configuracion
from .tiempo import etiqueta_zona, hora_local


def _estado(ruta: str) -> dict:
    p = Path(ruta)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


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


def construir_parte(cfg, ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now(timezone.utc)
    hoy = ahora.date()
    est = _estado(os.getenv("ORO_ESTADO", "oro_estado.json"))
    historial = est.get("historial", []) or []

    def _de_hoy(tipos):
        out = []
        for h in historial:
            try:
                m = datetime.fromisoformat(str(h.get("momento", "")))
            except ValueError:
                continue
            if m.date() == hoy and h.get("tipo") in tipos:
                out.append(h)
        return out

    entradas = _de_hoy({"entrada"})
    salidas = _de_hoy({"cierre"})
    gestiones = _de_hoy({"tp_alcanzado", "mover_stop"})
    abiertas = est.get("abiertas", []) or []

    # Días desde la última señal (mide el silencio de forma objetiva).
    ultima = None
    for h in historial:
        if h.get("tipo") == "entrada":
            try:
                ultima = datetime.fromisoformat(str(h["momento"]))
            except (ValueError, KeyError):
                pass
            break
    dias_sin = (ahora - ultima).days if ultima else None

    precio, motivo = _motivo_actual(cfg)

    L = ["=" * 52, f"  PARTE DIARIO XAU/USD — {hoy}", "=" * 52,
         f"El vigilante está EN MARCHA. (Horas en {etiqueta_zona(ahora)}, tu hora.)"]
    L.append(f"Oro ahora: {precio:.2f} $" if precio else "Oro ahora: (sin dato)")
    L.append("")
    L.append(f"Hoy: {len(entradas)} entrada(s), {len(salidas)} salida(s), "
             f"{len(gestiones)} aviso(s) de gestión.")

    if entradas or salidas or gestiones:
        L.append("")
        for h in reversed(entradas + gestiones + salidas):
            try:
                hh = hora_local(datetime.fromisoformat(str(h.get("momento", ""))))
            except ValueError:
                hh = str(h.get("momento", ""))[11:16]
            L.append(f"  · {hh}  {str(h.get('mensaje',''))[:70]}")

    L.append("")
    if abiertas:
        L.append(f"OPERACIÓN ABIERTA ({len(abiertas)}): se avisará al cerrarse.")
        for a in abiertas:
            L.append(f"  · {str(a.get('direccion','')).upper()} desde {a.get('entrada')} "
                     f"| stop {a.get('stop_actual')}")
    else:
        L.append("Sin operaciones abiertas: no hay nada que cerrar ahora mismo.")
        L.append("(Si no recibes avisos de salida es porque no hay nada abierto.)")

    L.append("")
    if not entradas:
        L.append("Hoy no ha habido señal. Motivo ahora mismo:")
        L.append(f"  {motivo}")
    if dias_sin is not None and dias_sin >= 3:
        L.append("")
        L.append(f"⚠ Llevas {dias_sin} días sin señales. No es una avería: los filtros")
        L.append("  son muy selectivos y el oro lleva en rango. Si quieres MÁS avisos")
        L.append("  (a cambio de menos calidad media) se pueden bajar los umbrales.")

    L += ["", "Parte automático. Análisis, no asesoramiento financiero."]
    return "\n".join(L)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = cargar_configuracion()
    texto = construir_parte(cfg)
    print(texto)
    if "--email" in argv:
        from .cli import _construir_notificador
        from .notificaciones.base import Evento
        ok = _construir_notificador().enviar(
            f"📋 Parte diario XAU/USD — {datetime.now(timezone.utc).date()}",
            texto, Evento.CAMBIO_MERCADO)
        print("\n(Parte enviado.)" if ok else "\n⚠️  No se pudo enviar el parte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
