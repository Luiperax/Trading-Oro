"""Pruebas de los dos fallos detectados en la auditoría del 24-ago-2026.

1. RELOJ: con datos en vivo, las decisiones de tiempo (cierre intradía) deben
   usar la hora REAL. Antes usaban la marca de la última vela, que se congela
   cuando el mercado cierra -> una operación abierta el viernes seguía abierta
   todo el fin de semana (observado: 07-ago 17:00 -> 09-ago 22:00, 53 h).

2. DUPLICADOS: el vigilante revisa cada pocos minutos; sobre la MISMA vela
   cerrada volvía a emitir la MISMA señal -> operación y aviso duplicados
   (observado: 11 registros para solo 6 setups reales).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from oro.config import cargar_configuracion
from oro.datos import ProveedorSintetico
from oro.dominio import Direccion, EstadoOperacion, Signal, TakeProfit
from oro.sentimiento import AnalizadorSentimiento
from oro.vivo import GestorOperaciones, RunnerVivo


def _runner(en_vivo: bool):
    prov = ProveedorSintetico(velas=1200, semilla=7)
    prov.en_vivo = en_vivo
    return RunnerVivo(
        cargar_configuracion(), proveedor=prov,
        analizador=AnalizadorSentimiento(fuente_titulares=lambda: [],
                                         fuente_eventos=lambda: []),
        usar_sentimiento=False,
    )


def _signal(entrada=2000.0):
    return Signal(momento=datetime(2020, 1, 2, 12, tzinfo=timezone.utc),
                  direccion=Direccion.COMPRA, entrada=entrada, stop_loss=entrada - 10,
                  take_profits=[TakeProfit(entrada + 10, 0.5, 1.0),
                                TakeProfit(entrada + 20, 0.5, 2.0)],
                  probabilidad=0.6, confianza=0.7, riesgo_recompensa=1.5,
                  tamano_posicion=5.0)


# ---------- 1) reloj ----------
def test_reloj_en_vivo_usa_hora_real():
    r = _runner(en_vivo=True)
    vela = r.proveedor.historico(1).index[-1].to_pydatetime()
    ahora = r._reloj(vela)
    assert (datetime.now(timezone.utc) - ahora) < timedelta(seconds=5)


def test_reloj_sintetico_usa_la_vela():
    r = _runner(en_vivo=False)
    vela = r.proveedor.historico(1).index[-1].to_pydatetime()
    assert r._reloj(vela) == vela


def test_en_vivo_cierra_operacion_de_un_dia_anterior():
    """La operación abierta OTRO día se cierra (no aguanta el fin de semana)."""
    r = _runner(en_vivo=True)
    g = GestorOperaciones(_signal(), cerrar_intradia=True, hora_cierre_utc=21)
    # Abierta en 2020: con el reloj real (hoy) el día ha cambiado -> debe cerrar.
    r.abiertas.append(g)
    res = r.ciclo()
    assert g.estado is not EstadoOperacion.ABIERTA
    assert res.eventos_salida and "INTRADÍA" in res.eventos_salida[0]
    assert len(r.abiertas) == 0


def test_sin_reloj_real_la_vela_congelada_no_cerraria():
    """Comprobación del fallo original: con la marca de vela, no cerraba."""
    g = GestorOperaciones(_signal(), cerrar_intradia=True, hora_cierre_utc=21)
    congelado = g.abierta_en + timedelta(hours=3)   # misma marca "congelada"
    assert not g._debe_cerrar_intradia(congelado)
    # Con el reloj real (día siguiente) sí cierra.
    assert g._debe_cerrar_intradia(g.abierta_en + timedelta(days=1))


# ---------- 2) duplicados ----------
def test_no_repite_senal_en_la_misma_vela():
    r = _runner(en_vivo=False)
    vela = r.proveedor.historico(1).index[-1].to_pydatetime()
    r._ultima_vela_senal = vela           # esa vela ya avisó
    res = r.ciclo()
    assert res.nueva_senal is None
    assert "ya generó" in res.motivo_sin_entrada


def test_una_sola_posicion_simultanea_por_defecto():
    """Dos posiciones a la vez sobre el mismo activo = riesgo duplicado."""
    r = _runner(en_vivo=False)
    assert r.max_concurrentes == 1
    # Sin cierre intradía para que siga abierta al evaluar el tope.
    r.abiertas.append(GestorOperaciones(_signal(), cerrar_intradia=False))
    res = r.ciclo()
    assert res.nueva_senal is None
    assert "simultáneas" in res.motivo_sin_entrada


def test_la_guarda_sobrevive_al_reinicio(tmp_path):
    """Si no persiste, cada arranque duplicaría la última señal."""
    ruta = tmp_path / "estado.json"
    r1 = _runner(en_vivo=False)
    marca = datetime(2026, 8, 19, 4, tzinfo=timezone.utc)
    r1._ultima_vela_senal = marca
    r1.guardar_estado(ruta)

    r2 = _runner(en_vivo=False)
    r2.cargar_estado(ruta)
    assert r2._ultima_vela_senal == marca


# ---------- 3) operación fantasma ----------
class _NotificadorCaido:
    """Simula un canal de aviso que falla (SMTP caído, secreto mal puesto)."""

    def notificar_senal(self, signal):
        return False

    def enviar(self, titulo, cuerpo, evento=None, html=None):
        return False


def test_si_el_aviso_falla_no_se_abre_la_operacion(monkeypatch):
    """Sin aviso entregado el usuario no entra: abrirla crearía una fantasma.

    Una operación fantasma mandaría luego avisos de SALIDA de algo que nunca se
    abrió y falsearía el registro que alimenta el aprendizaje.
    """
    from oro.dominio import Signal as _S

    r = _runner(en_vivo=False)
    r.notificador = _NotificadorCaido()

    # Forzar que el motor encuentre siempre una señal.
    sig = _signal(entrada=2000.0)

    class _Analisis:
        hay_operacion = True
        signal = sig
        motivos_no: list = []
        mensaje = ""

    monkeypatch.setattr(r.motor, "analizar", lambda df, snap: _Analisis())

    res = r.ciclo()
    assert res.nueva_senal is None
    assert len(r.abiertas) == 0
    assert r._senales_hoy == 0
    assert "no se pudo enviar" in res.motivo_sin_entrada
    # No se marca la vela: así se reintenta el mismo aviso en el próximo ciclo.
    assert r._ultima_vela_senal is None
