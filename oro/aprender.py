"""Aprendizaje continuo a partir de las SEÑALES REALES enviadas.

Este es el lazo cerrado que pediste: el sistema guarda las condiciones de cada
señal que te manda (features) y, al cerrarse, apunta si salió bien o mal. Aquí
aprende de esos resultados reales —por qué ganó o perdió— y, si de verdad
encuentra un patrón que se sostiene FUERA DE MUESTRA, actualiza el modelo para
mejorar las futuras señales. Si no hay evidencia suficiente, NO cambia nada
(no inventa confianza que no tiene).

Uso:
    python -m oro.aprender

Necesita acumular suficientes operaciones reales para que el aprendizaje tenga
valor estadístico (aprender de 5 operaciones no significa nada). Mientras tanto,
informa del progreso.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from .config import cargar_configuracion

# Mínimo de operaciones reales para intentar aprender (por debajo, no hay valor
# estadístico). Con ~5 señales/semana, son ~2-3 meses de datos.
MIN_OPERACIONES = 50

# AUC mínimo para plantearse promocionar. NO basta por sí solo: con el corte
# 70/30 y 50 operaciones, el test tiene 15, y un modelo de PURO RUIDO supera 0.55
# el 38% de las veces (medido con 4.000 simulaciones). Un umbral fijo sobre una
# muestra pequeña no mide destreza, mide varianza. Por eso se exige además que el
# AUC sea significativamente mayor que 0.50, lo que se adapta solo al tamaño de
# la muestra: con pocas operaciones hace falta un AUC enorme para pasar, que es
# exactamente lo que debe ocurrir.
AUC_MINIMO = 0.55
P_MAXIMO = 0.05


def _p_auc(y, puntuaciones) -> float:
    """p-valor de una cola de que el AUC sea > 0.50 (Mann-Whitney).

    Devuelve 1.0 si no se puede calcular, para que en la duda NO se promocione.
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
        n1, n2 = len(pos), len(neg)
        from .ml.validacion import _auc

        auc = _auc(y, s)
        if np.isnan(auc):
            return 1.0
        sigma = np.sqrt((n1 + n2 + 1) / (12.0 * n1 * n2))
        if sigma <= 0:
            return 1.0
        z = (auc - 0.5) / sigma
        return float(0.5 * math.erfc(z / math.sqrt(2.0)))


def _cargar_operaciones(ruta: Path) -> list:
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
    # Sin deduplicar, la MISMA operación podría caer en entrenamiento y en
    # prueba a la vez (fuga de datos): el AUC saldría inflado y se promocionaría
    # un modelo que en realidad no predice nada.
    from .informe import deduplicar
    return deduplicar(filas)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    forzar = "--forzar" in argv
    cfg = cargar_configuracion()

    try:
        import numpy as np
        import pandas as pd
        from .features import COLUMNAS_FEATURES
        from .ml import ModeloProbabilidad, SKLEARN_DISPONIBLE
        from .ml.validacion import _auc
    except Exception as e:  # noqa: BLE001
        print("No se pudo cargar el módulo de ML:", e)
        return 1
    if not SKLEARN_DISPONIBLE:
        print("scikit-learn no disponible; no se puede aprender.")
        return 1

    print("APRENDIZAJE — a partir de las señales reales enviadas")
    ops = _cargar_operaciones(Path(cfg.ruta_operaciones))
    # Solo las que tienen condiciones (features) y etiqueta de resultado.
    con_datos = [o for o in ops if o.get("features") and "label" in o]
    n = len(con_datos)
    print(f"  Operaciones reales con datos para aprender: {n}")

    if n < MIN_OPERACIONES and not forzar:
        faltan = MIN_OPERACIONES - n
        print(f"  ⏳ Necesito ~{MIN_OPERACIONES} para que el aprendizaje tenga valor "
              f"estadístico. Faltan {faltan}.")
        print("  El sistema sigue registrando cada operación y se mantiene prudente.")
        Path("aprendizaje_estado.json").write_text(json.dumps(
            {"operaciones_reales": n, "minimo": MIN_OPERACIONES,
             "modelo_promocionado": False, "motivo": "datos insuficientes"},
            ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    # Construir el conjunto (features -> ganó/perdió), en orden cronológico.
    X = pd.DataFrame([o["features"] for o in con_datos]).reindex(columns=COLUMNAS_FEATURES)
    y = pd.Series([int(o["label"]) for o in con_datos])
    if y.nunique() < 2:
        print("  Todavía no hay ganadoras Y perdedoras suficientes para aprender.")
        return 0

    # Validación fuera de muestra: entrenar con el 70% más antiguo, probar con el
    # 30% más reciente (nunca se evalúa con lo que se ha entrenado).
    corte = int(n * 0.7)
    X_tr, y_tr = X.iloc[:corte], y.iloc[:corte]
    X_te, y_te = X.iloc[corte:], y.iloc[corte:]
    informe = {"operaciones_reales": n}
    if y_tr.nunique() < 2 or y_te.nunique() < 2:
        print("  Aún no hay suficiente variedad de resultados para validar.")
        return 0

    # Hiperparámetros para dataset PEQUEÑO (aprender de pocas operaciones reales):
    # árboles poco profundos, hojas pequeñas y regularización fuerte (anti-sobreajuste).
    hp_pequeno = dict(max_depth=2, min_samples_leaf=8, max_iter=120,
                      l2_regularization=2.0, learning_rate=0.05, early_stopping=False)
    modelo = ModeloProbabilidad(**hp_pequeno).entrenar(X_tr, y_tr)
    proba_te = modelo.predecir_proba(X_te)
    auc_test = _auc(y_te.to_numpy(), proba_te)
    p_valor = _p_auc(y_te.to_numpy(), proba_te)
    informe["auc_test"] = round(float(auc_test), 4)
    informe["p_valor"] = round(float(p_valor), 4)
    informe["n_test"] = int(len(y_te))
    print(f"  Validación fuera de muestra ({len(y_te)} operaciones): "
          f"AUC = {informe['auc_test']}  (0.50 = azar)")
    print(f"  ¿Podría salir de la casualidad? p = {informe['p_valor']} "
          f"(se exige p < {P_MAXIMO} y AUC ≥ {AUC_MINIMO})")

    aceptable = ((not np.isnan(auc_test)) and auc_test >= AUC_MINIMO
                 and p_valor < P_MAXIMO)
    if aceptable or forzar:
        # Modelo final entrenado con TODAS las operaciones reales.
        ModeloProbabilidad(**hp_pequeno).entrenar(X, y).guardar(cfg.ruta_modelo)
        informe["modelo_promocionado"] = True
        print(f"  ✅ MODELO ACTUALIZADO con lo aprendido de tus señales reales.")
        print("     A partir de ahora la confianza usa este modelo.")
    else:
        informe["modelo_promocionado"] = False
        if not np.isnan(auc_test) and auc_test >= AUC_MINIMO:
            print(f"  ⏸️  No se actualiza: el AUC de {auc_test:.2f} parece bueno, pero con")
            print(f"     {len(y_te)} operaciones podría salir de la casualidad (p = {p_valor:.3f}).")
            print("     Hacen falta más señales para distinguir destreza de suerte.")
        else:
            print("  ⏸️  No se actualiza el modelo: lo aprendido no se sostiene fuera de")
            print("     muestra. Correcto: no cambiar sin evidencia.")

    Path("aprendizaje_estado.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
