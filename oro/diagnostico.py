"""Diagnóstico de las SEÑALES ENVIADAS: ¿se cumplieron? y sobre todo, ¿por qué?

A diferencia de ``oro.informe`` (que da el marcador: acierto, Profit Factor…),
aquí el sistema **analiza sus propias órdenes** para entender POR QUÉ salieron
bien o mal, y así ir mejorándolas. Todo se calcula a partir de las señales que el
vigilante te mandó y su resultado real (``operaciones_oro.jsonl``); NO usa tu
operativa personal del bróker (el sistema no la ve).

Analiza:

* **Calibración**: cuando el sistema te dijo "confianza alta", ¿acertó más? Si su
  propia confianza no distingue ganadoras de perdedoras, hay que mejorarla.
* **Por dirección**: ¿acierta más en compras o en ventas?
* **Por hora (UTC)**: ¿a qué horas se cumplen más sus señales?
* **Motivo de cierre**: cuántas por objetivo, por stop o por cierre intradía.
* **Condiciones de mercado**: qué indicadores separan mejor a las que se
  cumplieron de las que fallaron (en lenguaje claro).

Uso:
    python -m oro.diagnostico            # todo el histórico
    python -m oro.diagnostico --mes 2026-08
    python -m oro.diagnostico --email    # lo envía por los canales configurados

Honestidad estadística: con pocas señales las conclusiones son orientativas. El
diagnóstico avisa cuando aún no hay datos suficientes y nunca afirma un patrón
que no se sostenga en el número de señales disponible.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .config import cargar_configuracion
from .informe import _cargar, _filtrar_mes, construir_resumen

# Mínimos para no sacar conclusiones de la nada.
_MIN_TOTAL = 12          # por debajo, solo marcador; el "porqué" no es fiable.
_MIN_GRUPO = 4           # tamaño mínimo de un grupo para compararlo.

# Nombres legibles de las condiciones (features) que guarda cada señal.
_ETIQUETA_FEATURE = {
    "ret_1": "impulso de la última vela",
    "ret_5": "impulso de las últimas 5 velas",
    "ret_20": "impulso de las últimas 20 velas",
    "dist_ema20_atr": "distancia a la media de 20",
    "dist_ema50_atr": "distancia a la media de 50",
    "dist_ema200_atr": "distancia a la media de 200 (tendencia de fondo)",
    "pendiente_ema50": "pendiente de la media de 50 (fuerza de tendencia)",
    "rsi_14": "RSI (sobrecompra/sobreventa)",
    "rsi_norm": "RSI normalizado",
    "macd_hist_norm": "impulso del MACD",
    "adx": "fuerza de la tendencia (ADX)",
    "di_diff": "dirección dominante (+DI vs -DI)",
    "bb_pct_b": "posición dentro de las Bandas de Bollinger",
    "bb_ancho": "anchura de las Bandas (volatilidad)",
    "atr_rel": "volatilidad relativa (ATR/precio)",
    "atr_z": "volatilidad frente a su media",
    "dist_vwap_atr": "distancia al precio medio del día (VWAP)",
    "vol_rel": "volumen frente a lo normal",
    "cuerpo_rel": "tamaño del cuerpo de la vela",
    "mecha_sup_rel": "mecha superior de la vela",
    "mecha_inf_rel": "mecha inferior de la vela",
}
# Codificaciones cíclicas de la sesión: se analizan aparte (por hora), no aquí.
_FEATURES_EXCLUIDAS = {"sesion_sin", "sesion_cos"}


def _tasa(ops: list) -> float:
    ganadas = sum(1 for o in ops if o.get("resultado_r", 0.0) > 0)
    return ganadas / len(ops) if ops else 0.0


def _auc_una(valores: list, labels: list) -> float:
    """AUC de una sola condición: P(valor en ganadora > valor en perdedora).

    0.5 = no distingue; >0.5 = a mayor valor, más se cumple; <0.5 = al revés.
    Cálculo directo por pares (Mann-Whitney); N es pequeño, así que sobra.
    """
    pos = [v for v, l in zip(valores, labels) if l == 1 and v is not None]
    neg = [v for v, l in zip(valores, labels) if l == 0 and v is not None]
    if not pos or not neg:
        return 0.5
    mayor = igual = 0
    for a in pos:
        for b in neg:
            if a > b:
                mayor += 1
            elif a == b:
                igual += 1
    return (mayor + 0.5 * igual) / (len(pos) * len(neg))


def _bloque_calibracion(ops: list) -> list[str]:
    """¿La CONFIANZA que declara el sistema predice de verdad el resultado?"""
    tramos = [("alta (≥0.70)", 0.70, 1.01),
              ("media (0.62–0.70)", 0.62, 0.70),
              ("justa (<0.62)", 0.0, 0.62)]
    lineas = ["", "¿Su propia CONFIANZA acierta? (calibración)"]
    hubo = False
    for nombre, lo, hi in tramos:
        grupo = [o for o in ops if lo <= o.get("confianza", 0.0) < hi]
        if len(grupo) >= _MIN_GRUPO:
            hubo = True
            lineas.append(f"  · Confianza {nombre}: {_tasa(grupo):.0%} cumplidas "
                          f"({sum(1 for o in grupo if o.get('resultado_r',0)>0)}/{len(grupo)})")
    if not hubo:
        return ["", "¿Su propia confianza acierta? Aún pocas señales por tramo para saberlo."]
    lineas.append("  → Si a más confianza NO sube el % de cumplidas, la confianza")
    lineas.append("    todavía no aporta y el aprendizaje debe corregirla.")
    return lineas


def _bloque_por_clave(ops: list, clave_fn, titulo: str, orden=None) -> list[str]:
    grupos: dict = {}
    for o in ops:
        grupos.setdefault(clave_fn(o), []).append(o)
    claves = orden or sorted(grupos)
    lineas = ["", titulo]
    hubo = False
    for k in claves:
        grupo = grupos.get(k, [])
        if len(grupo) >= _MIN_GRUPO:
            hubo = True
            lineas.append(f"  · {k}: {_tasa(grupo):.0%} cumplidas ({len(grupo)} señales)")
    if not hubo:
        lineas.append("  (aún pocas señales por grupo para comparar)")
    return lineas


def _bloque_condiciones(ops: list) -> list[str]:
    """Qué condiciones de mercado separan mejor las cumplidas de las fallidas."""
    con_feat = [o for o in ops if o.get("features") and "label" in o]
    if len(con_feat) < _MIN_TOTAL:
        return ["", "¿Por qué se cumplen o fallan? Aún pocas señales con condiciones "
                "registradas para un análisis fiable."]
    labels = [int(o["label"]) for o in con_feat]
    if len(set(labels)) < 2:
        return ["", "¿Por qué se cumplen o fallan? Todavía no hay cumplidas Y fallidas "
                "suficientes para comparar."]

    ranking = []
    for feat, etiqueta in _ETIQUETA_FEATURE.items():
        if feat in _FEATURES_EXCLUIDAS:
            continue
        valores = [o["features"].get(feat) for o in con_feat]
        if sum(1 for v in valores if v is not None) < _MIN_TOTAL:
            continue
        auc = _auc_una(valores, labels)
        ranking.append((abs(auc - 0.5), auc, etiqueta))
    ranking.sort(reverse=True)

    lineas = ["", "¿Por qué se cumplen o fallan? (condiciones que más influyen)"]
    if not ranking or ranking[0][0] < 0.08:
        lineas.append("  Ninguna condición separa con claridad todavía: con estas señales,")
        lineas.append("  el resultado se parece más al azar. Hacen falta más datos.")
        return lineas
    for sep, auc, etiqueta in ranking[:4]:
        sentido = "ALTOS" if auc > 0.5 else "BAJOS"
        lineas.append(f"  · Se cumplen más con {etiqueta} en valores {sentido} "
                      f"(poder de separación {sep*2:.0%}).")
    lineas.append("  → El aprendizaje usa estas condiciones para afinar las próximas órdenes.")
    return lineas


def _bloque_motivos(ops: list) -> list[str]:
    """¿Qué motivos de entrada funcionan y cuáles no?

    Es la parte de "cómo lo puedo hacer mejor" en el lenguaje que el usuario leyó
    en el correo, no en features numéricas que nadie interpreta. Compara la tasa
    de acierto CON el motivo presente frente a SIN él: un motivo que aparece en
    todas las señales no explica nada, aunque la tasa parezca alta.
    """
    con_motivos = [o for o in ops if o.get("motivos") and "label" in o]
    if len(con_motivos) < _MIN_TOTAL:
        faltan = _MIN_TOTAL - len(con_motivos)
        return ["", "¿Qué motivos funcionan mejor? Faltan "
                f"{faltan} señales con motivos registrados para poder compararlos."]

    todos = sorted({m for o in con_motivos for m in o["motivos"]})
    filas = []
    for motivo in todos:
        con = [o for o in con_motivos if motivo in o["motivos"]]
        sin = [o for o in con_motivos if motivo not in o["motivos"]]
        if len(con) < _MIN_GRUPO or len(sin) < _MIN_GRUPO:
            continue          # sin contraste no se puede atribuir nada al motivo.
        t_con = sum(int(o["label"]) for o in con) / len(con)
        t_sin = sum(int(o["label"]) for o in sin) / len(sin)
        filas.append((t_con - t_sin, t_con, len(con), motivo))
    if not filas:
        return ["", "¿Qué motivos funcionan mejor? Todos aparecen casi siempre (o casi "
                "nunca): sin contraste no se puede saber cuál aporta."]

    filas.sort(reverse=True)
    # El signo manda: poner un ✓ a un motivo que RESTA acierto es peor que no
    # decir nada, porque invita a fiarse justo de lo que está haciendo daño.
    _RELEVANTE = 0.05
    ayudan = [f for f in filas if f[0] >= _RELEVANTE][:3]
    estorban = [f for f in filas if f[0] <= -_RELEVANTE][-2:]

    lineas = ["", "¿Qué motivos funcionan mejor? (acierto con el motivo vs sin él)"]
    if not ayudan and not estorban:
        lineas.append("  Ninguno destaca todavía: con estas señales, aciertan más o menos")
        lineas.append("  igual estén presentes o no. Hacen falta más datos.")
        return lineas

    def _linea(marca, dif, t_con, n, motivo, cola=""):
        corto = motivo[:66] + ("…" if len(motivo) > 66 else "")
        lineas.append(f"  {marca} {corto}")
        lineas.append(f"      {t_con:.0%} de acierto en {n} señales "
                      f"({dif:+.0%} frente a cuando no aparece){cola}")

    for dif, t_con, n, motivo in ayudan:
        _linea("✓", dif, t_con, n, motivo)
    for dif, t_con, n, motivo in estorban:
        _linea("✗", dif, t_con, n, motivo, ": NO está ayudando")
    lineas.append("  ⚠️ Orientativo: con pocas señales, estas diferencias pueden ser azar.")
    return lineas


def _hora(o: dict) -> str:
    ap = str(o.get("apertura", ""))
    return f"{ap[11:13]}:00 UTC" if len(ap) >= 13 else "?"


def _motivo(o: dict) -> str:
    est = str(o.get("estado", "")).lower()
    if "tp" in est:
        return "objetivo alcanzado"
    if "sl" in est:
        return "stop (pérdida)"
    return "cierre intradía / break-even"


def construir_diagnostico(ops: list, titulo: str = "DIAGNÓSTICO DE SEÑALES — XAU/USD") -> str:
    """Marcador + análisis del PORQUÉ, para que el sistema mejore sus órdenes."""
    partes = [construir_resumen(ops, titulo)]
    if not ops:
        return partes[0]
    if len(ops) < _MIN_TOTAL:
        partes.append("\n" + "-" * 52)
        partes.append(f"Análisis del porqué: aún hay {len(ops)} señales cerradas; a partir "
                      f"de ~{_MIN_TOTAL} el diagnóstico empieza a ser fiable. De momento, "
                      "solo el marcador de arriba.")
        return "\n".join(partes)

    lineas = ["\n" + "-" * 52, "ANÁLISIS: por qué se cumplen o fallan sus señales"]
    lineas += _bloque_calibracion(ops)
    lineas += _bloque_por_clave(ops, lambda o: str(o.get("direccion", "?")).upper(),
                                "Por dirección:")
    lineas += _bloque_por_clave(ops, _hora, "Por hora de entrada (UTC):")
    lineas += _bloque_por_clave(ops, _motivo, "Cómo se cerraron:")
    lineas += _bloque_motivos(ops)
    lineas += _bloque_condiciones(ops)
    lineas += ["", "Esto lo usa el sistema para APRENDER de sus propias órdenes e ir",
               "mejorándolas. Análisis, no asesoramiento financiero."]
    return "\n".join(partes + ["\n".join(lineas)])


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = cargar_configuracion()
    ops = _cargar(Path(cfg.ruta_operaciones))

    mes = None
    if "--mes" in argv:
        i = argv.index("--mes")
        mes = argv[i + 1] if i + 1 < len(argv) else None
    ops_mes = _filtrar_mes(ops, mes)
    titulo = f"DIAGNÓSTICO {mes}" if mes else "DIAGNÓSTICO DE SEÑALES — XAU/USD"
    texto = construir_diagnostico(ops_mes, titulo)
    print(texto)

    if "--email" in argv:
        from .cli import _construir_notificador
        from .notificaciones.base import Evento
        _construir_notificador().enviar(f"🔎 {titulo} — XAU/USD", texto, Evento.CAMBIO_MERCADO)
        print("\n(Diagnóstico enviado por los canales configurados.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
