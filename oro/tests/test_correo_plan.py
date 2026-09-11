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
    """La estrategia acierta el 45 % y tuvo cuatro años malos seguidos. Si el
    correo no lo dice, está vendiendo algo que no es."""
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "45 %" in texto
        assert "2017" in texto and "2020" in texto
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


def test_el_correo_no_calcula_el_lote(plan):
    """El tamaño de la posición lo decide el usuario. El correo da el riesgo POR
    ONZA —que es lo que necesita para hacer su cuenta— y nada más: ni lote
    sugerido, ni aviso de mínimo, ni porcentaje del capital."""
    from oro.notificaciones.plan import riesgo_por_onza

    assert riesgo_por_onza(plan) == pytest.approx(plan.rango.amplitud)
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert f"{plan.rango.amplitud:.2f} $ por onza" in texto
        for prohibido in ("Lote", "lote", "LOTE", "del capital"):
            assert prohibido not in texto, f"aparece {prohibido!r}"


def _plan_con_asia(sube: bool = True):
    from oro.tests.test_ruptura_sesion import ASIA_BAJA, ASIA_SUBE, JULIO, LONDRES
    cfg = ConfiguracionSistema()
    cfg.riesgo.coste_operacion = 0.30
    velas = {**(ASIA_SUBE if sube else ASIA_BAJA), **LONDRES}
    return construir_plan(_marco("2026-07-15", velas), cfg, ahora=JULIO).plan


@pytest.mark.parametrize("sube,esperada,otra", [(True, "COMPRA", "VENTA"),
                                                (False, "VENTA", "COMPRA")])
def test_el_correo_explica_el_sesgo_sin_marcar_ninguna_orden(sube, esperada, otra):
    """Aquí había una estrella junto a una de las dos órdenes. Medido sobre
    3.180 días, la marcada es la que salta el 50,0 % de las veces (z = 0.00):
    como predicción vale lo que una moneda, y puesta al lado de una orden se lee
    como predicción. El 49 % de los días parecía equivocarse."""
    plan = _plan_con_asia(sube)
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        # Lo primero que se dice es lo que NO es.
        assert "NO dice cuál de las dos va a saltar" in texto
        assert "50,0 %" in texto
        assert esperada in texto and "+0,088" in texto and "+0,013" in texto
        # Y que la otra salte no es un fallo del sistema.
        assert f"Si hoy salta la {otra}" in texto
        # Ninguna orden va marcada.
        assert "MÁS RESPALDO" not in texto
        assert "más respaldo hoy" not in texto


def test_el_correo_no_vende_la_confianza_como_certeza():
    """La diferencia entre lados da t = 2,07 y no pasa la corrección. Decirlo es
    la diferencia entre una indicación y una promesa."""
    plan = _plan_con_asia()
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "INDICACIÓN" in texto and "no un hecho probado" in texto
        assert "2,07" in texto
        assert "las DOS órdenes puestas" in texto


def test_con_asia_plana_el_correo_dice_que_ninguna_destaca(plan):
    """El `plan` de la fixture no tiene velas asiáticas: no hay favorita."""
    assert plan.favorita is None
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "trata las dos órdenes como iguales" in texto
        assert "MÁS RESPALDO" not in texto


def test_el_objetivo_es_una_red_de_seguridad_no_la_salida(plan):
    """Antes el objetivo a 3R era la salida y cortaba las ganadoras grandes
    (+0,050 R/op frente a +0,069 cerrando al final). Ahora solo cubre el día
    extraordinario, y el correo tiene que decirlo o alguien se quedará
    esperando a que llegue."""
    riesgo = plan.rango.amplitud
    assert plan.compra.objetivo == pytest.approx(plan.compra.entrada + 6 * riesgo)
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "red de seguridad" in texto
        assert "no estás mirando" in texto


def test_el_objetivo_es_alcanzable_en_una_sola_sesion():
    """La operación se abre y se cierra el mismo día, así que un objetivo que el
    precio no puede recorrer en una sesión no es un objetivo: es adorno.

    Medido: 6R se alcanza el 0,8 % de las veces (1,6 al año), 10R el 0,1 %
    (una vez cada tres años). El tope de 8R deja fuera lo segundo.
    """
    from oro.config import ConfiguracionRuptura
    assert ConfiguracionRuptura().r_objetivo <= 8.0


def test_el_correo_manda_cerrar_a_mano_y_dice_a_que_hora(plan):
    from oro.notificaciones.plan import hora_cierre
    hora = hora_cierre(plan)
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "CIÉRRALA A MERCADO" in texto or "Ciérrala a mano" in texto
        assert hora in texto


def test_no_hay_dos_horas_de_cierre_distintas_en_el_mismo_correo(plan):
    """Fallo real detectado al cambiar la salida: la cabecera decía 22:00 y el
    paso a paso decía 21:50. Dos horas para lo mismo en el mismo correo es peor
    que no dar ninguna."""
    import re
    from oro.notificaciones.plan import hora_cierre
    from oro.tiempo import hora_local

    cierre, caduca = hora_cierre(plan), hora_local(plan.valido_hasta)
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        horas = set(re.findall(r"\b([012]\d:[0-5]\d)\b", texto))
        assert horas <= {cierre, caduca}, (
            f"aparecen horas que no son ni el cierre ({cierre}) ni la caducidad "
            f"({caduca}): {sorted(horas - {cierre, caduca})}")


def test_el_paso_opcional_de_break_even_da_su_cifra(plan):
    """Pedir una acción extra sin decir cuánto vale es pedir fe."""
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "OPCIONAL" in texto
        assert "+0,077" in texto and "+0,069" in texto
