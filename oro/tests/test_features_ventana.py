"""El vivo debe VER lo mismo que vio el entrenamiento.

El modelo se entrena sobre el histórico completo y predice sobre una ventana. La
media exponencial de 200 se siembra en la primera vela de la ventana, así que
con pocas velas el valor no converge al del entrenamiento y el modelo recibiría
en producción una variable distinta de la que aprendió. Es un fallo que no da
error: solo predicciones peores, en silencio.

Medido sobre datos reales, el error de ``dist_ema200_atr`` en desviaciones
típicas de la propia variable: 0.0353 con 400 velas, 0.0119 con 500 (las del
vivo), 0.0006 con 800. Con las 500 actuales es despreciable. Estas pruebas
existen para que nadie lo baje sin enterarse.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from oro.datos.sintetico import ProveedorSintetico
from oro.features import COLUMNAS_FEATURES, VELAS_MINIMAS, construir_features
from oro.vivo.runner import RunnerVivo


def test_la_ventana_del_vivo_cubre_el_minimo():
    """El ciclo en vivo pide suficientes velas para que las features converjan."""
    import inspect

    velas = inspect.signature(RunnerVivo.ciclo).parameters["velas"].default
    assert velas >= VELAS_MINIMAS, (
        f"el vivo pide {velas} velas pero las features necesitan {VELAS_MINIMAS}")


def test_calcular_sobre_una_ventana_coincide_con_el_historico_completo():
    """Misma vela, calculada con todo el histórico y con la ventana del vivo."""
    df = ProveedorSintetico(velas=4000, semilla=11, timeframe="H1").historico(4000)
    completo = construir_features(df)
    desv = completo[list(COLUMNAS_FEATURES)].iloc[500:].astype(float).std()

    peor, culpable = 0.0, None
    for corte in (1500, 2500, 3500):
        ventana = construir_features(df.iloc[corte - 500:corte]).iloc[-1]
        referencia = completo.iloc[corte - 1]
        for c in COLUMNAS_FEATURES:
            a, b = ventana.get(c), referencia.get(c)
            if a is None or b is None or pd.isna(a) or pd.isna(b):
                continue
            sigma = float(desv[c])
            if not np.isfinite(sigma) or sigma <= 0:
                continue
            error = abs(float(a) - float(b)) / sigma
            if error > peor:
                peor, culpable = error, c

    # 0.05 sigma es holgado: lo medido con 500 velas es 0.012.
    assert peor < 0.05, f"{culpable} se desvía {peor:.4f} sigma con la ventana del vivo"
