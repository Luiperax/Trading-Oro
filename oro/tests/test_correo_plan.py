"""El correo del plan: que diga lo que hay que teclear, y que no mienta."""

from __future__ import annotations

import re
from zoneinfo import ZoneInfo

import pytest

from oro.config import ConfiguracionSistema
from oro.notificaciones.base import Evento, Notificador
from oro.notificaciones.plan import (
    mensaje_de_plan,
    mensaje_html_de_plan,
    pasos_plan,
)
from oro.sesiones import construir_plan
from oro.tests.test_ruptura_sesion import AHORA, MANANA, _marco

NY = ZoneInfo("America/New_York")


@pytest.fixture()
def plan():
    cfg = ConfiguracionSistema()
    cfg.riesgo.coste_operacion = 0.30
    return construir_plan(_marco("2026-03-10", MANANA), cfg, ahora=AHORA).plan


def test_los_pasos_dan_los_dos_precios_de_disparo(plan):
    texto = " ".join(pasos_plan(plan))
    assert "2020.00" in texto and "2000.00" in texto
    assert "BUY STOP" in texto and "SELL STOP" in texto
    # Lo que más se olvida: cancelar la otra.
    assert "CANCELA" in texto or "cancela" in texto


def test_los_pasos_dicen_cuando_caducan_y_cuando_se_cierra(plan):
    texto = " ".join(pasos_plan(plan))
    from oro.tiempo import hora_local
    assert hora_local(plan.valido_hasta) in texto
    assert hora_local(plan.cierre_forzoso) in texto


def test_el_texto_plano_lleva_los_cuatro_niveles(plan):
    txt = mensaje_de_plan(plan)
    for precio in (plan.compra.entrada, plan.compra.objetivo,
                   plan.venta.entrada, plan.venta.objetivo):
        assert f"{precio:.2f}" in txt


def test_el_correo_no_promete_lo_que_no_hay(plan):
    """La estrategia acierta el 43 % y tuvo cinco años malos seguidos. Si el
    correo no lo dice, está vendiendo algo que no es."""
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "43" in texto
        assert "2016" in texto and "2021" in texto
        assert "no asesoramiento financiero" in texto


def test_el_html_no_desborda_el_movil(plan):
    html = mensaje_html_de_plan(plan)
    assert "max-width:460px" in html
    # Solo tablas y estilos en línea: es lo único que renderiza igual en Gmail,
    # Outlook y el móvil. Una hoja de estilos se descarta en la mitad de ellos.
    assert "<style" not in html and "class=" not in html


def test_el_html_esta_equilibrado(plan):
    html = mensaje_html_de_plan(plan)
    for etiqueta in ("table", "tr", "td", "div"):
        abre = len(re.findall(rf"<{etiqueta}[ >]", html))
        cierra = len(re.findall(rf"</{etiqueta}>", html))
        assert abre == cierra, f"{etiqueta}: {abre} abren y {cierra} cierran"


def test_el_asunto_lleva_los_dos_precios(plan):
    capturado = {}

    class Espia(Notificador):
        def enviar(self, titulo, cuerpo, evento=Evento.NUEVA_SENAL, html=None):
            capturado.update(titulo=titulo, cuerpo=cuerpo, evento=evento, html=html)
            return True

    assert Espia().notificar_plan(plan) is True
    assert capturado["evento"] is Evento.PLAN_RUPTURA
    assert "2020.00" in capturado["titulo"] and "2000.00" in capturado["titulo"]
    assert capturado["html"] is not None


def test_con_lote_por_debajo_del_minimo_se_avisa():
    """Con 3.000 € y un rango de 200 $, el 0.25 % del capital da menos del lote
    mínimo. El correo tiene que decirlo: el riesgo real será mayor."""
    cfg = ConfiguracionSistema()
    cfg.riesgo.coste_operacion = 0.30
    ancha = {h: (2200.0, 2000.0) for h in range(3, 8)}
    plan = construir_plan(_marco("2026-03-10", ancha), cfg, ahora=AHORA).plan
    assert plan.onzas < 1.0        # el tamaño teórico no llega ni a una onza
    # Y la cifra que da el correo tiene que ser la del lote QUE SE TECLEA
    # (0.01 lotes = 1 onza = 200 $ de riesgo), no la del tamaño teórico.
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "LOTE MÍNIMO" in texto
        assert "200 €" in texto
        assert "7 €" not in texto
