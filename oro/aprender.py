"""Aprendizaje a partir del HISTÓRICO COMPLETO, y vigilancia de lo que pasa en vivo.

QUÉ CAMBIÓ Y POR QUÉ
--------------------
La versión anterior aprendía solo de las operaciones enviadas en vivo y exigía
50 para empezar. Llevaba meses parada en "datos insuficientes" con 22, mientras
había más de dos mil operaciones en el histórico calculadas con las MISMAS
funciones. Era un error de diseño: no hay ninguna razón para esperar años a
juntar en vivo lo que ya está medido.

Ahora hace dos cosas distintas, y la segunda es la que de verdad vale:

1. APRENDER. Reconstruye el histórico con :mod:`oro.historico` y busca un
   filtro que mejore la estrategia. Con la evidencia actual NO encuentra
   ninguno, y eso es un resultado, no un fallo: ver el apartado siguiente.

2. VIGILAR. Compara lo que está pasando en vivo con lo que el histórico dice
   que debería pasar, y avisa si se separan más de lo que explica el azar. Esto
   sí es útil desde la primera semana, porque no necesita descubrir nada: solo
   comprobar que la estrategia sigue comportándose como se midió.

LO QUE YA SE PROBÓ Y NO FUNCIONA (no repetirlo)
-----------------------------------------------
Medido sobre el histórico entero, fuera de muestra, entrenando con los años
anteriores y puntuando el siguiente, 18 veces:

* AUC 0,5054 (0,50 es azar), t = 0,63 frente a 0,50, y 10 de 18 años por
  encima de 0,50. El cuartil "mejor" rinde -0,0900 R y el "peor" -0,0738: el
  modelo ordena al revés.
* Los motivos de entrada: 93 distintos, 50 con muestra suficiente, ninguno
  pasa Bonferroni (|t| > 3,29; el mejor da 2,87). Y la prueba que lo cierra:
  "ADX 28" da -0,1724 R y "ADX 29" da +0,1826. Un efecto real no cambia de
  signo entre dos enteros consecutivos.
* Filtrar por coste en R mejora el R por operación y EMPEORA el R al año,
  porque descarta más operaciones de las que compensa.

De ahí la tercera condición de la puerta de promoción: no basta mejorar el R
por operación, hay que mejorar el R AL AÑO. Es el error que este módulo cometía
sin saberlo.

Uso:
    python -m oro.aprender                 # con el histórico ya descargado
    python -m oro.aprender --reconstruir   # descarga y reconstruye primero
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Optional

from .config import cargar_configuracion

# Mínimo para intentar aprender algo. Con el histórico reconstruido se alcanza
# de sobra; con solo las operaciones en vivo no, y así debe ser.
MIN_OPERACIONES = 400

# El año de corte de las mitades bloqueadas. Se eligió antes de medir y no se
# ha tocado después: es lo único que impide ajustar el corte al resultado.
ANIO_CORTE = 2016

AUC_MINIMO = 0.55
P_MAXIMO = 0.05

RUTA_HISTORICO = "historico_ruptura.jsonl"
RUTA_INFORME = "aprendizaje_estado.json"


# --------------------------------------------------------------------------
# lectura
# --------------------------------------------------------------------------
def _leer_jsonl(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    filas = []
    for linea in ruta.open(encoding="utf-8"):
        linea = linea.strip()
        if not linea:
            continue
        try:
            filas.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return filas


def _cerradas(filas: list[dict]) -> list[dict]:
    """Solo las que tienen resultado NETO. Un día sin operación no es un cero.

    Contar los días sin operación como 0 R hundiría la media y haría parecer
    que la estrategia no gana: no es que gane poco, es que esos días no existen
    como operación.
    """
    vistos, salida = set(), []
    for f in filas:
        if f.get("r_neto") is None or not f.get("dia"):
            continue
        clave = (f["dia"], f.get("direccion"))
        if clave in vistos:        # el registro en vivo puede repetir un día.
            continue
        vistos.add(clave)
        salida.append(f)
    return sorted(salida, key=lambda f: f["dia"])


def _t(valores: list[float]) -> float:
    n = len(valores)
    if n < 3:
        return float("nan")
    media = sum(valores) / n
    var = sum((v - media) ** 2 for v in valores) / (n - 1)
    if var <= 0:
        return float("nan")
    return media / math.sqrt(var / n)


def _media(valores: list[float]) -> float:
    return sum(valores) / len(valores) if valores else float("nan")


def _anio(f: dict) -> int:
    return int(f["dia"][:4])


# --------------------------------------------------------------------------
# 1) aprender: ¿hay un filtro que mejore la estrategia?
# --------------------------------------------------------------------------
def _p_auc(y, puntuaciones) -> float:
    """p-valor de una cola de que el AUC sea > 0,50. 1.0 si no se puede calcular.

    En la duda NO se promociona: un modelo que no se puede validar es un modelo
    que no entra en producción.
    """
    import numpy as np

    y = np.asarray(y)
    s = np.asarray(puntuaciones, dtype=float)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 1.0
    try:
        from scipy.stats import mannwhitneyu

        return float(mannwhitneyu(pos, neg, alternative="greater").pvalue)
    except Exception:  # noqa: BLE001 - sin scipy, aproximación normal.
        from .ml.validacion import _auc

        n1, n2 = len(pos), len(neg)
        auc = _auc(y, s)
        if np.isnan(auc):
            return 1.0
        sigma = math.sqrt((n1 + n2 + 1) / (12.0 * n1 * n2))
        if sigma <= 0:
            return 1.0
        z = (auc - 0.5) / sigma
        return float(0.5 * math.erfc(z / math.sqrt(2.0)))


def _condiciones(f: dict) -> dict:
    """Lo que se sabía ANTES de que la orden saltara. Nada de después.

    Si aquí entrara cualquier dato del resultado —lo lejos que llegó, cuándo
    cerró— el modelo acertaría siempre en las pruebas y fallaría siempre en
    producción. Es el fallo que más veces ha aparecido en este proyecto.
    """
    amplitud = f.get("amplitud") or 0.0
    return {
        "amplitud": amplitud,
        "coste_r": f.get("coste_r") or 0.0,
        "sesgo_cuerpo": f.get("sesgo_cuerpo") or 0.0,
        "sesgo_rango": f.get("sesgo_rango") or 0.0,
        "sesgo_rel": ((f.get("sesgo_cuerpo") or 0.0) / (f.get("sesgo_rango") or 1.0)),
        "acompana_sesgo": 1.0 if f.get("acompaña_al_sesgo") else 0.0,
    }


def aprender(ops: list[dict], informe: dict) -> dict:
    """Walk-forward por años: entrenar con lo anterior, puntuar el siguiente.

    Cada año es una observación independiente, así que el t no está inflado por
    operaciones solapadas. Devuelve el informe con el resultado.
    """
    # Se usa sklearn directamente y no `oro.ml.ModeloProbabilidad`: ese
    # envoltorio exige las columnas del motor intradía (`COLUMNAS_FEATURES`),
    # que no son las condiciones de la ruptura. Forzarlas aquí obligaría a
    # inventar features que esta estrategia no mira.
    try:
        import numpy as np
        import pandas as pd
        from sklearn.ensemble import HistGradientBoostingClassifier
        from .ml.validacion import _auc
    except Exception as e:  # noqa: BLE001
        informe["aprendizaje"] = {"error": f"no se pudo cargar el ML: {e}"}
        return informe

    X = pd.DataFrame([_condiciones(o) for o in ops])
    y = np.array([1 if o["r_neto"] > 0 else 0 for o in ops])
    R = np.array([o["r_neto"] for o in ops])
    anios = np.array([_anio(o) for o in ops])
    hp = dict(max_depth=3, min_samples_leaf=40, max_iter=300,
              l2_regularization=1.0, learning_rate=0.05, early_stopping=False,
              random_state=42)

    aucs, difs, proba = [], [], np.full(len(ops), np.nan)
    for a in sorted(set(anios)):
        tr, te = anios < a, anios == a
        if tr.sum() < MIN_OPERACIONES or te.sum() < 30 or len(set(y[tr])) < 2:
            continue
        m = HistGradientBoostingClassifier(**hp)
        m.fit(X[tr].to_numpy(), y[tr])
        p = m.predict_proba(X[te].to_numpy())[:, 1]
        proba[te] = p
        med = np.median(p)
        alta, baja = p >= med, p < med
        # Si el modelo da la MISMA probabilidad a todo el año, no hay dos
        # mitades que comparar y la resta saldría `nan`. Un solo `nan` arrastra
        # la media y el t de todos los años, y el informe diría "no se puede
        # validar" cuando el problema es un año degenerado. Ese año se salta.
        if not alta.any() or not baja.any():
            continue
        aucs.append(float(_auc(y[te], p)))
        difs.append(float(R[te][alta].mean() - R[te][baja].mean()))

    if len(aucs) < 5:
        informe["aprendizaje"] = {"motivo": "no hay años suficientes para validar"}
        return informe

    ok = ~np.isnan(proba)
    mitad = np.nanmedian(proba[ok])
    alta = ok & (proba >= mitad)
    # La condición que faltaba: R AL AÑO, no R por operación. Quedarse con la
    # mitad mejor puntuada sube la media y puede bajar el total.
    n_anios = max(1, len(set(anios[ok])))
    r_ano_todo = float(R[ok].sum() / n_anios)
    r_ano_filtrado = float(R[alta].sum() / n_anios)

    auc = _media(aucs)
    p_valor = _p_auc(y[ok], proba[ok])
    resultado = {
        "operaciones": int(len(ops)),
        "anios_fuera_de_muestra": len(aucs),
        "auc": round(auc, 4),
        "auc_anios_sobre_050": int(sum(1 for a in aucs if a > 0.5)),
        "t_auc_vs_050": round(_t([a - 0.5 for a in aucs]), 2),
        "p_valor": round(p_valor, 4),
        "ventaja_mitad_alta_R": round(_media(difs), 4),
        "t_ventaja": round(_t(difs), 2),
        "r_al_anio_sin_filtrar": round(r_ano_todo, 2),
        "r_al_anio_filtrando": round(r_ano_filtrado, 2),
    }

    # --- la puerta de promoción: las tres condiciones, todas obligatorias ---
    razones = []
    if math.isnan(auc) or auc < AUC_MINIMO:
        razones.append(f"AUC {auc:.4f} < {AUC_MINIMO}")
    if p_valor >= P_MAXIMO:
        razones.append(f"p = {p_valor:.4f} ≥ {P_MAXIMO}")
    h1 = [d for d, a in zip(difs, sorted(set(anios))[-len(difs):]) if a < ANIO_CORTE]
    h2 = [d for d, a in zip(difs, sorted(set(anios))[-len(difs):]) if a >= ANIO_CORTE]
    if not (h1 and h2 and _media(h1) > 0 and _media(h2) > 0):
        razones.append("no es positivo en las dos mitades bloqueadas")
    if r_ano_filtrado <= r_ano_todo:
        razones.append(f"filtrando se gana MENOS al año "
                       f"({r_ano_filtrado:+.2f} R frente a {r_ano_todo:+.2f} R)")
    resultado["promocionado"] = not razones
    resultado["razones_para_no_promocionar"] = razones
    informe["aprendizaje"] = resultado
    return informe


# --------------------------------------------------------------------------
# 2) vigilar: ¿lo de en vivo se parece a lo medido?
# --------------------------------------------------------------------------
def vigilar(historico: list[dict], vivo: list[dict], informe: dict) -> dict:
    """Compara lo real con lo esperado y dice si la diferencia es explicable.

    Lo que se contrasta NO es "¿gana?" —para eso hacen falta cientos de
    operaciones— sino "¿se comporta como se midió?". El acierto y la forma de
    las salidas convergen mucho antes que la media, así que con dos docenas de
    operaciones ya dicen algo.
    """
    if not vivo:
        informe["vigilancia"] = {"motivo": "todavía no hay operaciones en vivo"}
        return informe

    rh = [f["r_neto"] for f in historico]
    rv = [f["r_neto"] for f in vivo]
    n = len(rv)
    esperado = _media(rh)
    real = _media(rv)
    # Desviación típica del histórico: con pocas operaciones en vivo es mejor
    # estimación que la suya propia.
    var_h = (sum((v - esperado) ** 2 for v in rh) / (len(rh) - 1)) if len(rh) > 2 else 0.0
    ee = math.sqrt(var_h / n) if var_h > 0 else float("nan")
    z = (real - esperado) / ee if ee and not math.isnan(ee) else float("nan")

    acierto_h = sum(1 for v in rh if v > 0) / len(rh)
    acierto_v = sum(1 for v in rv if v > 0) / n
    ee_ac = math.sqrt(acierto_h * (1 - acierto_h) / n)
    z_ac = (acierto_v - acierto_h) / ee_ac if ee_ac > 0 else float("nan")

    # Cuántas operaciones harían falta para distinguir "no gana" de lo medido.
    faltan = (((1.645 + 0.842) * math.sqrt(var_h) / esperado) ** 2
              if esperado > 0 and var_h > 0 else float("nan"))

    alerta = None
    if not math.isnan(z) and z < -2.5:
        alerta = (f"el resultado en vivo ({real:+.4f} R/op) está {abs(z):.1f} "
                  f"desviaciones por debajo de lo medido ({esperado:+.4f}). "
                  f"Con {n} operaciones eso ya no lo explica el azar: revisa "
                  f"ejecución, coste real y si la orden se está anulando cuando "
                  f"el rango rompe al alza.")
    elif not math.isnan(z_ac) and abs(z_ac) > 3.0:
        alerta = (f"el acierto en vivo ({100 * acierto_v:.0f} %) se separa del "
                  f"medido ({100 * acierto_h:.0f} %) en {abs(z_ac):.1f} "
                  f"desviaciones: el mecanismo no está funcionando igual.")

    informe["vigilancia"] = {
        "operaciones_en_vivo": n,
        "r_op_esperado": round(esperado, 4),
        "r_op_real": round(real, 4),
        "z": None if math.isnan(z) else round(z, 2),
        "acierto_esperado": round(acierto_h, 3),
        "acierto_real": round(acierto_v, 3),
        "z_acierto": None if math.isnan(z_ac) else round(z_ac, 2),
        "operaciones_para_demostrar_la_ventaja": (
            None if math.isnan(faltan) else int(faltan)),
        "alerta": alerta,
        "veredicto": ("compatible con lo medido" if alerta is None
                      else "se ha separado de lo medido"),
    }
    return informe


# --------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = cargar_configuracion()

    ruta_hist = Path(RUTA_HISTORICO)
    if "--reconstruir" in argv or not ruta_hist.exists():
        print("Reconstruyendo el histórico con el código de producción…")
        import datetime as dt

        from .datos.dukascopy import ProveedorDukascopy
        from .historico import reconstruir

        df = ProveedorDukascopy().rango(dt.date(2006, 1, 1), dt.date.today())
        fichas = reconstruir(df, cfg)
        with ruta_hist.open("w", encoding="utf-8") as fh:
            for f in fichas:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
        print(f"  {len(fichas)} días guardados en {ruta_hist}")

    historico = _cerradas(_leer_jsonl(ruta_hist))
    from .persistencia import RUTA_RUPTURAS

    vivo = _cerradas(_leer_jsonl(Path(RUTA_RUPTURAS)))

    print("APRENDIZAJE — del histórico completo, no de dos docenas de operaciones")
    print(f"  histórico: {len(historico)} operaciones")
    print(f"  en vivo:   {len(vivo)} operaciones")

    informe: dict = {"operaciones_historico": len(historico),
                     "operaciones_vivo": len(vivo)}

    if len(historico) < MIN_OPERACIONES:
        print(f"  Sin histórico suficiente ({MIN_OPERACIONES} mínimo). "
              f"Ejecuta con --reconstruir.")
        informe["aprendizaje"] = {"motivo": "histórico no reconstruido"}
    else:
        rs = [f["r_neto"] for f in historico]
        print(f"  Lo medido: {_media(rs):+.4f} R/op   t = {_t(rs):.2f}   "
              f"{sum(rs):+.1f} R acumulados")
        informe = aprender(historico, informe)
        a = informe.get("aprendizaje", {})
        if "auc" in a:
            print(f"  Fuera de muestra ({a['anios_fuera_de_muestra']} años): "
                  f"AUC = {a['auc']}  (0,50 = azar)")
            print(f"  Ventaja de la mitad mejor puntuada: "
                  f"{a['ventaja_mitad_alta_R']:+.4f} R/op (t = {a['t_ventaja']})")
            print(f"  R al año sin filtrar {a['r_al_anio_sin_filtrar']:+.2f}  "
                  f"filtrando {a['r_al_anio_filtrando']:+.2f}")
            if a["promocionado"]:
                print("  ✅ MODELO PROMOCIONADO: mejora fuera de muestra, en las dos "
                      "mitades y en R al año.")
            else:
                print("  ⏸️  No se promociona nada, y es lo correcto:")
                for r in a["razones_para_no_promocionar"]:
                    print(f"       · {r}")

    informe = vigilar(historico, vivo, informe) if historico else informe
    v = informe.get("vigilancia", {})
    if "r_op_real" in v:
        print()
        print("VIGILANCIA — ¿lo de en vivo se parece a lo medido?")
        print(f"  esperado {v['r_op_esperado']:+.4f} R/op, real "
              f"{v['r_op_real']:+.4f} con {v['operaciones_en_vivo']} operaciones "
              f"(z = {v['z']})")
        print(f"  acierto esperado {100 * v['acierto_esperado']:.0f} %, real "
              f"{100 * v['acierto_real']:.0f} % (z = {v['z_acierto']})")
        if v["operaciones_para_demostrar_la_ventaja"]:
            print(f"  para demostrar la ventaja hacen falta "
                  f"~{v['operaciones_para_demostrar_la_ventaja']} operaciones "
                  f"(~{v['operaciones_para_demostrar_la_ventaja'] // 101} años)")
        print(f"  → {v['veredicto']}")
        if v["alerta"]:
            print(f"  ⚠️  {v['alerta']}")

    Path(RUTA_INFORME).write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
