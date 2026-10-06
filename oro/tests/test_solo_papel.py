"""El plan en «solo papel»: se manda y se sigue, pero nadie debe operarlo.

Desde el 6-oct-2026, porque contados los días en que una misma vela cruza el
techo y el suelo del rango (resueltos con velas de un minuto), la estrategia
no tiene ventaja. Ver ConfiguracionRuptura.solo_papel.
"""

from __future__ import annotations

from oro.config import ConfiguracionSistema
from oro.notificaciones.plan import mensaje_de_plan, mensaje_html_de_plan
from oro.tests.test_solo_ventas import _plan


def test_por_defecto_va_en_papel():
    assert ConfiguracionSistema().ruptura.solo_papel is True


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
