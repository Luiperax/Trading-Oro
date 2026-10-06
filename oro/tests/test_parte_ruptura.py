"""El parte diario cuando lo único que opera es el plan de ruptura."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from oro.config import cargar_configuracion
from oro.latido import construir_parte, construir_parte_html

# El 6-oct a las 06:39 UTC el parte informa de la sesión del 5.
AHORA = datetime(2026, 10, 6, 6, 39, tzinfo=timezone.utc)


def _estado(tmp_path, monkeypatch, plan_json, fichas=()):
    (tmp_path / "plan.json").write_text(json.dumps(plan_json), encoding="utf-8")
    (tmp_path / "r.jsonl").write_text(
        "".join(json.dumps(f) + "\n" for f in fichas), encoding="utf-8")
    monkeypatch.setenv("ORO_PLAN_ESTADO", str(tmp_path / "plan.json"))
    monkeypatch.setenv("ORO_RUTA_RUPTURAS", str(tmp_path / "r.jsonl"))
    monkeypatch.setenv("ORO_ESTADO", str(tmp_path / "nada.json"))


PLAN = {"ultimo_plan": "2026-10-05", "avisados": ["2026-10-05:break-even"],
        "plan": {"venta": {"entrada": 4149.17}, "compra": {"entrada": 4170.14},
                 "dia_de_empleo": False}}


def test_el_parte_cuenta_el_plan_y_su_resultado(tmp_path, monkeypatch):
    _estado(tmp_path, monkeypatch, PLAN, [
        {"dia": "2026-10-02", "r_neto": -1.1, "estado": "cerrada"},
        {"dia": "2026-10-05", "estado": "cerrada", "direccion": "venta",
         "entrada": 4149.17, "salida": 4139.28, "motivo_cierre": "cierre de sesión",
         "r_neto": 0.44}])
    t = construir_parte(cargar_configuracion(), AHORA)
    assert "PLAN DE RUPTURA" in t and "4149.17" in t and "4170.14" in t
    assert "+0.44 R" in t and "break-even" in t
    assert "2 operación(es), -0.66 R" in t
    # Y no habla de un motor que está apagado.
    assert "días sin señales" not in t and "Entradas" not in construir_parte_html(
        cargar_configuracion(), AHORA)


def test_el_parte_dice_cuando_no_hubo_plan(tmp_path, monkeypatch):
    _estado(tmp_path, monkeypatch, {**PLAN, "ultimo_plan": "2026-10-02"})
    t = construir_parte(cargar_configuracion(), AHORA)
    assert "no hubo plan" in t


def test_el_parte_explica_un_plan_descartado(tmp_path, monkeypatch):
    _estado(tmp_path, monkeypatch, {**PLAN, "registrado": "2026-10-05",
                                    "nota": "Plan calculado con el futuro GC=F."})
    t = construir_parte(cargar_configuracion(), AHORA)
    assert "GC=F" in t
