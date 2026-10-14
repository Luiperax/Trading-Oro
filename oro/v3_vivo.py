"""Los avisos del indicador «XAU/USD — Activo v3», en velas de 1 hora.

    python -m oro.v3_vivo          # una pasada (el vigilante lo llama cada 3 min)

Cada vez que cierra una vela horaria (Dukascopy la publica ~2 minutos
después) se calculan las reglas del v3 sobre ~6 semanas de velas H1 (ver
:mod:`oro.serie_horaria`). Si hay señal y no hay otra operación abierta, llega
un correo para entrar a mercado con el stop y los dos objetivos. Después se
sigue la operación vela a vela: TP1 (se cierra la mitad), TP2 (el resto) o el
stop, cada uno con su aviso, y al terminar se guarda la ficha.

Las reglas y los ajustes son exactamente los medidos en :mod:`oro.estudio_v3`
(H29, H30 y H30-bis, docs/ESTRATEGIAS_MEDIDAS.md), con los parámetros de
:class:`oro.config.ConfiguracionV3`. Lo medido, sin adornos: fuera de muestra
−0,0005 R por operación (t = −0,02), ni gana ni pierde; en 21 años, −0,023.
No es una ventaja demostrada.

Estado: ``oro_v3.json`` (última vela procesada, operación abierta y avisos
mandados). Registro: ``oro_v3.jsonl``.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

RUTA_V3 = "oro_v3.json"
RUTA_V3_REGISTRO = "oro_v3.jsonl"
VELA = pd.Timedelta(hours=1)
_FED: dict = {}


def _ruta() -> Path:
    return Path(os.getenv("ORO_RUTA_V3", RUTA_V3))


def _ruta_registro() -> Path:
    return Path(os.getenv("ORO_RUTA_V3_REGISTRO", RUTA_V3_REGISTRO))


def _cargar() -> dict:
    try:
        return json.loads(_ruta().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar(estado: dict) -> None:
    try:
        _ruta().write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as e:  # noqa: BLE001
        print(f"⚠️  v3: no se pudo guardar el estado ({e}).")


def _anotar(ficha: dict) -> None:
    try:
        with _ruta_registro().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ficha, ensure_ascii=False) + "\n")
    except OSError as e:  # noqa: BLE001
        print(f"⚠️  v3: no se pudo guardar la ficha ({e}).")


def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t if t.tzinfo is not None else t.tz_localize("UTC")


# ---------------------------------------------------------------------------
# Seguimiento de la operación abierta
# ---------------------------------------------------------------------------
def _orden_en_vela(op: dict, hora: pd.Timestamp, proveedor) -> Optional[str]:
    """Si una vela toca stop y objetivo, qué fue primero según los ticks de
    esa hora ("stop" / "objetivo"), o None si no se puede saber."""
    if proveedor is None or not hasattr(proveedor, "velas_minuto"):
        return None
    try:
        m = proveedor.velas_minuto(hora.to_pydatetime())
    except Exception:  # noqa: BLE001
        return None
    if m is None or not len(m):
        return None
    s = op["dir"]
    objetivo = op["tp2"] if op.get("tp1_en") else op["tp1"]
    for _, v in m.iterrows():
        toca_stop = (v["low"] <= op["stop"]) if s > 0 else (v["high"] >= op["stop"])
        toca_obj = (v["high"] >= objetivo) if s > 0 else (v["low"] <= objetivo)
        if toca_stop:
            return "stop"                    # en el mismo minuto, prudencia
        if toca_obj:
            return "objetivo"
    return None


def seguir_operacion(op: dict, serie: pd.DataFrame, proveedor=None) -> list[dict]:
    """Reproduce la operación con las velas posteriores a su señal.

    Devuelve la lista de sucesos (entrada, tp1, tp2, stop) con su momento y
    precio, en orden. Es la misma lógica que :func:`oro.estudio_v3.simular`:
    entrada en la apertura de la vela siguiente a la señal, TP1 cierra la
    mitad, el stop no se mueve, y si una vela toca stop y objetivo se mira qué
    fue primero en sus ticks (y si no se puede, cuenta el stop).
    """
    s = op["dir"]
    t_senal = _ts(op["t"])
    velas = serie[serie.index >= t_senal + VELA]
    sucesos: list[dict] = []
    if velas.empty:
        return sucesos
    entrada = float(velas["open"].iloc[0])
    sucesos.append({"tipo": "entrada", "t": velas.index[0].isoformat(), "precio": entrada})
    if s * (op["stop"] - entrada) >= 0:
        # Abre ya al otro lado del stop (un hueco, casi siempre tras el fin de
        # semana): no hay operación, igual que en la medición.
        sucesos.append({"tipo": "anulada", "t": velas.index[0].isoformat(), "precio": entrada})
        return sucesos
    estado = dict(op)
    for t, v in velas.iterrows():
        peor = v["low"] if s > 0 else v["high"]
        mejor = v["high"] if s > 0 else v["low"]
        objetivo = estado["tp2"] if estado.get("tp1_en") else estado["tp1"]
        toca_stop = s * (peor - estado["stop"]) <= 0
        toca_obj = s * (mejor - objetivo) >= 0
        if toca_stop and toca_obj:
            primero = _orden_en_vela(estado, t, proveedor) or "stop"
            toca_obj = primero == "objetivo"
            toca_stop = not toca_obj
        if toca_stop:
            sucesos.append({"tipo": "stop", "t": t.isoformat(), "precio": estado["stop"]})
            break
        if toca_obj and not estado.get("tp1_en"):
            estado["tp1_en"] = t.isoformat()
            sucesos.append({"tipo": "tp1", "t": t.isoformat(), "precio": estado["tp1"]})
            # ¿Llega también al TP2 en la misma vela? Solo sin tocar el stop.
            if s * (mejor - estado["tp2"]) >= 0:
                sucesos.append({"tipo": "tp2", "t": t.isoformat(), "precio": estado["tp2"]})
                break
            continue
        if toca_obj:
            sucesos.append({"tipo": "tp2", "t": t.isoformat(), "precio": estado["tp2"]})
            break
    return sucesos


def _resultado(op: dict, sucesos: list[dict]) -> Optional[dict]:
    """La ficha de una operación terminada (None si sigue abierta)."""
    from .spread import spread_de

    final = sucesos[-1] if sucesos else None
    if final is None or final["tipo"] not in ("stop", "tp2"):
        return None
    s = op["dir"]
    entrada = sucesos[0]["precio"]
    riesgo = abs(entrada - op["stop"])
    tp1 = next((x for x in sucesos if x["tipo"] == "tp1"), None)
    salida1 = tp1["precio"] if tp1 else final["precio"]
    salida2 = final["precio"]
    r_bruto = s * (0.5 * (salida1 - entrada) + 0.5 * (salida2 - entrada)) / riesgo
    # Noches (rollover de las 21:00 UTC) con la financiación de CFD medida.
    t0, t1 = _ts(sucesos[0]["t"]), _ts(final["t"])
    k = t0.normalize() + pd.Timedelta(hours=21)
    if k <= t0:
        k += pd.Timedelta(days=1)
    noches = 0
    while k < t1:
        noches += 1
        k += pd.Timedelta(days=1)
    tf = _tipo_fed()
    tasa = -(tf + 0.025) if s > 0 else (tf - 0.025)
    fin = noches * tasa * entrada / 365
    coste = spread_de(t0.year) + 0.25
    return {"t": op["t"], "dir": "compra" if s > 0 else "venta", "entrada": round(entrada, 2),
            "stop": round(op["stop"], 2), "tp1": round(op["tp1"], 2), "tp2": round(op["tp2"], 2),
            "riesgo": round(riesgo, 2), "salida": final["t"], "motivo": final["tipo"],
            "tp1_alcanzado": tp1 is not None, "noches": noches,
            "r_bruto": round(r_bruto, 4), "r_neto": round(r_bruto + (fin - coste) / riesgo, 4),
            "papel": op.get("papel", False)}


def _tipo_fed() -> float:
    if "v" not in _FED:
        try:
            from .estudio_v3 import tipo_fed
            serie = tipo_fed()
            _FED["v"] = float(serie.iloc[-1]) if len(serie) else 0.04
        except Exception:  # noqa: BLE001
            _FED["v"] = 0.04
    return _FED["v"]


def _apertura(desde: pd.Timestamp) -> pd.Timestamp:
    """La primera hora con el mercado abierto a partir de ``desde``.

    La última vela de la sesión (20:00-21:00 UTC) cierra, en horario de verano
    de Nueva York, justo cuando el oro hace su parada diaria, y el viernes,
    cuando cierra el fin de semana. La medición entra en la apertura siguiente;
    el correo tiene que decir lo mismo, no «entra ya» con el mercado cerrado.
    """
    from .datos.dukascopy_vivo import ProveedorDukascopyVivo

    h = desde
    for _ in range(80):
        if not ProveedorDukascopyVivo.mercado_cerrado(h.to_pydatetime()):
            return h
        h += VELA
    return desde


# ---------------------------------------------------------------------------
# Correos
# ---------------------------------------------------------------------------
_MEDIDO = ("Medido sobre 21 años (2006-2026) con todos los costes: −0,023 R por "
           "operación (t = −1,03), en positivo 8 de 21 años. En 2016-2026, que "
           "no se usó para elegir los ajustes, −0,0005 R (t = −0,02): ni gana ni "
           "pierde; solo 2022-2026, +0,074 R (t = 1,61). Acierta el 41 %. NO es "
           "una ventaja demostrada: opera solo lo que puedas perder.")


def _pref(op: dict) -> str:
    return "📝 [papel] " if op.get("papel") else ""


def correo_entrada(op: dict) -> tuple[str, str]:
    from .tiempo import fecha_hora_local, hora_local

    compra = op["dir"] > 0
    lado = "COMPRA" if compra else "VENTA"
    t = _ts(op["t"])
    abre = _ts(op["abre"]).to_pydatetime() if op.get("abre") else None
    cuando = f"al abrir, {fecha_hora_local(abre)}" if abre else "ahora"
    titulo = (f"{_pref(op)}{'🟢' if compra else '🔴'} v3 · {lado} XAU/USD {cuando} "
              f"(~{op['ref']:.2f}) · SL {op['stop']:.2f} · TP1 {op['tp1']:.2f} · "
              f"TP2 {op['tp2']:.2f}")
    if abre:
        que_hacer = (f"QUÉ HACER: el mercado está cerrado ahora (parada diaria o fin "
                     f"de semana). Entra a mercado en {lado} en cuanto abra, a las "
                     f"{fecha_hora_local(abre)} (hora de Madrid), con estos niveles "
                     f"(precio de referencia {op['ref']:.2f}). Si abre ya más allá "
                     f"del stop, no entres: te llegará un aviso.")
    else:
        que_hacer = (f"QUÉ HACER: entra a mercado en {lado} ya (precio de referencia "
                     f"{op['ref']:.2f}).")
    cuerpo = "\n".join([
        f"Señal del v3 (velas de 1 hora) al cierre de la vela de las "
        f"{hora_local(t.to_pydatetime())}-{hora_local((t + VELA).to_pydatetime())} "
        f"(hora de Madrid), con {op['puntos']} de 6 confirmaciones.",
        "",
        f"{que_hacer} Abre dos posiciones de la MITAD del tamaño que "
        f"decidas, las dos con stop loss en {op['stop']:.2f}:",
        f"  · una con take profit en {op['tp1']:.2f} (TP1, a 3 ATR);",
        f"  · otra con take profit en {op['tp2']:.2f} (TP2, a 5 ATR).",
        "El stop no se mueve y no hay hora de cierre: la operación termina "
        "en el stop o en el TP2. Dura unas 40 horas de mediana y suele dormir "
        "alguna noche (tu bróker cobra la financiación).",
        f"Riesgo si salta el stop: {abs(op['ref'] - op['stop']):.2f} $ por onza.",
        "",
        _MEDIDO,
        "",
        "⚠️ Herramienta de análisis, no asesoramiento financiero.",
    ])
    if op.get("papel"):
        cuerpo = "📝 SOLO PAPEL — NO OPERES CON DINERO REAL\n\n" + cuerpo
    return titulo, cuerpo


def correo_suceso(op: dict, x: dict, ficha: Optional[dict]) -> tuple[str, str]:
    lado = "compra" if op["dir"] > 0 else "venta"
    if x["tipo"] == "anulada":
        titulo = (f"{_pref(op)}⚪ v3: NO entres — el precio abrió en {x['precio']:.2f}, "
                  f"más allá del stop ({op['stop']:.2f})")
        cuerpo = (f"La {lado} queda anulada: el mercado ha abierto ya al otro lado "
                  f"del stop, así que no hay operación (igual que en la medición). "
                  f"Si llegaste a entrar, sal.")
        return titulo, cuerpo
    if x["tipo"] == "tp1":
        titulo = f"{_pref(op)}✅ v3: TP1 alcanzado ({x['precio']:.2f}) — la mitad cerrada"
        cuerpo = (f"Tu {lado} ha llegado al TP1 en {x['precio']:.2f}: la mitad "
                  f"de la posición queda cerrada por su take profit. La otra "
                  f"mitad sigue con el stop en {op['stop']:.2f} y el TP2 en "
                  f"{op['tp2']:.2f}. Si tu bróker no cerró la mitad, ciérrala.")
    elif x["tipo"] == "tp2":
        titulo = f"{_pref(op)}✅ v3: TP2 alcanzado ({x['precio']:.2f}) — operación terminada"
        cuerpo = (f"Tu {lado} ha llegado al TP2 en {x['precio']:.2f}: operación "
                  f"terminada.")
    else:
        titulo = f"{_pref(op)}🛑 v3: stop tocado ({x['precio']:.2f}) — operación terminada"
        cuerpo = (f"Tu {lado} ha tocado el stop en {x['precio']:.2f}: lo que "
                  f"quedara abierto se ha cerrado. Comprueba en el bróker que "
                  f"no queda nada.")
    if ficha is not None:
        cuerpo += (f"\n\nResultado: {ficha['r_neto']:+.2f} R con costes y "
                   f"financiación ({ficha['noches']} noche(s)).")
    return titulo, cuerpo


# ---------------------------------------------------------------------------
# La pasada
# ---------------------------------------------------------------------------
def ejecutar(ahora: Optional[dt.datetime] = None, serie: Optional[pd.DataFrame] = None,
             proveedor=None) -> int:
    from .cli import _construir_notificador
    from .config import cargar_configuracion
    from .estudio_v3 import indicadores, senales

    cfg = cargar_configuracion()
    c = cfg.v3
    if not c.activa:
        return 0
    ahora = _ts(ahora or dt.datetime.now(dt.timezone.utc))
    if serie is None:
        from .plan_sesion import VELAS_EN_VIVO, _proveedor
        from .serie_horaria import serie_h1

        proveedor = proveedor or _proveedor(False)
        serie = serie_h1(proveedor.historico(VELAS_EN_VIVO), ahora.date())
    if serie is None or len(serie) < 300:
        print(f"v3: solo {0 if serie is None else len(serie)} velas H1; hacen falta "
              f"unas 300 para los indicadores. Nada que hacer.")
        return 0
    serie = serie[serie.index + VELA <= ahora]          # solo velas cerradas
    estado = _cargar()
    avisados = set(estado.get("avisados", []))
    noti = None

    def _enviar(clave, titulo, cuerpo):
        nonlocal noti
        if clave in avisados:
            return True
        noti = noti or _construir_notificador()
        from .notificaciones.base import Evento
        from .notificaciones.plan import mensaje_html_de_aviso
        if noti.enviar(titulo, cuerpo, Evento.NUEVA_SENAL,
                       html=mensaje_html_de_aviso(titulo, cuerpo)):
            avisados.add(clave)
            return True
        print(f"⚠️  v3: aviso no enviado ({clave}); se reintentará.")
        return False

    # 1) La operación abierta.
    op = estado.get("abierta")
    if op:
        sucesos = seguir_operacion(op, serie, proveedor)
        ficha = _resultado(op, sucesos)
        entregados = [_enviar(f"{op['t']}:{x['tipo']}",
                              *correo_suceso(op, x, ficha if x is sucesos[-1] else None))
                      for x in sucesos[1:]]
        anulada = bool(sucesos) and sucesos[-1]["tipo"] == "anulada"
        # Solo se da por terminada cuando el último aviso ha llegado: si no,
        # la pasada siguiente lo reintenta con la operación aún guardada.
        if (ficha is not None or anulada) and all(entregados):
            if ficha is not None:
                _anotar(ficha)
                print(f"v3: operación de {op['t']} terminada en {ficha['motivo']}: "
                      f"{ficha['r_neto']:+.2f} R.")
            else:
                print(f"v3: operación de {op['t']} anulada: abrió más allá del stop.")
            estado["abierta"] = None
            op = None

    # 2) ¿Señal nueva en las velas cerradas desde la última revisada? Casi
    #    siempre es una; son más si una hora llegó tarde o el vigilante estuvo
    #    parado (y entonces solo se manda lo que aún llega a tiempo).
    procesada = estado.get("procesada")
    pendientes = (serie.index[serie.index > _ts(procesada)] if procesada
                  else serie.index[-1:])
    falta = _hueco_reciente(serie)
    tolerancia = pd.Timedelta(minutes=c.max_retraso_min)
    if len(pendientes) and falta is not None and ahora - (falta + VELA) <= tolerancia:
        # Falta una hora reciente (Dukascopy a veces da 503 durante varios
        # minutos): sin ella los indicadores no son los medidos y su posible
        # señal se perdería. Se espera; la pasada siguiente la vuelve a pedir.
        print(f"v3: falta la vela de las {falta:%H:%M} UTC; se espera a que llegue.")
        pendientes = pendientes[:0]
    if len(pendientes):
        d = senales(indicadores(serie[["open", "high", "low", "close"]]),
                    min_score=c.min_score, h4_obligatorio=c.h4_obligatorio)
    for t in pendientes:
        s = int(d.at[t, "senal"])
        retraso = ahora - (t + VELA)
        if s != 0 and op is None and retraso <= tolerancia:
            fila = d.loc[t]
            ref, atr = float(fila["close"]), float(fila["atr"])
            nueva = {"t": t.isoformat(), "dir": s, "ref": round(ref, 2),
                     "atr": round(atr, 3), "puntos": _puntos(d, s, t),
                     "stop": round(ref - s * c.sl_atr * atr, 2),
                     "tp1": round(ref + s * c.tp1_atr * atr, 2),
                     "tp2": round(ref + s * c.tp2_atr * atr, 2),
                     "papel": c.papel}
            abre = _apertura(t + VELA)
            if abre != t + VELA:
                nueva["abre"] = abre.isoformat()
            if _enviar(f"{nueva['t']}:entrada", *correo_entrada(nueva)):
                estado["abierta"] = op = nueva
                print(f"v3: señal de {'compra' if s > 0 else 'venta'} a las "
                      f"{t:%H:%M} UTC, enviada.")
            else:
                estado["avisados"] = sorted(avisados)
                _guardar(estado)
                return 1                             # se reintenta sin marcar
        elif s != 0 and op is None:
            print(f"v3: señal de {t:%d-%m %H:%M} UTC descartada: llega "
                  f"{int(retraso.total_seconds() // 60)} min tarde.")
        estado["procesada"] = t.isoformat()

    estado["avisados"] = sorted(avisados)[-200:]
    _guardar(estado)
    return 0


def _hueco_reciente(serie: pd.DataFrame, horas: int = 6) -> Optional[pd.Timestamp]:
    """La hora de mercado abierto más antigua que falta entre las últimas."""
    from .datos.dukascopy_vivo import ProveedorDukascopyVivo

    ultima = serie.index[-1]
    h = ultima - pd.Timedelta(hours=horas)
    while h < ultima:
        if h not in serie.index and not ProveedorDukascopyVivo.mercado_cerrado(h.to_pydatetime()):
            return h
        h += VELA
    return None


def _puntos(d: pd.DataFrame, s: int, t: Optional[pd.Timestamp] = None) -> int:
    """Cuántas de las 6 confirmaciones tiene la señal (para el correo)."""
    i = d.index.get_loc(t) if t is not None else len(d) - 1
    f = d.iloc[i]
    p = d.iloc[i - 1]
    q = d.iloc[i - 2]
    c = f["close"]
    if s > 0:
        return int((c > f["ema50h4"]) + (f["ema21"] > f["ema50"])
                   + ((f["rsi"] > p["rsi"] > q["rsi"]) and f["rsi"] < 60)
                   + (f["macdh"] > p["macdh"] > q["macdh"])
                   + (f["ema21"] * 0.994 < c < f["ema21"] * 1.008 and f["ema21"] > f["ema50"])
                   + (f["adx"] > 18))
    return int((c < f["ema50h4"]) + (f["ema21"] < f["ema50"])
               + ((f["rsi"] < p["rsi"] < q["rsi"]) and f["rsi"] > 40)
               + (f["macdh"] < p["macdh"] < q["macdh"])
               + (f["ema21"] * 0.992 < c < f["ema21"] * 1.006 and f["ema21"] < f["ema50"])
               + (f["adx"] > 18))


def main(argv: Optional[list[str]] = None) -> int:
    return ejecutar()


if __name__ == "__main__":
    sys.exit(main())
