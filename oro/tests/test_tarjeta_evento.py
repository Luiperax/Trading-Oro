"""La tarjeta de los avisos de gestión: qué debe verse y qué no debe romperse.

Los clientes de correo son hostiles —Gmail recorta, Outlook ignora flexbox,
todos bloquean CSS externo e imágenes— así que la tarjeta solo puede usar
tablas y estilos en línea. Y el respaldo en texto plano tiene que seguir
sirviendo por sí solo.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from oro.config import cargar_configuracion
from oro.dominio import Direccion, Signal, TakeProfit
from oro.notificaciones.base import Evento, mensaje_html_evento
from oro.vivo import RunnerVivo
from oro.vivo.gestor import GestorOperaciones


def _senal():
    return Signal(
        momento=datetime(2026, 9, 4, tzinfo=timezone.utc), direccion=Direccion.COMPRA,
        entrada=4531.90, stop_loss=4508.30,
        take_profits=[TakeProfit(4555.5, 0.5, 1.0), TakeProfit(4579.1, 0.5, 2.0)],
        probabilidad=0.67, confianza=0.86, riesgo_recompensa=1.8, tamano_posicion=0.111)


class _Captura:
    entrega = True

    def __init__(self):
        self.titulo = self.texto = self.html = None

    def enviar(self, titulo, cuerpo, evento=None, html=None):
        self.titulo, self.texto, self.html = titulo, cuerpo, html
        return True

    def notificar_senal(self, signal):
        return True


def _aviso(precio_salida=4508.30, motivo="STOP alcanzado"):
    n = _Captura()
    r = RunnerVivo(cargar_configuracion(), proveedor=None, notificador=n, modelo=None)
    g = GestorOperaciones(_senal(), cerrar_intradia=False)
    ev = g.cerrar_ahora(precio_salida, datetime(2026, 9, 4, 13, 39, tzinfo=timezone.utc),
                        motivo)[0]
    r._notificar_evento(ev, g)
    return n


# ---------- lo que el usuario tiene que ver ----------
def test_la_tarjeta_muestra_accion_resultado_y_precios():
    html = _aviso().html
    assert "Cierra la operación completa AHORA." in html, "falta la ACCIÓN"
    assert "-1.00" in html, "falta el RESULTADO en R"
    assert "4531.90" in html and "4508.30" in html, "faltan entrada y salida"
    assert "COMPRA" in html and "15:39" in html, "falta el contexto"


def test_el_resultado_va_en_rojo_si_pierde_y_en_verde_si_gana():
    from oro.notificaciones.base import _ROJO, _VERDE

    assert _ROJO in _aviso(4508.30).html
    assert _VERDE in _aviso(4560.0, "Cierre en ganancias").html


def test_un_objetivo_parcial_dice_cuanto_queda_abierto():
    """En un TP no sales del todo: hay que decirlo o el usuario cierra de más."""
    n = _Captura()
    r = RunnerVivo(cargar_configuracion(), proveedor=None, notificador=n, modelo=None)
    g = GestorOperaciones(_senal(), cerrar_intradia=False)
    for ev in g.actualizar(4556.0, datetime(2026, 9, 4, 11, 15, tzinfo=timezone.utc)):
        if ev.tipo is Evento.TP_ALCANZADO:
            r._notificar_evento(ev, g)
            break
    assert "Queda abierto" in n.html and "50%" in n.html
    assert "Asegurado hasta ahora" in n.html


# ---------- lo que no puede romperse ----------
def test_no_muestra_etiquetas_html_como_texto():
    """El fallo que llegó al usuario: "<b>Cierra la operación...</b>" literal."""
    escapadas = re.findall(r"&lt;/?(?:b|br|span|table|td)[^&]*&gt;", _aviso().html)
    assert not escapadas, f"etiquetas visibles como texto: {escapadas[:3]}"


@pytest.mark.parametrize("prohibido,motivo", [
    ("display:flex", "Outlook no soporta flexbox"),
    ("display:grid", "Outlook no soporta grid"),
    ("<style", "muchos clientes eliminan los bloques de estilo"),
    ("<link", "el CSS externo se bloquea"),
    ("<script", "todos los clientes lo eliminan"),
    ("<img", "las imágenes externas se bloquean por defecto"),
])
def test_la_tarjeta_sobrevive_a_un_cliente_tosco(prohibido, motivo):
    assert prohibido not in _aviso().html, motivo


def test_maquetada_con_tablas_y_estilos_en_linea():
    html = _aviso().html
    assert html.count("<table") >= 3
    assert html.count('style="') >= 10
    assert html.count("<table") == html.count("</table")
    assert html.count("<tr") == html.count("</tr")
    assert len(html) < 102 * 1024, "Gmail recorta los correos que pasan de 102 KB"


def test_el_respaldo_en_texto_plano_se_basta_solo():
    """Quien lee sin HTML tiene que poder operar igual."""
    texto = _aviso().texto
    for imprescindible in ("STOP alcanzado", "Qué hacer", "Hora", "Entrada", "COMPRA"):
        assert imprescindible in texto


def test_sin_datos_estructurados_sigue_funcionando():
    """Otras rutas llaman sin `datos`: no deben romperse."""
    html = mensaje_html_evento("Título", "<b>cuerpo</b>", Evento.CIERRE)
    assert "<b>cuerpo</b>" in html


# ---------- fallos vistos en la maqueta renderizada ----------
def test_el_motivo_no_se_corta_en_el_decimal_del_precio():
    """Se veía "STOP alcanzado a 4508" en vez de "...a 4508.30".

    El motivo se recortaba con split(".") y los precios llevan decimales.
    """
    html = _aviso().html
    assert "4508.30" in html
    assert "STOP alcanzado a 4508<" not in html and "a 4508 " not in html


def test_el_break_even_no_dice_salida_porque_no_se_sale():
    """Decía "SALIDA 4531.90" y "RESULTADO TOTAL" en un simple movimiento de
    stop. Invitaba a cerrar la posición por error."""
    n = _Captura()
    r = RunnerVivo(cargar_configuracion(), proveedor=None, notificador=n, modelo=None)
    g = GestorOperaciones(_senal(), cerrar_intradia=False)
    for ev in g.actualizar(4556.0, datetime(2026, 9, 4, 11, 15, tzinfo=timezone.utc)):
        if ev.tipo is Evento.MOVER_STOP:
            r._notificar_evento(ev, g)
            break
    assert "NUEVO STOP" in n.html.upper(), "debe hablar de stop, no de salida"
    assert ">Salida<" not in n.html, "no se sale de nada al mover el stop"
    assert "Resultado total" not in n.html, "la operación sigue abierta"
    assert "Asegurado hasta ahora" in n.html


def test_la_tarjeta_cabe_en_la_pantalla_de_un_movil():
    """Con tres chips en celdas de tabla, la tarjeta se ensanchaba y desbordaba.

    Los chips van como spans en UNA celda para que puedan partirse en varias
    líneas en lugar de estirar la tabla.
    """
    n = _Captura()
    r = RunnerVivo(cargar_configuracion(), proveedor=None, notificador=n, modelo=None)
    g = GestorOperaciones(_senal(), cerrar_intradia=False)
    for ev in g.actualizar(4556.0, datetime(2026, 9, 4, 11, 15, tzinfo=timezone.utc)):
        r._notificar_evento(ev, g)          # TP: es el que lleva TRES chips
    assert "white-space:nowrap" not in n.html, "impide que los chips se partan"
    assert n.html.count("max-width:460px") == 1
    # los chips no pueden ir cada uno en su celda de tabla
    assert 'padding:0 6px 0 0;"><span' not in n.html
