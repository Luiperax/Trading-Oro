"""La puerta que decide si el sistema se cree lo que ha aprendido.

Es el sitio con más capacidad de hacer daño en silencio de todo el programa: si
promociona un modelo que no predice nada, no falla ni avisa —simplemente empieza
a mandar señales peores con más confianza.

El listón anterior era "AUC ≥ 0.55" a secas. Con MIN_OPERACIONES = 50 y corte
70/30 el conjunto de prueba tiene 15 operaciones, y midiendo con 4.000
simulaciones de ruido puro, un modelo SIN NINGUNA capacidad predictiva superaba
ese listón el 38% de las veces. No medía destreza: medía varianza.

Ahora se exige además significancia (p < 0.05), que se adapta sola al tamaño de
la muestra: con pocas operaciones hace falta un AUC enorme para pasar. Medido
igual, la promoción por azar baja al 4.5% y se queda ahí crezca o no la muestra.
"""

from __future__ import annotations

import numpy as np
import pytest

from oro.aprender import AUC_MINIMO, P_MAXIMO, _p_auc
from oro.ml.validacion import _auc


def test_el_ruido_puro_no_pasa_la_puerta_mas_del_5_por_ciento():
    rng = np.random.default_rng(1)
    n_test = 15                      # el que sale con MIN_OPERACIONES y corte 70/30.
    promociona = validas = 0
    for _ in range(2000):
        y = rng.integers(0, 2, n_test)
        if len(set(y)) < 2:
            continue
        validas += 1
        s = rng.normal(size=n_test)
        if _auc(y, s) >= AUC_MINIMO and _p_auc(y, s) < P_MAXIMO:
            promociona += 1
    tasa = promociona / validas
    assert tasa < 0.08, (
        f"se promociona ruido el {tasa:.1%} de las veces; la puerta no protege")


def test_una_senal_de_verdad_si_pasa_la_puerta():
    # Contrapeso del anterior: una puerta que no deja pasar NADA tampoco sirve.
    rng = np.random.default_rng(2)
    n = 120
    y = rng.integers(0, 2, n)
    s = y + rng.normal(scale=0.6, size=n)      # señal real, con ruido encima.
    assert _auc(y, s) >= AUC_MINIMO
    assert _p_auc(y, s) < P_MAXIMO


def test_el_p_valor_castiga_las_muestras_pequenas():
    # El MISMO AUC debe ser menos creíble con menos datos. Es justo lo que el
    # umbral fijo no hacía.
    rng = np.random.default_rng(3)
    ps = []
    for n in (16, 60, 240):
        y = np.tile([0, 1], n // 2)
        s = y + rng.normal(scale=1.0, size=n)
        ps.append(_p_auc(y, s))
    assert ps[0] > ps[1] > ps[2], f"el p-valor no se ajusta al tamaño: {ps}"


def test_en_la_duda_no_promociona():
    # Sin variedad de resultados no se puede validar nada; debe devolver 1.0
    # (no promocionar) en vez de un número optimista.
    assert _p_auc(np.array([1, 1, 1]), np.array([0.4, 0.5, 0.6])) == pytest.approx(1.0)
    assert _p_auc(np.array([0, 0]), np.array([0.4, 0.5])) == pytest.approx(1.0)
