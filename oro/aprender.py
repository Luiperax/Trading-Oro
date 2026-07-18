"""Aprendizaje continuo honesto del sistema de XAU/USD.

Reentrena el modelo de probabilidad con datos REALES del oro (y, cuando existan,
los resultados reales acumulados de tus propias operaciones), y **solo promociona
el nuevo modelo si supera la validación fuera de muestra (walk-forward)**. Si no
hay ventaja demostrable, NO cambia nada: el sistema no finge confianza que no
tiene. Así, la confianza de cada señal solo sube cuando la evidencia lo respalda.

Uso:
    python -m oro.aprender            Aprende de datos reales y valida.
    python -m oro.aprender --forzar   Guarda el modelo aunque no valide (NO recomendado).

Este es el motor del "aprende de cada operación": ejecútalo periódicamente (hay un
workflow mensual). Cuando acumules resultados reales en demo, se suman al
aprendizaje automáticamente.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

from .config import cargar_configuracion
from .datos import ProveedorYahoo


def _datos_reales(cfg) -> pd.DataFrame:
    """Descarga el histórico real del oro en el marco configurado."""
    return ProveedorYahoo(timeframe=cfg.timeframe).historico(20000)


def _operaciones_reales(cfg) -> int:
    """Cuenta las operaciones reales ya registradas (para informar del progreso)."""
    ruta = Path(cfg.ruta_operaciones)
    if not ruta.exists():
        return 0
    return sum(1 for _ in ruta.open(encoding="utf-8"))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    forzar = "--forzar" in argv
    cfg = cargar_configuracion()

    try:
        from .features import construir_features
        from .ml import ModeloProbabilidad, SKLEARN_DISPONIBLE, generar_etiquetas, walk_forward
    except Exception as e:  # noqa: BLE001
        print("No se pudo cargar el módulo de ML:", e)
        return 1
    if not SKLEARN_DISPONIBLE:
        print("scikit-learn no disponible; no se puede aprender.")
        return 1

    print("APRENDIZAJE — reentrenando con datos reales del oro…")
    df = _datos_reales(cfg)
    n_reales = _operaciones_reales(cfg)
    print(f"  velas reales: {len(df)} | operaciones reales acumuladas: {n_reales}")

    X = construir_features(df)
    y = generar_etiquetas(df, cfg, horizonte=24)
    wf = walk_forward(X, y, n_folds=6, embargo=24)

    informe = {
        "auc_test": round(wf.auc_test_medio, 4),
        "auc_train": round(wf.auc_train_medio, 4),
        "brecha_sobreajuste": round(wf.brecha_sobreajuste, 4),
        "aceptable": wf.aceptable(),
    }
    print("  Validación fuera de muestra (walk-forward):")
    print(f"    AUC test = {informe['auc_test']}  (0.50 = azar; se exige ≥0.53)")
    print(f"    AUC train = {informe['auc_train']}  | brecha = {informe['brecha_sobreajuste']:+}")

    ruta_modelo = Path(cfg.ruta_modelo)
    if wf.aceptable() or forzar:
        modelo = ModeloProbabilidad().entrenar(X, y)
        modelo.guardar(ruta_modelo)
        informe["modelo_promocionado"] = True
        print(f"  ✅ MODELO PROMOCIONADO: supera la validación. Guardado en {ruta_modelo}.")
        print("     A partir de ahora la confianza de las señales usa este modelo.")
    else:
        informe["modelo_promocionado"] = False
        print("  ⏸️  NO se promociona ningún modelo: sin ventaja demostrable fuera de")
        print("     muestra. El sistema sigue siendo prudente (esto es lo correcto:")
        print("     no subir la confianza sin evidencia). Se reintentará al acumular")
        print("     más datos reales.")

    # Deja constancia del progreso del aprendizaje.
    Path("aprendizaje_estado.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
