"""Pruebas del diagnóstico de señales (¿se cumplieron? y ¿por qué?)."""

from __future__ import annotations

from oro.diagnostico import construir_diagnostico, _auc_una


def _ops(n=30, patron=True):
    """Genera señales sintéticas: si ``patron``, ADX alto -> se cumple."""
    ops = []
    for i in range(n):
        adx = 35.0 if i % 2 == 0 else 12.0
        gana = (adx > 20) if patron else (i % 3 == 0)
        ops.append({
            "apertura": f"2026-08-{(i % 20) + 1:02d}T{9 + (i % 6):02d}:00:00+00:00",
            "cierre": f"2026-08-{(i % 20) + 1:02d}T15:00:00+00:00",
            "direccion": "compra" if i % 2 else "venta",
            "entrada": 4000 + i,
            "resultado_r": 1.2 if gana else -0.8,
            "ganada": gana,
            "estado": "cerrada_tp" if gana else "cerrada_sl",
            "probabilidad": 0.7 if gana else 0.61,
            "confianza": 0.75 if gana else 0.62,
            "features": {"adx": adx, "rsi_14": 55.0, "atr_rel": 0.004},
            "label": 1 if gana else 0,
        })
    return ops


def test_auc_una_detecta_separacion():
    # Valores altos en ganadoras -> AUC > 0.5; sin separación -> ~0.5.
    assert _auc_una([3, 4, 5], [1, 1, 1]) == 0.5  # sin clase negativa
    assert _auc_una([5, 6, 1, 2], [1, 1, 0, 0]) == 1.0
    assert _auc_una([1, 2, 5, 6], [1, 1, 0, 0]) == 0.0


def test_diagnostico_pocas_senales_solo_marcador():
    texto = construir_diagnostico(_ops(6))
    assert "Operaciones cerradas : 6" in texto
    assert "empieza a ser fiable" in texto            # aviso de datos insuficientes
    assert "condiciones que más influyen" not in texto  # no analiza el porqué aún


def test_diagnostico_identifica_condicion_influyente():
    texto = construir_diagnostico(_ops(30, patron=True))
    assert "ANÁLISIS" in texto
    assert "calibración" in texto
    assert "Por dirección" in texto
    assert "Cómo se cerraron" in texto
    # Con el patrón ADX->gana, el ADX debe salir como condición influyente ALTA.
    assert "ADX" in texto and "ALTOS" in texto


def test_diagnostico_vacio_no_rompe():
    texto = construir_diagnostico([])
    assert "Todavía no hay operaciones" in texto
