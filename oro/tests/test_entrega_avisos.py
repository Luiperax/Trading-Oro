"""La consola MUESTRA el aviso; no lo ENTREGA.

Fallo real detectado en auditoría: ``NotificadorConsola`` siempre devolvía
verdadero y estaba siempre en la lista de canales, así que
``NotificadorMultiple.enviar`` devolvía verdadero AUNQUE no hubiera ningún canal
real configurado. En GitHub Actions eso significaba que, si faltaba o caducaba
un secreto SMTP, el vigilante daba la señal por avisada, ABRÍA la operación y el
usuario no recibía nada —y luego le llegaban las salidas de una operación que
nunca abrió. Justo la operación fantasma que el runner comprueba para evitar.
"""

from __future__ import annotations

import pytest

from oro.notificaciones.base import Evento, Notificador, NotificadorMultiple
from oro.notificaciones.canales import NotificadorConsola


class _Real(Notificador):
    """Un canal que sí entrega (correo, Telegram…)."""

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.enviados = 0

    def enviar(self, titulo, cuerpo, evento=Evento.NUEVA_SENAL, html=None) -> bool:
        self.enviados += 1
        return self.ok


def test_la_consola_no_cuenta_como_entrega():
    assert NotificadorConsola.entrega is False
    assert _Real.entrega is True


def test_desatendido_sin_canales_no_da_el_aviso_por_entregado(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    n = NotificadorMultiple([NotificadorConsola()])
    assert n.enviar("t", "c", Evento.NUEVA_SENAL) is False
    assert "NINGÚN canal de aviso" in capsys.readouterr().out


def test_en_local_la_consola_si_vale(monkeypatch):
    """Delante de una terminal, el usuario SÍ está leyendo el aviso."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    n = NotificadorMultiple([NotificadorConsola()])
    assert n.enviar("t", "c", Evento.NUEVA_SENAL) is True


@pytest.mark.parametrize("en_actions", [True, False])
def test_un_canal_real_caido_no_lo_tapa_la_consola(monkeypatch, en_actions):
    """Lo importante: la consola nunca puede rescatar a un canal real caído."""
    if en_actions:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
    else:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    caido = _Real(ok=False)
    n = NotificadorMultiple([NotificadorConsola(), caido])
    assert n.enviar("t", "c", Evento.NUEVA_SENAL) is False
    assert caido.enviados == 1


def test_con_un_canal_real_que_funciona_si_se_entrega(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    n = NotificadorMultiple([NotificadorConsola(), _Real(ok=True)])
    assert n.enviar("t", "c", Evento.NUEVA_SENAL) is True


def test_un_canal_que_revienta_no_tumba_al_resto(monkeypatch):
    class Explosivo(Notificador):
        def enviar(self, *a, **k):
            raise RuntimeError("SMTP caído")

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    bueno = _Real(ok=True)
    assert NotificadorMultiple([Explosivo(), bueno]).enviar("t", "c") is True


# ---------- escapado de HTML ----------
def test_el_titulo_del_correo_se_escapa():
    """El título es TEXTO PLANO: si llevara un "<" rompería la tarjeta."""
    from oro.notificaciones.base import mensaje_html_evento

    html = mensaje_html_evento("<script>alert(1)</script>", "cuerpo", Evento.CIERRE)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_el_cuerpo_del_correo_conserva_su_formato():
    """FALLO REAL que llegó al usuario: el correo de cierre se veía así:

        <b>Cierra la operación completa AHORA.</b><br>STOP alcanzado a 4508.30

    con las etiquetas como texto literal. Al añadir el escapado de HTML se
    escapó también el CUERPO, que se compone a propósito con negritas y saltos
    (ver RunnerVivo._notificar_evento). El título sí es texto plano y se escapa;
    el cuerpo ya es HTML y no debe tocarse.
    """
    import re

    from oro.notificaciones.base import mensaje_html_evento

    cuerpo = ("<b>Cierra la operación completa AHORA.</b><br>STOP alcanzado."
              "<br><br><span style='color:#8A93A3;'>Hora: <b>15:39 CEST</b></span>")
    html = mensaje_html_evento("SAL DE LA OPERACIÓN", cuerpo, Evento.CIERRE)

    assert "<b>Cierra la operación completa AHORA.</b>" in html, "la negrita se perdió"
    escapadas = re.findall(r"&lt;/?(?:b|br|span)[^&]*&gt;", html)
    assert not escapadas, f"etiquetas visibles como texto: {escapadas[:3]}"


def test_el_correo_de_entrada_tampoco_muestra_etiquetas():
    import re
    from datetime import datetime, timezone

    from oro.dominio import Direccion, Signal, TakeProfit
    from oro.notificaciones.base import mensaje_html_de_senal

    s = Signal(momento=datetime(2026, 9, 4, tzinfo=timezone.utc),
               direccion=Direccion.COMPRA, entrada=4531.9, stop_loss=4508.3,
               take_profits=[TakeProfit(4555.5, 1.0, 1.0)], probabilidad=0.67,
               confianza=0.86, riesgo_recompensa=1.8, tamano_posicion=0.111,
               motivos_entrada=["A favor de la tendencia."],
               contexto_tecnico="Tendencia alcista; ADX 31.")
    escapadas = re.findall(r"&lt;/?(?:b|br|span)[^&]*&gt;", mensaje_html_de_senal(s))
    assert not escapadas, f"etiquetas visibles como texto: {escapadas[:3]}"


# ---------- validación del marco temporal ----------
@pytest.mark.parametrize("valor,esperado", [
    ("", "H1"),            # GitHub manda cadena vacía si la Variable no existe.
    ("h4", "H4"),          # se normaliza en vez de caer en silencio a H1.
    ("  D1 ", "D1"),
    ("basura", "H1"),      # desconocido -> avisa y mantiene el actual.
])
def test_marco_temporal_validado(monkeypatch, valor, esperado):
    from oro.config import cargar_configuracion

    monkeypatch.setenv("ORO_TIMEFRAME", valor)
    assert cargar_configuracion().timeframe == esperado
