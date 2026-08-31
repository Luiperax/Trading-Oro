"""Pruebas del cierre garantizado de fin de sesión (oro.cierre).

Cubre la queja concreta del usuario: no recibía el aviso para cerrar lo que
estuviera abierto antes del cierre del mercado. El aviso no puede depender de
que haya una ventana de vigilancia viva justo a esa hora.
"""

from __future__ import annotations

from datetime import datetime, timezone

from oro.dominio import Direccion, EstadoOperacion, Signal, TakeProfit
from oro.notificaciones.base import Evento
from oro.vivo import GestorOperaciones


def _gestor():
    sig = Signal(momento=datetime(2026, 8, 25, 10, tzinfo=timezone.utc),
                 direccion=Direccion.COMPRA, entrada=4700.0, stop_loss=4670.0,
                 take_profits=[TakeProfit(4730.0, 0.5, 1.0), TakeProfit(4760.0, 0.5, 2.0)],
                 probabilidad=0.6, confianza=0.8, riesgo_recompensa=1.7,
                 tamano_posicion=1.0)
    return GestorOperaciones(sig, entrada_real=4700.0, cerrar_intradia=True,
                             hora_cierre_et=16)


def test_cerrar_ahora_cierra_y_avisa():
    g = _gestor()
    evs = g.cerrar_ahora(4712.0, datetime(2026, 8, 25, 20, 45, tzinfo=timezone.utc),
                         "CIERRE DE SESIÓN")
    assert not g.abierta
    assert g.estado is EstadoOperacion.CERRADA_MANUAL
    assert evs and evs[0].cierra_operacion
    assert evs[0].tipo is Evento.CIERRE
    assert "CIERRE DE SESIÓN" in evs[0].mensaje
    # +12 puntos sobre 30 de riesgo = +0.40R
    assert round(g.r_acumulado, 2) == 0.40


def test_cerrar_ahora_respeta_los_parciales_ya_asegurados():
    g = _gestor()
    g.actualizar(4730.0, datetime(2026, 8, 25, 12, tzinfo=timezone.utc))  # TP1: +0.5R
    g.cerrar_ahora(4700.0, datetime(2026, 8, 25, 20, 45, tzinfo=timezone.utc))
    assert not g.abierta
    assert round(g.r_acumulado, 2) == 0.50   # el parcial cobrado se conserva


def test_cerrar_ahora_es_idempotente():
    """Llamarlo dos veces no debe duplicar resultado ni avisos."""
    g = _gestor()
    g.cerrar_ahora(4712.0, datetime(2026, 8, 25, 20, 45, tzinfo=timezone.utc))
    r1 = g.r_acumulado
    assert g.cerrar_ahora(4650.0, datetime(2026, 8, 25, 20, 50, tzinfo=timezone.utc)) == []
    assert g.r_acumulado == r1


# ---------- franja de aviso: 21:50 en la hora del usuario ----------
def _utc(mes, dia, h, mi=0):
    return datetime(2026, mes, dia, h, mi, tzinfo=timezone.utc)


def test_el_aviso_cae_a_las_2150_locales_en_verano_y_en_invierno():
    """El cron va en UTC y no sabe del cambio de hora; el programa sí.

    El oro cierra siempre a las 23:00 de Madrid, pero eso son las 21:00 UTC en
    verano y las 22:00 en invierno. El aviso debe caer a las 21:50 locales todo
    el año, dejando ~70 min para cerrar en el bróker.
    """
    from oro.cierre import _toca_cerrar

    # Verano: actúa con la cita de las 19:50 UTC, no con la de invierno.
    assert _toca_cerrar(_utc(8, 28, 19, 50))[0] is True
    assert _toca_cerrar(_utc(8, 28, 20, 50))[0] is False
    # Invierno: al revés.
    assert _toca_cerrar(_utc(1, 16, 19, 50))[0] is False
    assert _toca_cerrar(_utc(1, 16, 20, 50))[0] is True


def test_no_cierra_fuera_de_la_franja():
    """Sin nada abierto no hay nada que cerrar, sea la hora que sea."""
    from oro.cierre import _toca_cerrar

    for m in (_utc(8, 28, 10, 0), _utc(8, 28, 19, 0), _utc(8, 28, 22, 30)):
        toca, motivo = _toca_cerrar(m)
        assert toca is False and "no hay nada abierto" in motivo


def test_no_cierra_una_operacion_sana_de_la_sesion_en_curso():
    """A media mañana, lo abierto HOY se respeta: aún no es hora de cerrar."""
    from oro.cierre import _toca_cerrar

    abierta_hoy = [{"abierta_en": "2026-08-28T13:00:00+00:00"}]
    toca, motivo = _toca_cerrar(_utc(8, 28, 14, 0), abierta_hoy)
    assert toca is False and "sesión en curso" in motivo


def test_recupera_lo_que_quedo_abierto_de_una_sesion_anterior():
    """El caso REAL que dejaba operaciones sin cerrar.

    GitHub arrancó este trabajo entre 5 h 29 min y 7 h 59 min tarde en las seis
    ejecuciones programadas que hubo: siempre de madrugada, nunca en la franja de
    20 minutos que exigía la guarda anterior. Resultado: el aviso de cierre no se
    ejecutó jamás. Ahora, si llega tarde pero hay algo abierto de una sesión ya
    terminada, cierra igualmente.
    """
    from oro.cierre import _toca_cerrar

    abierta_ayer = [{"abierta_en": "2026-08-28T13:00:00+00:00"}]
    # Horas REALES en que GitHub arrancó la tarea (madrugada del día siguiente).
    for h, mi in ((2, 27), (2, 43), (2, 55), (3, 4)):
        toca, _ = _toca_cerrar(_utc(8, 29, h, mi), abierta_ayer)
        assert toca is True, f"a las {h:02d}:{mi:02d} UTC debía recuperar el cierre"


def test_una_abierta_sin_fecha_fiable_se_cierra():
    """Ante la duda, cerrar: quedarse abierto de un día para otro es lo peor."""
    from oro.cierre import _toca_cerrar

    assert _toca_cerrar(_utc(8, 29, 3, 0), [{"abierta_en": "no-es-una-fecha"}])[0] is True
    assert _toca_cerrar(_utc(8, 29, 3, 0), [{}])[0] is True


def test_la_red_de_seguridad_tambien_entra_en_la_franja():
    """Si GitHub retrasa la primera cita, la segunda debe servir igual."""
    from oro.cierre import _toca_cerrar

    assert _toca_cerrar(_utc(8, 28, 19, 58))[0] is True
    assert _toca_cerrar(_utc(1, 16, 20, 58))[0] is True


def test_el_vigilante_ya_cedio_cuando_entra_el_cierre():
    """Nunca deben coincidir: si no, cierran la operación dos veces."""
    import datetime as D

    from oro.config import cargar_configuracion
    import oro.vigilar as V

    cfg = cargar_configuracion()

    def cede(momento):
        class _F(D.datetime):
            @classmethod
            def now(cls, tz=None):
                return momento
        orig = D.datetime
        D.datetime = _F
        try:
            return V._toca_relevo(cfg)
        finally:
            D.datetime = orig

    from oro.cierre import _toca_cerrar
    for m in (_utc(8, 28, 19, 50), _utc(8, 28, 19, 58),
              _utc(1, 16, 20, 50), _utc(1, 16, 20, 58)):
        assert _toca_cerrar(m)[0] is True
        assert cede(m) is True, f"el vigilante seguía activo en {m}"


# ---------- el vigilante cierra ANTES de ceder el turno ----------
def test_el_vigilante_cierra_lo_abierto_antes_de_apartarse(tmp_path, monkeypatch):
    """El agujero que dejaba la operación huérfana.

    El vigilante se apartaba a las 21:30 locales para dejar paso al trabajo de
    cierre, pero ese trabajo llegaba de madrugada (5-8 h tarde, medido en las
    seis ejecuciones reales). Nadie cerraba. Ahora el vigilante cierra él mismo
    justo antes de ceder, y avisa.
    """
    import oro.vigilar as vig

    monkeypatch.chdir(tmp_path)
    avisos = []

    class RunnerFalso:
        def __init__(self):
            self.abiertas = [_gestor()]
            self.proveedor = type("P", (), {"precio_actual": staticmethod(lambda: 4712.0)})()
            self.historial = []
            self._perdida_r_hoy = 0.0
            self.guardado = False

        def _notificar_evento(self, ev, gestor):
            avisos.append(ev.mensaje)

        def _registrar_historial(self, d):
            self.historial.append(d)

        def _registrar_operacion(self, gestor, ahora):
            pass

        def guardar_estado(self, ruta):
            self.guardado = True

    monkeypatch.setattr(vig, "_guardar_en_repo", lambda ruta: True)
    r = RunnerFalso()
    vig._cerrar_antes_de_ceder(r, "estado.json")

    assert r.abiertas == [], "la operación debía quedar cerrada"
    assert any("CIERRE DE SESIÓN" in m for m in avisos), "debía avisarte del cierre"
    assert r.guardado is True, "el estado debía guardarse antes de terminar"
    assert r.historial and r.historial[0]["tipo"] == "cierre"


def test_ceder_el_turno_sin_nada_abierto_no_hace_nada(tmp_path, monkeypatch):
    import oro.vigilar as vig

    monkeypatch.chdir(tmp_path)
    llamadas = []
    monkeypatch.setattr(vig, "_guardar_en_repo", lambda ruta: llamadas.append(ruta))
    vig._cerrar_antes_de_ceder(type("R", (), {"abiertas": []})(), "estado.json")
    assert llamadas == []
