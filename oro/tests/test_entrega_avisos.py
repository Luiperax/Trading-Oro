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
def test_el_html_del_correo_escapa_el_texto():
    """El resumen de sentimiento incluye el nombre del evento macro, que viene
    de un calendario de terceros. Si algún día se añade a la tarjeta, un "<" no
    debe poder romper el correo ni inyectar marcado."""
    from oro.notificaciones.base import mensaje_html_evento

    html = mensaje_html_evento("<script>alert(1)</script>", 'a & b "c"', Evento.CIERRE)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


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
