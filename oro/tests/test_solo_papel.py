"""El plan en «solo papel»: se manda y se sigue, pero nadie debe operarlo.

Desde el 6-oct-2026, porque contados los días en que una misma vela cruza el
techo y el suelo del rango (resueltos con velas de un minuto), la estrategia
no tiene ventaja. Ver ConfiguracionRuptura.solo_papel.
"""

from __future__ import annotations

import pytest

from oro.config import ConfiguracionSistema
from oro.notificaciones.plan import mensaje_de_plan, mensaje_html_de_plan
from oro.tests.test_solo_ventas import _plan


def test_desde_el_14_oct_opera_y_se_vuelve_al_papel_con_la_variable(monkeypatch):
    from oro.config import cargar_configuracion
    assert ConfiguracionSistema().ruptura.solo_papel is False
    monkeypatch.setenv("ORO_RUPTURA_SOLO_PAPEL", "1")
    assert cargar_configuracion().ruptura.solo_papel is True


@pytest.fixture(autouse=True)
def _en_papel(monkeypatch):
    monkeypatch.setenv("ORO_RUPTURA_SOLO_PAPEL", "1")


def test_el_correo_dice_no_operes_arriba_del_todo():
    plan, _ = _plan()
    texto = mensaje_de_plan(plan)
    assert texto.splitlines()[0].startswith("📝 SOLO PAPEL")
    assert "NO OPERES" in mensaje_html_de_plan(plan)


def test_el_correo_en_papel_no_cita_la_ventaja_que_ya_no_vale():
    plan, _ = _plan()
    for t in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "+0,073 R por operación, 15 años" not in t
        assert "+117 €" not in t


def test_el_asunto_lo_dice(monkeypatch):
    from oro.notificaciones.base import Notificador

    class Espia(Notificador):
        def enviar(self, titulo, cuerpo, evento=None, html=None):
            self.titulo = titulo
            return True

    plan, _ = _plan()
    e = Espia()
    e.notificar_plan(plan)
    assert e.titulo.startswith("📝 SOLO PAPEL, NO OPERES")


def test_se_vuelve_a_operar_con_la_variable(monkeypatch):
    monkeypatch.setenv("ORO_RUPTURA_SOLO_PAPEL", "0")
    plan, _ = _plan()
    assert "SOLO PAPEL" not in mensaje_de_plan(plan)


def test_los_avisos_dicen_el_modo_con_el_que_se_mando_el_plan(tmp_path, monkeypatch):
    """El 14-oct el plan salió en papel por la mañana y el modo cambió a
    operar por la tarde: el «CIERRA» de las 22:00 no podía salir sin la marca."""
    import json

    from oro import plan_sesion, seguir_plan
    from oro.tests.test_seguimiento import _a_las, _con_sesion, _marco, ASIA_SUBE, LONDRES, DIA

    monkeypatch.setenv("ORO_PLAN_ESTADO", str(tmp_path / "plan.json"))
    monkeypatch.setenv("ORO_RUTA_RUPTURAS", str(tmp_path / "r.jsonl"))
    titulos = []

    class N:
        def notificar_plan(self, plan): return True
        def enviar(self, t, c, e=None, html=None): titulos.append(t); return True

    monkeypatch.setattr(plan_sesion, "_construir_notificador", lambda: N())
    monkeypatch.setattr(seguir_plan, "_construir_notificador", lambda: N())
    df = _marco(DIA, {**ASIA_SUBE, **LONDRES})
    monkeypatch.setattr(plan_sesion, "_proveedor", lambda s: type("P", (), {"historico": lambda self, n: df})())
    plan_sesion.ejecutar(ahora=_a_las(8))                     # en papel (fixture)
    assert json.loads((tmp_path / "plan.json").read_text())["papel"] is True
    monkeypatch.setenv("ORO_RUPTURA_SOLO_PAPEL", "0")         # cambia a operar
    tarde = _con_sesion({8: (4005, 3990), 9: (3995, 3985), 10: (3992, 3984),
                         11: (3990, 3982), 12: (3991, 3983), 13: (3990, 3984),
                         14: (3989, 3983), 15: (3988, 3980)})
    monkeypatch.setattr(seguir_plan, "_proveedor", lambda s: type("P", (), {"historico": lambda self, n: tarde})())
    seguir_plan.ejecutar(ahora=_a_las(16, 3))
    assert titulos and all(t.startswith("📝 [papel]") for t in titulos)
