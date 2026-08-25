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


def test_parte_resume_los_avisos_del_dia(tmp_path, monkeypatch):
    _sin_red(monkeypatch)
    hoy = datetime.now(timezone.utc).replace(hour=10).isoformat()
    _escribir_estado(tmp_path, monkeypatch, {
        "historial": [{"tipo": "entrada", "momento": hoy, "mensaje": "[COMPRA] XAU/USD @ 4500"},
                      {"tipo": "cierre", "momento": hoy, "mensaje": "STOP alcanzado"}],
        "abiertas": []})
    t = construir_parte(cargar_configuracion())
    assert "1 entrada(s), 1 salida(s)" in t
