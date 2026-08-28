"""Pruebas del parte diario (oro.latido)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from oro.config import cargar_configuracion
from oro.latido import construir_parte


def _escribir_estado(tmp_path, monkeypatch, datos):
    ruta = tmp_path / "estado.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    monkeypatch.setenv("ORO_ESTADO", str(ruta))


def _sin_red(monkeypatch):
    monkeypatch.setattr("oro.latido._motivo_actual",
                        lambda cfg: (4700.0, "mercado en rango"))


def test_parte_sin_nada_abierto_lo_dice_claro(tmp_path, monkeypatch):
    _sin_red(monkeypatch)
    _escribir_estado(tmp_path, monkeypatch, {"historial": [], "abiertas": []})
    t = construir_parte(cargar_configuracion())
    assert "EN MARCHA" in t
    assert "Sin operaciones abiertas" in t
    assert "no hay nada abierto" in t          # responde a la duda del usuario
    assert "mercado en rango" in t             # y explica POR QUÉ no hay señal


def test_parte_avisa_del_silencio_prolongado(tmp_path, monkeypatch):
    _sin_red(monkeypatch)
    _escribir_estado(tmp_path, monkeypatch, {
        "historial": [{"tipo": "entrada", "momento": "2026-08-01T10:00:00+00:00",
                       "mensaje": "[VENTA] ..."}],
        "abiertas": []})
    t = construir_parte(cargar_configuracion(),
                        ahora=datetime(2026, 8, 25, 21, tzinfo=timezone.utc))
    assert "días sin señales" in t
    assert "No es una avería" in t


def test_parte_muestra_la_operacion_abierta(tmp_path, monkeypatch):
    _sin_red(monkeypatch)
    _escribir_estado(tmp_path, monkeypatch, {
        "historial": [], "abiertas": [{"direccion": "compra", "entrada": 4500.0,
                                       "stop_actual": 4480.0}]})
    t = construir_parte(cargar_configuracion())
    assert "OPERACIÓN ABIERTA" in t
    assert "se avisará al cerrarse" in t


def test_parte_resume_los_avisos_de_la_sesion(tmp_path, monkeypatch):
    _sin_red(monkeypatch)
    # Avisos de la sesión del 27; el parte se genera el 28 a las 05:27 UTC
    # (el retraso REAL de GitHub que destapó el fallo).
    _escribir_estado(tmp_path, monkeypatch, {
        "historial": [
            {"tipo": "entrada", "momento": "2026-08-27T10:00:00+00:00",
             "mensaje": "[COMPRA] XAU/USD @ 4500"},
            {"tipo": "cierre", "momento": "2026-08-27T15:00:00+00:00",
             "mensaje": "STOP alcanzado"}],
        "abiertas": []})
    t = construir_parte(cargar_configuracion(),
                        ahora=datetime(2026, 8, 28, 5, 27, tzinfo=timezone.utc))
    assert "sesión del 2026-08-27" in t
    assert "1 entrada(s), 1 salida(s)" in t


def test_parte_tardio_informa_de_la_sesion_CERRADA_no_del_dia_nuevo(tmp_path, monkeypatch):
    """EL FALLO: entregado a la mañana siguiente, resumía un día recién empezado.

    GitHub retrasa las tareas de forma irregular (medido: de 30 min a 8 h). El
    28-ago el parte llegó a las 05:27 UTC e informó del 28 —todo a cero— en vez
    de la sesión del 27, que era la que acababa de cerrar.
    """
    _sin_red(monkeypatch)
    _escribir_estado(tmp_path, monkeypatch, {
        "historial": [{"tipo": "entrada", "momento": "2026-08-27T16:00:00+00:00",
                       "mensaje": "[VENTA] XAU/USD @ 4702"}],
        "abiertas": []})
    for h, m in ((21, 30), (23, 30)):      # mismo día, tras el cierre
        t = construir_parte(cargar_configuracion(),
                            ahora=datetime(2026, 8, 27, h, m, tzinfo=timezone.utc))
        assert "sesión del 2026-08-27" in t
    for h in (5, 12):                      # al día siguiente, con retraso
        t = construir_parte(cargar_configuracion(),
                            ahora=datetime(2026, 8, 28, h, tzinfo=timezone.utc))
        assert "sesión del 2026-08-27" in t
        assert "1 entrada(s)" in t         # y SÍ cuenta lo que pasó


def test_parte_html_se_genera_y_es_visual(tmp_path, monkeypatch):
    from oro.latido import construir_parte_html

    _sin_red(monkeypatch)
    _escribir_estado(tmp_path, monkeypatch, {
        "historial": [{"tipo": "entrada", "momento": "2026-08-27T10:00:00+00:00",
                       "mensaje": "[COMPRA] XAU/USD @ 4500"}],
        "abiertas": [{"direccion": "compra", "entrada": 4500.0, "stop_actual": 4480.0}]})
    h = construir_parte_html(cargar_configuracion(),
                             ahora=datetime(2026, 8, 28, 5, 27, tzinfo=timezone.utc))
    assert "<div" in h and "table" in h
    assert "PARTE DIARIO" in h
    assert "Sesión del 2026-08-27" in h
    assert "Operación abierta" in h        # avisa de lo que sigue vivo
    assert "CEST" in h or "CET" in h       # hora local
