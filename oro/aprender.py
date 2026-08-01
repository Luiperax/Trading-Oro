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
import sys
from pathlib import Path

from .config import cargar_configuracion

# Mínimo de operaciones reales para intentar aprender (por debajo, no hay valor
# estadístico). Con ~5 señales/semana, son ~2-3 meses de datos.
MIN_OPERACIONES = 50


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
    return filas


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
    auc_test = _auc(y_te.to_numpy(), modelo.predecir_proba(X_te))
    informe["auc_test"] = round(float(auc_test), 4)
    print(f"  Validación fuera de muestra: AUC test = {informe['auc_test']} "
          f"(0.50 = azar; se exige ≥0.55)")

    aceptable = (not np.isnan(auc_test)) and auc_test >= 0.55
    if aceptable or forzar:
        # Modelo final entrenado con TODAS las operaciones reales.
        ModeloProbabilidad(**hp_pequeno).entrenar(X, y).guardar(cfg.ruta_modelo)
        informe["modelo_promocionado"] = True
        print(f"  ✅ MODELO ACTUALIZADO con lo aprendido de tus señales reales.")
        print("     A partir de ahora la confianza usa este modelo.")
    else:
        informe["modelo_promocionado"] = False
        print("  ⏸️  No se actualiza el modelo: lo aprendido no se sostiene fuera de")
        print("     muestra. Correcto: no cambiar sin evidencia. Se reintentará con más datos.")

    Path("aprendizaje_estado.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
